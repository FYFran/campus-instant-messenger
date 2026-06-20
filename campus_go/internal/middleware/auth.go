package middleware

import (
	"fmt"
	"os"
	"strings"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

var jwtSecret = []byte(os.Getenv("JWT_SECRET"))

// ValidateConfig checks required environment variables.
// Call once at server startup — not at package init time.
func ValidateConfig() error {
	if len(jwtSecret) == 0 {
		return fmt.Errorf("JWT_SECRET env var is required — set it before starting the server")
	}
	return nil
}

func CORS() gin.HandlerFunc {
	return func(c *gin.Context) {
		origin := c.GetHeader("Origin")
		allowedOrigins := map[string]bool{
			"capacitor://localhost":  true,
			"http://localhost":       true,
			"http://139.196.50.134":  true,
			"https://139.196.50.134": true,
		}
		if allowedOrigins[origin] {
			c.Header("Access-Control-Allow-Origin", origin)
		}
		c.Header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type,Authorization")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	}
}

type Claims struct {
	UserID       int    `json:"user_id"`
	Role         string `json:"role"`
	TokenVersion int    `json:"ver"`
	jwt.RegisteredClaims
}

func GenerateToken(userID int, role string, tokenVersion int) (string, error) {
	claims := Claims{
		UserID:       userID,
		Role:         role,
		TokenVersion: tokenVersion,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(1 * time.Hour)),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
		},
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString(jwtSecret)
}

// ParseToken validates a JWT token string and returns the claims
func ParseToken(tokenStr string) (*Claims, error) {
	token, err := jwt.ParseWithClaims(tokenStr, &Claims{}, func(t *jwt.Token) (any, error) {
		if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
			return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
		}
		return jwtSecret, nil
	})
	if err != nil {
		return nil, err
	}
	claims, ok := token.Claims.(*Claims)
	if !ok || !token.Valid {
		return nil, fmt.Errorf("invalid token")
	}
	return claims, nil
}

func JWT(db *pgxpool.Pool) gin.HandlerFunc {
	return func(c *gin.Context) {
		auth := c.GetHeader("Authorization")
		if !strings.HasPrefix(auth, "Bearer ") {
			c.AbortWithStatusJSON(401, gin.H{"detail": "未登录"})
			return
		}
		token, err := jwt.ParseWithClaims(auth[7:], &Claims{}, func(t *jwt.Token) (any, error) {
			if _, ok := t.Method.(*jwt.SigningMethodHMAC); !ok {
				return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
			}
			return jwtSecret, nil
		})
		if err != nil || !token.Valid {
			c.AbortWithStatusJSON(401, gin.H{"detail": "Token过期，请重新登录"})
			return
		}
		claims, ok := token.Claims.(*Claims)
		if !ok {
			c.AbortWithStatusJSON(401, gin.H{"detail": "Token无效"})
			return
		}

		// Verify user is still active + single-device enforcement
		var isActive bool
		var dbTokenVersion int
		err = db.QueryRow(c.Request.Context(),
			"SELECT COALESCE(is_active,true), COALESCE(token_version,0) FROM users WHERE id=$1", claims.UserID,
		).Scan(&isActive, &dbTokenVersion)
		if err != nil || !isActive {
			c.AbortWithStatusJSON(401, gin.H{"detail": "账户已被禁用"})
			return
		}
		if claims.TokenVersion > 0 && dbTokenVersion != claims.TokenVersion {
			c.AbortWithStatusJSON(401, gin.H{"detail": "您的账号已在其他设备登录，请重新登录"})
			return
		}

		c.Set("user_id", claims.UserID)
		c.Set("role", claims.Role)
		c.Set("token_iat", claims.IssuedAt.Time)
		c.Next()
	}
}

// RateLimit returns a Gin middleware that limits requests per IP.
// Uses a sliding window: at most `requests` per `window` duration.
func RateLimit(requests int, window time.Duration) gin.HandlerFunc {
	var mu sync.Mutex
	type entry struct {
		count   int
		resetAt time.Time
	}
	counters := make(map[string]*entry)

	return func(c *gin.Context) {
		ip := c.ClientIP()
		mu.Lock()
		now := time.Now()
		e, exists := counters[ip]
		if !exists || now.After(e.resetAt) {
			counters[ip] = &entry{count: 1, resetAt: now.Add(window)}
			mu.Unlock()
			c.Next()
			return
		}
		e.count++
		if e.count > requests {
			mu.Unlock()
			c.AbortWithStatusJSON(429, gin.H{"detail": "请求过于频繁，请稍后重试"})
			return
		}
		mu.Unlock()
		c.Next()
	}
}
