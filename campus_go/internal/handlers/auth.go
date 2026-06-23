package handlers

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"log"
	"os"
	"strings"
	"sync"
	"time"

	"campus-go/internal/middleware"
	"github.com/alexedwards/argon2id"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/crypto/bcrypt"
)

// Rate limiters
var loginRateLimit = make(map[string]time.Time)
var loginRateMu sync.Mutex

var resetPhoneRateLimit = make(map[string]time.Time)
var resetPhoneRateMu sync.Mutex

var resetIPRateLimit = make(map[string]time.Time)
var resetIPRateMu sync.Mutex

type LoginReq struct {
	StudentID string `json:"student_id"`
	Password  string `json:"password"`
}

type RegisterReq struct {
	StudentID string `json:"student_id"`
	Name      string `json:"name"`
	Password  string `json:"password"`
	ClassName string `json:"class_name"`
	College   string `json:"college"`
	Gender    string `json:"gender"`
	Grade     string `json:"grade"`
	QQ        string `json:"qq"`
	Phone     string `json:"phone"`
	RegCode   string `json:"reg_code"`
}

func Version(c *gin.Context) {
	c.JSON(200, gin.H{
		"version":       "1.0.15",
		"version_code":  32,
		"apk_url":       "/static/app-release.apk",
		"release_notes": "v1.0.14: WebSocket实时推送+发布权限全流程+报名bug修复+Token持久化+弹窗防叠加+自动刷新",
	})
}

