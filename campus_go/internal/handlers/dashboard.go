package handlers

import (
	"fmt"
	"log"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

func CollegeDashboard(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		role := c.GetString("role")
		if role != "college_admin" && role != "school_admin" && role != "teacher" {
			c.JSON(403, gin.H{"detail": "需要学院管理员或教师权限"})
			return
		}
		userID := c.GetInt("user_id")
		var college string
		err := db.QueryRow(c.Request.Context(), "SELECT COALESCE(college,'') FROM users WHERE id=$1", userID).Scan(&college)
		if err != nil {
			log.Printf("CollegeDashboard user query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询用户失败"})
			return
		}

		var students, teachers, activities int
		var totalHours float64
		if err := db.QueryRow(c.Request.Context(), "SELECT COUNT(*) FROM users WHERE college=$1 AND role='student'", college).Scan(&students); err != nil {
			log.Printf("CollegeDashboard student count error: %v", err)
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		if err := db.QueryRow(c.Request.Context(), "SELECT COUNT(*) FROM users WHERE college=$1 AND role='teacher'", college).Scan(&teachers); err != nil {
			log.Printf("CollegeDashboard teacher count error: %v", err)
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		if err := db.QueryRow(c.Request.Context(), "SELECT COUNT(*) FROM activities WHERE college=$1", college).Scan(&activities); err != nil {
			log.Printf("CollegeDashboard activities count error: %v", err)
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		if err := db.QueryRow(c.Request.Context(), "SELECT COALESCE(SUM(hours),0) FROM certificates WHERE user_id IN (SELECT id FROM users WHERE college=$1)", college).Scan(&totalHours); err != nil {
			log.Printf("CollegeDashboard total hours error: %v", err)
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}

		c.JSON(200, gin.H{
			"college": college, "students": students, "teachers": teachers,
			"activities": activities, "total_hours": totalHours,
		})
	}
}

func SchoolDashboard(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		role := c.GetString("role")
		if role != "school_admin" {
			c.JSON(403, gin.H{"detail": "需要学校管理员权限"})
			return
		}
		var totalStudents, totalActs int
		var totalHours float64
		if err := db.QueryRow(c.Request.Context(), "SELECT COUNT(*) FROM users WHERE role='student'").Scan(&totalStudents); err != nil {
			log.Printf("SchoolDashboard student count error: %v", err)
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		if err := db.QueryRow(c.Request.Context(), "SELECT COUNT(*) FROM activities").Scan(&totalActs); err != nil {
			log.Printf("SchoolDashboard activity count error: %v", err)
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		if err := db.QueryRow(c.Request.Context(), "SELECT COALESCE(SUM(hours),0) FROM certificates").Scan(&totalHours); err != nil {
			log.Printf("SchoolDashboard total hours error: %v", err)
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}

		rows, err := db.Query(c.Request.Context(),
			"SELECT college, COUNT(*) FROM users WHERE role='student' AND college != '' GROUP BY college ORDER BY COUNT(*) DESC")
		if err != nil {
			log.Printf("SchoolDashboard query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询失败"})
			return
		}
		defer rows.Close()
		var colleges []gin.H
		for rows.Next() {
			var c string
			var cnt int
			if err := rows.Scan(&c, &cnt); err != nil {
				log.Printf("SchoolDashboard scan error: %v", err)
				continue
			}
			colleges = append(colleges, gin.H{"college": c, "cnt": cnt})
		}
		if colleges == nil {
			colleges = []gin.H{}
		}
		c.JSON(200, gin.H{"total_students": totalStudents, "total_acts": totalActs, "total_hours": totalHours, "colleges": colleges})
	}
}

func CollegeStudents(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		role := c.GetString("role")
		if role != "teacher" && role != "college_admin" && role != "school_admin" {
			c.JSON(403, gin.H{"detail": "权限不足"})
			return
		}
		var college string
		err := db.QueryRow(c.Request.Context(), "SELECT COALESCE(college,'') FROM users WHERE id=$1", userID).Scan(&college)
		if err != nil {
			log.Printf("CollegeStudents user query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询用户失败"})
			return
		}

		rows, err := db.Query(c.Request.Context(),
			"SELECT id, name, student_id, COALESCE(class,''), COALESCE(volunteer_hours,0), COALESCE(is_poor,0)::boolean, COALESCE(college,''), role FROM users WHERE college=$1 AND role='student'", college)
		if err != nil {
			log.Printf("CollegeStudents query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询学生失败"})
			return
		}
		defer rows.Close()
		var students []gin.H
		for rows.Next() {
			var id int
			var name, sid, cls, college, role string
			var volunteerHours float64
			var isPoor bool
			if err := rows.Scan(&id, &name, &sid, &cls, &volunteerHours, &isPoor, &college, &role); err != nil {
				log.Printf("CollegeStudents scan error: %v", err)
				continue
			}
			students = append(students, gin.H{"id": id, "name": name, "student_id": sid, "class_name": cls, "volunteer_hours": volunteerHours, "is_poor": isPoor, "college": college, "role": role})
		}
		if students == nil {
			students = []gin.H{}
		}
		c.JSON(200, students)
	}
}

