package main

import (
	"log"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
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
	if err := db.Migrate(database, "sql/schema.sql"); err != nil {
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

	// SMS/Voice OTP via YunPian
	handler.InitOTP()

	// Router — public routes with rate limiting
	pub := http.NewServeMux()
	pub.HandleFunc("POST /api/auth/register", authH.Register)
	pub.HandleFunc("POST /api/auth/login", authH.Login)

	mux := http.NewServeMux()
	mux.Handle("/api/auth/", middleware.RateLimit(authLimiter)(pub))
	mux.HandleFunc("GET /api/health", func(w http.ResponseWriter, r *http.Request) {
		if err := database.PingContext(r.Context()); err != nil {
			http.Error(w, `{"status":"degraded"}`, 503)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok"}`))
	})

	// Protected routes with rate limiting
	mux.HandleFunc("POST /api/chat", chain(chatH.Chat, middleware.Auth(cfg.JWTSecret), middleware.RateLimit(chatLimiter)))
	mux.HandleFunc("GET /api/chat/history", chain(userH.History, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/payment/create", chain(payH.Create, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/payment/callback", payH.Callback)
	mux.HandleFunc("GET /api/me", chain(userH.Me, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/auth/change-password", chain(authH.ChangePassword, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/auth/send-otp", chain(authH.SendOTP, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/auth/send-otp-voice", chain(authH.SendOTPVoice, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/auth/verify-otp", chain(authH.VerifyOTP, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/auth/request-reset", chain(authH.RequestPasswordReset, middleware.RateLimit(authLimiter)))
	mux.HandleFunc("POST /api/auth/reset-password", chain(authH.ResetPassword, middleware.RateLimit(authLimiter)))
	mux.HandleFunc("GET /api/me/stats", chain(userH.Stats, middleware.Auth(cfg.JWTSecret)))
	mux.HandleFunc("POST /api/feedback", handler.FeedbackHandler)
	mux.HandleFunc("POST /api/me/refund", chain(userH.RequestRefund, middleware.Auth(cfg.JWTSecret)))

	// CORS
	corsHandler := corsMiddleware(mux)

	// Graceful shutdown
	server := &http.Server{
		Addr:         "127.0.0.1:" + cfg.Port,
		Handler:      corsHandler,
		ReadTimeout:  30 * time.Second,
		WriteTimeout: 180 * time.Second,
	}
	go func() {
		slog.Info("listening", "port", cfg.Port)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("server: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	slog.Info("shutting down...")
	server.Close()
	database.Close()
}

func chain(h http.HandlerFunc, mws ...func(http.Handler) http.Handler) http.HandlerFunc {
	for i := len(mws) - 1; i >= 0; i-- {
		h = mws[i](h).ServeHTTP
	}
	return h
}

func corsMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := r.Header.Get("Origin")
		if origin == "https://tokenline.top" || origin == "https://www.tokenline.top" {
			w.Header().Set("Access-Control-Allow-Origin", origin)
		}
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
		if r.Method == "OPTIONS" {
			w.WriteHeader(204)
			return
		}
		next.ServeHTTP(w, r)
	})
}
