package main

import (
	"context"
	"encoding/json"
	"log"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"syscall"
	"time"

	"tokenline/internal/config"
	"tokenline/internal/db"
	"tokenline/internal/deepseek"
	"tokenline/internal/handler"
	"tokenline/internal/middleware"
)

func main() {
	cfg := config.Load()

	// DB
	database, err := db.Open(cfg.DBPath)
	if err != nil {
		log.Fatalf("db: %v", err)
	}
	schemaPath := filepath.Join(filepath.Dir(cfg.DBPath), "..", "sql", "schema.sql")
	if _, err := os.Stat(schemaPath); os.IsNotExist(err) {
		schemaPath = "/app/rewriter-go/sql/schema.sql" // production fallback
	}
	if err := db.Migrate(database, schemaPath); err != nil {
		log.Fatalf("migrate: %v", err)
	}
	slog.Info("db ready")

	// DeepSeek
	ds := deepseek.New(cfg.DeepSeekKey, cfg.DeepSeekBaseURL)

	// Rate limiters
	authLimiter := middleware.NewRateLimiter(3, 5)  // 3/sec burst 5 for auth
	chatLimiter := middleware.NewRateLimiter(5, 10) // 5/sec burst 10 for chat

	// Handlers
	authH := &handler.AuthHandler{DB: database, JWTSecret: cfg.JWTSecret}
	chatH := &handler.ChatHandler{DB: database, DeepSeek: ds}
	payH := &handler.PayHandler{DB: database}
	userH := &handler.UserHandler{DB: database}
	handler.InitDodo()
	handler.InitOTP()

	// Cost tracker — monitors API spend, predicts burn rate
	costTracker := handler.NewCostTracker(database)
	handler.GlobalCostTracker = costTracker

	// Revenue tracker — monitors cash flow + New API health
	revenueTracker := handler.NewRevenueTracker(database)
	handler.GlobalRevenue = revenueTracker

	// New API health check (every 60s) + periodic DB refresh (every 5min)
	go func() {
		for {
			revenueTracker.CheckNewAPI()
			time.Sleep(60 * time.Second)
		}
	}()
	go func() {
		for {
			time.Sleep(5 * time.Minute)
			revenueTracker.RefreshFromDB()
		}
	}()

	// Periodic balance check from New API (every 30 min)
	go func() {
		for {
			time.Sleep(30 * time.Minute)
			req, err := http.NewRequest("GET", "http://127.0.0.1:3100/api/balance", nil)
			if err != nil {
				continue
			}
			req.Header.Set("Content-Type", "application/json")
			client := &http.Client{Timeout: 10 * time.Second}
			resp, err := client.Do(req)
			if err != nil {
				continue
			}
			var result struct {
				Balance float64 `json:"balance"`
			}
			if json.NewDecoder(resp.Body).Decode(&result) == nil {
				costTracker.SetBalance(result.Balance)
				slog.Info("api balance updated", "balance_usd", result.Balance)
			}
			resp.Body.Close()
		}
	}()

	// Router — public routes with rate limiting
	pub := http.NewServeMux()
	pub.HandleFunc("POST /api/auth/register", authH.Register)
	pub.HandleFunc("POST /api/auth/login", authH.Login)

	mux := http.NewServeMux()
	mux.Handle("/api/auth/", middleware.RateLimit(authLimiter)(pub))
	mux.HandleFunc("GET /api/health", func(w http.ResponseWriter, r *http.Request) {
		snap := middleware.HealthSnapshotNow()
		var m runtime.MemStats
		runtime.ReadMemStats(&m)
		dbOK := database.PingContext(r.Context()) == nil
		alerts := middleware.Alerts(snap)
		status := "ok"
		if !dbOK {
			status = "degraded"
		}
		if len(alerts) > 0 {
			status = "warning"
		}
		pred := middleware.PredictTrend()
		resp := map[string]interface{}{
			"prediction":        pred,
			"status":            status,
			"db":                dbOK,
			"uptime_hours":      snap.UptimeSeconds / 3600,
			"error_rate_pct":    snap.ErrorRate,
			"chat_errors":       snap.ChatErrors,
			"rate_limited":      snap.RateLimited,
			"active_users_5m":   snap.ActiveUsers5Min,
			"active_users_1h":   snap.ActiveUsers1H,
			"memory_mb":         m.Alloc / 1024 / 1024,
			"goroutines":        runtime.NumGoroutine(),
			"alerts":            alerts,
		}
		if costTracker != nil {
			resp = costTracker.EnrichHealth(resp)
		}
		if revenueTracker != nil {
			resp = revenueTracker.EnrichHealth(resp)
		}
		w.Header().Set("Content-Type", "application/json")
		if status == "degraded" {
			w.WriteHeader(503)
		}
		json.NewEncoder(w).Encode(resp)
	})

	// Protected routes with rate limiting
	mux.HandleFunc("POST /api/chat", chain(chatH.Chat, middleware.Auth(cfg.JWTSecret), middleware.RateLimit(chatLimiter)))
	mux.HandleFunc("GET /api/chat/history", chain(userH.History, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("GET /api/packs", payH.ListPacks)
	mux.HandleFunc("POST /api/payment/create", chain(payH.Create, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/payment/callback", payH.Callback)
	mux.HandleFunc("GET /api/me", chain(userH.Me, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("GET /api/me/balance", chain(chatH.GetBalance, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/auth/send-otp", chain(authH.SendOTP, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/auth/send-otp-voice", chain(authH.SendOTPVoice, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/auth/verify-otp", chain(authH.VerifyOTP, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/auth/change-password", chain(authH.ChangePassword, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/auth/request-reset", chain(authH.RequestPasswordReset, middleware.RateLimit(authLimiter)))
	mux.HandleFunc("POST /api/auth/reset-password", chain(authH.ResetPassword, middleware.RateLimit(authLimiter)))
	mux.HandleFunc("GET /api/me/stats", chain(userH.Stats, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/feedback", chain(handler.FeedbackHandler, middleware.RateLimit(authLimiter)))
	mux.HandleFunc("POST /api/me/refund", chain(userH.RequestRefund, middleware.Auth(cfg.JWTSecret)))

	// Admin routes — password-protected, exposes financial/ops data
	adminMux := http.NewServeMux()
	adminMux.HandleFunc("GET /api/admin/cost", costTracker.CostStatusHandler)
	adminMux.HandleFunc("GET /api/admin/balance", handler.AdminDeepSeekBalance)
	adminMux.HandleFunc("GET /api/admin/revenue", revenueTracker.StatusHandler)
	adminMux.HandleFunc("GET /api/admin/dashboard", handler.AdminDashboard)
	mux.Handle("/api/admin/", handler.AdminAuth(adminMux))

	// Monitoring wrapper
	monitoredMux := monitorMiddleware(mux)

	// CORS
	corsHandler := corsMiddleware(monitoredMux)

	// Hourly trend recording
	go func() {
		for {
			time.Sleep(1 * time.Hour)
			snap := middleware.HealthSnapshotNow()
			var m runtime.MemStats
			runtime.ReadMemStats(&m)
			middleware.RecordTrend(snap.ActiveUsers1H, snap.TotalRequests, snap.ErrorCount, m.Alloc/1024/1024)
		}
	}()

	// Graceful shutdown
	server := &http.Server{
		Addr:         "127.0.0.1:" + cfg.Port,
		Handler:      corsHandler,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 180 * time.Second,
	}
	go func() {
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("server: %v", err)
		}
	}()
	slog.Info("listening", "port", cfg.Port)

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	slog.Info("shutting down...")
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	server.Shutdown(ctx)
	database.Close()
}

func chain(h http.HandlerFunc, mws ...func(http.Handler) http.Handler) http.HandlerFunc {
	for i := len(mws) - 1; i >= 0; i-- {
		h = mws[i](h).ServeHTTP
	}
	return h
}

func monitorMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		sw := &statusWriter{ResponseWriter: w, status: 200}
		next.ServeHTTP(sw, r)
		middleware.TrackRequest(sw.status)
	})
}

type statusWriter struct {
	http.ResponseWriter
	status int
}

func (sw *statusWriter) WriteHeader(code int) {
	sw.status = code
	sw.ResponseWriter.WriteHeader(code)
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if origin == "https://tokenline.top" || origin == "https://www.tokenline.top" {
			w.Header().Set("Access-Control-Allow-Origin", origin)
		}
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if r.Method == "OPTIONS" {
			w.WriteHeader(204)
			return
		}
		next.ServeHTTP(w, r)
	})
}
