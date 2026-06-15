package handler

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"time"
)

type PayHandler struct{ DB *sql.DB }

// TokenLine v3.0 — dual-currency: Flash tokens + Pro tokens.
// Three tiers: Flash (pure Flash), Ultimate (Flash+Pro combo), Pro (pure Pro).

type tokenPack struct {
	Name     string
	Amount   int64  // price IDR
	FlashAmt int64  // Flash tokens (0 for pure Pro packs)
	ProAmt   int64  // Pro tokens (0 for pure Flash packs)
	Model    string // model for display
	PackType string // "flash" | "ultimate" | "pro"
}

var flashPacks = map[string]tokenPack{
	"flash_500k": {"TokenLine Flash 500K", 19900, 500000, 0, "deepseek-v4-flash", "flash"},
	"flash_1m5":  {"TokenLine Flash 1.5M", 49900, 1500000, 0, "deepseek-v4-flash", "flash"},
	"flash_4m":   {"TokenLine Flash 4M", 99900, 4000000, 0, "deepseek-v4-flash", "flash"},
}

var ultimatePacks = map[string]tokenPack{
	"ultimate_3m":  {"满血 3M", 189900, 2400000, 600000, "dual", "ultimate"},
	"ultimate_8m":  {"满血 8M", 449900, 6400000, 1600000, "dual", "ultimate"},
	"ultimate_20m": {"满血 20M", 999900, 16000000, 4000000, "dual", "ultimate"},
}

var proPacks = map[string]tokenPack{
	"pro_500k": {"TokenLine Pro 500K", 399000, 0, 500000, "deepseek-v4-pro", "pro"},
	"pro_2m":   {"TokenLine Pro 2M", 1499000, 0, 2000000, "deepseek-v4-pro", "pro"},
	"pro_5m":   {"TokenLine Pro 5M", 3499000, 0, 5000000, "deepseek-v4-pro", "pro"},
}

var modelWeight = map[string]int64{
	"deepseek-v4-flash": 1,
	"deepseek-v4-pro":   5,
}

var dodoAPIKey string
var dodoProductID string
var dodoBaseURL string
var dodoWebhookSecret string

func DodoAvailable() bool     { return dodoAPIKey != "" && dodoProductID != "" }
func MidtransAvailable() bool { return midtransServerKey != "" }

func InitDodo() {
	dodoAPIKey = os.Getenv("DODO_API_KEY")
	dodoProductID = os.Getenv("DODO_PRODUCT_ID")
	dodoBaseURL = os.Getenv("DODO_BASE_URL")
	dodoWebhookSecret = os.Getenv("DODO_WEBHOOK_SECRET")
	if dodoBaseURL == "" {
		dodoBaseURL = "https://test.dodopayments.com"
	}
	if dodoAPIKey == "" {
		slog.Warn("DODO_API_KEY not set - payments in mock mode")
	}
	if dodoWebhookSecret == "" && dodoAPIKey != "" {
		panic("DODO_WEBHOOK_SECRET required when DODO_API_KEY is set")
	}
}

// lookupPack finds a pack across all three tiers.
func lookupPack(packID string) (tokenPack, bool) {
	if pk, ok := flashPacks[packID]; ok {
		return pk, true
	}
	if pk, ok := ultimatePacks[packID]; ok {
		return pk, true
	}
	if pk, ok := proPacks[packID]; ok {
		return pk, true
	}
	return tokenPack{}, false
}

type payReq struct {
	Pack string `json:"pack"` // "flash_1m5" | "ultimate_3m" | "pro_500k"
}

