package handler

import (
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log/slog"
	"math/big"
	"net"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"golang.org/x/crypto/bcrypt"
	"tokenline/internal/middleware"
)

type AuthHandler struct {
	DB        *sql.DB
	JWTSecret string
}

type authReq struct {
	Email    string `json:"email"`
	Password string `json:"password"`
	Ref      string `json:"ref"`
}

func (h *AuthHandler) Register(w http.ResponseWriter, r *http.Request) {
	var req authReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Email == "" || len(req.Password) < 6 {
		writeJSON(w, 400, "Email dan password minimal 6 karakter diperlukan")
		return
	}
	if len(req.Email) > 100 || len(req.Password) > 100 {
		writeJSON(w, 400, "Email atau password terlalu panjang")
		return
	}
	if !isValidEmail(req.Email) {
		writeJSON(w, 400, "Format email tidak valid")
		return
	}
	pwHash, err := hashPassword(req.Password)
	if err != nil {
		slog.Error("bcrypt hash failed", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan. Silakan coba lagi.")
		return
	}

	var userID int64
	err = h.DB.QueryRowContext(r.Context(),
		"INSERT INTO users(email, password_hash) VALUES(?,?) RETURNING id",
		req.Email, pwHash).Scan(&userID)
	if err != nil {
		if isUniqueErr(err) {
			writeJSON(w, 200, map[string]string{"message": "Jika email belum terdaftar, silakan cek email Anda untuk verifikasi."})
			return
		}
		slog.Error("register insert", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan")
		return
	}
	// Create free subscription with 0 token balance
		// IP-based anti-abuse: max 3 registrations per IP per 24h.
		// Prefer X-Real-IP set by nginx, fallback to RemoteAddr.
		clientIP := r.Header.Get("X-Real-IP")
		if clientIP == "" {
			clientIP, _, _ = net.SplitHostPort(r.RemoteAddr)
		}
		var regCount int
		_ = h.DB.QueryRowContext(r.Context(),
			"SELECT COUNT(*) FROM ip_log WHERE ip=? AND created_at > datetime('now','-24 hours')",
			clientIP).Scan(&regCount)
		if regCount >= 3 {
			writeJSON(w, 429, "Terlalu banyak pendaftaran dari jaringan Anda. Silakan coba lagi besok.")
			return
		}

		// Log this registration
		h.DB.ExecContext(r.Context(),
			"INSERT INTO ip_log(ip, action) VALUES(?, 'register')", clientIP)

		now := time.Now().UTC().Format(time.RFC3339)
		exp := time.Now().UTC().AddDate(100, 0, 0).Format(time.RFC3339)
		if _, err := h.DB.ExecContext(r.Context(),
			"INSERT INTO subscriptions(user_id, plan, started_at, expires_at, flash_balance, status) VALUES(?,?,?,?,50000,1)",
			userID, "gratis", now, exp); err != nil {
			slog.Error("create free sub with bonus", "error", err)
		}

		// Referral bonus: referrer also gets 50K
		if req.Ref != "" && req.Ref != req.Email {
			var refID int64
			err := h.DB.QueryRowContext(r.Context(),
				"SELECT id FROM users WHERE email=? AND status=1", req.Ref).Scan(&refID)
			if err == nil {
				h.DB.ExecContext(r.Context(),
					"UPDATE subscriptions SET flash_balance=COALESCE(flash_balance,0)+50000 WHERE user_id=? AND status=1",
					refID)
				slog.Info("referral bonus applied", "referrer", refID, "new_user", userID)
			}
		}


	token, err := genJWT(userID, h.JWTSecret)
	if err != nil {
		slog.Error("jwt generate", "error", err)
		writeJSON(w, 500, "Gagal membuat token. Silakan coba lagi.")
		return
	}
	writeJSON(w, 200, map[string]interface{}{
		"token": token,
		"user":  map[string]interface{}{"id": userID, "email": req.Email, "plan": "gratis"},
	})
}

func (h *AuthHandler) Login(w http.ResponseWriter, r *http.Request) {
	var req authReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, 400, "Format tidak valid")
		return
	}
	if len(req.Email) > 100 || len(req.Password) > 100 {
		writeJSON(w, 401, "Email atau password salah")
		return
	}
	var userID int64
	var status int
	var pwHash string
	err := h.DB.QueryRowContext(r.Context(),
		"SELECT id, status, password_hash FROM users WHERE email=?", req.Email).Scan(&userID, &status, &pwHash)
	if err == sql.ErrNoRows {
		writeJSON(w, 401, "Email atau password salah")
		return
	}
	if err != nil {
		slog.Error("login query", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan")
		return
	}
	if status != 1 {
		writeJSON(w, 403, "Akun dinonaktifkan")
		return
	}
	ok, rehash := verifyPassword(req.Password, pwHash)
	if !ok {
		writeJSON(w, 401, "Email atau password salah")
		return
	}
	if rehash != "" {
		h.DB.ExecContext(r.Context(), "UPDATE users SET password_hash=? WHERE id=?", rehash, userID)
	}
	token, err := genJWT(userID, h.JWTSecret)
	if err != nil {
		slog.Error("jwt generate", "error", err)
		writeJSON(w, 500, "Gagal membuat token. Silakan coba lagi.")
		return
	}
	writeJSON(w, 200, map[string]interface{}{"token": token, "user": map[string]interface{}{"id": userID, "email": req.Email}})
}

func (h *AuthHandler) ChangePassword(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}
	var req struct {
		OldPassword string `json:"old_password"`
		NewPassword string `json:"new_password"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || len(req.NewPassword) < 6 {
		writeJSON(w, 400, "Password baru minimal 6 karakter")
		return
	}
	var dbHash string
	err := h.DB.QueryRowContext(r.Context(), "SELECT password_hash FROM users WHERE id=?", userID).Scan(&dbHash)
	if err != nil {
		writeJSON(w, 400, "User tidak ditemukan")
		return
	}
	valid, _ := verifyPassword(req.OldPassword, dbHash)
	if !valid {
		writeJSON(w, 400, "Password lama salah")
		return
	}
	newHash, err := hashPassword(req.NewPassword)
	if err != nil {
		slog.Error("bcrypt hash failed during password change", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan. Silakan coba lagi.")
		return
	}
	if _, err := h.DB.ExecContext(r.Context(), "UPDATE users SET password_hash=? WHERE id=?", newHash, userID); err != nil {
		slog.Error("change password db update failed", "user", userID, "error", err)
		writeJSON(w, 500, "Gagal mengubah password")
		return
	}
	writeJSON(w, 200, map[string]string{"message": "Password berhasil diubah"})
}

// hashPassword returns a bcrypt hash of pw. Returns error on failure instead
// of silently falling back to a weaker algorithm.
func hashPassword(pw string) (string, error) {
	h, err := bcrypt.GenerateFromPassword([]byte(pw), 12)
	if err != nil {
		return "", err
	}
	return string(h), nil
}

func verifyPassword(pw, stored string) (ok bool, rehash string) {
	// Legacy SHA-256 hash detection — existing passwords stored before the fix.
	// These users' passwords are verified and automatically upgraded to bcrypt on next login.
	if len(stored) == 64 && !strings.Contains(stored, "$") {
		sum := sha256.Sum256([]byte(pw))
		if subtle.ConstantTimeCompare([]byte(hex.EncodeToString(sum[:])), []byte(stored)) == 1 {
			newHash, err := hashPassword(pw)
			if err != nil {
				return true, "" // password correct but can't upgrade — let them in
			}
			return true, newHash
		}
		return false, ""
	}
	err := bcrypt.CompareHashAndPassword([]byte(stored), []byte(pw))
	return err == nil, ""
}

func genJWT(userID int64, secret string) (string, error) {
	claims := &middleware.Claims{
		UserID: userID,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(7 * 24 * time.Hour)),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
		},
	}
	return jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString([]byte(secret))
}

func userIDFrom(r *http.Request) (int64, bool) {
	id, ok := r.Context().Value("user_id").(int64)
	return id, ok
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func isUniqueErr(err error) bool {
	return err != nil && (strings.Contains(err.Error(), "UNIQUE") || strings.Contains(err.Error(), "unique"))
}

func isValidEmail(email string) bool {
	if len(email) < 3 || len(email) > 100 {
		return false
	}
	at := strings.LastIndex(email, "@")
	if at <= 0 || at >= len(email)-1 {
		return false
	}
	dot := strings.LastIndex(email, ".")
	if dot <= at+1 || dot >= len(email)-1 {
		return false
	}
	return true
}

// Phone OTP

func (h *AuthHandler) SendOTP(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}
	var req struct {
		Phone string `json:"phone"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || !isValidPhone(req.Phone) {
		writeJSON(w, 400, "Nomor telepon tidak valid. Format: 628xxxxxxxxxx")
		return
	}

	// Rate limit: 60s cooldown per phone number
	if checkCooldown(req.Phone, 60) {
		writeJSON(w, 429, "Tunggu 60 detik sebelum mengirim ulang kode verifikasi")
		return
	}

	// Clear previous OTP failure counter when sending new OTP
	clearOTPFailures(userID)

	otp := generateOTP()
	otpHash := hashOTP(otp)
	expires := time.Now().UTC().Add(5 * time.Minute).Format(time.RFC3339)
	h.DB.ExecContext(r.Context(),
		"UPDATE users SET phone=?, otp_hash=?, otp_expires_at=? WHERE id=?",
		req.Phone, otpHash, expires, userID)
	go func() { if err := SendSMSOTP(req.Phone, otp); err != nil { slog.Error("sms otp failed", "phone", req.Phone, "error", err) } }()
	setCooldown(req.Phone)
	slog.Info("OTP sent via SMS", "user", userID, "phone", req.Phone)
	writeJSON(w, 200, map[string]string{"message": "Kode verifikasi telah dikirim via SMS ke nomor Anda"})
}

// SendOTPVoice resends the OTP via voice call — fallback when SMS doesn't arrive.
func (h *AuthHandler) SendOTPVoice(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}

	// Check existing OTP: only allow voice if SMS was sent but not verified
	var phone, otpHash, expiresStr string
	err := h.DB.QueryRowContext(r.Context(),
		"SELECT COALESCE(phone,''), otp_hash, COALESCE(otp_expires_at,'') FROM users WHERE id=?",
		userID).Scan(&phone, &otpHash, &expiresStr)
	if err != nil || phone == "" || otpHash == "" {
		writeJSON(w, 400, "Kirim OTP via SMS terlebih dahulu sebelum menggunakan panggilan suara")
		return
	}
	expires, _ := time.Parse(time.RFC3339, expiresStr)
	if time.Now().UTC().After(expires) {
		writeJSON(w, 400, "OTP sudah kadaluarsa. Kirim ulang via SMS.")
		return
	}

	// Voice cooldown: 90s (voice calls cost more) — check BEFORE generating OTP
	if checkCooldown(phone+"_voice", 90) {
		writeJSON(w, 429, "Tunggu 90 detik sebelum panggilan suara ulang")
		return
	}

	// Regenerate OTP for voice clarity
	clearOTPFailures(userID)
	otp := generateOTP()
	otpHash = hashOTP(otp)
	expires = time.Now().UTC().Add(5 * time.Minute)
	h.DB.ExecContext(r.Context(),
		"UPDATE users SET otp_hash=?, otp_expires_at=? WHERE id=?",
		otpHash, expires.Format(time.RFC3339), userID)

	setCooldown(phone + "_voice")

	go func() { if err := SendVoiceOTP(phone, otp); err != nil { slog.Error("voice otp failed", "phone", phone, "error", err) } }()
	slog.Info("OTP sent via voice call", "user", userID, "phone", phone)
	writeJSON(w, 200, map[string]string{"message": "Kode verifikasi akan dikirim melalui panggilan suara ke nomor Anda"})
}

