package handlers

import (
	log "campus-go/internal/logger"
	"errors"
	"fmt"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

func ListActivities(db *pgxpool.Pool) gin.HandlerFunc {
	if db == nil {
		return func(c *gin.Context) {
			c.JSON(500, gin.H{"detail": "服务器配置错误"})
		}
	}
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		role := c.GetString("role")

		page := 1
		limit := 20
		if p, err := strconv.Atoi(c.DefaultQuery("page", "1")); err == nil && p > 0 {
			page = p
		}
		if l, err := strconv.Atoi(c.DefaultQuery("limit", "20")); err == nil && l > 0 && l <= 100 {
			limit = l
		}
		offset := (page - 1) * limit

		rows, err := db.Query(c.Request.Context(),
			`SELECT a.id, a.title, a.description, a.status, a.reward_type, a.signup_mode,
				 a.max_participants, (SELECT COUNT(*) FROM signups WHERE activity_id=a.id),
				 a.hours, COALESCE(a.activity_date,''), COALESCE(a.deadline,''), a.location,
				 a.scope_type, a.scope_value, COALESCE(u.name,'') as creator_name,
				 a.created_at, a.gender_limit, COALESCE(a.signup_start,''),
				 COALESCE(a.contact_qq,''), COALESCE(a.contact_phone,''), COALESCE(a.qq_group,''),
				 COALESCE(a.creator_override,'') as creator_override,
				 EXISTS(SELECT 1 FROM signups WHERE activity_id=a.id AND user_id=$1) as signed_up
				 FROM activities a LEFT JOIN users u ON a.created_by=u.id
				 WHERE a.status != 'draft'
				   AND ($4 != 'college_admin' OR a.scope_type = 'all' OR a.college = (SELECT college FROM users WHERE id=$1))
				 ORDER BY a.created_at DESC LIMIT $2 OFFSET $3`, userID, limit, offset, role)
		if err != nil {
			log.Printf("ListActivities query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询活动失败"})
			return
		}
		defer rows.Close()

		var acts []gin.H
		for rows.Next() {
			var id, signupCount, maxP int
			var hours float64
			var title, desc, status, rewardType, signupMode, activityDate, deadline string
			var location, scopeType, scopeVal, creatorName, creatorOverride string
			var genderLimit, contactQQ, contactPhone, qqGroup string
			var createdAt time.Time
			var signedUp bool
			var signupStart string
			if err := rows.Scan(&id, &title, &desc, &status, &rewardType, &signupMode,
				&maxP, &signupCount, &hours, &activityDate, &deadline,
				&location, &scopeType, &scopeVal, &creatorName,
				&createdAt, &genderLimit, &signupStart,
				&contactQQ, &contactPhone, &qqGroup, &creatorOverride, &signedUp); err != nil {
				log.Printf("ListActivities scan error: %v", err)
				continue
			}
			acts = append(acts, gin.H{
				"id": id, "title": title, "description": desc, "status": status,
				"reward_type": rewardType, "signup_mode": signupMode,
				"max_participants": maxP, "signup_count": signupCount, "hours": hours,
				"activity_date": activityDate, "deadline": deadline, "location": location,
				"scope_type": scopeType, "scope_value": scopeVal,
				"creator_name": creatorName, "creator_override": creatorOverride,
				"created_at":   createdAt.Format(time.RFC3339),
				"gender_limit": genderLimit, "contact_qq": contactQQ, "contact_phone": contactPhone,
				"qq_group": qqGroup, "signed_up": signedUp,
			})
		}
		if err := rows.Err(); err != nil {
			log.Printf("ListActivities rows iteration error: %v", err)
			c.JSON(500, gin.H{"detail": "查询活动失败"})
			return
		}
		if acts == nil {
			acts = []gin.H{}
		}
		c.JSON(200, gin.H{"items": acts, "page": page, "limit": limit})
	}
}

