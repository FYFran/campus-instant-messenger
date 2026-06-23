package handlers

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

// CreateActivity — POST /api/activities
func CreateActivity(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		role := c.GetString("role")

		var req struct {
			Title              string  `json:"title"`
			Description        string  `json:"description"`
			RewardType         string  `json:"reward_type"`
			SignupMode         string  `json:"signup_mode"`
			MaxParticipants    int     `json:"max_participants"`
			Hours              float64 `json:"hours"`
			StaffHours         float64 `json:"staff_hours"`
			ParticipantHours   float64 `json:"participant_hours"`
			ActivityDate       string  `json:"activity_date"`
			Deadline           string  `json:"deadline"`
			SignupStart        string  `json:"signup_start"`
			Location           string  `json:"location"`
			ScopeType          string  `json:"scope_type"`
			ScopeValue         string  `json:"scope_value"`
			GenderLimit        string  `json:"gender_limit"`
			ContactQQ          string  `json:"contact_qq"`
			ContactPhone       string  `json:"contact_phone"`
			QQGroup            string  `json:"qq_group"`
			CreatorOverride    string  `json:"creator_override"`
			CheckinType        string  `json:"checkin_type"`
			AssistEnabled      bool    `json:"assist_enabled"`
			CancelPolicy       string  `json:"cancel_policy"`
			CancelDeadlineLock bool    `json:"cancel_deadline_lock"`
			FormLink           string  `json:"form_link"`
			PuType             string  `json:"pu_type"`
			PuQQ               string  `json:"pu_qq"`
			ImageURL           string  `json:"image_url"`
		}
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(400, gin.H{"detail": "参数格式错误"})
			return
		}
		if req.Title == "" {
			c.JSON(400, gin.H{"detail": "活动名称不能为空"})
			return
		}
		if req.MaxParticipants < 0 || req.MaxParticipants > 10000 {
			c.JSON(400, gin.H{"detail": "报名人数需在0-10000之间"})
			return
		}

		status := "published"
		if role == "student" {
			var canPub bool
			db.QueryRow(c.Request.Context(),
				"SELECT COALESCE(can_publish,0)::boolean FROM users WHERE id=$1", userID).Scan(&canPub)
			if canPub {
				status = "published"
			} else {
				status = "pending"
			}
		}

		// Default staff_hours and participant_hours to hours value if not provided
		if req.StaffHours == 0 {
			req.StaffHours = req.Hours
		}
		if req.ParticipantHours == 0 {
			req.ParticipantHours = req.Hours
		}

		// Get the creator's college so activities.college is populated for college-scoped queries
		var creatorCollege string
		db.QueryRow(c.Request.Context(), "SELECT COALESCE(college,'') FROM users WHERE id=$1", userID).Scan(&creatorCollege)

		var activityID int
		err := db.QueryRow(c.Request.Context(),
			`INSERT INTO activities (title, description, reward_type, signup_mode,
		max_participants, hours, activity_date, deadline, signup_start,
		 location, scope_type, scope_value, status, gender_limit,
		 contact_qq, contact_phone, qq_group, created_by,
		 creator_override, checkin_type, assist_enabled, cancel_policy,
		 cancel_deadline_lock, form_link, pu_type, pu_qq,
		 staff_hours, participant_hours, college)
		 VALUES ($1,$2,$3,$4,$5,$6,$7,$8,NULLIF($9,''),$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29)
		 RETURNING id`,
			req.Title, req.Description, req.RewardType, req.SignupMode,
			req.MaxParticipants, req.Hours, req.ActivityDate, req.Deadline, req.SignupStart,
			req.Location, req.ScopeType, req.ScopeValue, status,
			req.GenderLimit, req.ContactQQ, req.ContactPhone, req.QQGroup,
			userID,
			req.CreatorOverride, req.CheckinType, req.AssistEnabled, req.CancelPolicy,
			req.CancelDeadlineLock, req.FormLink, req.PuType, req.PuQQ,
			req.StaffHours, req.ParticipantHours,
			creatorCollege,
		).Scan(&activityID)
		if err != nil {
			log.Printf("CreateActivity insert error: %v", err)
			c.JSON(500, gin.H{"detail": "创建活动失败"})
			return
		}
		if status == "published" {
			Broadcast("new_activity", gin.H{"id": activityID, "title": req.Title})
		}
		c.JSON(200, gin.H{"id": activityID, "status": status})
	}
}

