package handler

import (
	"context"
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
	Phone    string `json:"phone"`
	Ref      string `json:"ref"`
	Code     string `json:"code"`
}

func (h *AuthHandler) Register(w http.ResponseWriter, r *http.Request) {
	var req authReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Email == "" {
		writeJSON(w, 400, "Email diperlukan")
		return
	}
	if !isValidEmail(req.Email) {
		writeJSON(w, 400, "Format email tidak valid")
		return
	}
	if ok, msg := isValidPassword(req.Password); !ok {
		writeJSON(w, 400, msg)
		return
	}
	if !isValidPhone(req.Phone) {
		writeJSON(w, 400, "Nomor telepon diperlukan untuk reset password (628xxxxxxxxxx, +60xxxxxxxxx, +65xxxxxxxx)")
		return
	}
	if len(req.Email) > 100 || len(req.Password) > 100 {
		writeJSON(w, 400, "Email atau password terlalu panjang")
		return
	}
	pwHash, err := hashPassword(req.Password)
	if err != nil {
		slog.Error("bcrypt hash failed", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan. Silakan coba lagi.")
		return
	}

	// IP anti-abuse + user & subscription creation — single transaction.
	// Prefer X-Real-IP set by nginx, fallback to RemoteAddr.
	clientIP := r.Header.Get("X-Real-IP")
	if clientIP == "" {
		clientIP, _, _ = net.SplitHostPort(r.RemoteAddr)
		if clientIP == "" {
			clientIP = r.RemoteAddr
		}
	}

	tx, err := h.DB.BeginTx(r.Context(), nil)
	if err != nil {
		slog.Error("begin tx for register", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan. Silakan coba lagi.")
		return
	}
	defer func() { _ = tx.Rollback() }()

	// Insert ip_log FIRST — acquires write lock, serializes concurrent requests.
	// This prevents the TOCTOU race where concurrent requests all see count < 3.
	if _, err := tx.ExecContext(r.Context(),
		"INSERT INTO ip_log(ip, action) VALUES(?, 'register')", clientIP); err != nil {
		slog.Error("ip_log insert", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan. Silakan coba lagi.")
		return
	}

	var regCount int
	if err := tx.QueryRowContext(r.Context(),
		"SELECT COUNT(*) FROM ip_log WHERE ip=? AND created_at > datetime('now','-24 hours')",
		clientIP).Scan(&regCount); err != nil {
		slog.Error("ip_log count query", "error", err)
	}
	if regCount > 3 {
		writeJSON(w, 429, "Terlalu banyak pendaftaran dari jaringan Anda. Silakan coba lagi besok.")
		return
	}

	// Insert user inside transaction — no orphaned rows if IP limit exceeded.
	// Set token_version=1 so JWT matches; SQLite ALTER TABLE can't change column DEFAULT.
	var userID int64
	err = tx.QueryRowContext(r.Context(),
		"INSERT INTO users(email, password_hash, phone, token_version) VALUES(?,?,?,1) RETURNING id",
		req.Email, pwHash, req.Phone).Scan(&userID)
	if err != nil {
		if isUniqueErr(err) {
			writeJSON(w, 200, map[string]string{"message": "Jika email belum terdaftar, silakan cek email Anda untuk verifikasi."})
			return
		}
		slog.Error("register insert", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan")
		return
	}

	// Create subscription with 50K signup bonus.
	now := time.Now().UTC().Format(time.RFC3339)
	exp := time.Now().UTC().AddDate(100, 0, 0).Format(time.RFC3339)
	if _, err := tx.ExecContext(r.Context(),
		"INSERT INTO subscriptions(user_id, plan, started_at, expires_at, flash_balance, status) VALUES(?,?,?,?,50000,1)",
		userID, "gratis", now, exp); err != nil {
		slog.Error("create free sub with bonus", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan. Silakan coba lagi.")
		return
	}

	// Referral bonus: referrer gets 50K. Cap at 500K total flash balance to prevent abuse.
	if req.Ref != "" && req.Ref != req.Email {
		var refID int64
		err := tx.QueryRowContext(r.Context(),
			"SELECT id FROM users WHERE (id=? OR email=?) AND status=1", req.Ref, req.Ref).Scan(&refID)
		if err == nil {
			// Check referrer's current flash balance — cap bonus at 500K total.
			var currentBalance int64
			var refPackType string
			_ = tx.QueryRowContext(r.Context(),
				"SELECT COALESCE(flash_balance,0), COALESCE(pack_type,'flash') FROM subscriptions WHERE user_id=? AND status=1",
				refID).Scan(&currentBalance, &refPackType)
			// Creators get higher referral cap: 2,000,000 tokens
			referralCap := int64(500000)
			if refPackType == "ultimate" {
				referralCap = 5000000
			}
			if currentBalance < referralCap {
				if _, err := tx.ExecContext(r.Context(),
					"UPDATE subscriptions SET flash_balance=COALESCE(flash_balance,0)+50000, referral_count=COALESCE(referral_count,0)+1 WHERE user_id=? AND status=1",
					refID); err != nil {
					slog.Error("referral bonus update failed", "referrer", refID, "error", err)
				}
				slog.Info("referral bonus applied", "referrer", refID, "new_user", userID)
			} else {
				slog.Info("referral cap reached (500K)", "referrer", refID, "balance", currentBalance)
			}
		}
	}

	// Redeem code at registration — one-time use, applies flash + pro tokens.
	if req.Code != "" {
		var flashAmt, proAmt int64
		err := tx.QueryRowContext(r.Context(),
			"UPDATE redeem_codes SET used_by=?, used_at=datetime('now') WHERE code=? AND used_by=0 RETURNING flash_amount, pro_amount",
			userID, strings.ToUpper(strings.TrimSpace(req.Code))).Scan(&flashAmt, &proAmt)
		if err == nil {
			if _, err := tx.ExecContext(r.Context(),
				"UPDATE subscriptions SET flash_balance=flash_balance+?, pro_balance=pro_balance+? WHERE user_id=? AND status=1",
				flashAmt, proAmt, userID); err != nil {
				slog.Error("redeem bonus update failed", "user", userID, "error", err)
			} else {
				slog.Info("redeem code applied at registration", "user", userID, "code", req.Code, "flash", flashAmt, "pro", proAmt)
			}
		}
		// If code is invalid/used: silently ignore — don't block registration.
	}

	if err := tx.Commit(); err != nil {
		slog.Error("register commit", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan. Silakan coba lagi.")
		return
	}

	token, err := genJWT(userID, 1, h.JWTSecret)
	if err != nil {
		slog.Error("jwt generate", "error", err)
		writeJSON(w, 500, "Gagal membuat token. Silakan coba lagi.")
		return
	}
	// Set httpOnly cookie — XSS-proof, auto-sent by browser.
	http.SetCookie(w, &http.Cookie{
		Name:     "tl_token",
		Value:    token,
		HttpOnly: true,
		Secure:   true,
		SameSite: http.SameSiteStrictMode,
		MaxAge:   7 * 24 * 3600,
		Path:     "/",
	})
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
	if req.Email == "" {
		writeJSON(w, 400, "Email diperlukan")
		return
	}
	if len(req.Email) > 100 || len(req.Password) > 100 {
		writeJSON(w, 401, "Email atau password salah")
		return
	}

	clientIP := r.Header.Get("X-Real-IP")
	if clientIP == "" {
		clientIP, _, _ = net.SplitHostPort(r.RemoteAddr)
	}

	var userID int64
	var status int
	var pwHash string
	var tokenVersion int64
	err := h.DB.QueryRowContext(r.Context(),
		"SELECT id, status, password_hash, COALESCE(token_version,0) FROM users WHERE email=?",
		req.Email).Scan(&userID, &status, &pwHash, &tokenVersion)
	if err == sql.ErrNoRows {
		// Fake bcrypt to prevent timing leak — same cost as real verify.
		fakeHash, _ := bcrypt.GenerateFromPassword([]byte(req.Password), 12)
		_ = bcrypt.CompareHashAndPassword(fakeHash, []byte(req.Password))
		writeJSON(w, 401, "Email atau password salah")
		return
	}
	if err != nil {
		slog.Error("login query", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan")
		return
	}

	// Check account lockout — max 5 failed attempts in 15 minutes.
	if isAccountLocked(h.DB, userID) {
		writeJSON(w, 429, "Akun terkunci karena terlalu banyak percobaan login. Silakan coba lagi 15 menit.")
		return
	}

	if status != 1 {
		writeJSON(w, 403, "Akun dinonaktifkan")
		return
	}

	ok, rehash := verifyPassword(req.Password, pwHash)
	if !ok {
		recordLoginAttempt(h.DB, userID, clientIP, false)
		writeJSON(w, 401, "Email atau password salah")
		return
	}

	// Successful login — clear attempts.
	recordLoginAttempt(h.DB, userID, clientIP, true)

	if rehash != "" {
		if _, err := h.DB.ExecContext(r.Context(),
			"UPDATE users SET password_hash=? WHERE id=?", rehash, userID); err != nil {
			slog.Error("rehash update failed", "user", userID, "error", err)
		}
	}

	token, err := genJWT(userID, tokenVersion, h.JWTSecret)
	if err != nil {
		slog.Error("jwt generate", "error", err)
		writeJSON(w, 500, "Gagal membuat token. Silakan coba lagi.")
		return
	}
	http.SetCookie(w, &http.Cookie{
		Name:     "tl_token",
		Value:    token,
		HttpOnly: true,
		Secure:   true,
		SameSite: http.SameSiteStrictMode,
		MaxAge:   7 * 24 * 3600,
		Path:     "/",
	})
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
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, 400, "Format tidak valid")
		return
	}
	if ok, msg := isValidPassword(req.NewPassword); !ok {
		writeJSON(w, 400, msg)
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
	// Increment token_version to invalidate all existing tokens.
	if _, err := h.DB.ExecContext(r.Context(),
		"UPDATE users SET password_hash=?, token_version=COALESCE(token_version,0)+1 WHERE id=?",
		newHash, userID); err != nil {
		slog.Error("change password db update failed", "user", userID, "error", err)
		writeJSON(w, 500, "Gagal mengubah password")
		return
	}
	slog.Info("password changed, tokens revoked", "user", userID)
	writeJSON(w, 200, map[string]string{"message": "Password berhasil diubah. Silakan login kembali."})
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

// isValidPassword enforces minimum password strength:
// 8+ characters, at least 1 uppercase, 1 lowercase, 1 digit.
func isValidPassword(pw string) (bool, string) {
	if len(pw) < 8 {
		return false, "Password minimal 8 karakter"
	}
	if len(pw) > 100 {
		return false, "Password terlalu panjang"
	}
	hasUpper, hasLower, hasDigit := false, false, false
	for _, c := range pw {
		if c >= 'A' && c <= 'Z' {
			hasUpper = true
		}
		if c >= 'a' && c <= 'z' {
			hasLower = true
		}
		if c >= '0' && c <= '9' {
			hasDigit = true
		}
	}
	if !hasUpper {
		return false, "Password harus mengandung minimal 1 huruf besar (A-Z)"
	}
	if !hasLower {
		return false, "Password harus mengandung minimal 1 huruf kecil (a-z)"
	}
	if !hasDigit {
		return false, "Password harus mengandung minimal 1 angka (0-9)"
	}
	return true, ""
}

// isAccountLocked checks if user has ≥5 failed login attempts in the last 15 minutes.
func isAccountLocked(db *sql.DB, userID int64) bool {
	var count int
	err := db.QueryRowContext(context.Background(),
		"SELECT COUNT(*) FROM login_attempts WHERE user_id=? AND success=0 AND created_at > datetime('now','-15 minutes')",
		userID).Scan(&count)
	if err != nil {
		return false // DB error → don't lock out
	}
	return count >= 5
}

func recordLoginAttempt(db *sql.DB, userID int64, ip string, success bool) {
	successInt := 0
	if success {
		successInt = 1
	}
	if _, err := db.ExecContext(context.Background(),
		"INSERT INTO login_attempts(user_id, ip, success) VALUES(?,?,?)",
		userID, ip, successInt); err != nil {
		slog.Error("login_attempt insert failed", "user", userID, "error", err)
	}
}

func genJWT(userID int64, tokenVersion int64, secret string) (string, error) {
	claims := &middleware.Claims{
		UserID:       userID,
		TokenVersion: tokenVersion,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(time.Now().Add(7 * 24 * time.Hour)),
			IssuedAt:  jwt.NewNumericDate(time.Now()),
		},
	}
	return jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString([]byte(secret))
}

func userIDFrom(r *http.Request) (int64, bool) {
	return middleware.UserIDFromContext(r.Context())
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	// Normalize error messages: wrap plain strings in {"message": "..."} for consistent client parsing.
	if s, ok := data.(string); ok {
		_ = json.NewEncoder(w).Encode(map[string]string{"message": s})
		return
	}
	_ = json.NewEncoder(w).Encode(data)
}

func isUniqueErr(err error) bool {
	return err != nil && (strings.Contains(err.Error(), "UNIQUE") || strings.Contains(err.Error(), "unique"))
}

func isValidEmail(email string) bool {
	// Reject non-ASCII characters (emoji, CJK, etc.)
	for _, c := range email {
		if c > 127 {
			return false
		}
	}
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
	clearOTPFailures(r.Context(), h.DB, userID)

	otp := generateOTP()
	otpHash := hashOTP(otp)
	expires := time.Now().UTC().Add(5 * time.Minute).Format(time.RFC3339)
	if _, err := h.DB.ExecContext(r.Context(),
		"UPDATE users SET phone=?, otp_hash=?, otp_expires_at=? WHERE id=?",
		req.Phone, otpHash, expires, userID); err != nil {
		slog.Error("send otp db update failed", "user", userID, "error", err)
		writeJSON(w, 500, "Gagal menyimpan OTP. Silakan coba lagi.")
		return
	}
	go func() {
		if err := SendSMSOTP(req.Phone, otp); err != nil {
			slog.Error("sms otp failed", "phone", req.Phone, "error", err)
		}
	}()
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
	clearOTPFailures(r.Context(), h.DB, userID)
	otp := generateOTP()
	otpHash = hashOTP(otp)
	expires = time.Now().UTC().Add(5 * time.Minute)
	if _, err := h.DB.ExecContext(r.Context(),
		"UPDATE users SET otp_hash=?, otp_expires_at=? WHERE id=?",
		otpHash, expires.Format(time.RFC3339), userID); err != nil {
		slog.Error("voice otp db update failed", "user", userID, "error", err)
		writeJSON(w, 500, "Gagal menyimpan OTP. Silakan coba lagi.")
		return
	}

	setCooldown(phone + "_voice")

	go func() {
		if err := SendVoiceOTP(phone, otp); err != nil {
			slog.Error("voice otp failed", "phone", phone, "error", err)
		}
	}()
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

	// Check OTP brute-force limit via DB (survives restart).
	if ok := otpAttemptsExceeded(r.Context(), h.DB, userID); ok {
		if _, err := h.DB.ExecContext(r.Context(),
			"UPDATE users SET otp_hash='', otp_expires_at='' WHERE id=?", userID); err != nil {
			slog.Error("clear otp on lockout failed", "user", userID, "error", err)
		}
		clearOTPFailures(r.Context(), h.DB, userID)
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
		recordOTPFailure(r.Context(), h.DB, userID)
		writeJSON(w, 400, "Kode OTP salah")
		return
	}
	clearOTPFailures(r.Context(), h.DB, userID)
	if _, err := h.DB.ExecContext(r.Context(),
		"UPDATE users SET phone_verified=1, otp_hash='', otp_expires_at='' WHERE id=?", userID); err != nil {
		slog.Error("verify otp db update failed", "user", userID, "error", err)
		writeJSON(w, 500, "Gagal verifikasi OTP. Silakan coba lagi.")
		return
	}
	writeJSON(w, 200, map[string]string{"message": "Nomor telepon berhasil diverifikasi", "phone": phone})
}

func (h *AuthHandler) RequestPasswordReset(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Phone string `json:"phone"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Phone == "" {
		writeJSON(w, 400, "Nomor telepon diperlukan")
		return
	}

	if !isValidPhone(req.Phone) {
		writeJSON(w, 400, "Nomor telepon tidak valid")
		return
	}
	var userID int64
	var phoneVerified int
	err := h.DB.QueryRowContext(r.Context(),
		"SELECT id, phone_verified FROM users WHERE phone=? AND status=1", req.Phone).Scan(&userID, &phoneVerified)
	if err != nil {
		writeJSON(w, 200, map[string]string{"message": "Jika nomor terdaftar dan diverifikasi, kode OTP akan dikirim via SMS."})
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
	clearOTPFailures(r.Context(), h.DB, userID)
	otp := generateOTP()
	otpHash := hashOTP(otp)
	expires := time.Now().UTC().Add(5 * time.Minute).Format(time.RFC3339)
	if _, err := h.DB.ExecContext(r.Context(),
		"UPDATE users SET otp_hash=?, otp_expires_at=? WHERE id=?", otpHash, expires, userID); err != nil {
		slog.Error("request reset otp db update failed", "user", userID, "error", err)
		writeJSON(w, 500, "Gagal mengirim OTP. Silakan coba lagi.")
		return
	}
	setCooldown(req.Phone)
	go func() {
		if err := SendSMSOTP(req.Phone, otp); err != nil {
			slog.Error("sms otp failed", "phone", req.Phone, "error", err)
		}
	}()
	slog.Info("Password reset OTP via SMS", "user", userID, "phone", req.Phone)
	writeJSON(w, 200, map[string]string{"message": "Kode reset password telah dikirim via SMS ke nomor Anda"})
}

func (h *AuthHandler) ResetPassword(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Phone       string `json:"phone"`
		OTP         string `json:"otp"`
		NewPassword string `json:"new_password"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.NewPassword == "" {
		writeJSON(w, 400, "Password baru diperlukan")
		return
	}
	if ok, msg := isValidPassword(req.NewPassword); !ok {
		writeJSON(w, 400, msg)
		return
	}

	if req.Phone == "" || req.OTP == "" {
		writeJSON(w, 400, "Nomor telepon dan kode OTP diperlukan")
		return
	}
	var userID int64
	var otpHash, expiresStr string
	var phoneVerified int
	err := h.DB.QueryRowContext(r.Context(),
		"SELECT id, otp_hash, COALESCE(otp_expires_at,''), phone_verified FROM users WHERE phone=? AND status=1",
		req.Phone).Scan(&userID, &otpHash, &expiresStr, &phoneVerified)
	if err != nil {
		writeJSON(w, 404, "Nomor telepon tidak terdaftar")
		return
	}
	if phoneVerified == 0 {
		writeJSON(w, 400, "Nomor telepon belum diverifikasi. Tidak bisa reset password.")
		return
	}

	// OTP brute-force protection — same check as VerifyOTP, DB-persisted.
	if ok := otpAttemptsExceeded(r.Context(), h.DB, userID); ok {
		if _, err := h.DB.ExecContext(r.Context(),
			"UPDATE users SET otp_hash='', otp_expires_at='' WHERE id=?", userID); err != nil {
			slog.Error("clear otp on lockout failed", "user", userID, "error", err)
		}
		clearOTPFailures(r.Context(), h.DB, userID)
		writeJSON(w, 429, "Terlalu banyak percobaan OTP. Kirim ulang kode verifikasi.")
		return
	}

	expires, _ := time.Parse(time.RFC3339, expiresStr)
	if time.Now().UTC().After(expires) {
		writeJSON(w, 400, "Kode OTP kadaluarsa")
		return
	}
	if !verifyOTP(req.OTP, otpHash) {
		recordOTPFailure(r.Context(), h.DB, userID)
		writeJSON(w, 400, "Kode OTP salah")
		return
	}
	clearOTPFailures(r.Context(), h.DB, userID)
	newHash, err := hashPassword(req.NewPassword)
	if err != nil {
		slog.Error("bcrypt hash failed during password reset", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan. Silakan coba lagi.")
		return
	}
	// Increment token_version to invalidate all existing sessions.
	if _, err := h.DB.ExecContext(r.Context(),
		"UPDATE users SET password_hash=?, otp_hash='', otp_expires_at='', token_version=COALESCE(token_version,0)+1 WHERE id=?",
		newHash, userID); err != nil {
		slog.Error("reset password db update failed", "user", userID, "error", err)
		writeJSON(w, 500, "Gagal mereset password")
		return
	}
	slog.Info("password reset, tokens revoked", "user", userID)
	writeJSON(w, 200, map[string]string{"message": "Password berhasil direset. Silakan login kembali."})
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
	// Accept ID (+62), MY (+60), SG (+65)
	if !(strings.HasPrefix(phone, "62") || strings.HasPrefix(phone, "60") || strings.HasPrefix(phone, "65")) {
		return false
	}
	if len(phone) < 8 || len(phone) > 15 {
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
// Persisted in SQLite so it survives server restart and multi-instance deployments.

func otpAttemptsExceeded(ctx context.Context, db *sql.DB, userID int64) bool {
	var count int
	err := db.QueryRowContext(ctx,
		"SELECT COALESCE(otp_fail_count,0) FROM users WHERE id=?", userID).Scan(&count)
	if err != nil {
		return false // DB error → don't lock out
	}
	return count >= 5
}

func recordOTPFailure(ctx context.Context, db *sql.DB, userID int64) {
	if _, err := db.ExecContext(ctx,
		"UPDATE users SET otp_fail_count=COALESCE(otp_fail_count,0)+1 WHERE id=?",
		userID); err != nil {
		slog.Error("record otp failure failed", "user", userID, "error", err)
	}
}

func clearOTPFailures(ctx context.Context, db *sql.DB, userID int64) {
	if _, err := db.ExecContext(ctx,
		"UPDATE users SET otp_fail_count=0 WHERE id=?", userID); err != nil {
		slog.Error("clear otp failures failed", "user", userID, "error", err)
	}
}
