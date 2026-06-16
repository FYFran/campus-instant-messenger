package handler

import (
	"crypto/subtle"
	"encoding/json"
	"log/slog"
	"net/http"
	"os"
	"strconv"
	"time"
)

// AdminAuth protects admin routes with a password from env ADMIN_PASSWORD.
// Pass password via X-Admin-Key header only (query param disabled — leaks to access logs).
// Always requires authentication — no localhost bypass (nginx also connects from localhost).
func AdminAuth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Allow CORS preflight without password
		if r.Method == "OPTIONS" {
			w.WriteHeader(204)
			return
		}

		adminPass := os.Getenv("ADMIN_PASSWORD")
		if adminPass == "" {
			slog.Error("ADMIN_PASSWORD not set — rejecting admin request")
			writeJSON(w, 401, "Admin access not configured. Set ADMIN_PASSWORD in environment.")
			return
		}
		key := r.Header.Get("X-Admin-Key")
		if subtle.ConstantTimeCompare([]byte(key), []byte(adminPass)) != 1 {
			writeJSON(w, 401, "Password admin salah")
			return
		}
		next.ServeHTTP(w, r)
	})
}

// AdminDashboard returns aggregated real-time data for the admin panel.
func AdminDashboard(w http.ResponseWriter, r *http.Request) {
	// DeepSeek balance (call directly, bypassing New API)
	deepseekCNY := 0.0
	deepseekUSD := 0.0
	apiKey := os.Getenv("DEEPSEEK_REAL_KEY")
	if apiKey != "" {
		req, _ := http.NewRequest("GET", "https://api.deepseek.com/user/balance", nil)
		req.Header.Set("Authorization", "Bearer "+apiKey)
		client := &http.Client{Timeout: 10 * time.Second}
		resp, err := client.Do(req)
		if err == nil {
			defer resp.Body.Close()
			var result struct {
				IsAvailable  bool `json:"is_available"`
				BalanceInfos []struct {
					Currency        string `json:"currency"`
					TotalBalance    string `json:"total_balance"`
					ToppedUpBalance string `json:"topped_up_balance"`
				} `json:"balance_infos"`
			}
			if json.NewDecoder(resp.Body).Decode(&result) == nil {
				for _, bi := range result.BalanceInfos {
					if bi.Currency == "CNY" {
						if v, err := strconv.ParseFloat(bi.TotalBalance, 64); err == nil {
							deepseekCNY = v
							deepseekUSD = v * 0.137
						}
					}
				}
				if GlobalCostTracker != nil {
					GlobalCostTracker.SetBalance(deepseekUSD)
				}
			}
		}
	}

	// Cost tracker
	cost := map[string]interface{}{}
	if GlobalCostTracker != nil {
		cost = GlobalCostTracker.Status()
	}

	// Revenue tracker
	revenue := map[string]interface{}{}
	if GlobalRevenue != nil {
		revenue = GlobalRevenue.Status()
	}

	// DB stats
	var userCount, payingCount int64
	var totalRevenue int64
	if GlobalCostTracker != nil && GlobalCostTracker.DB != nil {
		GlobalCostTracker.DB.QueryRow("SELECT COUNT(*) FROM users").Scan(&userCount)
		GlobalCostTracker.DB.QueryRow("SELECT COUNT(*) FROM subscriptions WHERE status=1 AND (flash_balance>0 OR pro_balance>0)").Scan(&payingCount)
		GlobalCostTracker.DB.QueryRow("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid'").Scan(&totalRevenue)
	}

	resp := map[string]interface{}{
		"server": map[string]interface{}{
			"time": time.Now().UTC().Format(time.RFC3339),
		},
		"deepseek": map[string]interface{}{
			"balance_cny": deepseekCNY,
			"balance_usd": roundUSD(deepseekUSD),
			"balance_idr": int64(deepseekUSD * 16300),
			"checked_at":  time.Now().UTC().Format(time.RFC3339),
		},
		"cost":   cost,
		"revenue": revenue,
		"users": map[string]interface{}{
			"total":  userCount,
			"paying": payingCount,
		},
		"dodo": map[string]interface{}{
			"total_revenue_idr": totalRevenue,
			"total_revenue_cny": float64(totalRevenue) / 2233,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}

// AdminCharts returns daily stats for charts: user signups, revenue, pack sales.
func AdminCharts(w http.ResponseWriter, r *http.Request) {
	db := GlobalCostTracker.DB
	if db == nil {
		writeJSON(w, 500, "DB not available")
		return
	}
	type dp struct {
		Date     string `json:"date"`
		Users    int64  `json:"users"`
		Revenue  int64  `json:"revenue"`
		Payments int64  `json:"payments"`
	}
	points := []dp{}
	rows, err := db.Query(`WITH RECURSIVE dates(d) AS (
		SELECT date('now', '-29 days')
		UNION ALL SELECT date(d, '+1 day') FROM dates WHERE d < date('now')
	)
	SELECT dates.d, COALESCE(us.cnt,0), COALESCE(pr.rev,0), COALESCE(pr.pay,0)
	FROM dates
	LEFT JOIN (SELECT date(created_at) AS day, COUNT(*) AS cnt FROM users GROUP BY day) us ON dates.d=us.day
	LEFT JOIN (SELECT date(created_at) AS day, COALESCE(SUM(amount),0) AS rev, COUNT(*) AS pay FROM payments WHERE status='paid' GROUP BY day) pr ON dates.d=pr.day
	ORDER BY dates.d ASC`)
	if err == nil && rows != nil {
		defer rows.Close()
		for rows.Next() {
			var p dp
			rows.Scan(&p.Date, &p.Users, &p.Revenue, &p.Payments)
			points = append(points, p)
		}
	}
	var sf, su, sp int64
	db.QueryRow("SELECT COUNT(*) FROM payments WHERE status='paid' AND plan LIKE 'flash_%'").Scan(&sf)
	db.QueryRow("SELECT COUNT(*) FROM payments WHERE status='paid' AND plan LIKE 'ultimate_%'").Scan(&su)
	db.QueryRow("SELECT COUNT(*) FROM payments WHERE status='paid' AND plan LIKE 'pro_%'").Scan(&sp)
	var uf, ufl, up, uu int64
	db.QueryRow("SELECT COUNT(*) FROM subscriptions WHERE status=1 AND pack_type='gratis'").Scan(&uf)
	db.QueryRow("SELECT COUNT(*) FROM subscriptions WHERE status=1 AND pack_type='flash'").Scan(&ufl)
	db.QueryRow("SELECT COUNT(*) FROM subscriptions WHERE status=1 AND pack_type='pro'").Scan(&up)
	db.QueryRow("SELECT COUNT(*) FROM subscriptions WHERE status=1 AND pack_type='ultimate'").Scan(&uu)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"daily": points, "sold_flash": sf, "sold_ultimate": su, "sold_pro": sp,
		"users_free": uf, "users_flash": ufl, "users_pro": up, "users_ultimate": uu,
	})
}

