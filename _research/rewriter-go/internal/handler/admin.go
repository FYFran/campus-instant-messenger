package handler

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"
)

// AdminAuth protects admin routes with a password from env ADMIN_PASSWORD.
// Pass password as ?key=xxx query parameter.
func AdminAuth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Allow CORS preflight without password
		if r.Method == "OPTIONS" {
			w.WriteHeader(204)
			return
		}
		// Allow localhost without password (SSH tunnel / direct server access)
		ip := r.Header.Get("X-Real-IP")
		if ip == "" { ip = r.RemoteAddr }
		if strings.HasPrefix(ip, "127.0.0.1") || strings.HasPrefix(ip, "::1") || strings.HasPrefix(ip, "[::1]") {
			next.ServeHTTP(w, r)
			return
		}
		adminPass := os.Getenv("ADMIN_PASSWORD")
		if adminPass == "" {
			adminPass = "tokenline2026" // default password if not set
		}
		key := r.URL.Query().Get("key")
		if key == "" {
			key = r.Header.Get("X-Admin-Key")
		}
		if key != adminPass {
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
		GlobalCostTracker.DB.QueryRow("SELECT COUNT(*) FROM subscriptions WHERE status=1 AND token_balance>0").Scan(&payingCount)
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
			"total":   userCount,
			"paying":  payingCount,
		},
		"dodo": map[string]interface{}{
			"total_revenue_idr": totalRevenue,
			"total_revenue_cny": float64(totalRevenue) / 2233,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
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
