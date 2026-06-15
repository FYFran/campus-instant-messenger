package middleware

import (
	"sync"
	"sync/atomic"
	"time"
)

// Monitor tracks application-level metrics for alerting.
// Zero external dependencies — pure in-memory counters.

var (
	apiErrors4xx atomic.Int64  // 4xx client errors (expected, not server fault)
	apiErrors5xx atomic.Int64  // 5xx server errors (real problems)
	apiRequests  atomic.Int64  // total requests tracked
	chatErrors   atomic.Int64  // DeepSeek API failures
	rateLimited  atomic.Int64  // 429 responses served
	activeUsers  sync.Map      // userID → lastSeen (for active user count)
	startTime    = time.Now()
)

// TrackRequest records an API request outcome for error rate calculation.
// 4xx = client errors (expected: bad auth, dupes, validation). Not server fault.
// 5xx = server errors (real problems). Only 5xx triggers HIGH_ERROR_RATE alert.
func TrackRequest(statusCode int) {
	apiRequests.Add(1)
	if statusCode >= 500 {
		apiErrors5xx.Add(1)
	} else if statusCode >= 400 {
		apiErrors4xx.Add(1)
	}
	if statusCode == 429 {
		rateLimited.Add(1)
	}
}

// TrackChatError records a DeepSeek API failure.
func TrackChatError() { chatErrors.Add(1) }

// TrackActiveUser marks a user as recently active.
func TrackActiveUser(userID int64) {
	activeUsers.Store(userID, time.Now())
}

// HealthSnapshot returns all monitoring metrics.
type HealthSnapshot struct {
	UptimeSeconds   int64   `json:"uptime_seconds"`
	TotalRequests   int64   `json:"total_requests"`
	ErrorCount4xx   int64   `json:"error_count_4xx"`
	ErrorCount5xx   int64   `json:"error_count_5xx"`
	ErrorCount      int64   `json:"error_count"`
	ErrorRate       float64 `json:"error_rate_pct"`    // 5xx only — real server errors
	ChatErrors      int64   `json:"chat_errors"`
	RateLimited     int64   `json:"rate_limited"`
	ActiveUsers5Min int     `json:"active_users_5min"`
	ActiveUsers1H   int     `json:"active_users_1h"`
}

func HealthSnapshotNow() HealthSnapshot {
	total := apiRequests.Load()
	errs4xx := apiErrors4xx.Load()
	errs5xx := apiErrors5xx.Load()
	totalErrs := errs4xx + errs5xx
	var rate float64
	if total > 0 {
		rate = float64(errs5xx) / float64(total) * 100
	}

	now := time.Now()
	var active5m, active1h int
	activeUsers.Range(func(key, value interface{}) bool {
		lastSeen := value.(time.Time)
		if now.Sub(lastSeen) < 5*time.Minute {
			active5m++
			active1h++
		} else if now.Sub(lastSeen) < 1*time.Hour {
			active1h++
		}
		return true
	})

	return HealthSnapshot{
		UptimeSeconds:   int64(now.Sub(startTime).Seconds()),
		TotalRequests:   total,
		ErrorCount4xx:   errs4xx,
		ErrorCount5xx:   errs5xx,
		ErrorCount:      totalErrs,
		ErrorRate:       rate,
		ChatErrors:      chatErrors.Load(),
		RateLimited:     rateLimited.Load(),
		ActiveUsers5Min: active5m,
		ActiveUsers1H:   active1h,
	}
}

// ========== Trend Tracking & Prediction ==========

const maxSamples = 168 // 7 days of hourly snapshots

type trendSample struct {
	Time        time.Time
	ActiveUsers int
	Requests    int64
	Errors      int64
	MemoryMB    uint64
}

var (
	trendSamples []trendSample
	trendMu      sync.Mutex
)

// RecordTrend stores an hourly snapshot for trend analysis.
func RecordTrend(users int, reqs, errs int64, memMB uint64) {
	trendMu.Lock()
	defer trendMu.Unlock()
	trendSamples = append(trendSamples, trendSample{
		Time: time.Now(), ActiveUsers: users, Requests: reqs, Errors: errs, MemoryMB: memMB,
	})
	if len(trendSamples) > maxSamples {
		trendSamples = trendSamples[len(trendSamples)-maxSamples:]
	}
}

