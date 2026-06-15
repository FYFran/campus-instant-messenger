package handler

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"sync"
	"sync/atomic"
	"time"
)

// RevenueTracker monitors cash flow: what users paid, what's pending in Dodo, what's available.
// Dodo settlement: 7-30 days after payment. During KYC review, funds are locked.

type RevenueTracker struct {
	DB *sql.DB

	mu       sync.RWMutex
	exchangeRate float64 // USD to IDR

	newAPIUp        atomic.Int64
	newAPILastCheck atomic.Value

	totalPaidIDR    atomic.Int64
	totalPendingIDR atomic.Int64
	thisMonthIDR    atomic.Int64
	lastMonthIDR    atomic.Int64
}

var GlobalRevenue *RevenueTracker

func NewRevenueTracker(db *sql.DB) *RevenueTracker {
	rt := &RevenueTracker{DB: db, exchangeRate: 16300}
	rt.newAPIUp.Store(1)
	rt.newAPILastCheck.Store(time.Now())
	rt.RefreshFromDB()
	return rt
}

// SetExchangeRate updates the USD→IDR conversion rate.
func (rt *RevenueTracker) SetExchangeRate(rate float64) {
	rt.mu.Lock()
	rt.exchangeRate = rate
	rt.mu.Unlock()
}

func (rt *RevenueTracker) RefreshFromDB() {
	if rt.DB == nil {
		return
	}
	var total, pending, thisMonth, lastMonth int64
	rt.DB.QueryRow("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid'").Scan(&total)
	rt.DB.QueryRow("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='pending'").Scan(&pending)
	rt.DB.QueryRow("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid' AND paid_at >= date('now','start of month')").Scan(&thisMonth)
	rt.DB.QueryRow("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid' AND paid_at >= date('now','start of month','-1 month') AND paid_at < date('now','start of month')").Scan(&lastMonth)

	rt.totalPaidIDR.Store(total)
	rt.totalPendingIDR.Store(pending)
	rt.thisMonthIDR.Store(thisMonth)
	rt.lastMonthIDR.Store(lastMonth)
}

func (rt *RevenueTracker) CheckNewAPI() bool {
	client := &http.Client{Timeout: 5 * time.Second}
	resp, err := client.Get("http://127.0.0.1:3100/health")
	if err != nil {
		rt.newAPIUp.Store(0)
		rt.newAPILastCheck.Store(time.Now())
		return false
	}
	defer resp.Body.Close()
	up := resp.StatusCode < 500
	if up {
		rt.newAPIUp.Store(1)
	} else {
		rt.newAPIUp.Store(0)
	}
	rt.newAPILastCheck.Store(time.Now())
	return up
}

func (rt *RevenueTracker) Status() map[string]interface{} {
	rt.mu.RLock()
	rate := rt.exchangeRate
	rt.mu.RUnlock()

	newAPIUp := rt.newAPIUp.Load() == 1
	lastCheck, _ := rt.newAPILastCheck.Load().(time.Time)

	alerts := []string{}
	if !newAPIUp {
		alerts = append(alerts, "🚨 New API (127.0.0.1:3100) TIDAK MERESPON — semua chat akan gagal!")
	}
	if time.Since(lastCheck).Seconds() > 300 {
		alerts = append(alerts, "⚠️ New API health check terakhir > 5 menit lalu")
	}

	totalPaid := rt.totalPaidIDR.Load()
	pending := rt.totalPendingIDR.Load()
	twoWeeksAgo := time.Now().Add(-14 * 24 * time.Hour).Format("2006-01-02")
	var recentPaid int64
	if rt.DB != nil {
		rt.DB.QueryRow("SELECT COALESCE(SUM(amount),0) FROM payments WHERE status='paid' AND paid_at >= ?", twoWeeksAgo).Scan(&recentPaid)
	}
	estimatedInDodo := recentPaid
	availableNow := totalPaid - estimatedInDodo
	if availableNow < 0 {
		availableNow = 0
	}

	return map[string]interface{}{
		"new_api": map[string]interface{}{
			"healthy":     newAPIUp,
			"last_check":  lastCheck.Format(time.RFC3339),
			"seconds_ago": int(time.Since(lastCheck).Seconds()),
		},
		"revenue": map[string]interface{}{
			"total_paid_idr":      totalPaid,
			"total_paid_usd":      float64(totalPaid) / rate,
			"pending_idr":         pending,
			"this_month_idr":      rt.thisMonthIDR.Load(),
			"last_month_idr":      rt.lastMonthIDR.Load(),
			"estimated_in_dodo":   estimatedInDodo,
			"available_estimated": availableNow,
			"exchange_rate":       rate,
			"settlement_note":     "Dodo settlement 7-30 hari. Estimasi: dana 14 hari terakhir masih di Dodo.",
		},
		"alerts": alerts,
	}
}

func (rt *RevenueTracker) StatusHandler(w http.ResponseWriter, r *http.Request) {
	rt.RefreshFromDB()
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(rt.Status())
}

func (rt *RevenueTracker) EnrichHealth(base map[string]interface{}) map[string]interface{} {
	s := rt.Status()
	base["new_api"] = s["new_api"]
	base["revenue"] = s["revenue"]
	if existing, ok := base["alerts"].([]string); ok {
		if newAlerts, ok2 := s["alerts"].([]string); ok2 {
			base["alerts"] = append(existing, newAlerts...)
		}
	}
	return base
}
