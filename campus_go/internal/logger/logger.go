// Package logger provides structured JSON logging with request ID correlation.
// Thin wrapper around log/slog — use instead of log.Printf for observable handlers.
package logger

import (
	"log/slog"
	"os"

	"github.com/gin-gonic/gin"
)

var defaultLogger = slog.New(slog.NewJSONHandler(os.Stderr, &slog.HandlerOptions{
	Level: slog.LevelInfo,
}))

// Info logs an info-level message with request_id from gin context if available.
func Info(c *gin.Context, msg string, args ...any) {
	if id := getRequestID(c); id != "" {
		args = append([]any{"request_id", id}, args...)
	}
	defaultLogger.Info(msg, args...)
}

// Warn logs a warning-level message.
func Warn(c *gin.Context, msg string, args ...any) {
	if id := getRequestID(c); id != "" {
		args = append([]any{"request_id", id}, args...)
	}
	defaultLogger.Warn(msg, args...)
}

// Error logs an error-level message.
func Error(c *gin.Context, msg string, args ...any) {
	if id := getRequestID(c); id != "" {
		args = append([]any{"request_id", id}, args...)
	}
	defaultLogger.Error(msg, args...)
}

func getRequestID(c *gin.Context) string {
	if c == nil {
		return ""
	}
	if id, exists := c.Get("request_id"); exists {
		if s, ok := id.(string); ok {
			return s
		}
	}
	return ""
}