func GetActivity(db *pgxpool.Pool) gin.HandlerFunc {
	if db == nil {
		return func(c *gin.Context) {
			c.JSON(500, gin.H{"detail": "服务器配置错误"})
		}
	}
	return func(c *gin.Context) {
		id, err := strconv.Atoi(c.Param("id"))
		if err != nil {
			c.JSON(400, gin.H{"detail": "无效的活动ID"})
			return
		}
		userID := c.GetInt("user_id")
		role := c.GetString("role")
		var (
			actID, maxP, signupCount                                                             int
			hours                                                                                float64
			title, desc, status, rewardType, signupMode, activityDate, deadline                  string
			location, scopeType, scopeVal, creatorName, creatorOverride, genderLimit, actCollege string
			createdAt                                                                            time.Time
		)
		err = db.QueryRow(c.Request.Context(),
			`SELECT a.id, a.title, a.description, a.status, a.reward_type, a.signup_mode,
				 a.max_participants, (SELECT COUNT(*) FROM signups WHERE activity_id=a.id),
				 a.hours, COALESCE(a.activity_date,''), COALESCE(a.deadline,''), a.location,
				 a.scope_type, a.scope_value, COALESCE(u.name,'') as creator_name,
				 a.created_at, a.gender_limit, COALESCE(a.creator_override,'') as creator_override,
				 COALESCE(a.college,'')
				 FROM activities a LEFT JOIN users u ON a.created_by=u.id WHERE a.id=$1`, id,
		).Scan(&actID, &title, &desc, &status, &rewardType, &signupMode,
			&maxP, &signupCount, &hours, &activityDate, &deadline,
			&location, &scopeType, &scopeVal, &creatorName,
			&createdAt, &genderLimit, &creatorOverride, &actCollege)
		if err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				c.JSON(404, gin.H{"detail": "活动不存在"})
				return
			}
			log.Printf("GetActivity query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询活动失败"})
			return
		}
		// Scope isolation: internal/college-scoped activities restricted (破阵 finding)
		if role != "school_admin" && scopeType == "college" {
			var userCollege string
			db.QueryRow(c.Request.Context(), "SELECT COALESCE(college,'') FROM users WHERE id=$1", userID).Scan(&userCollege)
			if userCollege == "" || userCollege != actCollege {
				c.JSON(403, gin.H{"detail": "无权访问此活动"})
				return
			}
		}
		c.JSON(200, gin.H{
			"id": actID, "title": title, "description": desc, "status": status,
			"reward_type": rewardType, "signup_mode": signupMode,
			"max_participants": maxP, "signup_count": signupCount, "hours": hours,
			"activity_date": activityDate, "deadline": deadline, "location": location,
			"scope_type": scopeType, "scope_value": scopeVal,
			"creator_name": creatorName, "creator_override": creatorOverride,
			"created_at": createdAt.Format(time.RFC3339), "gender_limit": genderLimit,
		})
	}
}

