package handler

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"tokenline/internal/deepseek"
	"tokenline/internal/middleware"
)

type ChatHandler struct {
	DB       *sql.DB
	DeepSeek *deepseek.Client
}

type chatReq struct {
	Message        string `json:"message"`
	Model          string `json:"model"`
	ConversationID int64  `json:"conversation_id"`
}

func (h *ChatHandler) Chat(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}
	var req chatReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || strings.TrimSpace(req.Message) == "" {
		writeJSON(w, 400, "Pesan tidak boleh kosong")
		return
	}
	if req.Model == "" {
		req.Model = "deepseek-v4-flash"
	}
	if len(req.Message) > 20000 {
		writeJSON(w, 400, "Pesan terlalu panjang. Maks 20.000 karakter.")
		return
	}

	plan, balance, err := h.getBalance(r.Context(), userID)
	if err != nil {
		writeJSON(w, 500, "Gagal memeriksa kuota")
		return
	}

	isFree := plan == "gratis" || (plan == "" && balance <= 0)

	// Free tier: 3 requests/day, max 2000 chars, Flash only.
	if isFree {
		today := time.Now().UTC().Format("2006-01-02")
		var freeCount int
		if err := h.DB.QueryRowContext(r.Context(),
			"SELECT COUNT(*) FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id=?) AND role='user' AND created_at>=?",
			userID, today).Scan(&freeCount); err != nil {
			slog.Error("free count query", "error", err)
		}
		if freeCount >= 3 {
			writeJSON(w, 403, "Kuota gratis habis (3/hari). Beli token untuk lanjut — mulai Rp 19.900.")
			return
		}
		if len(req.Message) > 2000 {
			writeJSON(w, 400, "Gratis: maks 2.000 karakter. Upgrade untuk lebih panjang.")
			return
		}
		req.Model = "deepseek-v4-flash"
	}

	if req.Model == "deepseek-v4-pro" && balance <= 0 {
		writeJSON(w, 403, "Model Pro butuh token. Beli paket Pro mulai Rp 399.000.")
		return
	}

	// Find or create conversation
	convID := req.ConversationID
	if convID == 0 {
		if err := h.DB.QueryRowContext(r.Context(),
			"INSERT INTO conversations(user_id, title) VALUES(?,?) RETURNING id",
			userID, truncate(req.Message, 40)).Scan(&convID); err != nil {
			slog.Error("create conversation", "error", err)
			writeJSON(w, 500, "Gagal membuat percakapan")
			return
		}
	}

	if _, err := h.DB.ExecContext(r.Context(),
		"INSERT INTO messages(conversation_id, role, content, model) VALUES(?,?,?,?)",
		convID, "user", req.Message, req.Model); err != nil {
		slog.Error("save user message", "error", err)
	}

	// Load history
	rows, err := h.DB.QueryContext(r.Context(),
		"SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id ASC LIMIT 30", convID)
	var history []deepseek.Message
	history = append(history, deepseek.Message{Role: "system", Content: SanitizePrompt()})
	if err == nil && rows != nil {
		defer rows.Close()
		for rows.Next() {
			var role, content string
			rows.Scan(&role, &content)
			history = append(history, deepseek.Message{Role: role, Content: content})
		}
	}

	// Output cap: free=1000 tokens, paid=8000 tokens
	maxOut := 1000
	if !isFree {
		maxOut = 8000
	}

	// Stream from DeepSeek
	var buf bytes.Buffer
	ctx, cancel := context.WithTimeout(r.Context(), 120*time.Second)
	defer cancel()

	err = h.DeepSeek.ChatStream(ctx, history, req.Model, maxOut, &buf)
	if err != nil {
		middleware.TrackChatError()
		slog.Error("deepseek stream", "error", err)
		writeJSON(w, 500, "Layanan AI sedang sibuk. Silakan coba lagi.")
		return
	}

	fullResp := extractContent(buf.String())

	if safe, reason := FilterContent(fullResp); !safe {
		slog.Warn("blocked unsafe AI response", "user", userID, "reason", reason)
		fullResp = "Maaf, saya tidak bisa menampilkan jawaban itu karena melanggar aturan konten yang berlaku di Indonesia."
	}

	// Save assistant response
	if fullResp != "" {
		if _, err := h.DB.ExecContext(r.Context(),
			"INSERT INTO messages(conversation_id, role, content, model) VALUES(?,?,?,?)",
			convID, "assistant", fullResp, req.Model); err != nil {
			slog.Error("save assistant message", "error", err)
		}
	}

	// Deduct tokens for non-free users with RowsAffected check.
	if !isFree {
		inputEst := int64(len(req.Message) / 2)
		outputEst := int64(len(fullResp) / 2)
		weight := modelWeight[req.Model]
		if weight <= 0 {
			weight = 1
		}
		cost := (inputEst + outputEst) * weight
		if cost < 50 {
			cost = 50
		}
		res, err := h.DB.ExecContext(r.Context(),
			"UPDATE subscriptions SET token_balance=token_balance-? WHERE user_id=? AND status=1 AND token_balance>=?",
			cost, userID, cost)
		if err != nil {
			slog.Error("token deduction", "error", err)
		} else if n, _ := res.RowsAffected(); n == 0 {
			slog.Warn("token deduction skipped — insufficient balance", "user", userID, "cost", cost)
		}
		// cost tracked via middleware metrics
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Write(buf.Bytes())
	if flusher, ok := w.(http.Flusher); ok {
		flusher.Flush()
	}
}

