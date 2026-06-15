package handler

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"sync"
	"sync/atomic"
	"time"
)

// CostTracker tracks estimated API spend and predicts burn rate.
// DeepSeek V4 pricing per 1M tokens (CNY → USD @ ~0.137):
//   Flash: ¥1 input / ¥2 output → ~$0.14 / $0.27
//   Pro:   ¥3 input / ¥6 output → ~$0.41 / $0.82 (permanent 75% price drop May 2026)
// New API Type 43 passes through directly — no markup.

type CostTracker struct {
	DB *sql.DB

	mu              sync.RWMutex
	totalCostMicro  atomic.Int64
	totalRequests   atomic.Int64
	totalTokens     atomic.Int64
	hourlyCosts     [24]int64
	hourlyIdx       int
	lastHour        int
	lastBalanceUSD  float64
	lastBalanceAt   time.Time
}

var GlobalCostTracker *CostTracker

func NewCostTracker(db *sql.DB) *CostTracker {
	ct := &CostTracker{DB: db}
	var cost, reqs, toks int64
	db.QueryRow(`SELECT COALESCE(SUM(cost_micro_usd),0), COALESCE(SUM(requests),0), COALESCE(SUM(tokens),0)
		FROM cost_log WHERE created_at >= datetime('now','-24 hours')`).Scan(&cost, &reqs, &toks)
	ct.totalCostMicro.Store(cost)
	ct.totalRequests.Store(reqs)
	ct.totalTokens.Store(toks)
	ct.lastHour = time.Now().UTC().Hour()
	return ct
}

func (ct *CostTracker) RecordRequest(model string, inputTokens, outputTokens int64) {
	var inPrice, outPrice float64
	if model == "deepseek-v4-pro" {
		inPrice, outPrice = 0.41, 0.82 // ¥3/¥6 per 1M → USD
	} else {
		inPrice, outPrice = 0.14, 0.27 // ¥1/¥2 per 1M → USD
	}
	costUSD := float64(inputTokens)/1e6*inPrice + float64(outputTokens)/1e6*outPrice
	costMicro := int64(costUSD * 1_000_000)

	ct.totalCostMicro.Add(costMicro)
	ct.totalRequests.Add(1)
	ct.totalTokens.Add(inputTokens + outputTokens)

	ct.mu.Lock()
	hour := time.Now().UTC().Hour()
	if hour != ct.lastHour {
		ct.hourlyIdx = (ct.hourlyIdx + 1) % 24
		ct.hourlyCosts[ct.hourlyIdx] = 0
		ct.lastHour = hour
	}
	ct.hourlyCosts[ct.hourlyIdx] += costMicro
	ct.mu.Unlock()

	if ct.DB != nil {
		ct.DB.Exec(`INSERT INTO cost_log(model, input_tokens, output_tokens, cost_micro_usd, requests, tokens)
			VALUES(?,?,?,?,1,?)`, model, inputTokens, outputTokens, costMicro, inputTokens+outputTokens)
	}
}

