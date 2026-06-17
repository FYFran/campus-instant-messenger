package handler

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"strconv"
	"sync"
	"time"
)

// BalanceMonitor tracks ALL external service balances in real-time.
// YunPian SMS, Dodo Payments, DeepSeek API — single source of truth.

var GlobalBalance *BalanceMonitor

type BalanceSnapshot struct {
	// YunPian SMS
	YunPianBalance   float64 `json:"yunpian_balance_cny"`
	YunPianAlarm     float64 `json:"yunpian_alarm_cny"`
	YunPianLow       bool    `json:"yunpian_low"`
	YunPianLastCheck string  `json:"yunpian_last_check"`
	YunPianNick      string  `json:"yunpian_nick"`

	// Dodo Payments
	DodoEstimatedUSD   float64 `json:"dodo_estimated_usd"`
	DodoEstimatedIDR   float64 `json:"dodo_estimated_idr"`
	DodoPendingIDR     int64   `json:"dodo_pending_idr"`
	DodoLastSettlement string  `json:"dodo_last_settlement"`

	// DeepSeek API (via New API)
	DeepSeekBalance   float64 `json:"deepseek_balance_usd"`
	DeepSeekLastCheck string  `json:"deepseek_last_check"`

	// Pack sales stats
	SoldFlash    int64 `json:"sold_flash"`
	SoldUltimate int64 `json:"sold_ultimate"`
	SoldPro      int64 `json:"sold_pro"`

	// System
	TotalRevenueIDR     int64   `json:"total_revenue_idr"`
	ThisMonthIDR        int64   `json:"this_month_idr"`
	MonthlyBurnCNY      float64 `json:"monthly_burn_cny"`
	PredictedRunway     string  `json:"predicted_runway"`
	PredictedRunwayDays float64 `json:"-"` // numeric for alert checks
	ExchangeRate        float64 `json:"exchange_rate"`
}

type BalanceMonitor struct {
	mu          sync.RWMutex
	snapshot    BalanceSnapshot
	httpClient  *http.Client
	lastRefresh time.Time
	dbRef       *sql.DB

	// Historical data for charts
	balanceHistory  []float64 // YunPian balance history
	costHistory24h  []float64 // 24h cost per hour
	lastRateRefresh time.Time
}

func NewBalanceMonitor(db *sql.DB) *BalanceMonitor {
	bm := &BalanceMonitor{
		httpClient:     &http.Client{Timeout: 10 * time.Second},
		dbRef:          db,
		balanceHistory: make([]float64, 0, 168), // 7 days hourly
		costHistory24h: make([]float64, 24),
	}
	bm.snapshot.ExchangeRate = 16300
	bm.snapshot.YunPianAlarm = 10 // alarm at 10 CNY
	bm.snapshot.MonthlyBurnCNY = 70.25
	return bm
}

