package middleware

import (
	"context"
	"database/sql"
	"encoding/json"
	"log/slog"
	"net/http"
	"os"
	"strings"

	"github.com/golang-jwt/jwt/v5"
)

// ctxKey is an unexported type for context keys to prevent collisions across packages.
type ctxKey string

const userIDKey ctxKey = "user_id"

// UserIDFromContext extracts the authenticated user ID from the request context.
func UserIDFromContext(ctx context.Context) (int64, bool) {
	id, ok := ctx.Value(userIDKey).(int64)
	return id, ok
}

type Claims struct {
	UserID       int64 `json:"user_id"`
	TokenVersion int64 `json:"ver"`
	jwt.RegisteredClaims
}

// Auth returns middleware that validates JWT and checks token_version.
// Requires a *sql.DB in the request context or passed via closure.
func Auth(jwtSecret string, db *sql.DB) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// Check httpOnly cookie first (XSS-proof), fall back to Authorization header.
			tokenStr := ""
			if cookie, err := r.Cookie("tl_token"); err == nil {
				tokenStr = cookie.Value
			}
			if tokenStr == "" {
				tokenStr = strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
			}
			// Try current key first, then previous key for rotation.
			// Allows zero-downtime JWT secret rotation: set JWT_SECRET=new, JWT_SECRET_PREVIOUS=old.
			claims := &Claims{}
			prevSecret := os.Getenv("JWT_SECRET_PREVIOUS")
			token, err := jwt.ParseWithClaims(tokenStr, claims, func(t *jwt.Token) (interface{}, error) {
				return []byte(jwtSecret), nil
			}, jwt.WithValidMethods([]string{"HS256"}))
			if err != nil && prevSecret != "" {
				// Retry with previous secret — supports key rotation
				claims2 := &Claims{}
				token2, err2 := jwt.ParseWithClaims(tokenStr, claims2, func(t *jwt.Token) (interface{}, error) {
					return []byte(prevSecret), nil
				}, jwt.WithValidMethods([]string{"HS256"}))
				if err2 == nil && token2.Valid {
					token = token2
					claims = claims2
					err = nil
				}
			}
			if err != nil || !token.Valid {
				if err != nil {
					slog.Warn("jwt auth failed", "error", err, "remote", r.RemoteAddr)
				}
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(401)
				_ = json.NewEncoder(w).Encode(map[string]string{"message": "Silakan login terlebih dahulu"})
				return
			}

			// Verify token_version matches DB — allows forced logout / password-change revocation.
			// Always check: token_version starts at 1, password changes increment it.
			if db != nil {
				var dbVer int64
				err := db.QueryRowContext(r.Context(),
					"SELECT COALESCE(token_version,0) FROM users WHERE id=? AND status=1",
					claims.UserID).Scan(&dbVer)
				if err != nil || dbVer != claims.TokenVersion {
					w.Header().Set("Content-Type", "application/json")
					w.WriteHeader(401)
					_ = json.NewEncoder(w).Encode(map[string]string{"message": "Sesi telah berakhir. Silakan login kembali."})
					return
				}
			}

			ctx := context.WithValue(r.Context(), userIDKey, claims.UserID)
			TrackActiveUser(claims.UserID)
			next.ServeHTTP(w, r.WithContext(ctx))
		})
	}
}

// LocalhostOnly blocks requests not originating from 127.0.0.1 or ::1.
// Uses RemoteAddr only — never trusts X-Real-IP header for access control.
func LocalhostOnly(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ip := r.RemoteAddr
		// Strip port: IPv4 "127.0.0.1:12345" → "127.0.0.1", IPv6 "[::1]:12345" → "::1"
		if idx := strings.LastIndexByte(ip, ':'); idx > 0 {
			// IPv6 with brackets: "[::1]:port" — strip port + brackets
			if strings.HasPrefix(ip, "[") {
				ip = ip[1 : idx-1] // remove [ and ]:port
			} else if !strings.Contains(ip, "]") {
				// IPv4 with port: "127.0.0.1:port" — strip port only
				ip = ip[:idx]
			}
		}
		if ip != "127.0.0.1" && ip != "::1" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(403)
			_ = json.NewEncoder(w).Encode(map[string]string{"message": "Akses hanya dari localhost"})
			return
		}
		next.ServeHTTP(w, r)
	})
}
