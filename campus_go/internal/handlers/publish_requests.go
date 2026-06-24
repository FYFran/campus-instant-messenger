package handlers

import (
	log "campus-go/internal/logger"
	"encoding/json"
	"strconv"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

// GetAvailableReviewers — GET /api/available-reviewers
func GetAvailableReviewers(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		// Get the student's college
		var college string
		if err := db.QueryRow(c.Request.Context(), "SELECT COALESCE(college,'') FROM users WHERE id=$1", userID).Scan(&college); err != nil {
			log.Printf("GetAvailableReviewers college scan error uid=%d: %v", userID, err)
		}

		// Return teachers from same college + all school_admins
		rows, err := db.Query(c.Request.Context(),
			`SELECT id, name, role, COALESCE(college,'') as college
			 FROM users
			 WHERE (role IN ('teacher','college_admin') AND college=$1)
			    OR role='school_admin'
			 ORDER BY role='school_admin' DESC, name`, college)
		if err != nil {
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		defer rows.Close()

		var list []gin.H
		for rows.Next() {
			var id int
			var name, role, ucollege string
			if err := rows.Scan(&id, &name, &role, &ucollege); err != nil {
				log.Printf("GetAvailableReviewers scan error: %v", err)
				continue
			}
			list = append(list, gin.H{"id": id, "name": name, "role": role, "college": ucollege})
		}
		if err := rows.Err(); err != nil {
			log.Printf("GetAvailableReviewers iteration error: %v", err)
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		if list == nil {
			list = []gin.H{}
		}
		c.JSON(200, list)
	}
}

// parseReason extracts reason from content_json
func parseReason(contentJSON string) string {
	var m map[string]interface{}
	if err := json.Unmarshal([]byte(contentJSON), &m); err == nil {
		if r, ok := m["reason"].(string); ok {
			return r
		}
	}
	return contentJSON
}

// CreatePublishRequest — POST /api/publish-requests
func CreatePublishRequest(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		userRole := c.GetString("role")

		var req struct {
			Reason     string `json:"reason"`
			Days       int    `json:"days"`
			TeacherIDs []int  `json:"teacher_ids"`
		}
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(400, gin.H{"detail": "参数格式错误"})
			return
		}
		if len(req.Reason) < 5 {
			c.JSON(400, gin.H{"detail": "申请理由至少5字"})
			return
		}
		if req.Days < 1 || req.Days > 365 {
			c.JSON(400, gin.H{"detail": "申请天数需在1-365之间"})
			return
		}
		if len(req.TeacherIDs) < 1 || len(req.TeacherIDs) > 3 {
			c.JSON(400, gin.H{"detail": "需选择1-3位审批老师"})
			return
		}

		// Only students can request publish permission
		if userRole != "student" {
			c.JSON(400, gin.H{"detail": "只有学生可以申请发布权限"})
			return
		}

		// Verify all teacher IDs are valid teachers/admins
		for _, tid := range req.TeacherIDs {
			var role string
			err := db.QueryRow(c.Request.Context(),
				"SELECT role FROM users WHERE id=$1", tid).Scan(&role)
			if err != nil || (role != "teacher" && role != "college_admin" && role != "school_admin") {
				c.JSON(400, gin.H{"detail": "选择的老师无效"})
				return
			}
		}

		// Convert teacher_ids to comma-separated string (existing schema)
		targetTeachers := ""
		for i, tid := range req.TeacherIDs {
			if i > 0 {
				targetTeachers += ","
			}
			targetTeachers += strconv.Itoa(tid)
		}

		// Insert request (using existing schema: user_id, content_json, duration_days, target_teacher_ids)
		reasonJSON, _ := json.Marshal(map[string]string{"reason": req.Reason})
		var requestID int
		err := db.QueryRow(c.Request.Context(),
			`INSERT INTO publish_requests (user_id, content_json, duration_days, target_teacher_ids)
			 VALUES ($1, $2, $3, $4) RETURNING id`,
			userID, string(reasonJSON), req.Days, targetTeachers).Scan(&requestID)
		if err != nil {
			log.Printf("CreatePublishRequest insert error: %v", err)
			c.JSON(500, gin.H{"detail": "提交失败"})
			return
		}

		// Insert recipients into junction table
		for _, tid := range req.TeacherIDs {
			_, err := db.Exec(c.Request.Context(),
				`INSERT INTO publish_request_recipients (request_id, teacher_id)
				 VALUES ($1, $2)`, requestID, tid)
			if err != nil {
				log.Printf("CreatePublishRequest recipient insert error: %v", err)
			}
		}

		// Send notification to teachers
		var studentName string
		if err := db.QueryRow(c.Request.Context(),
			"SELECT COALESCE(name, student_id::text) FROM users WHERE id=$1", userID).Scan(&studentName); err != nil {
			log.Printf("CreatePublishRequest student name scan error uid=%d: %v", userID, err)
		}
		for _, tid := range req.TeacherIDs {
			db.Exec(c.Request.Context(),
				`INSERT INTO notifications (user_id, title, content, type)
				 VALUES ($1, '发布权限申请', $2, 'publish_request')`,
				tid, studentName+" 申请发布权限"+strconv.Itoa(req.Days)+"天："+req.Reason)
		}

		c.JSON(200, gin.H{"ok": true, "request_id": requestID})
	}
}