// RefreshAll queries all external services for real-time balance.
// Gathers data WITHOUT holding the write lock — API calls may take seconds.
// Only acquires write lock at the end to swap in the new snapshot.
func (bm *BalanceMonitor) RefreshAll() {
	now := time.Now()

	// Preserve current rate and alarm threshold under read lock
	bm.mu.RLock()
	snap := BalanceSnapshot{
		YunPianLastCheck:  now.Format("15:04:05"),
		DeepSeekLastCheck: now.Format("15:04:05"),
		ExchangeRate:      bm.snapshot.ExchangeRate,
		YunPianAlarm:      bm.snapshot.YunPianAlarm,
	}
	bm.mu.RUnlock()

	// 1. YunPian SMS balance
	bm.refreshYunPianInto(&snap)

	// 2. DeepSeek balance (via New API)
	bm.refreshDeepSeekInto(&snap)

	// 2.5. Live exchange rate (updates at most once per hour)
	bm.refreshExchangeRateInto(&snap)

	// 3. Revenue from DB + Live exchange rate
	if GlobalRevenue != nil {
		GlobalRevenue.mu.RLock()
		snap.TotalRevenueIDR = GlobalRevenue.totalPaidIDR.Load()
		snap.ThisMonthIDR = GlobalRevenue.thisMonthIDR.Load()
		snap.DodoPendingIDR = GlobalRevenue.totalPendingIDR.Load()
		GlobalRevenue.mu.RUnlock()

		snap.DodoEstimatedIDR = float64(snap.DodoPendingIDR)
		if snap.ExchangeRate > 0 {
			snap.DodoEstimatedUSD = float64(snap.DodoPendingIDR) / snap.ExchangeRate
		}
	}

	// 4. Cost burn rate
	if GlobalCostTracker != nil {
		snap.MonthlyBurnCNY = float64(GlobalCostTracker.totalCostMicro.Load()) / 1_000_000 * 7.2
	}

	// 5. Pack sales stats (non-blocking reads)
	if bm.dbRef != nil {
		_ = bm.dbRef.QueryRow("SELECT COUNT(*) FROM payments WHERE pack_type='flash' AND status='paid'").Scan(&snap.SoldFlash)
		_ = bm.dbRef.QueryRow("SELECT COUNT(*) FROM payments WHERE pack_type='ultimate' AND status='paid'").Scan(&snap.SoldUltimate)
		_ = bm.dbRef.QueryRow("SELECT COUNT(*) FROM payments WHERE pack_type='pro' AND status='paid'").Scan(&snap.SoldPro)
	}

	// 6. Predicted runway
	snap.PredictedRunway = bm.calculateRunwayFrom(&snap)

	// NOW acquire write lock — only for the swap.
	bm.mu.Lock()
	bm.snapshot = snap
	bm.lastRefresh = now

	// History append
	bm.balanceHistory = append(bm.balanceHistory, snap.YunPianBalance)
	if len(bm.balanceHistory) > 168 {
		bm.balanceHistory = bm.balanceHistory[len(bm.balanceHistory)-168:]
	}
	bm.mu.Unlock()
}

func (bm *BalanceMonitor) refreshYunPianInto(snap *BalanceSnapshot) {
	apiKey := os.Getenv("YUNPIAN_API_KEY")
	if apiKey == "" {
		slog.Warn("YUNPIAN_API_KEY not set, skipping balance check")
		return
	}

	resp, err := bm.httpClient.PostForm("https://sms.yunpian.com/v2/user/get.json",
		map[string][]string{"apikey": {apiKey}})
	if err != nil {
		slog.Error("yunpian balance check failed", "error", err)
		return
	}
	defer func() { _ = resp.Body.Close() }()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return
	}

	var data struct {
		Balance      float64 `json:"balance"`
		AlarmBalance float64 `json:"alarm_balance"`
		Nick         string  `json:"nick"`
	}
	if json.Unmarshal(body, &data) == nil {
		snap.YunPianBalance = data.Balance
		snap.YunPianAlarm = data.AlarmBalance
		snap.YunPianLow = data.Balance < 20 // warn below 20 CNY
		snap.YunPianNick = data.Nick
	}
}