func (h *PayHandler) Create(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}
	var req payReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, 400, "Format tidak valid")
		return
	}

	pk, ok := lookupPack(req.Pack)
	if !ok {
		writeJSON(w, 400, "Paket tidak tersedia")
		return
	}

	extID := fmt.Sprintf("tl-%d-%d", userID, time.Now().UnixMilli())
	_, err := h.DB.ExecContext(r.Context(),
		"INSERT INTO payments(user_id, xendit_invoice_id, plan, amount, pack_type) VALUES(?,?,?,?,?)",
		userID, extID, req.Pack, pk.Amount, pk.PackType)
	if err != nil {
		slog.Error("create payment", "error", err)
		writeJSON(w, 500, "Gagal membuat invoice")
		return
	}

	// Prefer Midtrans if available (Indonesian market)
	midFirst := os.Getenv("MIDTRANS_FIRST") != "false" || os.Getenv("MIDTRANS_SERVER_KEY") != ""

	if midFirst && midtransServerKey != "" {
		var userEmail string
		h.DB.QueryRowContext(r.Context(), "SELECT email FROM users WHERE id=?", userID).Scan(&userEmail)

		userName := userEmail
		for i := 0; i < len(userEmail); i++ {
			if userEmail[i] == '@' {
				userName = userEmail[:i]
				break
			}
		}

		snapToken, err := CreateMidtransSnapToken(extID, pk.Name, pk.Amount, userEmail, userName, nil)
		if err == nil && snapToken != "" {
			writeJSON(w, 200, map[string]interface{}{
				"invoice_id":     extID,
				"snap_token":     snapToken,
				"payment_method": "midtrans",
				"client_key":     MidtransClientKey(),
				"is_production":  MidtransIsProduction(),
				"amount":         pk.Amount,
				"pack":           req.Pack,
				"flash_tokens":   pk.FlashAmt,
				"pro_tokens":     pk.ProAmt,
				"pack_type":      pk.PackType,
				"status":         "pending",
			})
			return
		}
		slog.Error("midtrans snap token failed", "error", err)
	}

	if dodoAPIKey != "" && dodoProductID != "" {
		checkoutURL, err := createDodoCheckout(extID, pk.Name, pk.Amount, userID)
		if err == nil && checkoutURL != "" {
			writeJSON(w, 200, map[string]interface{}{
				"invoice_id":   extID,
				"invoice_url":  checkoutURL,
				"amount":       pk.Amount,
				"pack":         req.Pack,
				"flash_tokens": pk.FlashAmt,
				"pro_tokens":   pk.ProAmt,
				"pack_type":    pk.PackType,
				"status":       "pending",
			})
			return
		}
		slog.Error("dodo checkout failed", "error", err)
	}

	writeJSON(w, 200, map[string]interface{}{
		"invoice_id":   extID,
		"invoice_url":  fmt.Sprintf("https://tokenline.top/topup.html?pay=%s", extID),
		"amount":       pk.Amount,
		"pack":         req.Pack,
		"flash_tokens": pk.FlashAmt,
		"pro_tokens":   pk.ProAmt,
		"pack_type":    pk.PackType,
		"status":       "pending",
		"note":         "Dodo Payments akan segera aktif",
	})
}

func (h *PayHandler) ListPacks(w http.ResponseWriter, r *http.Request) {
	buildList := func(packs map[string]tokenPack, order []string) []map[string]interface{} {
		result := make([]map[string]interface{}, 0, len(order))
		for _, key := range order {
			pk := packs[key]
			result = append(result, map[string]interface{}{
				"id":           key,
				"name":         pk.Name,
				"amount":       pk.Amount,
				"flash_tokens": pk.FlashAmt,
				"pro_tokens":   pk.ProAmt,
				"model":        pk.Model,
				"pack_type":    pk.PackType,
			})
		}
		return result
	}

	writeJSON(w, 200, map[string]interface{}{
		"flash":    buildList(flashPacks, []string{"flash_500k", "flash_1m5", "flash_4m"}),
		"ultimate": buildList(ultimatePacks, []string{"ultimate_3m", "ultimate_8m", "ultimate_20m"}),
		"pro":      buildList(proPacks, []string{"pro_500k", "pro_2m", "pro_5m"}),
	})
}

func createDodoCheckout(extID, name string, amount int64, userID int64) (string, error) {
	payload := map[string]interface{}{
		"product_cart": []map[string]interface{}{{
			"product_id": dodoProductID,
			"quantity":   1,
		}},
		"metadata": map[string]interface{}{
			"invoice_id": extID,
			"user_id":    userID,
		},
		"customer_note": name,
		"return_url":    "https://tokenline.top/success.html?plan=" + extID,
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return "", err
	}
	req, err := http.NewRequest("POST", dodoBaseURL+"/v1/checkout_sessions", bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	req.Header.Set("Authorization", "Bearer "+dodoAPIKey)
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("dodo request: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("dodo read: %w", err)
	}
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("dodo error %d: %s", resp.StatusCode, string(respBody))
	}

	var result struct {
		CheckoutURL string `json:"checkout_url"`
		SessionID   string `json:"session_id"`
	}
	if err := json.Unmarshal(respBody, &result); err != nil {
		return "", fmt.Errorf("dodo parse: %w", err)
	}
	return result.CheckoutURL, nil
}