func (h *ChatHandler) getBalance(ctx context.Context, userID int64) (string, int64, error) {
	var plan string
	var balance int64
	err := h.DB.QueryRowContext(ctx,
		"SELECT plan, COALESCE(token_balance,0) FROM subscriptions WHERE user_id=? AND status=1 ORDER BY id DESC LIMIT 1",
		userID).Scan(&plan, &balance)
	if err != nil {
		return "gratis", 0, nil
	}
	return plan, balance, nil
}

func (h *ChatHandler) GetBalance(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}
	plan, balance, err := h.getBalance(r.Context(), userID)
	if err != nil {
		writeJSON(w, 500, "Gagal memeriksa saldo")
		return
	}
	today := time.Now().UTC().Format("2006-01-02")
	var freeUsed int
	h.DB.QueryRowContext(r.Context(),
		"SELECT COUNT(*) FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id=?) AND role='user' AND created_at>=?",
		userID, today).Scan(&freeUsed)

	weight := modelWeight
	packs := make([]map[string]interface{}, 0)
	order := []string{"flash_500k", "flash_1m5", "flash_4m", "pro_500k", "pro_2m", "pro_5m"}
	for _, key := range order {
		pk := tokenPacks[key]
		packs = append(packs, map[string]interface{}{
			"id": key, "name": pk.Name, "amount": pk.Amount,
			"tokens": pk.Tokens, "model": pk.Model,
		})
	}

	writeJSON(w, 200, map[string]interface{}{
		"plan": plan, "balance": balance,
		"free_used": freeUsed, "free_limit": 3,
		"model_weight": weight, "packs": packs,
	})
}

func truncate(s string, n int) string {
	r := []rune(s)
	if len(r) <= n {
		return s
	}
	return string(r[:n]) + "..."
}

func extractContent(sse string) string {
	var full strings.Builder
	for _, line := range strings.Split(sse, "\n") {
		if strings.HasPrefix(line, "data: ") && !strings.Contains(line, "[DONE]") {
			var chunk struct {
				Choices []struct {
					Delta struct {
						Content string `json:"content"`
					} `json:"delta"`
				} `json:"choices"`
			}
			if json.Unmarshal([]byte(line[6:]), &chunk) == nil && len(chunk.Choices) > 0 {
				full.WriteString(chunk.Choices[0].Delta.Content)
			}
		}
	}
	return full.String()
}