func (h *AuthHandler) VerifyOTP(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}
	var req struct {
		OTP string `json:"otp"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.OTP == "" {
		writeJSON(w, 400, "Kode OTP diperlukan")
		return
	}

	// Brute-force: max 5 failed OTP attempts, then OTP is invalidated
	if otpAttemptsExceeded(userID) {
		h.DB.ExecContext(r.Context(),
			"UPDATE users SET otp_hash='', otp_expires_at='' WHERE id=?", userID)
		clearOTPFailures(userID)
		writeJSON(w, 429, "Terlalu banyak percobaan OTP. Kirim ulang kode verifikasi.")
		return
	}

	var phone, otpHash, expiresStr string
	err := h.DB.QueryRowContext(r.Context(),
		"SELECT COALESCE(phone,''), otp_hash, COALESCE(otp_expires_at,'') FROM users WHERE id=?",
		userID).Scan(&phone, &otpHash, &expiresStr)
	if err != nil || phone == "" || otpHash == "" {
		writeJSON(w, 400, "Belum ada nomor telepon atau OTP. Kirim OTP terlebih dahulu.")
		return
	}
	expires, _ := time.Parse(time.RFC3339, expiresStr)
	if time.Now().UTC().After(expires) {
		writeJSON(w, 400, "Kode OTP sudah kadaluarsa. Kirim ulang.")
		return
	}
	if !verifyOTP(req.OTP, otpHash) {
		recordOTPFailure(userID)
		writeJSON(w, 400, "Kode OTP salah")
		return
	}
	clearOTPFailures(userID)
	h.DB.ExecContext(r.Context(),
		"UPDATE users SET phone_verified=1, otp_hash='', otp_expires_at='' WHERE id=?", userID)
	writeJSON(w, 200, map[string]string{"message": "Nomor telepon berhasil diverifikasi", "phone": phone})
}

func (h *AuthHandler) RequestPasswordReset(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Phone string `json:"phone"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || !isValidPhone(req.Phone) {
		writeJSON(w, 400, "Nomor telepon tidak valid")
		return
	}
	var userID int64
	var phoneVerified int
	err := h.DB.QueryRowContext(r.Context(),
		"SELECT id, phone_verified FROM users WHERE phone=? AND status=1", req.Phone).Scan(&userID, &phoneVerified)
	if err != nil {
		writeJSON(w, 404, "Nomor telepon tidak terdaftar")
		return
	}
	if phoneVerified == 0 {
		writeJSON(w, 400, "Nomor telepon belum diverifikasi. Tidak bisa reset password.")
		return
	}
	if checkCooldown(req.Phone, 60) {
		writeJSON(w, 429, "Tunggu 60 detik sebelum mengirim ulang kode verifikasi")
		return
	}
	clearOTPFailures(userID)
	otp := generateOTP()
	otpHash := hashOTP(otp)
	expires := time.Now().UTC().Add(5 * time.Minute).Format(time.RFC3339)
	h.DB.ExecContext(r.Context(),
		"UPDATE users SET otp_hash=?, otp_expires_at=? WHERE id=?", otpHash, expires, userID)
	setCooldown(req.Phone)
	go func() { if err := SendSMSOTP(req.Phone, otp); err != nil { slog.Error("sms otp failed", "phone", req.Phone, "error", err) } }()
	slog.Info("Password reset OTP via SMS", "user", userID, "phone", req.Phone)
	writeJSON(w, 200, map[string]string{"message": "Kode reset password telah dikirim via SMS ke nomor Anda"})
}

