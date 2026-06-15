package middleware

import (
	"net/http"
	"sync"
	"time"
)

type visitor struct {
	tokens    float64
	lastCheck time.Time
}

type RateLimiter struct {
	mu       sync.Mutex
	visitors map[string]*visitor
	rate     float64
	burst    int
}

func NewRateLimiter(ratePerSec float64, burst int) *RateLimiter {
	rl := &RateLimiter{
		visitors: make(map[string]*visitor),
		rate:     ratePerSec,
		burst:    burst,
	}
	go rl.cleanup(5 * time.Minute)
	return rl
}

func (rl *RateLimiter) cleanup(interval time.Duration) {
	for {
		time.Sleep(interval)
		rl.mu.Lock()
		for k, v := range rl.visitors {
			if time.Since(v.lastCheck) > interval {
				delete(rl.visitors, k)
			}
		}
		rl.mu.Unlock()
	}
}

func (rl *RateLimiter) Allow(key string) bool {
	rl.mu.Lock()
	defer rl.mu.Unlock()
	v, ok := rl.visitors[key]
	if !ok {
		v = &visitor{tokens: float64(rl.burst), lastCheck: time.Now()}
		rl.visitors[key] = v
	}
	elapsed := time.Since(v.lastCheck).Seconds()
	v.tokens += elapsed * rl.rate
	if v.tokens > float64(rl.burst) {
		v.tokens = float64(rl.burst)
	}
	v.lastCheck = time.Now()
	if v.tokens < 1 {
		return false
	}
	v.tokens--
	return true
}

func RateLimit(rl *RateLimiter) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// X-Real-IP is set by nginx from $remote_addr — not spoofable by client
			ip := r.Header.Get("X-Real-IP")
			if ip == "" {
				// Fallback for direct access (localhost health checks)
				ip = r.RemoteAddr
			}
			if !rl.Allow(ip) {
				http.Error(w, `{"message":"Terlalu banyak permintaan. Coba lagi nanti.","retry_after":"30"}`, 429)
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}