func (bm *BalanceMonitor) refreshDeepSeekInto(snap *BalanceSnapshot) {
	apiKey := os.Getenv("DEEPSEEK_REAL_KEY")
	if apiKey == "" {
		slog.Warn("DEEPSEEK_REAL_KEY not set, skipping DeepSeek balance check")
		return
	}
	req, err := http.NewRequest("GET", "https://api.deepseek.com/user/balance", nil)
	if err != nil {
		slog.Warn("deepseek balance request create failed", "error", err)
		return
	}
	req.Header.Set("Authorization", "Bearer "+apiKey)
	resp, err := bm.httpClient.Do(req)
	if err != nil {
		slog.Warn("deepseek balance check failed", "error", err)
		return
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode >= 400 {
		slog.Warn("deepseek balance check returned non-200", "status", resp.StatusCode)
		return
	}

	var result struct {
		IsAvailable  bool `json:"is_available"`
		BalanceInfos []struct {
			Currency        string `json:"currency"`
			TotalBalance    string `json:"total_balance"`
			ToppedUpBalance string `json:"topped_up_balance"`
		} `json:"balance_infos"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		slog.Warn("deepseek balance parse failed", "error", err)
		return
	}
	for _, bi := range result.BalanceInfos {
		if bi.Currency == "CNY" {
			if v, err := strconv.ParseFloat(bi.TotalBalance, 64); err == nil {
				snap.DeepSeekBalance = v * 0.137 // CNY → USD
			}
		}
	}
}

// calculateRunwayFrom returns a human-readable runway string in Indonesian.
// Also sets PredictedRunwayDays on the snapshot for numeric alert checks.
func (bm *BalanceMonitor) calculateRunwayFrom(snap *BalanceSnapshot) string {
	bal := snap.YunPianBalance + snap.DeepSeekBalance*7.2
	burn := snap.MonthlyBurnCNY
	if burn <= 0 {
		burn = 70
	}
	months := bal / burn
	switch {
	case months > 1200:
		return "充足"
	case months > 12:
		return fmt.Sprintf("%.1f 年", months/12)
	case months > 1:
		return fmt.Sprintf("%.1f 月", months)
	case months > 0.034: // > 1 day
		days := months * 30
		snap.PredictedRunwayDays = days
		return fmt.Sprintf("%.0f 天", days)
	default:
		snap.PredictedRunwayDays = months * 30
		return "不足1天"
	}
}

// refreshExchangeRateInto fetches live USD/IDR rate from exchangerate-api.com.
// Runs at most once per hour to respect rate limits.
func (bm *BalanceMonitor) refreshExchangeRateInto(snap *BalanceSnapshot) {
	if time.Since(bm.lastRateRefresh) < 1*time.Hour && snap.ExchangeRate > 0 {
		return // already fresh
	}
	resp, err := bm.httpClient.Get("https://api.exchangerate-api.com/v4/latest/USD")
	if err != nil {
		slog.Warn("exchange rate fetch failed", "error", err)
		return
	}
	defer func() { _ = resp.Body.Close() }()
	var data struct {
		Rates map[string]float64 `json:"rates"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		slog.Warn("exchange rate parse failed", "error", err)
		return
	}
	if rate, ok := data.Rates["IDR"]; ok && rate > 0 {
		snap.ExchangeRate = rate
		bm.lastRateRefresh = time.Now()
		if GlobalRevenue != nil {
			GlobalRevenue.mu.Lock()
			GlobalRevenue.exchangeRate = rate
			GlobalRevenue.mu.Unlock()
		}
		slog.Info("exchange rate updated", "rate", rate)
	}
}

// Snapshot returns a copy of the current balance state.
func (bm *BalanceMonitor) Snapshot() BalanceSnapshot {
	bm.mu.RLock()
	defer bm.mu.RUnlock()
	return bm.snapshot
}

// History returns balance history for chart rendering.
func (bm *BalanceMonitor) History() []float64 {
	bm.mu.RLock()
	defer bm.mu.RUnlock()
	h := make([]float64, len(bm.balanceHistory))
	copy(h, bm.balanceHistory)
	return h
}

// AdminBalanceHandler serves the comprehensive balance dashboard JSON.
func AdminBalanceHandler(w http.ResponseWriter, r *http.Request) {
	if GlobalBalance == nil {
		writeJSON(w, 500, "Balance monitor not initialized")
		return
	}
	GlobalBalance.RefreshAll()
	snap := GlobalBalance.Snapshot()
	history := GlobalBalance.History()

	// Alerts
	var alerts []map[string]string
	if snap.YunPianLow {
		alerts = append(alerts, map[string]string{
			"level": "warning", "service": "YunPian SMS",
			"message": fmt.Sprintf("Saldo SMS rendah: %.1f CNY. Isi ulang segera.", snap.YunPianBalance),
		})
	}
	if snap.DeepSeekBalance < 1.0 {
		alerts = append(alerts, map[string]string{
			"level": "warning", "service": "DeepSeek接口",
			"message": fmt.Sprintf("DeepSeek余额不足: $%.2f，请及时充值", snap.DeepSeekBalance),
		})
	}
	if snap.PredictedRunwayDays < 1.0 && (snap.DeepSeekBalance > 0 || snap.YunPianBalance > 0) {
		alerts = append(alerts, map[string]string{
			"level": "critical", "service": "系统",
			"message": "余额仅够运行不足1天！立即充值。",
		})
	}
	if snap.ThisMonthIDR == 0 {
		alerts = append(alerts, map[string]string{
			"level": "info", "service": "收入",
			"message": "本月暂无收入记录。",
		})
	}

	writeJSON(w, 200, map[string]interface{}{
		"balance":   snap,
		"history":   history,
		"alerts":    alerts,
		"refreshed": time.Now().Format("15:04:05"),
	})
}
