package main

import (
	"context"
	"crypto/x509"
	"encoding/json"
	"encoding/pem"
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

	"github.com/unrolled/secure"
	"tokenline/internal/handler"
	"tokenline/internal/middleware"
)

var (
	cachedCertExpiry *time.Time
)

func main() {
	cfg := config.Load()

	// DB
	database, err := db.Open(cfg.DBPath)
	if err != nil {
		log.Fatalf("db: %v", err)
	}
	syscall.Umask(0077) // restrict WAL/SHM file permissions to owner-only
	schemaPath := filepath.Join(filepath.Dir(cfg.DBPath), "..", "sql", "schema.sql")
	if _, err := os.Stat(schemaPath); os.IsNotExist(err) {
		schemaPath = "/app/rewriter-go/sql/schema.sql" // production fallback
	}
	if err := db.Migrate(database, schemaPath); err != nil {
		log.Fatalf("migrate: %v", err)
	}
	slog.Info("db ready")
	// Cache SSL cert expiry at startup — avoids disk read on every health check.
	if certData, err := os.ReadFile("/app/rewriter-go/cert.pem"); err == nil {
		if block, _ := pem.Decode(certData); block != nil {
			if cert, err := x509.ParseCertificate(block.Bytes); err == nil {
				exp := cert.NotAfter
				cachedCertExpiry = &exp
			}
		}
	}

	// DeepSeek
	ds := deepseek.New(cfg.DeepSeekKey, cfg.DeepSeekBaseURL)

	// Rate limiters
	authLimiter := middleware.NewRateLimiter(3, 5)  // 3/sec burst 5 for auth
	chatLimiter := middleware.NewRateLimiter(5, 10) // 5/sec burst 10 for chat
	pubLimiter := middleware.NewRateLimiter(10, 20) // 10/sec burst 20 for public reads

	// Handlers
	authH := &handler.AuthHandler{DB: database, JWTSecret: cfg.JWTSecret}
	chatH := &handler.ChatHandler{DB: database, DeepSeek: ds}
	payH := &handler.PayHandler{DB: database}
	userH := &handler.UserHandler{DB: database}
	exportH := &handler.ExportHandler{DB: database}
	tmplH := &handler.TemplateHandler{DB: database}
	handler.InitDodo()
	handler.InitOTP()
	handler.InitMidtrans()

	// Cost tracker — monitors API spend, predicts burn rate
	costTracker := handler.NewCostTracker(database)
	handler.GlobalCostTracker = costTracker

	// Revenue tracker — monitors cash flow + New API health
	revenueTracker := handler.NewRevenueTracker(database)
	handler.GlobalRevenue = revenueTracker

	// Balance monitor — tracks YunPian/Dodo/DeepSeek balances + alerts
	balanceMon := handler.NewBalanceMonitor(database)
	handler.GlobalBalance = balanceMon
	go func() {
		balanceMon.RefreshAll() // initial load
		for {
			time.Sleep(5 * time.Minute)
			balanceMon.RefreshAll()
		}
	}()

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
			"error_count_4xx":   snap.ErrorCount4xx,
			"error_count_5xx":   snap.ErrorCount5xx,
			"total_requests":    snap.TotalRequests,
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
		// SSL cert expiry — cached at startup
		if cachedCertExpiry != nil {
			daysLeft := int(time.Until(*cachedCertExpiry).Hours() / 24)
			resp["ssl_cert"] = map[string]interface{}{
				"expires_at": cachedCertExpiry.Format("2006-01-02"),
				"days_left":  daysLeft,
			}
		}
		w.Header().Set("Content-Type", "application/json")
		if status == "degraded" {
			w.WriteHeader(503)
		}
		json.NewEncoder(w).Encode(resp)
	})

	// Protected routes with rate limiting
	mux.HandleFunc("POST /api/chat", chain(chatH.Chat, middleware.Auth(cfg.JWTSecret), middleware.RateLimit(chatLimiter)))
	mux.HandleFunc("GET /api/chat/history", chain(userH.History, middleware.Auth(cfg.JWTSecret), middleware.RateLimit(chatLimiter)))
	mux.HandleFunc("GET /api/packs", chain(payH.ListPacks, middleware.RateLimit(pubLimiter)))
	mux.HandleFunc("GET /api/templates", chain(tmplH.List, middleware.RateLimit(pubLimiter)))
	mux.HandleFunc("GET /api/citation/search", chain(handler.SearchCitations, middleware.RateLimit(pubLimiter)))
	mux.HandleFunc("POST /api/export", chain(exportH.Export, middleware.Auth(cfg.JWTSecret), middleware.RateLimit(chatLimiter)))
	mux.HandleFunc("POST /api/upload", chain(handler.UploadHandler, middleware.Auth(cfg.JWTSecret), middleware.RateLimit(authLimiter)))
	mux.HandleFunc("POST /api/payment/create", chain(payH.Create, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/payment/callback", payH.Callback)
	mux.HandleFunc("POST /api/payment/midtrans-callback", payH.MidtransCallback)
	mux.HandleFunc("GET /api/payment/methods", func(w http.ResponseWriter, r *http.Request) {
		methods := []map[string]interface{}{}
		if handler.MidtransAvailable() {
			methods = append(methods, map[string]interface{}{
				"id":          "midtrans",
				"name":        "Midtrans",
				"channels":    []string{"gopay", "qris", "shopeepay", "bank_transfer", "echannel", "cstore"},
				"description": "GoPay, OVO, DANA, QRIS, transfer bank, Indomaret/Alfamart",
			})
		}
		if handler.DodoAvailable() {
			methods = append(methods, map[string]interface{}{
				"id":          "dodo",
				"name":        "Dodo Payments",
				"channels":    []string{"card", "ewallet"},
				"description": "Kartu kredit/debit, e-wallet internasional",
			})
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(methods)
	})
	mux.HandleFunc("GET /api/me", chain(userH.Me, middleware.Auth(cfg.JWTSecret), middleware.RateLimit(chatLimiter)))
	mux.HandleFunc("GET /api/me/balance", chain(chatH.GetBalance, middleware.Auth(cfg.JWTSecret), middleware.RateLimit(chatLimiter)))
	mux.HandleFunc("POST /api/auth/send-otp", chain(authH.SendOTP, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/auth/send-otp-voice", chain(authH.SendOTPVoice, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/auth/verify-otp", chain(authH.VerifyOTP, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/auth/change-password", chain(authH.ChangePassword, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/auth/request-reset", chain(authH.RequestPasswordReset, middleware.RateLimit(authLimiter)))
	mux.HandleFunc("POST /api/auth/reset-password", chain(authH.ResetPassword, middleware.RateLimit(authLimiter)))
	mux.HandleFunc("GET /api/me/stats", chain(userH.Stats, middleware.Auth(cfg.JWTSecret), middleware.RateLimit(chatLimiter)))
	mux.HandleFunc("POST /api/feedback", chain(handler.FeedbackHandler, middleware.Auth(cfg.JWTSecret), middleware.RateLimit(authLimiter)))

	// Admin routes — password-protected, exposes financial/ops data
	adminMux := http.NewServeMux()
	adminMux.HandleFunc("GET /api/admin/cost", costTracker.CostStatusHandler)
	adminMux.HandleFunc("GET /api/admin/balance", handler.AdminDeepSeekBalance)
	adminMux.HandleFunc("GET /api/admin/revenue", revenueTracker.StatusHandler)
	adminMux.HandleFunc("GET /api/admin/dashboard", handler.AdminDashboard)
	adminMux.HandleFunc("GET /api/admin/balances", handler.AdminBalanceHandler)
		adminMux.HandleFunc("GET /api/admin/charts", handler.AdminCharts)
	mux.Handle("/api/admin/", handler.AdminAuth(middleware.RateLimit(authLimiter)(adminMux)))

	// Monitoring wrapper
	monitoredMux := monitorMiddleware(mux)

	// Security headers — nginx terminates TLS, Go runs plain HTTP on localhost.
	secureMiddleware := secure.New(secure.Options{
		SSLRedirect:           false, // nginx handles HTTPS redirect
		STSSeconds:             31536000,
		STSIncludeSubdomains:   true,
		STSPreload:             true,
		FrameDeny:              true,
		ContentTypeNosniff:     true,
		BrowserXssFilter:       true,
		ReferrerPolicy:         "strict-origin-when-cross-origin",
		ContentSecurityPolicy:  "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data: https:; font-src 'self' https://fonts.googleapis.com https://fonts.gstatic.com; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
		PermissionsPolicy:      "camera=(), microphone=(), geolocation=()",
		AllowedHosts:           []string{"tokenline.top", "www.tokenline.top", "127.0.0.1:9100", "localhost"},
		IsDevelopment:          false,
	})
	secureHandler := secureMiddleware.Handler(monitoredMux)

	// CORS
	corsHandler := corsMiddleware(secureHandler)

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
			w.Header().Set("Vary", "Origin")
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
