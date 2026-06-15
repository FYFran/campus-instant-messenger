package middleware

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"strings"

	"github.com/golang-jwt/jwt/v5"
)

type Claims struct {
	UserID int64 `json:"user_id"`
	jwt.RegisteredClaims
}

func Auth(jwtSecret string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			tokenStr := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
			claims := &Claims{}
			token, err := jwt.ParseWithClaims(tokenStr, claims, func(t *jwt.Token) (interface{}, error) {
				return []byte(jwtSecret), nil
			}, jwt.WithValidMethods([]string{"HS256"}))
			if err != nil || !token.Valid {
				if err != nil {
					slog.Warn("jwt auth failed", "error", err, "remote", r.RemoteAddr)
				}
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(401)
				json.NewEncoder(w).Encode(map[string]string{"message": "Silakan login terlebih dahulu"})
				return
			}
			ctx := context.WithValue(r.Context(), "user_id", claims.UserID)
			TrackActiveUser(claims.UserID)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// LocalhostOnly blocks requests not originating from 127.0.0.1 or ::1.
// Used for admin endpoints that expose financial/operational data.
func LocalhostOnly(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ip := r.Header.Get("X-Real-IP")
		if ip == "" {
			ip = r.RemoteAddr
		}
		// Strip port from RemoteAddr if present
		if idx := strings.LastIndex(ip, ":"); idx > 0 && !strings.Contains(ip, "]") {
			ip = ip[:idx]
		}
		// Remove IPv6 brackets
		ip = strings.TrimPrefix(ip, "[")
		ip = strings.TrimSuffix(ip, "]")
		if ip != "127.0.0.1" && ip != "::1" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(403)
			json.NewEncoder(w).Encode(map[string]string{"message": "Akses hanya dari localhost"})
			return
		}
		next.ServeHTTP(w, r)
	})
}