func (ct *CostTracker) Status() map[string]interface{} {
	totalCost := ct.totalCostMicro.Load()
	totalReq := ct.totalRequests.Load()
	totalTok := ct.totalTokens.Load()

	ct.mu.RLock()
	var sum24h int64
	validHours := 0
	for _, c := range ct.hourlyCosts {
		if c > 0 {
			sum24h += c
			validHours++
		}
	}
	ct.mu.RUnlock()

	avgHourly := int64(0)
	if validHours > 0 {
		avgHourly = sum24h / int64(validHours)
	}

	daysRemaining := "∞"
	if avgHourly > 0 && ct.lastBalanceUSD > 0 {
		days := ct.lastBalanceUSD / (float64(avgHourly) / 1_000_000 * 24)
		if days < 365*10 {
			daysRemaining = fmt.Sprintf("%.0f hari", days)
		}
	}

	avgPerReq := float64(0)
	if totalReq > 0 {
		avgPerReq = float64(totalCost) / float64(totalReq) / 1_000_000
	}

	alerts := []string{}
	if ct.lastBalanceUSD > 0 && ct.lastBalanceUSD < 5.0 {
		alerts = append(alerts, "⚠️ Saldo API < $5 — segera isi ulang!")
	}
	if avgHourly > 0 && ct.lastBalanceUSD > 0 {
		days := ct.lastBalanceUSD / (float64(avgHourly) / 1_000_000 * 24)
		if days < 3 {
			alerts = append(alerts, "🚨 Saldo habis < 3 hari!")
		} else if days < 7 {
			alerts = append(alerts, "⚡ Saldo habis < 7 hari — siapkan isi ulang")
		}
	}

	return map[string]interface{}{
		"total_cost_usd_24h":      roundUSD(float64(totalCost) / 1_000_000),
		"total_requests_24h":      totalReq,
		"total_tokens_24h":        totalTok,
		"avg_cost_per_request_usd": roundUSD(avgPerReq),
		"burn_rate_hourly_usd":    roundUSD(float64(avgHourly) / 1_000_000),
		"burn_rate_daily_usd":     roundUSD(float64(avgHourly) / 1_000_000 * 24),
		"predicted_monthly_usd":   roundUSD(float64(avgHourly) / 1_000_000 * 24 * 30),
		"api_balance_usd":         roundUSD(ct.lastBalanceUSD),
		"days_remaining":          daysRemaining,
		"alerts":                  alerts,
	}
}

func (ct *CostTracker) SetBalance(b float64) {
	ct.lastBalanceUSD = b
	ct.lastBalanceAt = time.Now().UTC()
}

func (ct *CostTracker) CostStatusHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(ct.Status())
}

func (ct *CostTracker) EnrichHealth(base map[string]interface{}) map[string]interface{} {
	s := ct.Status()
	base["cost"] = map[string]interface{}{
		"total_usd_24h":     s["total_cost_usd_24h"],
		"burn_daily_usd":    s["burn_rate_daily_usd"],
		"predicted_monthly": s["predicted_monthly_usd"],
		"api_balance":       s["api_balance_usd"],
		"days_left":         s["days_remaining"],
		"alerts":            s["alerts"],
	}
	return base
}

func (ct *CostTracker) AdminCheckBalance(w http.ResponseWriter, r *http.Request) {
	req, _ := http.NewRequest("GET", "http://127.0.0.1:3100/api/balance", nil)
	req.Header.Set("Content-Type", "application/json")
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		slog.Warn("new-api balance check failed", "error", err)
		writeJSON(w, 502, "New API tidak terjangkau")
		return
	}
	defer resp.Body.Close()

	var result struct {
		Balance float64 `json:"balance"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		slog.Warn("new-api balance parse failed", "error", err)
		s := ct.Status()
		writeJSON(w, 200, map[string]interface{}{
			"balance_source": "estimated",
			"api_balance_usd": s["api_balance_usd"],
			"burn_daily_usd":  s["burn_rate_daily_usd"],
			"days_remaining":  s["days_remaining"],
			"alerts":          s["alerts"],
		})
		return
	}
	ct.SetBalance(result.Balance)
	s := ct.Status()
	writeJSON(w, 200, map[string]interface{}{
		"balance_source":  "new-api",
		"api_balance_usd": result.Balance,
		"burn_daily_usd":  s["burn_rate_daily_usd"],
		"days_remaining":  s["days_remaining"],
		"alerts":          s["alerts"],
	})
}

func TrackCostInChat(model string, inputChars, outputChars int) {
	if GlobalCostTracker == nil {
		return
	}
	inputTokens := int64(float64(inputChars) / 1.8)
	outputTokens := int64(float64(outputChars) / 1.8)
	if inputTokens < 10 {
		inputTokens = 10
	}
	if outputTokens < 10 {
		outputTokens = 10
	}
	GlobalCostTracker.RecordRequest(model, inputTokens, outputTokens)
}

func roundUSD(v float64) float64 {
	return float64(int64(v*10000)) / 10000
}
