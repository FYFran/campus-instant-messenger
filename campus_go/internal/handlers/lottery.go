package handlers

import (
	log "campus-go/internal/logger"
	"context"
	"fmt"
	"strconv"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/jackc/pgx/v5/pgxpool"
)

// DrawLottery — POST /api/activities/:id/lottery
// 手动抽签：从 status='pending' 的 signups 中随机选取 N 个设为 'selected'。
func DrawLottery(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		actID, err := strconv.Atoi(c.Param("id"))
		if err != nil {
			c.JSON(400, gin.H{"detail": "无效的活动ID"})
			return
		}

		role := c.GetString("role")
		if role != "college_admin" && role != "school_admin" && role != "teacher" {
			c.JSON(403, gin.H{"detail": "权限不足"})
			return
		}
		userID := c.GetInt("user_id")
		if role != "school_admin" {
			var actCollege, scopeType string
			err := db.QueryRow(c.Request.Context(),
				`SELECT COALESCE(u.college,''), COALESCE(a.scope_type,'') FROM activities a
				 JOIN users u ON a.created_by=u.id WHERE a.id=$1`, actID).Scan(&actCollege, &scopeType)
			if err != nil {
				c.JSON(500, gin.H{"detail": "查询活动失败"})
				return
			}
			// All-scope activities are manageable by any college_admin/teacher
			if scopeType != "all" {
				var userCollege string
				db.QueryRow(c.Request.Context(),
					"SELECT COALESCE(college,'') FROM users WHERE id=$1", userID).Scan(&userCollege)
				if actCollege != userCollege {
					c.JSON(403, gin.H{"detail": "权限不足"})
					return
				}
			}
		}

		countParam := c.DefaultQuery("count", "0")
		overCount, _ := strconv.Atoi(countParam)

		selected, err := executeLottery(c.Request.Context(), db, actID, overCount)
		if err != nil {
			c.JSON(500, gin.H{"detail": err.Error()})
			return
		}
		c.JSON(200, gin.H{"selected": selected})
	}
}

// executeLottery 执行抽签核心逻辑（可被手动 API 和后台任务调用）
func executeLottery(ctx context.Context, db *pgxpool.Pool, actID int, overCount int) (int, error) {
	var signupMode, actStatus string
	var maxP int
	err := db.QueryRow(ctx,
		`SELECT signup_mode, status, COALESCE(max_participants,0)
		 FROM activities WHERE id=$1 FOR UPDATE`, actID,
	).Scan(&signupMode, &actStatus, &maxP)
	if err != nil {
		log.Printf("DrawLottery query activity error: %v", err)
		return 0, err
	}
	if signupMode != "lottery" {
		if actStatus == "published" {
			if _, err := db.Exec(ctx, "UPDATE activities SET status='ended' WHERE id=$1", actID); err != nil {
				log.Printf("DrawLottery end non-lottery error act=%d: %v", actID, err)
			}
		}
		return 0, nil
	}
	if actStatus != "published" {
		return 0, nil
	}

	maxSel := maxP
	if overCount > 0 {
		maxSel = overCount
	}
	if maxSel <= 0 {
		var pendingCnt int
		err = db.QueryRow(ctx,
			"SELECT COUNT(*) FROM signups WHERE activity_id=$1 AND status='pending'", actID,
		).Scan(&pendingCnt)
		if err != nil {
			log.Printf("DrawLottery count pending error: %v", err)
			return 0, err
		}
		if pendingCnt == 0 {
			if _, err := db.Exec(ctx, "UPDATE activities SET status='ended' WHERE id=$1", actID); err != nil {
				log.Printf("DrawLottery end empty error act=%d: %v", actID, err)
			}
			return 0, nil
		}
		maxSel = pendingCnt
	}

	_, err = db.Exec(ctx, `
		WITH picked AS (
			SELECT id FROM signups
			WHERE activity_id=$1 AND status='pending'
			ORDER BY random() LIMIT $2
			FOR UPDATE
		)
		UPDATE signups SET status='selected'
		FROM picked
		WHERE signups.id = picked.id
	`, actID, maxSel)
	if err != nil {
		log.Printf("DrawLottery pick error: %v", err)
		return 0, err
	}

	_, err = db.Exec(ctx, `
		UPDATE signups SET status='waitlist'
		WHERE activity_id=$1 AND status='pending'
	`, actID)
	if err != nil {
		log.Printf("DrawLottery waitlist error: %v", err)
	}

	if _, err := db.Exec(ctx, "UPDATE activities SET status='ended', lottery_drawn_at=NOW() WHERE id=$1", actID); err != nil {
		log.Printf("DrawLottery end status error act=%d: %v", actID, err)
	}

	var actTitle string
	if err := db.QueryRow(ctx, "SELECT title FROM activities WHERE id=$1", actID).Scan(&actTitle); err != nil {
		log.Printf("DrawLottery title scan error act=%d: %v", actID, err)
		actTitle = fmt.Sprintf("活动#%d", actID)
	}

	var selectedCount int
	if err := db.QueryRow(ctx,
		"SELECT COUNT(*) FROM signups WHERE activity_id=$1 AND status='selected'", actID,
	).Scan(&selectedCount); err != nil {
		log.Printf("DrawLottery selected count error act=%d: %v", actID, err)
	}

	// 通知中签者
	rows, err := db.Query(ctx,
		"SELECT user_id FROM signups WHERE activity_id=$1 AND status='selected'", actID)
	if err == nil {
		for rows.Next() {
			var uid int
			if err := rows.Scan(&uid); err == nil {
				if _, err := db.Exec(ctx,
					"INSERT INTO notifications (user_id, type, title, content, is_read) VALUES ($1,'lottery','中签通知',$2,0)",
					uid, fmt.Sprintf("恭喜！你已中签活动「%s」", actTitle)); err != nil {
					log.Printf("DrawLottery notify winner error uid=%d: %v", uid, err)
				}
			}
		}
		rows.Close()
	}

	// 通知未中签者
	rows2, err := db.Query(ctx,
		"SELECT user_id FROM signups WHERE activity_id=$1 AND status='waitlist'", actID)
	if err == nil {
		for rows2.Next() {
			var uid int
			if err := rows2.Scan(&uid); err == nil {
				if _, err := db.Exec(ctx,
					"INSERT INTO notifications (user_id, type, title, content, is_read) VALUES ($1,'lottery','抽签结果',$2,0)",
					uid, fmt.Sprintf("很遗憾，你未中签活动「%s」，已进入候补队列", actTitle)); err != nil {
					log.Printf("DrawLottery notify loser error uid=%d: %v", uid, err)
				}
			}
		}
		rows2.Close()
	}

	return selectedCount, nil
}

