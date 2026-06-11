package handlers

import (
	"errors"
	"log"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

func ListActivities(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")

		// Pagination: default page=1, limit=20
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
				 a.max_participants, COALESCE(a.signup_count,0), a.hours, a.activity_date,
				 a.deadline, a.location, a.college, a.scope_type, a.scope_value,
				 a.creator_name, a.created_at, a.gender_limit, a.signup_start,
				 COALESCE(a.contact_qq,''), COALESCE(a.contact_phone,''), COALESCE(a.qq_group,''),
				 EXISTS(SELECT 1 FROM signups WHERE activity_id=a.id AND user_id=$1) as signed_up
				 FROM activities a WHERE a.status != 'draft' ORDER BY a.created_at DESC LIMIT $2 OFFSET $3`, userID, limit, offset)
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
			var title, desc, status, rewardType, signupMode, activityDate, deadline, location, college, scopeType, scopeValue, creatorName, genderLimit, contactQQ, contactPhone, qqGroup string
			var createdAt time.Time
			var signedUp bool
			var signupStart *time.Time
			if err := rows.Scan(&id, &title, &desc, &status, &rewardType, &signupMode, &maxP, &signupCount,
				&hours, &activityDate, &deadline, &location, &college, &scopeType, &scopeValue,
				&creatorName, &createdAt, &genderLimit, &signupStart, &contactQQ, &contactPhone, &qqGroup, &signedUp); err != nil {
				log.Printf("ListActivities scan error: %v", err)
				continue
			}
			acts = append(acts, gin.H{
				"id": id, "title": title, "description": desc, "status": status,
				"reward_type": rewardType, "signup_mode": signupMode,
				"max_participants": maxP, "signup_count": signupCount, "hours": hours,
				"activity_date": activityDate, "deadline": deadline, "location": location,
				"college": college, "scope_type": scopeType, "scope_value": scopeValue,
				"creator_name": creatorName, "created_at": createdAt.Format(time.RFC3339),
				"gender_limit": genderLimit, "contact_qq": contactQQ, "contact_phone": contactPhone,
				"qq_group": qqGroup, "signed_up": signedUp,
			})
		}
		if acts == nil {
			acts = []gin.H{}
		}
		c.JSON(200, gin.H{"items": acts, "page": page, "limit": limit})
	}
}

func GetActivity(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		id, err := strconv.Atoi(c.Param("id"))
		if err != nil {
			c.JSON(400, gin.H{"detail": "无效的活动ID"})
			return
		}
		var (
			actID, maxP, signupCount              int
			title, desc, status, rewardType        string
			signupMode, activityDate, deadline     string
			location, college, scopeType, scopeVal string
			creatorName, genderLimit               string
			hours                                  float64
			createdAt                              time.Time
		)
		err = db.QueryRow(c.Request.Context(),
			`SELECT id, title, description, status, reward_type, signup_mode,
				 max_participants, COALESCE(signup_count,0), hours, activity_date,
				 deadline, location, college, scope_type, scope_value,
				 creator_name, created_at, gender_limit
				 FROM activities WHERE id=$1`, id,
		).Scan(&actID, &title, &desc, &status, &rewardType, &signupMode,
			&maxP, &signupCount, &hours, &activityDate,
			&deadline, &location, &college, &scopeType, &scopeVal,
			&creatorName, &createdAt, &genderLimit)
		if err != nil {
			if err == pgx.ErrNoRows {
				c.JSON(404, gin.H{"detail": "活动不存在"})
				return
			}
			log.Printf("GetActivity query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询活动失败"})
			return
		}
		c.JSON(200, gin.H{
			"id": actID, "title": title, "description": desc, "status": status,
			"reward_type": rewardType, "signup_mode": signupMode,
			"max_participants": maxP, "signup_count": signupCount, "hours": hours,
			"activity_date": activityDate, "deadline": deadline, "location": location,
			"college": college, "scope_type": scopeType, "scope_value": scopeVal,
			"creator_name": creatorName, "created_at": createdAt.Format(time.RFC3339),
			"gender_limit": genderLimit,
		})
	}
}

func Signup(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		actID, err := strconv.Atoi(c.Param("id"))
		if err != nil {
			c.JSON(400, gin.H{"detail": "无效的活动ID"})
			return
		}

		// Begin transaction immediately for FOR UPDATE locking
		tx, err := db.Begin(c.Request.Context())
		if err != nil {
			log.Printf("Signup begin tx error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}
		defer tx.Rollback(c.Request.Context())

		// Query with FOR UPDATE inside transaction to prevent race conditions
		var deadline time.Time
		var signupStart *time.Time
		var status, signupMode string
		var maxP, cnt int
		err = tx.QueryRow(c.Request.Context(),
			`SELECT deadline, signup_start, status, signup_mode, max_participants, COALESCE(signup_count,0)
				 FROM activities WHERE id=$1 FOR UPDATE`, actID,
		).Scan(&deadline, &signupStart, &status, &signupMode, &maxP, &cnt)
		if err != nil {
			if err == pgx.ErrNoRows {
				c.JSON(404, gin.H{"detail": "活动不存在"})
				return
			}
			log.Printf("Signup query error: %v", err)
			c.JSON(500, gin.H{"detail": "查询活动失败"})
			return
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
		// Only enforce max_participants for first_come mode (lottery allows oversubscription)
		if signupMode == "first_come" && maxP > 0 && cnt >= maxP {
			c.JSON(400, gin.H{"detail": "名额已满"})
			return
		}

		// first_come -> selected immediately; lottery/review -> pending
		initialStatus := "pending"
		if signupMode == "first_come" {
			initialStatus = "selected"
		}

		var insertedID int
		err = tx.QueryRow(c.Request.Context(),
			"INSERT INTO signups (activity_id, user_id, status, signed_at) VALUES ($1,$2,$3,$4) ON CONFLICT (activity_id, user_id) DO NOTHING RETURNING id",
			actID, userID, initialStatus, time.Now()).Scan(&insertedID)
		if err != nil {
			if err == pgx.ErrNoRows {
				c.JSON(400, gin.H{"detail": "已报名"})
				return
			}
			log.Printf("Signup insert error: %v", err)
			c.JSON(500, gin.H{"detail": "报名失败"})
			return
		}

		// Update signup count
		_, err = tx.Exec(c.Request.Context(),
			"UPDATE activities SET signup_count = (SELECT COUNT(*) FROM signups WHERE activity_id=$1) WHERE id=$1",
			actID)
		if err != nil {
			log.Printf("Signup count update error: %v", err)
			c.JSON(500, gin.H{"detail": "更新报名数失败"})
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
	return func(c *gin.Context) {
		userID := c.GetInt("user_id")
		actID, err := strconv.Atoi(c.Param("id"))
		if err != nil {
			c.JSON(400, gin.H{"detail": "无效的活动ID"})
			return
		}

		// Get activity + signup info
		var signupMode, actStatus, signupStatus string
		var deadline string
		var cancelDeadlineLock bool
		var lotteryDrawnAt *time.Time
		err = db.QueryRow(c.Request.Context(),
			`SELECT a.signup_mode, a.status, COALESCE(a.deadline,''), COALESCE(a.cancel_deadline_lock,false), a.lottery_drawn_at, s.status
			 FROM activities a JOIN signups s ON s.activity_id=a.id AND s.user_id=$2 WHERE a.id=$1`,
			actID, userID,
		).Scan(&signupMode, &actStatus, &deadline, &cancelDeadlineLock, &lotteryDrawnAt, &signupStatus)
		if err != nil {
			if err == pgx.ErrNoRows {
				c.JSON(400, gin.H{"detail": "未报名或活动不存在"})
				return
			}
			log.Printf("CancelSignup query error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
			return
		}

		isLottery := signupMode == "lottery"
		isEnded := actStatus == "ended" || actStatus == "completed"

		// === LOTTERY: post-lottery cancel logic ===
		if isLottery && isEnded && signupStatus == "selected" {
			if lotteryDrawnAt != nil {
				elapsed := time.Since(*lotteryDrawnAt).Seconds()
				if elapsed > 300 {
					c.JSON(400, gin.H{"detail": "抽签结束已超过5分钟，中签名额已锁定，无法取消。请联系发布者处理"})
					return
				}
				// Within 5 min: cancel + auto-promote waitlist
				tx, err := db.Begin(c.Request.Context())
				if err != nil {
					log.Printf("CancelSignup begin tx error: %v", err)
					c.JSON(500, gin.H{"detail": "服务器错误"})
					return
				}
				defer tx.Rollback(c.Request.Context())

				_, err = tx.Exec(c.Request.Context(),
					"UPDATE signups SET status='cancelled' WHERE activity_id=$1 AND user_id=$2",
					actID, userID)
				if err != nil {
					log.Printf("CancelSignup update error: %v", err)
					c.JSON(500, gin.H{"detail": "取消失败"})
					return
				}

				// Auto-promote first waitlist to selected (no waitlist is OK)
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
					// Notify promoted student
					var actTitle string
					if err := tx.QueryRow(c.Request.Context(), "SELECT title FROM activities WHERE id=$1", actID).Scan(&actTitle); err != nil {
						log.Printf("CancelSignup promote title error: %v", err)
					}
					if _, err := tx.Exec(c.Request.Context(),
						"INSERT INTO notifications (user_id, type, title, content) VALUES ($1,'lottery','候补中签', $2)",
						promotedUserID, "你已候补中签活动「"+actTitle+"」，请等待发布者完结发放学时"); err != nil {
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
			// No lottery_drawn_at set, fall through to standard cancel
		}

		// === Non-lottery or pre-lottery: standard cancel ===
		// Check deadline lock
		if deadline != "" {
			t, err := time.Parse("2006-01-02 15:04:05", deadline)
			if err != nil {
				log.Printf("CancelSignup deadline parse error for activity %d: %v (deadline=%q)", actID, err, deadline)
			}
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
		if _, err := tx2.Exec(c.Request.Context(),
			"UPDATE activities SET signup_count = (SELECT COUNT(*) FROM signups WHERE activity_id=$1) WHERE id=$1",
			actID); err != nil {
			log.Printf("CancelSignup count update error: %v", err)
			c.JSON(500, gin.H{"detail": "服务器错误"})
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