func (h *PayHandler) Callback(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(r.Body)
	if err != nil {
		writeJSON(w, 400, "Failed to read body")
		return
	}

	if dodoWebhookSecret != "" {
		sig := r.Header.Get("Dodo-Signature")
		if sig == "" {
			slog.Warn("webhook rejected: missing signature")
			writeJSON(w, 401, "Missing signature")
			return
		}
		mac := hmac.New(sha256.New, []byte(dodoWebhookSecret))
		mac.Write(body)
		expected := hex.EncodeToString(mac.Sum(nil))
		if !hmac.Equal([]byte(sig), []byte(expected)) {
			slog.Warn("webhook rejected: invalid signature")
			writeJSON(w, 401, "Invalid signature")
			return
		}
	}

	var cb struct {
		EventType string `json:"event_type"`
		Data      struct {
			Metadata struct {
				InvoiceID string `json:"invoice_id"`
			} `json:"metadata"`
			Status string `json:"status"`
		} `json:"data"`
	}

	if err := json.Unmarshal(body, &cb); err != nil {
		writeJSON(w, 400, "Invalid callback")
		return
	}

	if cb.EventType != "payment.succeeded" {
		writeJSON(w, 200, map[string]string{"status": "ignored"})
		return
	}

	invoiceID := cb.Data.Metadata.InvoiceID
	if invoiceID == "" {
		writeJSON(w, 400, "Missing invoice_id")
		return
	}

	// Atomic CAS: prevent double-credit
	res, err := h.DB.ExecContext(r.Context(),
		"UPDATE payments SET status='paid', paid_at=datetime('now') WHERE xendit_invoice_id=? AND status='pending'",
		invoiceID)
	if err != nil {
		slog.Error("callback update failed", "invoice_id", invoiceID, "error", err)
		writeJSON(w, 500, "Gagal memproses pembayaran")
		return
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		var currentStatus string
		h.DB.QueryRowContext(r.Context(),
			"SELECT status FROM payments WHERE xendit_invoice_id=?", invoiceID).Scan(&currentStatus)
		if currentStatus == "paid" {
			slog.Info("callback duplicate ignored", "invoice_id", invoiceID)
			writeJSON(w, 200, map[string]string{"status": "already_paid"})
			return
		}
		slog.Error("callback invoice not pending", "invoice_id", invoiceID)
		writeJSON(w, 404, "Invoice not found or already processed")
		return
	}

	var userID int64
	var plan, packType string
	err = h.DB.QueryRowContext(r.Context(),
		"SELECT user_id, plan, COALESCE(pack_type,'flash') FROM payments WHERE xendit_invoice_id=?",
		invoiceID).Scan(&userID, &plan, &packType)
	if err != nil {
		slog.Error("callback invoice read after update", "invoice_id", invoiceID, "error", err)
		writeJSON(w, 500, "Gagal membaca invoice")
		return
	}

	pk, ok := lookupPack(plan)
	if !ok {
		slog.Error("callback unknown plan", "plan", plan)
		writeJSON(w, 400, "Unknown plan")
		return
	}

	creditTokens(h.DB, userID, pk)
	slog.Info("token pack activated via Dodo", "user", userID, "plan", plan, "pack_type", packType,
		"flash", pk.FlashAmt, "pro", pk.ProAmt)
	writeJSON(w, 200, map[string]interface{}{
		"status":       "activated",
		"flash_tokens": pk.FlashAmt,
		"pro_tokens":   pk.ProAmt,
	})
}

// creditTokens credits flash and/or pro tokens to the user's active subscription.
// Wraps in a transaction to prevent double-credit from concurrent callbacks.
// Shared by Dodo callback, Midtrans callback, and any future payment processor.
func creditTokens(db *sql.DB, userID int64, pk tokenPack) {
	tx, err := db.Begin()
	if err != nil {
		slog.Error("creditTokens begin tx", "user", userID, "error", err)
		return
	}
	defer tx.Rollback() // no-op if Commit succeeds

	// Atomic SELECT-then-INSERT-or-UPDATE within transaction
	var subID int64
	var existingFlash, existingPro int64
	err = tx.QueryRow(
		"SELECT id, COALESCE(flash_balance,0), COALESCE(pro_balance,0) FROM subscriptions WHERE user_id=? AND status=1 ORDER BY id DESC LIMIT 1",
		userID).Scan(&subID, &existingFlash, &existingPro)
	if err != nil {
		// No subscription yet — create one. pack_type defaults to 'flash' (DB default).
		_, err = tx.Exec(
			"INSERT INTO subscriptions(user_id, plan, started_at, expires_at, flash_balance, pro_balance, status) VALUES(?,?,?,?,?,?,1)",
			userID, "v3", time.Now().UTC().Format(time.RFC3339), "2099-12-31T23:59:59Z", pk.FlashAmt, pk.ProAmt)
		if err != nil {
			slog.Error("creditTokens insert", "user", userID, "error", err)
			return
		}
	} else {
		// Existing subscription — add both Flash and Pro. pack_type upgraded separately below.
		_, err = tx.Exec("UPDATE subscriptions SET flash_balance=flash_balance+?, pro_balance=pro_balance+? WHERE id=?",
			pk.FlashAmt, pk.ProAmt, subID)
		if err != nil {
			slog.Error("creditTokens update", "user", userID, "sub", subID, "error", err)
			return
		}
	}

	// Upgrade pack_type — never downgrade. ultimate > pro > flash.
	if pk.PackType == "ultimate" {
		tx.Exec("UPDATE subscriptions SET pack_type='ultimate' WHERE user_id=? AND status=1 AND pack_type!='ultimate'",
			userID)
	} else if pk.PackType == "pro" {
		tx.Exec("UPDATE subscriptions SET pack_type='pro' WHERE user_id=? AND status=1 AND pack_type NOT IN ('pro','ultimate')",
			userID)
	}

	if err := tx.Commit(); err != nil {
		slog.Error("creditTokens commit", "user", userID, "error", err)
	}
}
