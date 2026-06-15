package handler

import (
	"database/sql"
	"encoding/json"
	"log/slog"
	"net/http"
)

type UserHandler struct{ DB *sql.DB }

func (h *UserHandler) Me(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}
	var email, plan, phone string
	var phoneVerified int
	var tokenBalance int64
	err := h.DB.QueryRowContext(r.Context(),
		`SELECT u.email, COALESCE(s.plan,'gratis'), COALESCE(s.token_balance,0), COALESCE(u.phone,''), COALESCE(u.phone_verified,0)
		 FROM users u LEFT JOIN subscriptions s ON s.user_id=u.id AND s.status=1
		 WHERE u.id=? ORDER BY s.id DESC LIMIT 1`, userID).Scan(&email, &plan, &tokenBalance, &phone, &phoneVerified)
	if err != nil {
		writeJSON(w, 404, "User not found")
		return
	}
	var usedTokens int64
	h.DB.QueryRowContext(r.Context(),
		`SELECT COALESCE(SUM(LENGTH(content)*2),0) FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id=?)`,
		userID).Scan(&usedTokens)
	var totalDeposited int64
	h.DB.QueryRowContext(r.Context(),
		`SELECT COALESCE(SUM(amount),0) FROM payments WHERE user_id=? AND status='paid'`, userID).Scan(&totalDeposited)
	// For token model: refundable = remaining token balance value (pro-rata estimate)
	var refundableAmount int64
	if tokenBalance > 0 && totalDeposited > 0 {
		// Rough estimate: refundable = balance / (total_deposited/average_token_price)
		// Simpler: just show token balance as-is. Refund handled by RequestRefund endpoint.
		refundableAmount = tokenBalance // token count, not IDR — UI labels this correctly
	}

	writeJSON(w, 200, map[string]interface{}{
		"id":                userID,
		"email":             email,
		"plan":              plan,
		"phone":             phone,
		"phone_verified":    phoneVerified == 1,
		"token_balance":     tokenBalance,
		"tokens_used":       usedTokens,
		"total_deposited":   totalDeposited,
		"refundable_tokens": refundableAmount,
	})
}

func (h *UserHandler) Stats(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}
	dailyStats := []map[string]interface{}{}
	rows, err := h.DB.QueryContext(r.Context(),
		`SELECT DATE(created_at) as day, COUNT(*) as cnt FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id=?) GROUP BY day ORDER BY day DESC LIMIT 7`,
		userID)
	if err == nil && rows != nil {
		for rows.Next() {
			var day string
			var cnt int
			rows.Scan(&day, &cnt)
			dailyStats = append(dailyStats, map[string]interface{}{"date": day, "messages": cnt})
		}
		rows.Close()
	}

	payments := []map[string]interface{}{}
	pRows, err := h.DB.QueryContext(r.Context(),
		`SELECT plan, amount, status, created_at FROM payments WHERE user_id=? ORDER BY id DESC LIMIT 20`, userID)
	if err == nil && pRows != nil {
		for pRows.Next() {
			var plan, status, created string
			var amount int64
			pRows.Scan(&plan, &amount, &status, &created)
			payments = append(payments, map[string]interface{}{"plan": plan, "amount": amount, "status": status, "date": created})
		}
		pRows.Close()
	}

	writeJSON(w, 200, map[string]interface{}{"daily": dailyStats, "payments": payments})
}

