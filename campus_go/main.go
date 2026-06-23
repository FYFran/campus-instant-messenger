package main

import (
	"campus-go/internal/database"
	"campus-go/internal/handlers"
	"campus-go/internal/middleware"
	"log"
	"os"
	"time"

	"github.com/gin-gonic/gin"
)

func main() {
	// Validate config before connecting to DB
	if err := middleware.ValidateConfig(); err != nil {
		log.Fatal(err)
	}

	db := database.Connect()
	defer db.Close()

	r := gin.New()
	r.Use(gin.Logger(), gin.Recovery())
	r.Use(middleware.CORS())
	r.Use(middleware.RequestID()) // Trace every request (G01 observability fix)
	// Rate limiting is handled by nginx reverse proxy in production

	// Start WebSocket hub
	go handlers.Hub.Run()

	api := r.Group("/api")
	{
		api.GET("/version", handlers.Version)
		api.GET("/colleges", handlers.GetColleges(db))
		api.GET("/notices", handlers.ListNotices(db))
		api.GET("/health", handlers.HealthCheck(db))

		auth := api.Group("/auth")
		{
			auth.POST("/reset-password", handlers.ResetPassword(db))
		}

		api.POST("/login", handlers.Login(db))
		api.POST("/register", middleware.RateLimit(6, time.Minute), handlers.Register(db))
		api.POST("/token/refresh", handlers.RefreshToken(db)) // 不需要JWT — refresh_token自身就是凭证

		protected := api.Group("")
		protected.Use(middleware.JWT(db))
		protected.Use(middleware.RateLimit(60, time.Minute))
		{
			protected.POST("/upload", handlers.UploadImage())
			protected.GET("/me", handlers.GetMe(db))
			protected.GET("/activities", handlers.ListActivities(db))
			protected.GET("/activities/:id", handlers.GetActivity(db))
			protected.POST("/activities", handlers.CreateActivity(db))
			protected.POST("/activities/:id/signup", handlers.Signup(db))
			protected.POST("/activities/:id/cancel-signup", handlers.CancelSignup(db))
			protected.POST("/activities/:id/approve", handlers.ApproveActivity(db))
			protected.POST("/activities/:id/reject", handlers.RejectActivity(db))
			protected.POST("/activities/:id/modify", handlers.ModifyActivity(db))
			protected.GET("/activities/pending-approvals", handlers.GetPendingApprovals(db))
			protected.POST("/notices", handlers.CreateNotice(db))
			protected.GET("/college/dashboard", handlers.CollegeDashboard(db))
			protected.GET("/school/dashboard", handlers.SchoolDashboard(db))
			protected.GET("/college/students", handlers.CollegeStudents(db))
			protected.GET("/notifications", handlers.GetNotifications(db))
			protected.GET("/my-signups", handlers.GetMySignups(db))
			protected.GET("/my-stats", handlers.GetMyStats(db))
			protected.GET("/users", handlers.ListUsers(db))
			protected.GET("/config/codes", handlers.GetConfigCodes(db))
			api.GET("/ws", handlers.HandleWS)
			// Publish permission requests
			protected.GET("/available-reviewers", handlers.GetAvailableReviewers(db))
			protected.POST("/publish-requests", handlers.CreatePublishRequest(db))
			protected.GET("/publish-requests/my", handlers.GetMyPublishRequests(db))
			protected.POST("/publish-requests/:id/withdraw", handlers.WithdrawPublishRequest(db))
			protected.GET("/publish-requests/pending", handlers.GetPendingReviews(db))
			protected.POST("/publish-requests/:id/review", handlers.ReviewPublishRequest(db))
		}
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "9501"
	}
	log.Printf("Go backend starting on port %s", port)
	log.Fatal(r.Run(":" + port))
}
