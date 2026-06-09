package handlers

import (
	"log"
	"os"
	"sync"
	"time"

	"campus-go/internal/middleware"
	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"golang.org/x/crypto/bcrypt"
)

// Rate limiters
var loginRateLimit   = make(map[string]time.Time)
var loginRateMu      sync.Mutex

var resetPhoneRateLimit = make(map[string]time.Time)
var resetPhoneRateMu    sync.Mutex

var resetIPRateLimit    = make(map[string]time.Time)
var resetIPRateMu       sync.Mutex

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
		"version":       "1.0.4",
		"version_code":  21,
		"apk_url":       "/static/app-release.apk",
		"release_notes": "Go后端·极速版",
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
		// Rate limit: 12s per IP
		loginRateMu.Lock()
		lastAttempt, exists := loginRateLimit[c.ClientIP()]
		if exists && time.Since(lastAttempt) < 12*time.Second {
			loginRateMu.Unlock()
			c.JSON(429, gin.H{"detail": "登录过于频繁，请12秒后重试"})
			return
		}
		loginRateLimit[c.ClientIP()] = time.Now()
		loginRateMu.Unlock()

		var id int
		var name, role, pwHash string
		var canPublish bool
		err := db.QueryRow(c.Request.Context(),
			"SELECT id, name, role, password_hash, COALESCE(can_publish,false) FROM users WHERE student_id=$1",
			req.StudentID,
		).Scan(&id, &name, &role, &pwHash, &canPublish)
		if err != nil {
			c.JSON(401, gin.H{"detail": "学号或密码错误"})
			return
		}
		if bcrypt.CompareHashAndPassword([]byte(pwHash), []byte(req.Password)) != nil {
			c.JSON(401, gin.H{"detail": "学号或密码错误"})
			return
		}
		token, err := middleware.GenerateToken(id, role)
		if err != nil {
			log.Printf("GenerateToken error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}
		c.JSON(200, gin.H{"token": token, "user": gin.H{"id": id, "name": name, "role": role, "can_publish": canPublish}})
	}
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
		case req.RegCode == teacherCode:
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
		token, err := middleware.GenerateToken(userID, role)
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
		var canPublish, isPoor bool
		var volunteerHours float64
		err := db.QueryRow(c.Request.Context(),
			`SELECT name, student_id, role, COALESCE(college,''), COALESCE(class,''),
				 COALESCE(gender,''), COALESCE(grade,''), COALESCE(phone,''), COALESCE(qq,''),
				 COALESCE(can_publish,false), COALESCE(is_poor,false), COALESCE(volunteer_hours,0)
				 FROM users WHERE id=$1`, userID,
		).Scan(&name, &studentID, &role, &college, &className, &gender, &grade, &phone, &qq, &canPublish, &isPoor, &volunteerHours)
		if err != nil {
			log.Printf("GetMe query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询用户失败"})
			return
		}
		c.JSON(200, gin.H{
			"id": userID, "name": name, "student_id": studentID,
			"role": role, "college": college, "class_name": className, "class": className,
			"gender": gender, "grade": grade, "phone": phone, "qq": qq,
			"can_publish": canPublish, "is_poor": isPoor, "volunteer_hours": volunteerHours,
		})
	}
}

func RefreshToken(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		c.JSON(501, gin.H{"detail": "请使用Python后端进行Token刷新，Go后端不支持安全刷新"})
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