func (h *AuthHandler) ResetPassword(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Phone       string `json:"phone"`
		OTP         string `json:"otp"`
		NewPassword string `json:"new_password"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Phone == "" || req.OTP == "" || len(req.NewPassword) < 6 {
		writeJSON(w, 400, "Semua field diperlukan. Password minimal 6 karakter.")
		return
	}
	var userID int64
	var otpHash, expiresStr string
	var phoneVerified int
	err := h.DB.QueryRowContext(r.Context(),
		"SELECT id, otp_hash, COALESCE(otp_expires_at,''), phone_verified FROM users WHERE phone=? AND status=1", req.Phone).Scan(&userID, &otpHash, &expiresStr, &phoneVerified)
	if err != nil {
		writeJSON(w, 404, "Nomor telepon tidak terdaftar")
		return
	}
	if phoneVerified == 0 {
		writeJSON(w, 400, "Nomor telepon belum diverifikasi. Tidak bisa reset password.")
		return
	}
	expires, _ := time.Parse(time.RFC3339, expiresStr)
	if time.Now().UTC().After(expires) {
		writeJSON(w, 400, "Kode OTP kadaluarsa")
		return
	}
	if !verifyOTP(req.OTP, otpHash) {
		writeJSON(w, 400, "Kode OTP salah")
		return
	}
	newHash, err := hashPassword(req.NewPassword)
	if err != nil {
		slog.Error("bcrypt hash failed during password reset", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan. Silakan coba lagi.")
		return
	}
	h.DB.ExecContext(r.Context(),
		"UPDATE users SET password_hash=?, otp_hash='', otp_expires_at='' WHERE id=?", newHash, userID)
	writeJSON(w, 200, map[string]string{"message": "Password berhasil direset. Silakan login."})
}

// generateOTP returns a 6-digit OTP using crypto/rand.
// Go 1.24+ guarantees rand.Int with rand.Reader never returns an error —
// the runtime panics irrecoverably if the OS entropy source fails.
func generateOTP() string {
	n, _ := rand.Int(rand.Reader, big.NewInt(1000000))
	return fmt.Sprintf("%06d", n.Int64())
}

func hashOTP(otp string) string {
	h := sha256.Sum256([]byte(otp))
	return hex.EncodeToString(h[:])
}

func verifyOTP(otp, hash string) bool {
	return subtle.ConstantTimeCompare([]byte(hashOTP(otp)), []byte(hash)) == 1
}

func isValidPhone(phone string) bool {
	phone = strings.TrimPrefix(phone, "+")
	if !strings.HasPrefix(phone, "62") || len(phone) < 10 || len(phone) > 15 {
		return false
	}
	for _, c := range phone {
		if c < '0' || c > '9' {
			return false
		}
	}
	return true
}

// OTP brute-force protection: max 5 failed attempts per OTP session.
var (
	otpFailures   = map[int64]int{}
	otpFailuresMu sync.Mutex
)

func otpAttemptsExceeded(userID int64) bool {
	otpFailuresMu.Lock()
	defer otpFailuresMu.Unlock()
	return otpFailures[userID] >= 5
}

func recordOTPFailure(userID int64) {
	otpFailuresMu.Lock()
	otpFailures[userID]++
	otpFailuresMu.Unlock()
}

func clearOTPFailures(userID int64) {
	otpFailuresMu.Lock()
	delete(otpFailures, userID)
	otpFailuresMu.Unlock()
}