func Signup(db *pgxpool.Pool) gin.HandlerFunc {
	if db == nil {
		return func(c *gin.Context) {
			c.JSON(500, gin.H{"detail": "服务器配置错误"})
		}
	}
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		actID, err := strconv.Atoi(c.Param("id"))
		if err != nil {
			c.JSON(400, gin.H{"detail": "无效的活动ID"})
			return
		}

		tx, err := db.Begin(c.Request.Context())
		if err != nil {
			log.Printf("Signup begin tx error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}
		defer func() { _ = tx.Rollback(c.Request.Context()) }()

		var deadlineStr, signupStartStr string
		var status, signupMode string
		var maxP, cnt int
		err = tx.QueryRow(c.Request.Context(),
			`SELECT COALESCE(deadline,''), COALESCE(signup_start,''), status, signup_mode, max_participants,
				 (SELECT COUNT(*) FROM signups WHERE activity_id=$1)
				 FROM activities WHERE id=$1 FOR UPDATE`, actID,
		).Scan(&deadlineStr, &signupStartStr, &status, &signupMode, &maxP, &cnt)
		if err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				c.JSON(404, gin.H{"detail": "活动不存在"})
				return
			}
			log.Printf("Signup query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询活动失败"})
			return
		}
		// Parse deadline from text column (DB uses text for timestamps)
		deadline, err := time.Parse(time.RFC3339, deadlineStr)
		if err != nil {
			log.Printf("Signup deadline parse error: %v (value=%q)", err, deadlineStr)
			c.JSON(500, gin.H{"detail": "查询活动失败"})
			return
		}
		var signupStart *time.Time
		if signupStartStr != "" {
			if t, err := time.Parse(time.RFC3339, signupStartStr); err == nil {
				signupStart = &t
			}
		}
		if status != "published" {
			c.JSON(400, gin.H{"detail": "活动未开放报名"})
			return
		}
		if time.Now().After(deadline) {
			c.JSON(400, gin.H{"detail": "报名已截止"})
			return
		}
		if signupStart != nil && time.Now().Before(*signupStart) {
			c.JSON(400, gin.H{"detail": "报名尚未开始"})
			return
		}
		if signupMode == "first_come" && maxP > 0 && cnt >= maxP {
			c.JSON(400, gin.H{"detail": "名额已满"})
			return
		}

		// B02v2: After FOR UPDATE lock is acquired, re-check the count with a FRESH snapshot.
		// In PostgreSQL READ COMMITTED, the FOR UPDATE subquery COUNT(*) was evaluated from
		// the statement's original snapshot, which may be stale if another concurrent
		// transaction committed between the snapshot and lock acquisition. A new statement
		// here gets the latest committed count, preventing over-capacity.
		if signupMode == "first_come" && maxP > 0 {
			var freshCount int
			if err := tx.QueryRow(c.Request.Context(),
				"SELECT COUNT(*) FROM signups WHERE activity_id=$1", actID,
			).Scan(&freshCount); err != nil {
				log.Printf("Signup recount error: %v", err)
				c.JSON(500, gin.H{"detail": "服务器错误"})
				return
			}
			if freshCount >= maxP {
				c.JSON(400, gin.H{"detail": "名额已满"})
				return
			}
		}

		initialStatus := "pending"
		if signupMode == "first_come" {
			initialStatus = "selected"
		}

		var insertedID int
		err = tx.QueryRow(c.Request.Context(),
			"INSERT INTO signups (activity_id, user_id, status, signed_at) VALUES ($1,$2,$3,$4) ON CONFLICT (activity_id, user_id) DO NOTHING RETURNING id",
			actID, userID, initialStatus, time.Now()).Scan(&insertedID)
		if err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				c.JSON(400, gin.H{"detail": "已报名"})
				return
			}
			log.Printf("Signup insert error: %v", err)
			c.JSON(500, gin.H{"detail": "报名失败"})
			return
		}

		if err = tx.Commit(c.Request.Context()); err != nil {
			log.Printf("Signup commit error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}
		c.JSON(200, gin.H{"ok": true})
	}
}

