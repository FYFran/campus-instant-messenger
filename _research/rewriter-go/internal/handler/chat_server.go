package handler

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"strings"
	"strconv"
	"time"

	"tokenline/internal/deepseek"
)

type ChatHandler struct {
	DB      *sql.DB
	DeepSeek *deepseek.Client
}

type chatReq struct {
	Message        string `json:"message"`
	Model          string `json:"model"`
	ConversationID int64  `json:"conversation_id"`
}

func (h *ChatHandler) Chat(w http.ResponseWriter, r *http.Request) {
	userID := r.Context().Value("user_id").(int64)
	var req chatReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || strings.TrimSpace(req.Message) == "" {
		writeJSON(w, 400, "Pesan tidak boleh kosong")
		return
	}
	if req.Model == "" { req.Model = "deepseek-v4-flash" }
	if len(req.Message) > 10000 {
		writeJSON(w, 400, "Pesan terlalu panjang")
		return
	}
	// Free: 1 panjang (<=5000 karakter) + 2 pendek (<=2000 karakter) per hari
	if h.checkSubQuick(userID) == "gratis" {
		today := time.Now().UTC().Format("2006-01-02")
		var longC, shortC int
		h.DB.QueryRowContext(r.Context(),"SELECT COUNT(*) FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id=?) AND role='user' AND LENGTH(content)>2000 AND created_at>=?",userID,today).Scan(&longC)
		h.DB.QueryRowContext(r.Context(),"SELECT COUNT(*) FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id=?) AND role='user' AND LENGTH(content)<=2000 AND created_at>=?",userID,today).Scan(&shortC)
		if len(req.Message) > 5000 {
			writeJSON(w, 400, "Gratis: maks 5.000 karakter. Upgrade untuk lebih panjang.")
			return
		}
		if len(req.Message) > 2000 {
			if longC >= 1 {
				writeJSON(w, 400, "Kuota panjang habis (1/hari). Tersisa "+strconv.Itoa(2-shortC)+" pertanyaan pendek. Upgrade untuk unlimited.")
				return
			}
		} else {
			if shortC >= 2 {
				writeJSON(w, 400, "Kuota pendek habis (2/hari). Beli token untuk lanjut.")
				return
			}
		}
	}

	ok, plan := h.checkSub(r.Context(), userID)
	previewMode := false
	if !ok && plan == "gratis" {
		// Preview mode: show first 300 chars, gate the rest
		previewMode = true
		plan = "gratis"
	} else if !ok {
		writeJSON(w, 403, "Kuota habis. Silakan upgrade paket.")
		return
	}

	// Find or create conversation
	convID := req.ConversationID
	if convID == 0 {
		h.DB.QueryRowContext(r.Context(),
			"INSERT INTO conversations(user_id, title) VALUES(?,?) RETURNING id",
			userID, truncate(req.Message, 40)).Scan(&convID)
	}

	// Save user msg
	h.DB.ExecContext(r.Context(),
		"INSERT INTO messages(conversation_id, role, content, model) VALUES(?,?,?,?)",
		convID, "user", req.Message, req.Model)

	// Load history
	rows, _ := h.DB.QueryContext(r.Context(),
		"SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id ASC LIMIT 30", convID)
	var history []deepseek.Message
	history = append(history, deepseek.Message{Role: "system", Content: "Anda asisten AI berbahasa Indonesia. Jawab dalam bahasa Indonesia yang ramah dan membantu."})
	for rows.Next() {
		var role, content string
		rows.Scan(&role, &content)
		history = append(history, deepseek.Message{Role: role, Content: content})
	}
	rows.Close()

	// Buffer to capture SSE stream
	var buf bytes.Buffer
	ctx, cancel := context.WithTimeout(r.Context(), 120*time.Second)
	defer cancel()

	// Output cap: free=2000 tokens (~1200 chars), paid=6000 tokens
	maxOut := "1000"
	if plan != "gratis" { maxOut = "6000" }
	err := h.DeepSeek.ChatStream(ctx, history, req.Model, maxOut, &buf)
	if err != nil {
		slog.Error("deepseek stream", "error", err)
		writeJSON(w, 500, "Layanan AI sedang sibuk. Silakan coba lagi.")
		return
	}

	// Extract content from SSE for saving
	fullResp := extractContent(buf.String())

	// Save full response to DB
	if fullResp != "" {
		h.DB.ExecContext(r.Context(),
			"INSERT INTO messages(conversation_id, role, content, model) VALUES(?,?,?,?)",
			convID, "assistant", fullResp, req.Model)
	}

	// Stream to client — truncate in preview mode
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	if previewMode {
		displayText := fullResp
		runes := []rune(displayText)
		if len(runes) > 500 {
			displayText = string(runes[:500]) + "...\n\n[Upgrade ke Bulanan (Rp 30rb/bln) atau beli unlock (Rp 2rb) — lihat selengkapnya.]"
		}
		fmt.Fprintf(w, "data: {\"choices\":[{\"delta\":{\"content\":\"%s\"}}]}\n\ndata: [DONE]\n", jsonEscape(displayText))
	} else {
		w.Write(buf.Bytes())
	}
	if flusher, ok := w.(http.Flusher); ok { flusher.Flush() }

	// Deduct tokens for token-based plans
	if plan == "pulsa_s" || plan == "pulsa_m" || plan == "pulsa_l" {
		// Deduct based on actual token usage (estimated from response + input)
		used := int64(len(req.Message)+len(fullResp)) * 2 // rough token estimate
		if used < 1000 { used = 1000 }                     // minimum 1K tokens per msg
		h.DB.ExecContext(r.Context(),
			"UPDATE subscriptions SET token_balance=MAX(0,COALESCE(token_balance,0)-?) WHERE user_id=? AND status=1", used, userID)
	}
	// Update daily count for subscription plans
	if plan != "premium" && plan != "tahunan" {
		h.DB.ExecContext(r.Context(),
			"UPDATE subscriptions SET daily_used=daily_used+1 WHERE user_id=? AND status=1", userID)
	}
}

