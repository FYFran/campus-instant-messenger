package handler

import (
	"database/sql"
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
	var email, packType, plan, phone string
	var phoneVerified int
	var flashBal, proBal int64
	err := h.DB.QueryRowContext(r.Context(),
		`SELECT u.email, COALESCE(s.pack_type,'gratis'), COALESCE(s.plan,'gratis'),
		        COALESCE(s.flash_balance,0), COALESCE(s.pro_balance,0),
		        COALESCE(u.phone,''), COALESCE(u.phone_verified,0)
		 FROM users u LEFT JOIN subscriptions s ON s.user_id=u.id AND s.status=1
		 WHERE u.id=? ORDER BY s.id DESC LIMIT 1`, userID).Scan(&email, &packType, &plan, &flashBal, &proBal, &phone, &phoneVerified)
	if err != nil {
		writeJSON(w, 404, "User not found")
		return
	}
	var usedTokens int64
	h.DB.QueryRowContext(r.Context(),
		`SELECT COALESCE(SUM(LENGTH(content)*2),0) FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE c.user_id=?`,
		userID).Scan(&usedTokens)
	var totalDeposited int64
	h.DB.QueryRowContext(r.Context(),
		`SELECT COALESCE(SUM(amount),0) FROM payments WHERE user_id=? AND status='paid'`, userID).Scan(&totalDeposited)
	var refCount, isCreator int64
	h.DB.QueryRowContext(r.Context(),
		`SELECT COALESCE(referral_count,0), COALESCE(is_creator,0) FROM subscriptions WHERE user_id=? AND status=1`,
		userID).Scan(&refCount, &isCreator)
	referralCap := int64(500000)
	if packType == "ultimate" {
		referralCap = 5000000
	}

	writeJSON(w, 200, map[string]interface{}{
		"id":              userID,
		"email":           email,
		"plan":            packType,
		"plan_name":       plan,
		"phone":           phone,
		"phone_verified":  phoneVerified == 1,
		"flash_balance":   flashBal,
		"pro_balance":     proBal,
		"token_balance":   flashBal + proBal,
		"tokens_used":     usedTokens,
		"total_deposited": totalDeposited,
		"referral_count":  refCount,
		"referral_cap":    referralCap,
		"is_creator":      isCreator == 1,
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
		`SELECT DATE(m.created_at) as day, COUNT(*) as cnt FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE c.user_id=? GROUP BY day ORDER BY day DESC LIMIT 7`,
		userID)
	if err != nil {
		slog.Error("stats daily query failed", "user", userID, "error", err)
	} else {
		defer rows.Close()
		for rows.Next() {
			var day string
			var cnt int
			if err := rows.Scan(&day, &cnt); err != nil {
				slog.Warn("stats row scan failed", "error", err)
				continue
			}
			dailyStats = append(dailyStats, map[string]interface{}{"date": day, "messages": cnt})
		}
	}

	payments := []map[string]interface{}{}
	pRows, err := h.DB.QueryContext(r.Context(),
		`SELECT plan, amount, status, created_at FROM payments WHERE user_id=? ORDER BY id DESC LIMIT 20`, userID)
	if err != nil {
		slog.Error("stats payments query failed", "user", userID, "error", err)
	} else {
		defer pRows.Close()
		for pRows.Next() {
			var plan, status, created string
			var amount int64
			_ = pRows.Scan(&plan, &amount, &status, &created)
			payments = append(payments, map[string]interface{}{"plan": plan, "amount": amount, "status": status, "date": created})
		}
	}

	writeJSON(w, 200, map[string]interface{}{"daily": dailyStats, "payments": payments})
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
				_ = rows.Scan(&id, &title, &created)
				list = append(list, map[string]interface{}{"id": id, "title": title, "created_at": created})
			}
			defer func() { _ = rows.Close() }()
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
			_ = rows.Scan(&role, &content, &model, &created)
			msgs = append(msgs, map[string]interface{}{"role": role, "content": content, "model": model, "created_at": created})
		}
		defer func() { _ = rows.Close() }()
	}
	if msgs == nil {
		msgs = []map[string]interface{}{}
	}
	writeJSON(w, 200, msgs)
}