func (h *UserHandler) RequestRefund(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}
	var req struct {
		InvoiceID string `json:"invoice_id"`
		Reason    string `json:"reason"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.InvoiceID == "" {
		writeJSON(w, 400, "Invoice ID diperlukan")
		return
	}
	if len(req.Reason) < 10 {
		writeJSON(w, 400, "Alasan refund minimal 10 karakter")
		return
	}
	var amount int64
	var plan string
	err := h.DB.QueryRowContext(r.Context(),
		"SELECT amount, plan FROM payments WHERE xendit_invoice_id=? AND user_id=? AND status='paid'",
		req.InvoiceID, userID).Scan(&amount, &plan)
	if err != nil {
		writeJSON(w, 404, "Invoice tidak ditemukan atau belum dibayar")
		return
	}

	// Prevent double-refund: check if a refund was already requested for this invoice.
	var refundExists int
	h.DB.QueryRowContext(r.Context(),
		"SELECT COUNT(*) FROM payments WHERE xendit_invoice_id=? AND status='refund_pending'",
		"REFUND-"+req.InvoiceID).Scan(&refundExists)
	if refundExists > 0 {
		writeJSON(w, 409, "Refund untuk invoice ini sudah pernah diajukan")
		return
	}

	// Refund based on the specific pack's remaining proportion.
	// User's total balance may include multiple packs — we refund only the
	// unused portion of THIS pack, capped by total remaining balance.
	var totalBalance int64
	h.DB.QueryRowContext(r.Context(),
		"SELECT COALESCE(SUM(token_balance),0) FROM subscriptions WHERE user_id=? AND status=1",
		userID).Scan(&totalBalance)

	pk, knownPack := tokenPacks[plan]
	refundAmount := int64(0)
	if knownPack && pk.Tokens > 0 && totalBalance > 0 {
		// Remaining proportion of this pack = min(pack tokens, total balance)
		packRemaining := pk.Tokens
		if totalBalance < pk.Tokens {
			packRemaining = totalBalance
		}
		if float64(pk.Tokens-packRemaining)/float64(pk.Tokens) < 0.5 {
			// < 50% used → refund remaining portion
			refundAmount = int64(float64(amount) * float64(packRemaining) / float64(pk.Tokens))
		}
	}
	if refundAmount < 0 {
		refundAmount = 0
	}
	if refundAmount > 0 && totalBalance > 0 {
		deduct := pk.Tokens
		if totalBalance < pk.Tokens {
			deduct = totalBalance
		}
		h.DB.ExecContext(r.Context(),
			"UPDATE subscriptions SET token_balance=MAX(0, token_balance-?) WHERE user_id=? AND status=1",
			deduct, userID)
	}
	h.DB.ExecContext(r.Context(), "INSERT INTO payments(user_id, xendit_invoice_id, plan, amount, status) VALUES(?,?,?,?,?)",
		userID, "REFUND-"+req.InvoiceID, "refund", refundAmount, "refund_pending")
	slog.Info("refund requested", "user", userID, "invoice", req.InvoiceID, "original", amount, "balance", totalBalance, "refund", refundAmount, "reason", req.Reason)
	writeJSON(w, 200, map[string]interface{}{
		"message":         "Permintaan refund diterima.",
		"original_amount": amount,
		"refund_amount":   refundAmount,
		"token_balance":   totalBalance,
	})
}

func (h *UserHandler) History(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}
	convID := r.URL.Query().Get("conversation_id")

	if convID == "" {
		rows, _ := h.DB.QueryContext(r.Context(),
			"SELECT id, title, created_at FROM conversations WHERE user_id=? ORDER BY id DESC LIMIT 50", userID)
		var list []map[string]interface{}
		if rows != nil {
			for rows.Next() {
				var id int64
				var title, created string
				rows.Scan(&id, &title, &created)
				list = append(list, map[string]interface{}{"id": id, "title": title, "created_at": created})
			}
			rows.Close()
		}
		if list == nil {
			list = []map[string]interface{}{}
		}
		writeJSON(w, 200, list)
		return
	}

	var ownerID int64
	err := h.DB.QueryRowContext(r.Context(),
		"SELECT user_id FROM conversations WHERE id=?", convID).Scan(&ownerID)
	if err != nil || ownerID != userID {
		writeJSON(w, 404, "Conversation not found")
		return
	}

	rows, _ := h.DB.QueryContext(r.Context(),
		"SELECT role, content, model, created_at FROM messages WHERE conversation_id=? ORDER BY id ASC", convID)
	var msgs []map[string]interface{}
	if rows != nil {
		for rows.Next() {
			var role, content, model, created string
			rows.Scan(&role, &content, &model, &created)
			msgs = append(msgs, map[string]interface{}{"role": role, "content": content, "model": model, "created_at": created})
		}
		rows.Close()
	}
	if msgs == nil {
		msgs = []map[string]interface{}{}
	}
	writeJSON(w, 200, msgs)
}
