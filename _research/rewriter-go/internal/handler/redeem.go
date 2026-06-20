package handler

import (
	"crypto/rand"
	"database/sql"
	"encoding/json"
	"fmt"
	"log/slog"
	"math/big"
	"net/http"
	"strings"
	"time"
)

type RedeemHandler struct{ DB *sql.DB }

// Redeem handles code redemption: POST /api/redeem {"code": "XXXX"}
func (h *RedeemHandler) Redeem(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}

	var req struct {
		Code string `json:"code"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || strings.TrimSpace(req.Code) == "" {
		writeJSON(w, 400, "Kode diperlukan")
		return
	}
	code := strings.TrimSpace(strings.ToUpper(req.Code))

	tx, err := h.DB.BeginTx(r.Context(), nil)
	if err != nil {
		slog.Error("redeem begin tx", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan")
		return
	}
	defer func() { _ = tx.Rollback() }()

	var flashAmt, proAmt int64
	var usedBy int64
	err = tx.QueryRowContext(r.Context(),
		"SELECT flash_amount, pro_amount, COALESCE(used_by,0) FROM redeem_codes WHERE code=?",
		code).Scan(&flashAmt, &proAmt, &usedBy)
	if err == sql.ErrNoRows {
		writeJSON(w, 404, "Kode tidak ditemukan")
		return
	}
	if err != nil {
		slog.Error("redeem query code", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan")
		return
	}
	if usedBy != 0 {
		writeJSON(w, 400, "Kode sudah digunakan")
		return
	}

	if _, err := tx.ExecContext(r.Context(),
		"UPDATE redeem_codes SET used_by=?, used_at=? WHERE code=? AND used_by=0",
		userID, time.Now().UTC().Format(time.RFC3339), code); err != nil {
		slog.Error("redeem mark used", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan")
		return
	}

	if _, err := tx.ExecContext(r.Context(),
		"UPDATE subscriptions SET flash_balance=COALESCE(flash_balance,0)+?, pro_balance=COALESCE(pro_balance,0)+? WHERE user_id=? AND status=1",
		flashAmt, proAmt, userID); err != nil {
		slog.Error("redeem credit", "error", err)
		writeJSON(w, 500, "Gagal mengkredit token")
		return
	}

	if err := tx.Commit(); err != nil {
		slog.Error("redeem commit", "error", err)
		writeJSON(w, 500, "Terjadi kesalahan")
		return
	}

	slog.Info("code redeemed", "user", userID, "code", code, "flash", flashAmt, "pro", proAmt)
	writeJSON(w, 200, map[string]interface{}{
		"message":     "Kode berhasil ditukarkan!",
		"flash_added": flashAmt,
		"pro_added":   proAmt,
	})
}

// AdminGenCodes generates redeem codes: POST /api/admin/gen-codes
// Limited to 200 codes per day total to prevent unlimited token minting.
func (h *RedeemHandler) AdminGenCodes(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Prefix string `json:"prefix"`
		Flash  int64  `json:"flash"`
		Pro    int64  `json:"pro"`
		Count  int    `json:"count"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Count < 1 || req.Count > 50 {
		writeJSON(w, 400, "count harus 1-50")
		return
	}

	// Daily cap: prevent unlimited token minting if admin password is leaked
	var todayCount int
	if err := h.DB.QueryRowContext(r.Context(),
		"SELECT COUNT(*) FROM redeem_codes WHERE date(created_at)=date('now')").Scan(&todayCount); err == nil {
		if todayCount >= 200 {
			writeJSON(w, 429, "batas harian 200 kode tercapai, coba lagi besok")
			slog.Error("redeem: daily generation cap reached", "today", todayCount)
			return
		}
		if todayCount+req.Count > 200 {
			req.Count = 200 - todayCount
		}
	}

	if req.Prefix == "" {
		req.Prefix = "TOKEN"
	}

	var codes []string
	for i := 0; i < req.Count; i++ {
		code := fmt.Sprintf("%s-%s-%s", strings.ToUpper(req.Prefix),
			time.Now().Format("0102"),
			randCode(8))
		if _, err := h.DB.ExecContext(r.Context(),
			"INSERT INTO redeem_codes(code, flash_amount, pro_amount) VALUES(?,?,?)",
			code, req.Flash, req.Pro); err != nil {
			continue
		}
		codes = append(codes, code)
	}

	writeJSON(w, 200, map[string]interface{}{
		"codes":     codes,
		"flash":     req.Flash,
		"pro":       req.Pro,
		"prefix":    req.Prefix,
		"remaining": 200 - todayCount - len(codes),
	})
}

// randCode generates a random 8-char code using crypto/rand.
func randCode(n int) string {
	const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
	result := make([]byte, n)
	for i := range result {
		idx, _ := rand.Int(rand.Reader, big.NewInt(int64(len(chars))))
		result[i] = chars[idx.Int64()]
	}
	return string(result)
}