func Login(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req LoginReq
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(422, gin.H{"detail": "请求参数格式错误"})
			return
		}
		if req.StudentID == "" || req.Password == "" {
			c.JSON(400, gin.H{"detail": "学号或密码错误"})
			return
		}
		// Rate limit: 12s cooldown per IP
		loginRateMu.Lock()
		lastAttempt, exists := loginRateLimit[c.ClientIP()]
		if exists && time.Since(lastAttempt) < 12*time.Second {
			loginRateMu.Unlock()
			c.JSON(429, gin.H{"detail": "登录过于频繁，请12秒后重试"})
			return
		}
		loginRateLimit[c.ClientIP()] = time.Now()
		loginRateMu.Unlock()

		var id, tokenVersion int
		var name, role, pwHash string
		var canPublish bool
		err := db.QueryRow(c.Request.Context(),
			"SELECT id, name, role, password_hash, COALESCE(can_publish,0)::boolean, COALESCE(token_version,0) FROM users WHERE student_id=$1",
			req.StudentID,
		).Scan(&id, &name, &role, &pwHash, &canPublish, &tokenVersion)
		if err != nil {
			c.JSON(401, gin.H{"detail": "学号或密码错误"})
			return
		}
		if !verifyPassword(pwHash, req.Password) {
			c.JSON(401, gin.H{"detail": "学号或密码错误"})
			return
		}
		// 登录时bump token_version → 旧token失效(单设备控制)
		tokenVersion++
		_, _ = db.Exec(c.Request.Context(), "UPDATE users SET token_version=$1 WHERE id=$2", tokenVersion, id)
		token, err := middleware.GenerateToken(id, role, tokenVersion)
		if err != nil {
			log.Printf("GenerateToken error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}
		// Generate refresh token (64-char hex)
		rawRefresh := make([]byte, 32)
		if _, err := rand.Read(rawRefresh); err != nil {
			log.Printf("rand.Read error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}
		refreshToken := hex.EncodeToString(rawRefresh)
		refreshHash := sha256.Sum256([]byte(refreshToken))
		_, err = db.Exec(c.Request.Context(),
			"UPDATE users SET refresh_token_hash=$1, refresh_token_exp=$2 WHERE id=$3",
			hex.EncodeToString(refreshHash[:]), time.Now().Add(30*24*time.Hour), id)
		if err != nil {
			log.Printf("refresh token store error: %v", err)
			// non-fatal — login still works
		}
		c.JSON(200, gin.H{"token": token, "refresh_token": refreshToken, "user": gin.H{"id": id, "name": name, "role": role, "can_publish": canPublish}})
	}
}

// verifyPassword checks a password against an Argon2id or bcrypt hash.
func verifyPassword(hash, password string) bool {
	if strings.HasPrefix(hash, "$argon2") {
		ok, err := argon2id.ComparePasswordAndHash(password, hash)
		return err == nil && ok
	}
	return bcrypt.CompareHashAndPassword([]byte(hash), []byte(password)) == nil
}

func Register(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req RegisterReq
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(422, gin.H{"detail": "请求参数格式错误"})
			return
		}
		if req.StudentID == "" || req.Name == "" || len(req.Password) < 6 {
			c.JSON(400, gin.H{"detail": "学号、姓名必填，密码至少6位"})
			return
		}
		if len(req.Password) > 72 {
			c.JSON(400, gin.H{"detail": "密码不能超过72个字符"})
			return
		}
		if len(req.Name) > 100 || len(req.ClassName) > 200 || len(req.College) > 200 {
			c.JSON(400, gin.H{"detail": "姓名/班级/学院字段过长"})
			return
		}
		if len(req.Phone) > 30 || len(req.QQ) > 30 {
			c.JSON(400, gin.H{"detail": "手机号/QQ号字段过长"})
			return
		}
		hash, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
		if err != nil {
			log.Printf("bcrypt error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}
		// Default role is student
		role := "student"
		teacherCode := os.Getenv("REG_TEACHER_CODE")
		// No fallback — must be explicitly configured
		collegeAdminCode := os.Getenv("REG_COLLEGE_ADMIN_CODE")
		superCode := os.Getenv("REG_SUPER_CODE")
		switch {
		case teacherCode != "" && req.RegCode == teacherCode:
			role = "teacher"
		case collegeAdminCode != "" && req.RegCode == collegeAdminCode:
			role = "college_admin"
		case superCode != "" && req.RegCode == superCode:
			role = "super"
		}
		var userID int
		err = db.QueryRow(c.Request.Context(),
			`INSERT INTO users (student_id, name, password_hash, class, college, gender, grade, qq, phone, role, created_at)
				 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
				 ON CONFLICT (student_id) DO NOTHING RETURNING id`,
			req.StudentID, req.Name, string(hash), req.ClassName, req.College, req.Gender, req.Grade, req.QQ, req.Phone, role, time.Now(),
		).Scan(&userID)
		if err != nil {
			if err == pgx.ErrNoRows {
				c.JSON(400, gin.H{"detail": "该学号已注册"})
				return
			}
			log.Printf("Register insert error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}
		token, err := middleware.GenerateToken(userID, role, 0)
		if err != nil {
			log.Printf("GenerateToken error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}
		c.JSON(200, gin.H{"token": token})
	}
}

func GetMe(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		var name, studentID, role, college, className, gender, grade, phone, qq string
		var canPublish, isPoor, showPhone, showQQ, isActive bool
		var volunteerHours float64
		var publisherOrgID *int
		var createdAt time.Time
		err := db.QueryRow(c.Request.Context(),
			`SELECT name, student_id, role, COALESCE(college,''), COALESCE(class,''),
				 COALESCE(gender,''), COALESCE(grade,''), COALESCE(phone,''), COALESCE(qq,''),
				 COALESCE(can_publish,0)::boolean, COALESCE(is_poor,0)::boolean, COALESCE(volunteer_hours,0),
				 COALESCE(show_phone,0)::boolean, COALESCE(show_qq,0)::boolean, publisher_org_id,
				 created_at, COALESCE(is_active,true)::boolean
				 FROM users WHERE id=$1`, userID,
		).Scan(&name, &studentID, &role, &college, &className, &gender, &grade, &phone, &qq, &canPublish, &isPoor, &volunteerHours,
			&showPhone, &showQQ, &publisherOrgID, &createdAt, &isActive)
		if err != nil {
			log.Printf("GetMe query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询用户失败"})
			return
		}
		resp := gin.H{
			"id": userID, "name": name, "student_id": studentID,
			"role": role, "college": college, "class_name": className, "class": className,
			"gender": gender, "grade": grade, "phone": phone, "qq": qq,
			"can_publish": canPublish, "is_poor": isPoor, "volunteer_hours": volunteerHours,
			"show_phone": showPhone, "show_qq": showQQ, "publisher_org_id": publisherOrgID,
			"created_at": createdAt.Format(time.RFC3339), "is_active": isActive,
		}
		// Compute publish_expires_at for student publishers
		if canPublish && role == "student" {
			var pubCreatedAt *time.Time
			var durationDays int
			err := db.QueryRow(c.Request.Context(),
				"SELECT created_at, COALESCE(duration_days,30) FROM publish_codes WHERE used_by=$1 AND revoked=false ORDER BY created_at DESC LIMIT 1",
				userID).Scan(&pubCreatedAt, &durationDays)
			if err == nil && pubCreatedAt != nil {
				exp := pubCreatedAt.Add(time.Duration(durationDays) * 24 * time.Hour)
				resp["publish_expires_at"] = exp.Format(time.RFC3339)
			}
		}
		c.JSON(200, resp)
	}
}

func RefreshToken(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req struct {
			RefreshToken string `json:"refresh_token"`
		}
		if err := c.ShouldBindJSON(&req); err != nil || len(req.RefreshToken) < 32 {
			c.JSON(400, gin.H{"detail": "无效的refresh_token"})
			return
		}
		// SHA256 hash the incoming refresh token
		hash := sha256.Sum256([]byte(req.RefreshToken))
		hashStr := hex.EncodeToString(hash[:])

		// Begin transaction with FOR UPDATE to prevent race conditions
		tx, err := db.Begin(c.Request.Context())
		if err != nil {
			log.Printf("RefreshToken begin tx error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}
		defer func() { _ = tx.Rollback(c.Request.Context()) }()

		var userID, tokenVer int
		var role string
		err = tx.QueryRow(c.Request.Context(),
			"SELECT id, role, COALESCE(token_version,0) FROM users WHERE refresh_token_hash=$1 AND refresh_token_exp > NOW() FOR UPDATE",
			hashStr,
		).Scan(&userID, &role, &tokenVer)
		if err != nil {
			if err == pgx.ErrNoRows {
				c.JSON(401, gin.H{"detail": "refresh_token无效或已过期，请重新登录"})
				return
			}
			log.Printf("RefreshToken query error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}

		// Generate new access token
		newToken, err := middleware.GenerateToken(userID, role, tokenVer)
		if err != nil {
			log.Printf("GenerateToken error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}

		// Generate new refresh token (rotation)
		rawRefresh := make([]byte, 32)
		if _, err := rand.Read(rawRefresh); err != nil {
			log.Printf("rand.Read error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}
		newRefresh := hex.EncodeToString(rawRefresh)
		newHash := sha256.Sum256([]byte(newRefresh))

		_, err = tx.Exec(c.Request.Context(),
			"UPDATE users SET refresh_token_hash=$1, refresh_token_exp=$2 WHERE id=$3",
			hex.EncodeToString(newHash[:]), time.Now().Add(30*24*time.Hour), userID)
		if err != nil {
			log.Printf("refresh token update error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}

		if err = tx.Commit(c.Request.Context()); err != nil {
			log.Printf("RefreshToken commit error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}

		c.JSON(200, gin.H{"token": newToken, "refresh_token": newRefresh})
	}
}

func ResetPassword(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req struct {
			StudentID   string `json:"student_id"`
			Name        string `json:"name"`
			Phone       string `json:"phone"`
			NewPassword string `json:"new_password"`
		}
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(400, gin.H{"detail": "参数错误"})
			return
		}
		if req.StudentID == "" || req.Name == "" || req.Phone == "" || len(req.NewPassword) < 6 {
			c.JSON(400, gin.H{"detail": "请填写完整信息，密码至少6位"})
			return
		}
		if len(req.NewPassword) > 72 {
			c.JSON(400, gin.H{"detail": "密码不能超过72个字符"})
			return
		}
		// Rate limit: 5-minute cooldown per phone
		resetPhoneRateMu.Lock()
		lastPhoneReset, exists := resetPhoneRateLimit[req.Phone]
		if exists && time.Since(lastPhoneReset) < 5*time.Minute {
			resetPhoneRateMu.Unlock()
			c.JSON(429, gin.H{"detail": "该手机号5分钟内已发起过重置"})
			return
		}
		resetPhoneRateLimit[req.Phone] = time.Now()
		resetPhoneRateMu.Unlock()
		// Rate limit: 20-second cooldown per IP (~3/minute)
		resetIPRateMu.Lock()
		lastIPReset, exists := resetIPRateLimit[c.ClientIP()]
		if exists && time.Since(lastIPReset) < 20*time.Second {
			resetIPRateMu.Unlock()
			c.JSON(429, gin.H{"detail": "操作过于频繁，请稍后重试"})
			return
		}
		resetIPRateLimit[c.ClientIP()] = time.Now()
		resetIPRateMu.Unlock()

		hash, err := bcrypt.GenerateFromPassword([]byte(req.NewPassword), bcrypt.DefaultCost)
		if err != nil {
			log.Printf("bcrypt error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}
		tag, err := db.Exec(c.Request.Context(),
			"UPDATE users SET password_hash=$1 WHERE student_id=$2 AND name=$3 AND phone=$4",
			string(hash), req.StudentID, req.Name, req.Phone,
		)
		if err != nil || tag.RowsAffected() == 0 {
			c.JSON(400, gin.H{"detail": "信息不匹配，无法重置密码"})
			return
		}
		c.JSON(200, gin.H{"ok": true, "message": "密码已重置"})
	}
}
