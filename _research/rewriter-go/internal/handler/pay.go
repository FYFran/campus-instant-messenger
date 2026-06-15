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

// TokenLine — pure token model. No unlimited subscriptions. Never lose money.

type tokenPack struct {
	Name      string
	Amount    int64  // price IDR
	Tokens    int64  // token count
	Model     string // model for display
	MaxOutput int    // max output tokens per request
}

var tokenPacks = map[string]tokenPack{
	"flash_500k": {"TokenLine Flash 500K", 19900, 500000, "deepseek-v4-flash", 4000},
	"flash_1m5":  {"TokenLine Flash 1.5M", 49900, 1500000, "deepseek-v4-flash", 6000},
	"flash_4m":   {"TokenLine Flash 4M", 99900, 4000000, "deepseek-v4-flash", 6000},
	"pro_500k":   {"TokenLine Pro 500K", 399000, 500000, "deepseek-v4-pro", 8000},
	"pro_2m":     {"TokenLine Pro 2M", 1499000, 2000000, "deepseek-v4-pro", 8000},
	"pro_5m":     {"TokenLine Pro 5M", 3499000, 5000000, "deepseek-v4-pro", 8000},
}

var modelWeight = map[string]int64{
	"deepseek-v4-flash": 1,
	"deepseek-v4-pro":   5,
}

var dodoAPIKey string
var dodoProductID string
var dodoBaseURL string
var dodoWebhookSecret string

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

type payReq struct{ Plan string `json:"plan"` }

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

	pk, ok := tokenPacks[req.Plan]
	if !ok {
		writeJSON(w, 400, "Paket tidak tersedia. Pilih: flash_500k, flash_1m5, flash_4m, pro_500k, pro_2m, pro_5m")
		return
	}

	extID := fmt.Sprintf("tl-%d-%d", userID, time.Now().UnixMilli())
	_, err := h.DB.ExecContext(r.Context(),
		"INSERT INTO payments(user_id, xendit_invoice_id, plan, amount) VALUES(?,?,?,?)",
		userID, extID, req.Plan, pk.Amount)
	if err != nil {
		slog.Error("create payment", "error", err)
		writeJSON(w, 500, "Gagal membuat invoice")
		return
	}

	if dodoAPIKey != "" && dodoProductID != "" {
		checkoutURL, err := createDodoCheckout(extID, pk.Name, pk.Amount, userID)
		if err == nil && checkoutURL != "" {
			writeJSON(w, 200, map[string]interface{}{
				"invoice_id":  extID,
				"invoice_url": checkoutURL,
				"amount":      pk.Amount,
				"plan":        req.Plan,
				"tokens":      pk.Tokens,
				"status":      "pending",
			})
			return
		}
		slog.Error("dodo checkout failed", "error", err)
	}

	writeJSON(w, 200, map[string]interface{}{
		"invoice_id":  extID,
		"invoice_url": fmt.Sprintf("https://tokenline.top/topup.html?pay=%s", extID),
		"amount":      pk.Amount,
		"plan":        req.Plan,
		"tokens":      pk.Tokens,
		"status":      "pending",
		"note":        "Dodo Payments akan segera aktif",
	})
}

func (h *PayHandler) ListPacks(w http.ResponseWriter, r *http.Request) {
	packs := make([]map[string]interface{}, 0, len(tokenPacks))
	order := []string{"flash_500k", "flash_1m5", "flash_4m", "pro_500k", "pro_2m", "pro_5m"}
	for _, key := range order {
		pk := tokenPacks[key]
		packs = append(packs, map[string]interface{}{
			"id":     key,
			"name":   pk.Name,
			"amount": pk.Amount,
			"tokens": pk.Tokens,
			"model":  pk.Model,
		})
	}
	writeJSON(w, 200, packs)
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
		"return_url":    "https://tokenline.top/chat/",
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

	// Atomic race-condition guard: use UPDATE WHERE status='pending' as a
	// compare-and-swap. Only ONE concurrent webhook will succeed.
	// First, mark as paid atomically — if RowsAffected=0, another webhook won.
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
		// Check if already paid (idempotent retry) or invoice doesn't exist
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

	// Fetch invoice details (now guaranteed to be ours exclusively)
	var userID int64
	var plan string
	err = h.DB.QueryRowContext(r.Context(),
		"SELECT user_id, plan FROM payments WHERE xendit_invoice_id=?",
		invoiceID).Scan(&userID, &plan)
	if err != nil {
		slog.Error("callback invoice read after update", "invoice_id", invoiceID, "error", err)
		writeJSON(w, 500, "Gagal membaca invoice")
		return
	}

	pk, ok := tokenPacks[plan]
	if !ok {
		slog.Error("callback unknown plan", "plan", plan)
		writeJSON(w, 400, "Unknown plan")
		return
	}

	// Stack tokens: find or create active subscription row.
	var subID int64
	var existingBalance int64
	err = h.DB.QueryRowContext(r.Context(),
		"SELECT id, COALESCE(token_balance,0) FROM subscriptions WHERE user_id=? AND status=1 ORDER BY id DESC LIMIT 1",
		userID).Scan(&subID, &existingBalance)
	if err != nil {
		h.DB.ExecContext(r.Context(),
			"INSERT INTO subscriptions(user_id, plan, started_at, expires_at, token_balance, status) VALUES(?,?,?,?,?,1)",
			userID, plan, time.Now().UTC().Format(time.RFC3339), "2099-12-31T23:59:59Z", pk.Tokens)
	} else {
		h.DB.ExecContext(r.Context(),
			"UPDATE subscriptions SET token_balance=token_balance+? WHERE id=?",
			pk.Tokens, subID)
	}

	slog.Info("token pack activated via Dodo", "user", userID, "plan", plan, "tokens", pk.Tokens)
	writeJSON(w, 200, map[string]interface{}{
		"status":  "activated",
		"tokens":  pk.Tokens,
		"balance": existingBalance + pk.Tokens,
	})
}