// StartAutoProcessor 启动后台自动处理任务（goroutine）
// 每分钟检查过期活动：lottery→抽签，其他→自动结束
func StartAutoProcessor(db *pgxpool.Pool) {
	go func() {
		log.Println("[AutoProcessor] 后台自动处理已启动（60s间隔）")
		ticker := time.NewTicker(60 * time.Second)
		defer ticker.Stop()

		cleanupTick := 0
		for range ticker.C {
			ctx := context.Background()

			expired, err := db.Query(ctx, `
				SELECT a.id, a.signup_mode, a.max_participants
				FROM activities a
				WHERE a.status='published'
				  AND a.deadline IS NOT NULL AND a.deadline != ''
				  AND a.deadline::timestamptz < NOW()
			`)
			if err != nil {
				log.Printf("[AutoProcessor] query error: %v", err)
				continue
			}

			processed := 0
			for expired.Next() {
				var actID, maxP int
				var signupMode string
				if err := expired.Scan(&actID, &signupMode, &maxP); err != nil {
					log.Printf("[AutoProcessor] scan error: %v", err)
					continue
				}

				if signupMode == "lottery" {
					_, err := executeLottery(ctx, db, actID, maxP)
					if err != nil {
						log.Printf("[AutoProcessor] lottery error act=%d: %v", actID, err)
					}
				} else {
					// first_come/direct 等其他模式：直接结束活动
					if _, err := db.Exec(ctx, "UPDATE activities SET status='ended' WHERE id=$1", actID); err != nil {
						log.Printf("[AutoProcessor] end error act=%d: %v", actID, err)
					}
				}
				processed++
			}
			expired.Close()

			if processed > 0 {
				log.Printf("[AutoProcessor] 处理了 %d 个活动", processed)
			}

			// 每 10 个 tick 清理一次
			cleanupTick++
			if cleanupTick >= 10 {
				cleanupTick = 0
				if _, err := db.Exec(ctx, "DELETE FROM notifications WHERE is_read=1 AND created_at < NOW() - INTERVAL '7 days'"); err != nil {
					log.Printf("[AutoProcessor] cleanup notifications error: %v", err)
				}
				if _, err := db.Exec(ctx, "DELETE FROM checkin_tokens WHERE expires_at < NOW()"); err != nil {
					log.Printf("[AutoProcessor] cleanup tokens error: %v", err)
				}
			}
		}
	}()
}