// ApproveActivity — POST /api/activities/:id/approve
func ApproveActivity(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		actID, err := strconv.Atoi(c.Param("id"))
		if err != nil {
			c.JSON(400, gin.H{"detail": "无效的活动ID"})
			return
		}
		role := c.GetString("role")
		if role != "college_admin" && role != "school_admin" {
			c.JSON(403, gin.H{"detail": "权限不足"})
			return
		}
		userID := c.GetInt("user_id")
		tag, err := db.Exec(c.Request.Context(),
			`UPDATE activities SET status='published' WHERE id=$1 AND status='pending'
			 AND ($2 = 'school_admin' OR activities.scope_type = 'all' OR activities.college = (SELECT college FROM users WHERE id=$3))`,
			actID, role, userID)
		if err != nil {
			log.Printf("ApproveActivity error: %v", err)
			c.JSON(500, gin.H{"detail": "审批失败"})
			return
		}
		if tag.RowsAffected() == 0 {
			c.JSON(400, gin.H{"detail": "活动不存在或已审批"})
			return
		}
		var createdBy int
		var title string
		if err := db.QueryRow(c.Request.Context(),
			"SELECT created_by, title FROM activities WHERE id=$1", actID).Scan(&createdBy, &title); err == nil {
			_, _ = db.Exec(c.Request.Context(),
				"INSERT INTO notifications (user_id, type, title, content, is_read) VALUES ($1,'approval','活动已通过',$2,0)",
				createdBy, "你的活动「"+title+"」已通过审核")
		}
		c.JSON(200, gin.H{"ok": true})
	}
}

// RejectActivity — POST /api/activities/:id/reject
func RejectActivity(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		actID, err := strconv.Atoi(c.Param("id"))
		if err != nil {
			c.JSON(400, gin.H{"detail": "无效的活动ID"})
			return
		}
		role := c.GetString("role")
		if role != "college_admin" && role != "school_admin" {
			c.JSON(403, gin.H{"detail": "权限不足"})
			return
		}
		var req struct {
			Reason string `json:"reason"`
		}
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(400, gin.H{"detail": "参数错误"})
			return
		}
		userID := c.GetInt("user_id")
		tag, err := db.Exec(c.Request.Context(),
			`UPDATE activities SET status='rejected' WHERE id=$1 AND status='pending'
			 AND ($2 = 'school_admin' OR activities.scope_type = 'all' OR activities.college = (SELECT college FROM users WHERE id=$3))`,
			actID, role, userID)
		if err != nil {
			log.Printf("RejectActivity error: %v", err)
			c.JSON(500, gin.H{"detail": "驳回失败"})
			return
		}
		if tag.RowsAffected() == 0 {
			c.JSON(400, gin.H{"detail": "活动不存在或已处理"})
			return
		}
		var createdBy int
		var title string
		if err := db.QueryRow(c.Request.Context(),
			"SELECT created_by, title FROM activities WHERE id=$1", actID).Scan(&createdBy, &title); err == nil {
			reason := req.Reason
			if reason == "" {
				reason = "未提供原因"
			}
			_, _ = db.Exec(c.Request.Context(),
				"INSERT INTO notifications (user_id, type, title, content, is_read) VALUES ($1,'approval','活动已驳回',$2,0)",
				createdBy, "你的活动「"+title+"」已被驳回："+reason)
		}
		c.JSON(200, gin.H{"ok": true})
	}
}

// ModifyActivity — POST /api/activities/:id/modify
func ModifyActivity(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		actID, err := strconv.Atoi(c.Param("id"))
		if err != nil {
			c.JSON(400, gin.H{"detail": "无效的活动ID"})
			return
		}
		role := c.GetString("role")
		if role != "college_admin" && role != "school_admin" {
			c.JSON(403, gin.H{"detail": "权限不足"})
			return
		}
		var req struct {
			Suggestion string `json:"suggestion"`
		}
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(400, gin.H{"detail": "参数错误"})
			return
		}
		userID := c.GetInt("user_id")
		tag, err := db.Exec(c.Request.Context(),
			`UPDATE activities SET status='needs_revision' WHERE id=$1 AND status='pending'
			 AND ($2 = 'school_admin' OR activities.scope_type = 'all' OR activities.college = (SELECT college FROM users WHERE id=$3))`,
			actID, role, userID)
		if err != nil {
			log.Printf("ModifyActivity error: %v", err)
			c.JSON(500, gin.H{"detail": "操作失败"})
			return
		}
		if tag.RowsAffected() == 0 {
			c.JSON(400, gin.H{"detail": "活动不存在或已处理"})
			return
		}
		var createdBy int
		var title string
		if err := db.QueryRow(c.Request.Context(),
			"SELECT created_by, title FROM activities WHERE id=$1", actID).Scan(&createdBy, &title); err == nil {
			_, _ = db.Exec(c.Request.Context(),
				"INSERT INTO notifications (user_id, type, title, content, is_read) VALUES ($1,'approval','活动需修改',$2,0)",
				createdBy, "你的活动「"+title+"」需要修改："+req.Suggestion)
		}
		c.JSON(200, gin.H{"ok": true})
	}
}