// TrendPrediction forecasts capacity usage based on linear regression.
type TrendPrediction struct {
	WeeklyGrowthPct    float64 `json:"weekly_growth_pct"`    // user growth rate per week
	UsersIn4Weeks      int     `json:"users_in_4_weeks"`     // projected active users
	UsersIn12Weeks     int     `json:"users_in_12_weeks"`    // projected active users
	MemoryIn4WeeksMB   uint64  `json:"memory_in_4_weeks_mb"` // projected memory usage
	WeeksUntil1GB      float64 `json:"weeks_until_1gb"`      // weeks until 1GB memory usage
	DBGrowthMBPerWeek  float64 `json:"db_growth_mb_per_week"`// database growth rate
	CapacityStatus     string  `json:"capacity_status"`      // "healthy"|"monitor"|"plan"
}

func PredictTrend() TrendPrediction {
	trendMu.Lock()
	samples := make([]trendSample, len(trendSamples))
	copy(samples, trendSamples)
	trendMu.Unlock()

	p := TrendPrediction{CapacityStatus: "healthy"}

	if len(samples) < 24 { // need at least 24 hours of data
		p.CapacityStatus = "collecting"
		return p
	}

	// Linear regression on active users over time
	// y = ax + b, where x = hours since first sample
	n := float64(len(samples))
	baseTime := samples[0].Time
	var sumX, sumY, sumXY, sumX2 float64
	for _, s := range samples {
		x := s.Time.Sub(baseTime).Hours()
		y := float64(s.ActiveUsers)
		sumX += x
		sumY += y
		sumXY += x * y
		sumX2 += x * x
	}

	slope := (n*sumXY - sumX*sumY) / (n*sumX2 - sumX*sumX)

	// Convert slope (users/hour) to weekly growth rate
	currentUsers := float64(samples[len(samples)-1].ActiveUsers)
	if currentUsers < 1 {
		currentUsers = 1
	}
	weeklySlope := slope * 24 * 7
	p.WeeklyGrowthPct = (weeklySlope / currentUsers) * 100

	// Projections
	p.UsersIn4Weeks = int(currentUsers + slope*24*7*4)
	p.UsersIn12Weeks = int(currentUsers + slope*24*7*12)

	// Memory trend
	currentMem := samples[len(samples)-1].MemoryMB
	if len(samples) > 24 {
		firstMem := samples[len(samples)-24].MemoryMB
		p.DBGrowthMBPerWeek = float64(currentMem-firstMem) / float64(len(samples)-24) * 24 * 7
	}
	p.MemoryIn4WeeksMB = currentMem + uint64(currentMem)*uint64(p.WeeklyGrowthPct/100)*4
	if currentMem > 0 && currentMem < 1000 {
		p.WeeksUntil1GB = float64(1000-currentMem) / (float64(currentMem)*p.WeeklyGrowthPct/100/7 + 0.001)
	} else {
		p.WeeksUntil1GB = 999
	}

	// Capacity status
	if p.UsersIn12Weeks > 800 || p.MemoryIn4WeeksMB > 800 {
		p.CapacityStatus = "plan"
	} else if p.UsersIn4Weeks > 400 || p.WeeklyGrowthPct > 30 {
		p.CapacityStatus = "monitor"
	}

	return p
}

// Alerts checks if any thresholds are exceeded. Returns warning messages.
// HIGH_ERROR_RATE uses 5xx only — 4xx are client errors (bad auth, dupes, scanners), not server fault.
func Alerts(snap HealthSnapshot) []string {
	var alerts []string

	if snap.ErrorRate > 10 && snap.ErrorCount5xx > 3 {
		alerts = append(alerts, "HIGH_ERROR_RATE")
	}
	if snap.ChatErrors > 20 {
		alerts = append(alerts, "DEEPSEEK_API_DEGRADED")
	}
	if snap.RateLimited > 100 {
		alerts = append(alerts, "UNUSUAL_TRAFFIC")
	}
	if snap.ErrorCount4xx > snap.TotalRequests/2 && snap.TotalRequests > 50 {
		alerts = append(alerts, "SCANNER_NOISE") // mostly 4xx = likely scanner/bot traffic
	}

	// Capacity trend alerts
	pred := PredictTrend()
	if pred.CapacityStatus == "plan" {
		alerts = append(alerts, "CAPACITY_PLAN_NEEDED")
	}
	if pred.WeeklyGrowthPct > 50 {
		alerts = append(alerts, "RAPID_GROWTH_DETECTED")
	}

	return alerts
}