// checkSubQuick returns just the plan name without side effects
func (h *ChatHandler) checkSubQuick(userID int64) string {
	var plan string
	h.DB.QueryRowContext(context.Background(),
		"SELECT plan FROM subscriptions WHERE user_id=? AND status=1 ORDER BY id DESC LIMIT 1",
		userID).Scan(&plan)
	if plan == "" { plan = "gratis" }
	return plan
}

func (h *ChatHandler) checkSub(ctx context.Context, userID int64) (bool, string) {
	var plan, expiresAt string
	var dailyUsed int
	err := h.DB.QueryRowContext(ctx,
		"SELECT plan, expires_at, daily_used FROM subscriptions WHERE user_id=? AND status=1 ORDER BY id DESC LIMIT 1",
		userID).Scan(&plan, &expiresAt, &dailyUsed)
	if err != nil { return false, "" }

	// Daily reset: count today's messages from the messages table
	today := time.Now().UTC().Format("2006-01-02")
	var todayCount int
	h.DB.QueryRowContext(ctx,
		"SELECT COUNT(*) FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id=?) AND role='user' AND created_at >= ?",
		userID, today).Scan(&todayCount)

	// Sync stored count with actual
	if todayCount != dailyUsed {
		h.DB.ExecContext(ctx, "UPDATE subscriptions SET daily_used=? WHERE user_id=? AND status=1", todayCount, userID)
		dailyUsed = todayCount
	}

	exp, err := time.Parse(time.RFC3339, expiresAt)
	if err != nil || time.Now().UTC().After(exp) { return false, plan }

	// Safety caps: free 3/day, flash 50/day, premium 200/day
	maxPerDay := 3
	switch {
	case plan == "harian": maxPerDay = 50
	case plan == "bulanan": maxPerDay = 50
	case plan == "premium": maxPerDay = 200
	case plan == "tahunan": maxPerDay = 200
	case plan == "pulsa_s": maxPerDay = 999 // unlimited per day, capped by total
	case plan == "pulsa_m": maxPerDay = 999
	case plan == "pulsa_l": maxPerDay = 999
	}
	if dailyUsed >= maxPerDay { return false, plan }

	// Token packs: check remaining balance
	if plan == "pulsa_s" || plan == "pulsa_m" || plan == "pulsa_l" {
		var balance int64
		h.DB.QueryRowContext(ctx,
			"SELECT COALESCE(token_balance,0) FROM subscriptions WHERE user_id=? AND status=1 ORDER BY id DESC LIMIT 1",
			userID).Scan(&balance)
		if balance <= 0 { return false, plan }
	}
	return true, plan
}

func truncate(s string, n int) string {
	r := []rune(s)
	if len(r) <= n { return s }
	return string(r[:n]) + "..."
}

func jsonEscape(s string) string {
	b, _ := json.Marshal(s)
	return string(b[1 : len(b)-1])
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

func (h *ChatHandler) History(w http.ResponseWriter, r *http.Request) {
	userID := r.Context().Value("user_id").(int64)
	convID := r.URL.Query().Get("conversation_id")
	if convID == "" {
		// List conversations
		rows, _ := h.DB.QueryContext(r.Context(),
			"SELECT id, title, created_at FROM conversations WHERE user_id=? ORDER BY id DESC", userID)
		var convs []map[string]interface{}
		for rows.Next() {
			var id int64; var title, createdAt string
			rows.Scan(&id, &title, &createdAt)
			convs = append(convs, map[string]interface{}{"id": id, "title": title, "created_at": createdAt})
		}
		rows.Close()
		if convs == nil { convs = []map[string]interface{}{} }
		writeJSON(w, 200, convs)
		return
	}
	// Get messages for a conversation
	rows, _ := h.DB.QueryContext(r.Context(),
		"SELECT role, content, model, created_at FROM messages WHERE conversation_id=? ORDER BY id ASC", convID)
	var msgs []map[string]interface{}
	for rows.Next() {
		var role, content, model, createdAt string
		rows.Scan(&role, &content, &model, &createdAt)
		msgs = append(msgs, map[string]interface{}{"role": role, "content": content, "model": model, "created_at": createdAt})
	}
	rows.Close()
	if msgs == nil { msgs = []map[string]interface{}{} }
	writeJSON(w, 200, msgs)
}