// GetPendingApprovals — GET /api/activities/pending-approvals
func GetPendingApprovals(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		role := c.GetString("role")
		if role != "college_admin" && role != "school_admin" && role != "teacher" {
			c.JSON(403, gin.H{"detail": "权限不足"})
			return
		}
		userID := c.GetInt("user_id")
		rows, err := db.Query(c.Request.Context(),
			`SELECT a.id, a.title, a.description, a.reward_type, a.signup_mode, a.max_participants,
			 a.hours, a.activity_date, a.deadline, a.location, a.scope_type, a.scope_value,
			 COALESCE(u.name,'') as creator_name, COALESCE(a.created_at, 'epoch'::timestamptz) as created_at, a.gender_limit, a.status
			 FROM activities a LEFT JOIN users u ON a.created_by=u.id
			 WHERE a.status IN ('pending','needs_revision')
			   AND ($1 = 'school_admin' OR a.scope_type = 'all' OR a.college = (SELECT college FROM users WHERE id=$2))
			 ORDER BY a.created_at DESC`, role, userID)
		if err != nil {
			log.Printf("GetPendingApprovals query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		defer rows.Close()
		var list []gin.H
		for rows.Next() {
			var id, maxP int
			var hours float64
			var title, desc, rewardType, signupMode, activityDate, deadline, location string
			var scopeType, scopeVal, creatorName, genderLimit, status string
			var createdAt time.Time
			if err := rows.Scan(&id, &title, &desc, &rewardType, &signupMode, &maxP,
				&hours, &activityDate, &deadline, &location, &scopeType, &scopeVal,
				&creatorName, &createdAt, &genderLimit, &status); err != nil {
				log.Printf("GetPendingApprovals scan error: %v", err)
				continue
			}
			list = append(list, gin.H{
				"id": id, "title": title, "description": desc,
				"reward_type": rewardType, "signup_mode": signupMode,
				"max_participants": maxP, "hours": hours,
				"activity_date": activityDate, "deadline": deadline,
				"location":   location,
				"scope_type": scopeType, "scope_value": scopeVal,
				"creator_name": creatorName, "created_at": createdAt.Format(time.RFC3339),
				"gender_limit": genderLimit, "status": status,
			})
		}
		if err := rows.Err(); err != nil {
			log.Printf("GetPendingApprovals iteration error: %v", err)
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		if list == nil {
			list = []gin.H{}
		}
		c.JSON(200, list)
	}
}

// ListNotices — GET /api/notices
func ListNotices(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		rows, err := db.Query(c.Request.Context(),
			`SELECT id, title, content, type, created_at
			 FROM notifications WHERE type='notice'
			 ORDER BY created_at DESC LIMIT 50`)
		if err != nil {
			log.Printf("ListNotices query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询公告失败"})
			return
		}
		defer rows.Close()
		var list []gin.H
		for rows.Next() {
			var id int
			var title, content, ntype string
			var createdAt time.Time
			if err := rows.Scan(&id, &title, &content, &ntype, &createdAt); err != nil {
				log.Printf("ListNotices scan error: %v", err)
				continue
			}
			list = append(list, gin.H{
				"id": id, "title": title, "content": content,
				"type": ntype, "created_at": createdAt.Format(time.RFC3339),
			})
		}
		if err := rows.Err(); err != nil {
			log.Printf("ListNotices iteration error: %v", err)
			c.JSON(500, gin.H{"detail": "查询公告失败"})
			return
		}
		if list == nil {
			list = []gin.H{}
		}
		c.JSON(200, list)
	}
}

// CreateNotice — POST /api/notices
func CreateNotice(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		role := c.GetString("role")
		if role != "college_admin" && role != "school_admin" {
			var canPub bool
			db.QueryRow(c.Request.Context(),
				"SELECT COALESCE(can_publish,0)::boolean FROM users WHERE id=$1", userID).Scan(&canPub)
			if !canPub {
				c.JSON(403, gin.H{"detail": "只有管理员可以发布公告"})
				return
			}
		}
		var req struct {
			Title   string `json:"title"`
			Content string `json:"content"`
		}
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(400, gin.H{"detail": "参数错误"})
			return
		}
		if req.Title == "" {
			c.JSON(400, gin.H{"detail": "公告标题不能为空"})
			return
		}
		var id int
		err := db.QueryRow(c.Request.Context(),
			`INSERT INTO notifications (title, content, type, user_id, is_read)
			 VALUES ($1,$2,'notice',$3,0) RETURNING id`,
			req.Title, req.Content, userID,
		).Scan(&id)
		if err != nil {
			log.Printf("CreateNotice insert error: %v", err)
			c.JSON(500, gin.H{"detail": "发布公告失败"})
			return
		}
		Broadcast("new_notice", gin.H{"id": id, "title": req.Title})
		c.JSON(200, gin.H{"id": id})
	}
}