// GetMyPublishRequests — GET /api/publish-requests/my
func GetMyPublishRequests(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		rows, err := db.Query(c.Request.Context(),
			`SELECT pr.id, COALESCE(pr.content_json,'{}'), pr.duration_days, pr.status, pr.created_at, pr.resolved_at,
			 COALESCE(u.name,'') as resolved_by_name
			 FROM publish_requests pr
			 LEFT JOIN users u ON pr.resolved_by = u.id
			 WHERE pr.user_id=$1 ORDER BY pr.created_at DESC`, userID)
		if err != nil {
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		defer rows.Close()

		var list []gin.H
		for rows.Next() {
			var id, days int
			var reason, status, resolvedByName string
			var createdAt, resolvedAt any
			if err := rows.Scan(&id, &reason, &days, &status, &createdAt, &resolvedAt, &resolvedByName); err != nil {
				continue
			}
			// Extract reason from content_json
			reasonText := parseReason(reason)
			item := gin.H{
				"id": id, "reason": reasonText, "days": days, "status": status,
				"created_at": createdAt, "resolved_at": resolvedAt, "resolved_by_name": resolvedByName,
			}
			// Get recipients for this request
			rRows, err := db.Query(c.Request.Context(),
				`SELECT prr.teacher_id, COALESCE(u.name,'') as name, prr.status
				 FROM publish_request_recipients prr
				 JOIN users u ON prr.teacher_id = u.id
				 WHERE prr.request_id=$1`, id)
			if err == nil {
				var recipients []gin.H
				for rRows.Next() {
					var tid int
					var tname, tstatus string
					if err := rRows.Scan(&tid, &tname, &tstatus); err != nil {
						log.Printf("GetMyPublishRequests recipient scan error: %v", err)
						continue
					}
					recipients = append(recipients, gin.H{"teacher_id": tid, "name": tname, "status": tstatus})
				}
				if err := rRows.Err(); err != nil {
					log.Printf("GetMyPublishRequests recipient iteration error: %v", err)
				}
				rRows.Close()
				if recipients != nil {
					item["recipients"] = recipients
				}
			}
			list = append(list, item)
		}
		if err := rows.Err(); err != nil {
			log.Printf("GetMyPublishRequests iteration error: %v", err)
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		if list == nil {
			list = []gin.H{}
		}
		c.JSON(200, list)
	}
}

// WithdrawPublishRequest — POST /api/publish-requests/:id/withdraw
func WithdrawPublishRequest(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		reqID, err := strconv.Atoi(c.Param("id"))
		if err != nil {
			c.JSON(400, gin.H{"detail": "无效的请求ID"})
			return
		}

		var status string
		var studentID int
		err = db.QueryRow(c.Request.Context(),
			"SELECT status, user_id FROM publish_requests WHERE id=$1", reqID).Scan(&status, &studentID)
		if err != nil {
			c.JSON(404, gin.H{"detail": "申请不存在"})
			return
		}
		if studentID != userID {
			c.JSON(403, gin.H{"detail": "无权操作"})
			return
		}
		if status != "pending" {
			c.JSON(400, gin.H{"detail": "只能撤销待审批的申请"})
			return
		}

		_, err = db.Exec(c.Request.Context(),
			"UPDATE publish_requests SET status='withdrawn', resolved_at=now() WHERE id=$1", reqID)
		if err != nil {
			c.JSON(500, gin.H{"detail": "操作失败"})
			return
		}
		c.JSON(200, gin.H{"ok": true})
	}
}

