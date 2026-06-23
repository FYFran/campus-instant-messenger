package middleware

import (
	"crypto/rand"
	"fmt"

	"github.com/gin-gonic/gin"
)

// RequestID generates a unique request ID for every HTTP request.
// Sets X-Request-ID header on the response and request_id in the Gin context.
// This enables log correlation across handler calls for a single request.
func RequestID() gin.HandlerFunc {
	return func(c *gin.Context) {
		id := generateID()
		c.Set("request_id", id)
		c.Header("X-Request-ID", id)
		c.Next()
	}
}

// GetRequestID retrieves the request ID from the Gin context.
// Returns empty string if middleware was not applied.
func GetRequestID(c *gin.Context) string {
	if id, exists := c.Get("request_id"); exists {
		if s, ok := id.(string); ok {
			return s
		}
	}
	return ""
}

func generateID() string {
	b := make([]byte, 8)
	if _, err := rand.Read(b); err != nil {
		return fmt.Sprintf("%x", b) // Fallback: zero bytes
	}
	return fmt.Sprintf("%x", b)
}