// ListUsers — GET /api/users
func ListUsers(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		role := c.GetString("role")
		if role != "college_admin" && role != "school_admin" {
			c.JSON(403, gin.H{"detail": "权限不足"})
			return
		}
		userID := c.GetInt("user_id")
		rows, err := db.Query(c.Request.Context(),
			`SELECT id, name, student_id, COALESCE(college,''), COALESCE(class,''), role,
			 COALESCE(volunteer_hours,0), COALESCE(is_poor,false)::boolean
			 FROM users
			 WHERE $1 = 'school_admin' OR college = (SELECT college FROM users WHERE id=$2)
			 ORDER BY id`, role, userID)
		if err != nil {
			log.Printf("ListUsers query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		defer rows.Close()
		var list []gin.H
		for rows.Next() {
			var id int
			var name, sid, college, class, urole string
			var hours float64
			var isPoor bool
			if err := rows.Scan(&id, &name, &sid, &college, &class, &urole, &hours, &isPoor); err != nil {
				log.Printf("ListUsers scan error: %v", err)
				continue
			}
			list = append(list, gin.H{
				"id": id, "name": name, "student_id": sid,
				"college": college, "class_name": class, "role": urole,
				"volunteer_hours": hours, "is_poor": isPoor,
			})
		}
		if err := rows.Err(); err != nil {
			log.Printf("ListUsers iteration error: %v", err)
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		if list == nil {
			list = []gin.H{}
		}
		c.JSON(200, list)
	}
}

// GetConfigCodes — GET /api/config/codes (role-gated: admin only for code prefixes)
func GetConfigCodes(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		role := c.GetString("role")
		mask := func(key string) string {
			v := os.Getenv(key)
			if v == "" {
				return ""
			}
			if role != "college_admin" && role != "school_admin" && role != "super" {
				return "****" // Full mask for unprivileged users (R02 fix)
			}
			if len(v) <= 4 {
				return "****"
			}
			return v[:4] + "****"
		}
		c.JSON(200, gin.H{
			"teacher_code":       mask("REG_TEACHER_CODE"),
			"college_admin_code": mask("REG_COLLEGE_ADMIN_CODE"),
			"super_code":         mask("REG_SUPER_CODE"),
		})
	}
}

// UploadImage — POST /api/upload
func UploadImage() gin.HandlerFunc {
	return func(c *gin.Context) {
		file, err := c.FormFile("file")
		if err != nil {
			c.JSON(400, gin.H{"detail": "请选择图片文件"})
			return
		}
		ext := strings.ToLower(file.Filename[strings.LastIndex(file.Filename, ".")+1:])
		allowed := map[string]bool{"jpg": true, "jpeg": true, "png": true, "gif": true, "webp": true}
		if !allowed[ext] {
			c.JSON(400, gin.H{"detail": "图片格式不支持，仅支持 JPG/PNG/GIF/WEBP"})
			return
		}
		if file.Size > 10*1024*1024 {
			c.JSON(400, gin.H{"detail": "图片不能超过10MB"})
			return
		}
		b := make([]byte, 8)
		rand.Read(b)
		filename := fmt.Sprintf("%d_%s.%s", time.Now().UnixNano(), hex.EncodeToString(b), ext)
		uploadDir := "/app/static/uploads"
		_ = os.MkdirAll(uploadDir, 0755) //nolint:errcheck
		dst := filepath.Join(uploadDir, filename)
		if err := c.SaveUploadedFile(file, dst); err != nil {
			log.Printf("UploadImage save error: %v", err)
			c.JSON(500, gin.H{"detail": "上传失败"})
			return
		}
		c.JSON(200, gin.H{"url": "/static/uploads/" + filename})
	}
}

// HealthCheck — GET /api/health
func HealthCheck(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx, cancel := context.WithTimeout(c.Request.Context(), 2*time.Second)
		defer cancel()
		dbOK := true
		if err := db.Ping(ctx); err != nil {
			dbOK = false
		}
		status := "ok"
		if !dbOK {
			status = "degraded"
		}
		c.JSON(200, gin.H{
			"status":         status,
			"uptime_seconds": 0,
			"version":        "1.0.12",
			"database":       map[bool]string{true: "ok", false: "error"}[dbOK],
			"redis":          "ok",
		})
	}
}