func AdminDeepSeekBalance(w http.ResponseWriter, r *http.Request) {
	apiKey := os.Getenv("DEEPSEEK_REAL_KEY")
	if apiKey == "" {
		writeJSON(w, 500, "DEEPSEEK_API_KEY not configured")
		return
	}
	req, _ := http.NewRequest("GET", "https://api.deepseek.com/user/balance", nil)
	req.Header.Set("Authorization", "Bearer "+apiKey)
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		slog.Warn("deepseek balance check failed", "error", err)
		writeJSON(w, 502, "DeepSeek API tidak terjangkau")
		return
	}
	defer resp.Body.Close()
	var result struct {
		IsAvailable  bool `json:"is_available"`
		BalanceInfos []struct {
			Currency        string `json:"currency"`
			TotalBalance    string `json:"total_balance"`
			ToppedUpBalance string `json:"topped_up_balance"`
		} `json:"balance_infos"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		writeJSON(w, 500, "Gagal parse response DeepSeek")
		return
	}
	var balances []map[string]interface{}
	for _, bi := range result.BalanceInfos {
		balances = append(balances, map[string]interface{}{
			"currency":      bi.Currency,
			"total_balance": bi.TotalBalance,
			"topped_up":     bi.ToppedUpBalance,
		})
	}
	writeJSON(w, 200, map[string]interface{}{
		"is_available": result.IsAvailable,
		"balances":     balances,
		"checked_at":   time.Now().UTC().Format(time.RFC3339),
	})
}