func GetNotifications(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		rows, err := db.Query(c.Request.Context(),
			"SELECT id, title, content, type, is_read, created_at FROM notifications WHERE user_id=$1 ORDER BY created_at DESC LIMIT 50", userID)
		if err != nil {
			log.Printf("GetNotifications query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询通知失败"})
			return
		}
		defer rows.Close()
		var notifs []gin.H
		for rows.Next() {
			var id int
			var title, content, ntype string
			var isRead bool
			var createdAt time.Time
			if err := rows.Scan(&id, &title, &content, &ntype, &isRead, &createdAt); err != nil {
				log.Printf("GetNotifications scan error: %v", err)
				continue
			}
			notifs = append(notifs, gin.H{"id": id, "title": title, "content": content, "type": ntype, "is_read": isRead, "created_at": createdAt.Format(time.RFC3339)})
		}
		if notifs == nil {
			notifs = []gin.H{}
		}
		c.JSON(200, notifs)
	}
}

func GetMySignups(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		rows, err := db.Query(c.Request.Context(),
			`SELECT s.activity_id, a.title as activity_title, s.status, a.status as act_status,
				 a.reward_type, a.hours, a.college
				 FROM signups s JOIN activities a ON s.activity_id=a.id
				 WHERE s.user_id=$1 ORDER BY s.signed_at DESC`, userID)
		if err != nil {
			log.Printf("GetMySignups query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询报名记录失败"})
			return
		}
		defer rows.Close()
		var signups []gin.H
		for rows.Next() {
			var actID int
			var actTitle, status, actStatus, rewardType, college string
			var hours float64
			if err := rows.Scan(&actID, &actTitle, &status, &actStatus, &rewardType, &hours, &college); err != nil {
				log.Printf("GetMySignups scan error: %v", err)
				continue
			}
			signups = append(signups, gin.H{
				"activity_id": actID, "activity_title": actTitle,
				"status": status, "act_status": actStatus,
				"reward_type": rewardType, "hours": hours, "college": college,
			})
		}
		if signups == nil {
			signups = []gin.H{}
		}
		c.JSON(200, signups)
	}
}

func GetMyStats(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")

		// Query total volunteer hours from certificates
		var totalHours float64
		if err := db.QueryRow(c.Request.Context(),
			"SELECT COALESCE(SUM(hours),0) FROM certificates WHERE user_id=$1", userID).Scan(&totalHours); err != nil {
			log.Printf("GetMyStats totalHours error: %v", err)
		}

		// Query total signups count
		var totalSignups int
		if err := db.QueryRow(c.Request.Context(),
			"SELECT COUNT(*) FROM signups WHERE user_id=$1", userID).Scan(&totalSignups); err != nil {
			log.Printf("GetMyStats totalSignups error: %v", err)
		}

		// Query total selected (selected or checked_in)
		var totalSelected int
		if err := db.QueryRow(c.Request.Context(),
			"SELECT COUNT(*) FROM signups WHERE user_id=$1 AND status IN ('selected','checked_in')", userID).Scan(&totalSelected); err != nil {
			log.Printf("GetMyStats totalSelected error: %v", err)
		}

		// Compute select_rate
		selectRate := "0%"
		if totalSignups > 0 {
			rate := float64(totalSelected) / float64(totalSignups) * 100
			selectRate = fmt.Sprintf("%.1f%%", rate)
		}

		// Compute community hours (only for is_poor students)
		var communityHours float64
		var isPoor bool
		if err := db.QueryRow(c.Request.Context(),
			"SELECT COALESCE(is_poor,0)::boolean FROM users WHERE id=$1", userID).Scan(&isPoor); err != nil {
			log.Printf("GetMyStats isPoor error: %v", err)
		}
		if isPoor {
			if err := db.QueryRow(c.Request.Context(),
				"SELECT COALESCE(SUM(hours),0) FROM certificates WHERE user_id=$1", userID).Scan(&communityHours); err != nil {
				log.Printf("GetMyStats communityHours error: %v", err)
			}
		}

		c.JSON(200, gin.H{
			// Python-style fields (new, primary)
			"total_hours":          totalHours,
			"total_signups":        totalSignups,
			"total_selected":       totalSelected,
			"select_rate":          selectRate,
			"volunteer":            totalHours,
			"volunteer_convertible": 0,
			"community":            communityHours,
			// Go-style fields (backward compatibility)
			"activity_count":       float64(totalSignups),
			"trend":                0,
		})
	}
}

func GetColleges(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		rows, err := db.Query(c.Request.Context(), "SELECT id, name FROM colleges ORDER BY id")
		if err != nil {
			log.Printf("GetColleges query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询学院失败"})
			return
		}
		defer rows.Close()
		var cols []gin.H
		for rows.Next() {
			var id int
			var name string
			if err := rows.Scan(&id, &name); err != nil {
				log.Printf("GetColleges scan error: %v", err)
				continue
			}
			cols = append(cols, gin.H{"id": id, "name": name})
		}
		if cols == nil {
			cols = []gin.H{}
		}
		c.JSON(http.StatusOK, cols)
	}
}