func CancelSignup(db *pgxpool.Pool) gin.HandlerFunc {
	if db == nil {
		return func(c *gin.Context) {
			c.JSON(500, gin.H{"detail": "服务器配置错误"})
		}
	}
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		actID, err := strconv.Atoi(c.Param("id"))
		if err != nil {
			c.JSON(400, gin.H{"detail": "无效的活动ID"})
			return
		}

		var signupMode, actStatus, signupStatus string
		var deadline string
		var cancelDeadlineLock bool
		var lotteryDrawnAt *time.Time
		err = db.QueryRow(c.Request.Context(),
			`SELECT a.signup_mode, a.status, COALESCE(a.deadline,''), COALESCE(a.cancel_policy='lock',false), a.lottery_drawn_at, s.status
				 FROM activities a JOIN signups s ON s.activity_id=a.id AND s.user_id=$2 WHERE a.id=$1`,
			actID, userID,
		).Scan(&signupMode, &actStatus, &deadline, &cancelDeadlineLock, &lotteryDrawnAt, &signupStatus)
		if err != nil {
			if errors.Is(err, pgx.ErrNoRows) {
				c.JSON(400, gin.H{"detail": "未报名或活动不存在"})
				return
			}
			log.Printf("CancelSignup query error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}

		isLottery := signupMode == "lottery"
		isEnded := actStatus == "ended" || actStatus == "completed"

		if isLottery && isEnded && signupStatus == "selected" {
			if lotteryDrawnAt != nil {
				elapsed := time.Since(*lotteryDrawnAt).Seconds()
				if elapsed > 300 {
					c.JSON(400, gin.H{"detail": "抽签结束已超过5分钟，中签名额已锁定，无法取消。请联系发布者处理"})
					return
				}
				tx, err := db.Begin(c.Request.Context())
				if err != nil {
					log.Printf("CancelSignup begin tx error: %v", err)
					c.JSON(500, gin.H{"detail": "服务器错误"})
					return
				}
				defer func() { _ = tx.Rollback(c.Request.Context()) }()

				_, err = tx.Exec(c.Request.Context(),
					"UPDATE signups SET status='cancelled' WHERE activity_id=$1 AND user_id=$2",
					actID, userID)
				if err != nil {
					log.Printf("CancelSignup update error: %v", err)
					c.JSON(500, gin.H{"detail": "取消失败"})
					return
				}

				var promotedUserID, promotedID int
				if err := tx.QueryRow(c.Request.Context(),
					"SELECT id, user_id FROM signups WHERE activity_id=$1 AND status='waitlist' ORDER BY signed_at ASC LIMIT 1",
					actID,
				).Scan(&promotedID, &promotedUserID); err != nil && !errors.Is(err, pgx.ErrNoRows) {
					log.Printf("CancelSignup waitlist query error: %v", err)
				}
				if promotedUserID > 0 {
					_, err = tx.Exec(c.Request.Context(),
						"UPDATE signups SET status='selected' WHERE id=$1", promotedID)
					if err != nil {
						log.Printf("CancelSignup promote error: %v", err)
						c.JSON(500, gin.H{"detail": "递补失败"})
						return
					}
					var actTitle string
					if err := tx.QueryRow(c.Request.Context(), "SELECT title FROM activities WHERE id=$1", actID).Scan(&actTitle); err != nil {
						log.Printf("CancelSignup promote title error: %v", err)
					}
					if _, err := tx.Exec(c.Request.Context(),
						"INSERT INTO notifications (user_id, type, title, content, is_read) VALUES ($1,'lottery','候补中签', $2, 0)",
						promotedUserID, fmt.Sprintf("你已候补中签活动「%s」，请等待发布者完结发放学时", actTitle)); err != nil {
						log.Printf("CancelSignup promote notify error: %v", err)
					}
				}

				if err = tx.Commit(c.Request.Context()); err != nil {
					log.Printf("CancelSignup commit error: %v", err)
					c.JSON(500, gin.H{"detail": "服务器错误"})
					return
				}

				if promotedUserID > 0 {
					c.JSON(200, gin.H{"ok": true, "message": "已取消报名，候补已自动递补", "promoted": true})
				} else {
					c.JSON(200, gin.H{"ok": true, "message": "已取消报名", "promoted": false})
				}
				return
			}
		}

		// Standard cancel
		if deadline != "" {
			t, err := time.Parse(time.RFC3339, deadline)
			if err == nil && time.Now().After(t) {
				if cancelDeadlineLock {
					c.JSON(400, gin.H{"detail": "报名已截止且开启截止锁定，取消需发布者审批"})
					return
				} else if !isLottery {
					c.JSON(400, gin.H{"detail": "报名已截止，无法取消"})
					return
				}
			}
		}

		tx2, err := db.Begin(c.Request.Context())
		if err != nil {
			log.Printf("CancelSignup begin error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}
		defer tx2.Rollback(c.Request.Context())

		tag, err := tx2.Exec(c.Request.Context(),
			"DELETE FROM signups WHERE activity_id=$1 AND user_id=$2", actID, userID)
		if err != nil {
			log.Printf("CancelSignup delete error: %v", err)
			c.JSON(500, gin.H{"detail": "取消失败"})
			return
		}
		if tag.RowsAffected() == 0 {
			c.JSON(400, gin.H{"detail": "未报名"})
			return
		}
		if err = tx2.Commit(c.Request.Context()); err != nil {
			log.Printf("CancelSignup commit error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}
		c.JSON(200, gin.H{"ok": true})
	}
}
