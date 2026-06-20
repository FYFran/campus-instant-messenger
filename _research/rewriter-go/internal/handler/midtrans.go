package handler

import (
	"bytes"
	"crypto/sha512"
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

// Midtrans Snap API integration 鈥?GoPay, OVO, DANA, QRIS, bank transfer, Indomaret/Alfamart.
// Uses raw HTTP (no external lib) for reliability and zero-dependency security audit.

var (
	midtransServerKey string
	midtransClientKey string
	midtransBaseURL   string
	midtransHTTP      = &http.Client{Timeout: 30 * time.Second}
)

// InitMidtrans loads Midtrans credentials from environment.
func InitMidtrans() {
	midtransServerKey = os.Getenv("MIDTRANS_SERVER_KEY")
	midtransClientKey = os.Getenv("MIDTRANS_CLIENT_KEY")
	isProduction := os.Getenv("MIDTRANS_ENV") == "production"

	if isProduction {
		midtransBaseURL = "https://app.midtrans.com"
	} else {
		midtransBaseURL = "https://app.sandbox.midtrans.com"
	}

	if midtransServerKey == "" {
		slog.Warn("MIDTRANS_SERVER_KEY not set 鈥?Midtrans payments disabled")
	} else {
		slog.Info("Midtrans enabled", "env", map[bool]string{true: "production", false: "sandbox"}[isProduction])
	}
}

type midtransSnapReq struct {
	TransactionDetails midtransTxDetails  `json:"transaction_details"`
	CustomerDetail     *midtransCustomer  `json:"customer_detail,omitempty"`
	Items              []midtransItem     `json:"items,omitempty"`
	EnabledPayments    []string           `json:"enabled_payments,omitempty"`
	Callbacks          *midtransCallbacks `json:"callbacks,omitempty"`
}

type midtransTxDetails struct {
	OrderID  string `json:"order_id"`
	GrossAmt int64  `json:"gross_amount"`
}

type midtransCustomer struct {
	FirstName string `json:"first_name"`
	LastName  string `json:"last_name,omitempty"`
	Email     string `json:"email"`
	Phone     string `json:"phone,omitempty"`
}

type midtransItem struct {
	ID       string `json:"id"`
	Price    int64  `json:"price"`
	Quantity int    `json:"quantity"`
	Name     string `json:"name"`
}

type midtransCallbacks struct {
	Finish string `json:"finish,omitempty"`
}

type midtransSnapResp struct {
	Token       string   `json:"token"`
	RedirectURL string   `json:"redirect_url"`
	ErrorMsg    []string `json:"error_messages,omitempty"`
}

// CreateMidtransSnapToken creates a Midtrans Snap transaction and returns the token.
func CreateMidtransSnapToken(orderID, itemName string, amount int64, userEmail, userName string, enabledPayments []string) (string, error) {
	if midtransServerKey == "" {
		return "", fmt.Errorf("midtrans not configured")
	}

	// Default enabled payments for Indonesian market
	payments := enabledPayments
	if len(payments) == 0 {
		payments = []string{"gopay", "qris", "shopeepay", "bank_transfer", "echannel", "cstore"}
	}

	req := midtransSnapReq{
		TransactionDetails: midtransTxDetails{
			OrderID:  orderID,
			GrossAmt: amount,
		},
		Items: []midtransItem{{
			ID:       orderID,
			Price:    amount,
			Quantity: 1,
			Name:     itemName,
		}},
		EnabledPayments: payments,
	}

	if userEmail != "" {
		firstName := userName
		if firstName == "" {
			firstName = "TokenLine"
		}
		req.CustomerDetail = &midtransCustomer{
			FirstName: firstName,
			Email:     userEmail,
		}
	}

	body, err := json.Marshal(req)
	if err != nil {
		return "", fmt.Errorf("midtrans marshal: %w", err)
	}

	httpReq, err := http.NewRequest("POST", midtransBaseURL+"/snap/v1/transactions", bytes.NewReader(body))
	if err != nil {
		return "", fmt.Errorf("midtrans request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")
	httpReq.Header.Set("Accept", "application/json")
	httpReq.SetBasicAuth(midtransServerKey, "")

	resp, err := midtransHTTP.Do(httpReq)
	if err != nil {
		return "", fmt.Errorf("midtrans http: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("midtrans read: %w", err)
	}

	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("midtrans error %d: %s", resp.StatusCode, string(respBody))
	}

	var snapResp midtransSnapResp
	if err := json.Unmarshal(respBody, &snapResp); err != nil {
		return "", fmt.Errorf("midtrans parse: %w", err)
	}

	if snapResp.Token == "" && len(snapResp.ErrorMsg) > 0 {
		return "", fmt.Errorf("midtrans: %v", snapResp.ErrorMsg)
	}

	return snapResp.Token, nil
}

// MidtransCallback handles HTTP notification from Midtrans.
// Notification JSON: https://docs.midtrans.com/reference/notification-json-example
func (h *PayHandler) MidtransCallback(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(r.Body)
	if err != nil {
		slog.Error("midtrans callback read", "error", err)
		writeJSON(w, 400, "Failed to read body")
		return
	}

	var cb struct {
		TransactionStatus string `json:"transaction_status"`
		OrderID           string `json:"order_id"`
		FraudStatus       string `json:"fraud_status,omitempty"`
		GrossAmount       string `json:"gross_amount,omitempty"`
	}

	if err := json.Unmarshal(body, &cb); err != nil {
		slog.Error("midtrans callback parse", "error", err)
		writeJSON(w, 400, "Invalid notification")
		return
	}

	if cb.OrderID == "" {
		writeJSON(w, 400, "Missing order_id")
		return
	}

	// Verify SHA512 signature before calling Midtrans API.
	// Prevents API quota exhaustion from forged callbacks.
	if midtransServerKey != "" {
		var sigCheck struct {
			SignatureKey string `json:"signature_key"`
			StatusCode   string `json:"status_code"`
			GrossAmount  string `json:"gross_amount"`
		}
		if json.Unmarshal(body, &sigCheck) == nil && sigCheck.SignatureKey != "" {
			if !VerifyMidtransSignature(cb.OrderID, sigCheck.StatusCode, sigCheck.GrossAmount, sigCheck.SignatureKey) {
				slog.Warn("midtrans callback rejected: invalid signature", "order_id", cb.OrderID)
				writeJSON(w, 401, "Invalid signature")
				return
			}
		}
	}

	verifiedStatus, err := verifyMidtransOrder(cb.OrderID)
	if err != nil {
		slog.Error("midtrans verify failed", "order_id", cb.OrderID, "error", err)
		writeJSON(w, 500, "Verification failed")
		return
	}

	// Map Midtrans status to our payment status
	newStatus := mapMidtransStatus(verifiedStatus.TransactionStatus, verifiedStatus.FraudStatus)
	if newStatus == "" {
		slog.Info("midtrans callback ignored", "order_id", cb.OrderID, "status", verifiedStatus.TransactionStatus)
		w.WriteHeader(200)
		_, _ = w.Write([]byte(`{"status":"ignored"}`))
		return
	}

	slog.Info("midtrans callback", "order_id", cb.OrderID, "status", verifiedStatus.TransactionStatus, "our_status", newStatus)

	if newStatus == "paid" {
		if err := processMidtransPayment(h.DB, cb.OrderID); err != nil {
			slog.Error("midtrans payment processing failed 鈥?returning 500 for retry", "order_id", cb.OrderID, "error", err)
			writeJSON(w, 500, "Gagal memproses pembayaran 鈥?akan dicoba ulang")
			return
		}
	}

	w.WriteHeader(200)
	_, _ = w.Write([]byte(`{"status":"ok"}`))
}

type midtransVerifyResp struct {
	TransactionStatus string `json:"transaction_status"`
	FraudStatus       string `json:"fraud_status"`
	OrderID           string `json:"order_id"`
}

func verifyMidtransOrder(orderID string) (*midtransVerifyResp, error) {
	req, err := http.NewRequest("GET",
		fmt.Sprintf("%s/v2/%s/status", midtransBaseURL, orderID), nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Accept", "application/json")
	req.SetBasicAuth(midtransServerKey, "")

	resp, err := midtransHTTP.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("midtrans status check %d: %s", resp.StatusCode, string(body))
	}

	var result midtransVerifyResp
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}
	return &result, nil
}

func mapMidtransStatus(txStatus, fraudStatus string) string {
	switch txStatus {
	case "capture":
		if fraudStatus == "accept" {
			return "paid"
		}
		return "" // challenge 鈥?manual review needed
	case "settlement":
		return "paid"
	case "deny", "cancel", "expire":
		return "failed"
	case "pending":
		return "" // still waiting, no action
	}
	return ""
}

// MidtransClientKey returns the client key for frontend Snap.js initialization.
func MidtransClientKey() string  { return midtransClientKey }
func MidtransIsProduction() bool { return midtransBaseURL == "https://app.midtrans.com" }

func processMidtransPayment(db *sql.DB, orderID string) error {
	// Atomic CAS 鈥?prevent double-credit from duplicate callbacks
	res, err := db.Exec(
		"UPDATE payments SET status='paid', paid_at=datetime('now') WHERE xendit_invoice_id=? AND status='pending'",
		orderID)
	if err != nil {
		slog.Error("midtrans payment update failed", "order_id", orderID, "error", err)
		return err
	}
	n, _ := res.RowsAffected()
	if n == 0 {
		var currentStatus string
		db.QueryRow("SELECT status FROM payments WHERE xendit_invoice_id=?", orderID).Scan(&currentStatus)
		if currentStatus == "paid" {
			slog.Info("midtrans duplicate callback ignored", "order_id", orderID)
			return nil
		}
		slog.Error("midtrans order not pending", "order_id", orderID)
		return fmt.Errorf("order %s not found or not pending", orderID)
	}

	var userID int64
	var plan string
	err = db.QueryRow("SELECT user_id, plan FROM payments WHERE xendit_invoice_id=?", orderID).Scan(&userID, &plan)
	if err != nil {
		slog.Error("midtrans read after update", "order_id", orderID, "error", err)
		return err
	}

	pk, ok := lookupPack(plan)
	if !ok {
		slog.Error("midtrans unknown plan", "plan", plan)
		return fmt.Errorf("unknown plan %s for order %s", plan, orderID)
	}

	if err := creditTokens(db, userID, pk); err != nil {
		slog.Error("creditTokens failed 鈥?reverting Midtrans payment status", "user", userID, "order_id", orderID, "error", err)
		_, _ = db.Exec("UPDATE payments SET status='pending', paid_at=NULL WHERE xendit_invoice_id=? AND status='paid'", orderID)
		return err
	}
	slog.Info("token pack activated via Midtrans", "user", userID, "plan", plan,
		"flash", pk.FlashAmt, "pro", pk.ProAmt)
	return nil
}

// VerifySignature validates Midtrans notification signature using SHA512(key+order_id+status_code+gross_amount+server_key).
func VerifyMidtransSignature(orderID, statusCode, grossAmount, receivedSig string) bool {
	if midtransServerKey == "" {
		return false
	}
	payload := orderID + statusCode + grossAmount + midtransServerKey
	hash := sha512.Sum512([]byte(payload))
	expected := hex.EncodeToString(hash[:])
	return expected == receivedSig
}
