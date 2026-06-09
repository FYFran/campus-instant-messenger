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
	db := database.Connect()
	defer db.Close()

	r := gin.New()
	r.Use(gin.Logger(), gin.Recovery())
	r.Use(middleware.CORS())
	// Rate limiting is handled by nginx reverse proxy in production

	api := r.Group("/api")
	{
		api.GET("/version", handlers.Version)
		api.GET("/colleges", handlers.GetColleges(db))

		auth := api.Group("/auth")
		{
			auth.POST("/reset-password", handlers.ResetPassword(db))
		}

		api.POST("/login", handlers.Login(db))
		api.POST("/register", handlers.Register(db))

		protected := api.Group("")
		protected.Use(middleware.JWT(db))
		protected.Use(middleware.RateLimit(60, time.Minute))
		{
			protected.GET("/me", handlers.GetMe(db))
			protected.POST("/token/refresh", handlers.RefreshToken(db))
			protected.GET("/activities", handlers.ListActivities(db))
			protected.GET("/activities/:id", handlers.GetActivity(db))
			protected.POST("/activities/:id/signup", handlers.Signup(db))
			protected.POST("/activities/:id/cancel", handlers.CancelSignup(db))
			protected.GET("/college/dashboard", handlers.CollegeDashboard(db))
			protected.GET("/school/dashboard", handlers.SchoolDashboard(db))
			protected.GET("/college/students", handlers.CollegeStudents(db))
			protected.GET("/notifications", handlers.GetNotifications(db))
			protected.GET("/my-signups", handlers.GetMySignups(db))
			protected.GET("/my-stats", handlers.GetMyStats(db))
		}
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "9501"
	}
	log.Printf("Go backend starting on :%s", port)
	log.Fatal(r.Run(":" + port))
}