// GetPendingReviews — GET /api/publish-requests/pending
func GetPendingReviews(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		rows, err := db.Query(c.Request.Context(),
			`SELECT pr.id, COALESCE(pr.content_json,'{}'), pr.duration_days, pr.status, pr.created_at,
			 COALESCE(u.name,'') as student_name, u.id as student_id
			 FROM publish_requests pr
			 JOIN publish_request_recipients prr ON prr.request_id=pr.id AND prr.teacher_id=$1
			 JOIN users u ON pr.user_id=u.id
			 WHERE pr.status='pending' AND prr.status='pending'
			 ORDER BY pr.created_at DESC`, userID)
		if err != nil {
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		defer rows.Close()
		var list []gin.H
		for rows.Next() {
			var id, days, studentID int
			var contentJSON, status, studentName string
			var createdAt any
			if err := rows.Scan(&id, &contentJSON, &days, &status, &createdAt, &studentName, &studentID); err != nil {
				log.Printf("GetPendingReviews scan error: %v", err)
				continue
			}
			list = append(list, gin.H{
				"id": id, "reason": parseReason(contentJSON), "days": days,
				"status": status, "created_at": createdAt,
				"student_name": studentName, "student_id": studentID,
			})
		}
		if err := rows.Err(); err != nil {
			log.Printf("GetPendingReviews iteration error: %v", err)
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		if list == nil {
			list = []gin.H{}
		}
		c.JSON(200, list)
	}
}

// ReviewPublishRequest — POST /api/publish-requests/:id/review
func ReviewPublishRequest(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		reqID, _ := strconv.Atoi(c.Param("id"))
		var req struct {
			Action string `json:"action"`
		}
		if err := c.ShouldBindJSON(&req); err != nil || (req.Action != "approve" && req.Action != "reject") {
			c.JSON(400, gin.H{"detail": "参数错误，action需为approve或reject"})
			return
		}
		var prrStatus string
		err := db.QueryRow(c.Request.Context(),
			"SELECT status FROM publish_request_recipients WHERE request_id=$1 AND teacher_id=$2",
			reqID, userID).Scan(&prrStatus)
		if err != nil {
			c.JSON(404, gin.H{"detail": "未找到该审批请求"})
			return
		}
		if prrStatus != "pending" {
			c.JSON(400, gin.H{"detail": "已处理过该申请"})
			return
		}
		if req.Action == "approve" {
			db.Exec(c.Request.Context(),
				`UPDATE publish_requests SET status='approved', resolved_by=$1, resolved_at=now() WHERE id=$2 AND status='pending'`,
				userID, reqID)
			db.Exec(c.Request.Context(),
				"UPDATE publish_request_recipients SET status='approved' WHERE request_id=$1 AND teacher_id=$2",
				reqID, userID)
			var studentID, days int
			db.QueryRow(c.Request.Context(),
				"SELECT user_id, duration_days FROM publish_requests WHERE id=$1", reqID).Scan(&studentID, &days)
			db.Exec(c.Request.Context(),
				"UPDATE users SET can_publish=1 WHERE id=$1", studentID)
			c.JSON(200, gin.H{"ok": true, "message": "已批准，学生已获得发布权限"})
		} else {
			db.Exec(c.Request.Context(),
				"UPDATE publish_request_recipients SET status='rejected' WHERE request_id=$1 AND teacher_id=$2",
				reqID, userID)
			var pendingCount int
			db.QueryRow(c.Request.Context(),
				"SELECT COUNT(*) FROM publish_request_recipients WHERE request_id=$1 AND status='pending'", reqID).Scan(&pendingCount)
			if pendingCount == 0 {
				db.Exec(c.Request.Context(),
					"UPDATE publish_requests SET status='rejected', resolved_at=now() WHERE id=$1", reqID)
			}
			c.JSON(200, gin.H{"ok": true, "message": "已拒绝"})
		}
	}
}
