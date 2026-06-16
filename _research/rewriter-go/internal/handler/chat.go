package handler

import (
	"bytes"
	"context"
	"errors"
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
	if len(req.Message) > 10000 {
		writeJSON(w, 400, "Pesan terlalu panjang. Maks 10.000 karakter.")
		return
	}

	packType, flashBal, proBal, err := h.getBalance(r.Context(), userID)
	if err != nil {
		writeJSON(w, 500, "Gagal memeriksa kuota")
		return
	}

	isFree := packType == "gratis" && flashBal <= 0 && proBal <= 0

	// Free tier: 3 requests/day enforced atomically at INSERT time (no TOCTOU).
	if isFree {
		if len(req.Message) > 2000 {
			writeJSON(w, 400, "Gratis: maks 2.000 karakter. Upgrade untuk lebih panjang.")
			return
		}
		req.Model = "deepseek-v4-flash"
	}

	if req.Model == "deepseek-v4-pro" && proBal <= 0 {
		writeJSON(w, 403, "Pro token habis. Upgrade ke Ultimate atau Pro untuk akses model Pro.")
		return
	}
	// Pre-flight balance check for Flash model — must have either flash or pro balance.
	if !isFree && req.Model == "deepseek-v4-flash" && flashBal <= 0 && proBal <= 0 {
		writeJSON(w, 403, "Token habis. Beli paket untuk melanjutkan.")
		return
	}

	// Estimate cost and deduct BEFORE calling DeepSeek — prevents cost leak from TOCTOU race.
	// Refund if DeepSeek fails.
	deducted := false
	deductModel := ""
	var deductCost int64
	if !isFree {
		// Rough estimate based on input length; adjusted after response.
		inputEst := int64(len(req.Message) / 2)
		weight := modelWeight[req.Model]
		if weight <= 0 {
			weight = 1
		}
		deductCost = inputEst * weight
		if deductCost < 50 {
			deductCost = 50
		}
		// For Flash: estimate includes typical output (~500 tokens * weight).
		// For Pro: estimate larger output.
		if req.Model == "deepseek-v4-flash" {
			deductCost += 500 * weight
		} else {
			deductCost += 1000 * weight
		}

		if req.Model == "deepseek-v4-flash" {
			// Prefer flash_balance, fallback to pro_balance at 5:1
			res, err := h.DB.ExecContext(r.Context(),
				"UPDATE subscriptions SET flash_balance=flash_balance-? WHERE user_id=? AND status=1 AND flash_balance>=?",
				deductCost, userID, deductCost)
			if err != nil {
				slog.Error("deduct flash reserve", "user", userID, "error", err)
				writeJSON(w, 500, "Gagal memproses token")
				return
			}
			n, _ := res.RowsAffected()
			if n > 0 {
				deducted = true
				deductModel = "flash"
			} else {
				// Flash insufficient — try Pro at 5:1 rate
				proCost := deductCost / 5
				if proCost < 1 {
					proCost = 1
				}
				res2, err2 := h.DB.ExecContext(r.Context(),
					"UPDATE subscriptions SET pro_balance=pro_balance-? WHERE user_id=? AND status=1 AND pro_balance>=?",
					proCost, userID, proCost)
				if err2 != nil {
					slog.Error("deduct pro reserve", "user", userID, "error", err2)
					writeJSON(w, 500, "Gagal memproses token")
					return
				}
				n2, _ := res2.RowsAffected()
				if n2 == 0 {
					writeJSON(w, 403, "Token habis. Beli paket untuk melanjutkan.")
					return
				}
				deducted = true
				deductModel = "pro_fallback"
				deductCost = proCost // track pro cost for refund
			}
		} else if req.Model == "deepseek-v4-pro" {
			res, err := h.DB.ExecContext(r.Context(),
				"UPDATE subscriptions SET pro_balance=pro_balance-? WHERE user_id=? AND status=1 AND pro_balance>=?",
				deductCost, userID, deductCost)
			if err != nil {
				slog.Error("deduct pro reserve", "user", userID, "error", err)
				writeJSON(w, 500, "Gagal memproses token")
				return
			}
			n, _ := res.RowsAffected()
			if n == 0 {
				writeJSON(w, 403, "Pro token habis. Upgrade ke Ultimate atau Pro untuk akses model Pro.")
				return
			}
			deducted = true
			deductModel = "pro"
		}
	}

	// Find or create conversation
	convID := req.ConversationID
	if convID == 0 {
		h.DB.QueryRowContext(r.Context(),
			"INSERT INTO conversations(user_id, title) VALUES(?,?) RETURNING id",
			userID, truncate(req.Message, 40)).Scan(&convID)
	} else {
		var ownerID int64
		err := h.DB.QueryRowContext(r.Context(),
			"SELECT user_id FROM conversations WHERE id=?", convID).Scan(&ownerID)
		if err != nil || ownerID != userID {
			// Refund reserved tokens before returning error
			h.refundReserved(userID, deductModel, deductCost)
			writeJSON(w, 404, "Percakapan tidak ditemukan")
			return
		}
	}

	// Insert user message — for free users, atomically enforce 3/day limit to prevent TOCTOU bypass.
	if isFree {
		today := time.Now().UTC().Format("2006-01-02")
		res, err := h.DB.ExecContext(r.Context(),
			"INSERT INTO messages(conversation_id, role, content, model) SELECT ?,?,?,? WHERE (SELECT COUNT(*) FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id=?) AND role='user' AND created_at>=?) < 3",
			convID, "user", req.Message, req.Model, userID, today)
		if err != nil {
			slog.Error("free tier message insert failed", "user", userID, "error", err)
			h.refundReserved(userID, deductModel, deductCost)
			writeJSON(w, 500, "Gagal menyimpan pesan")
			return
		}
		n, _ := res.RowsAffected()
		if n == 0 {
			h.refundReserved(userID, deductModel, deductCost)
			writeJSON(w, 403, "Kuota gratis habis (3/hari). Beli token untuk lanjut — mulai Rp 19.900.")
			return
		}
	} else {
		h.DB.ExecContext(r.Context(),
			"INSERT INTO messages(conversation_id, role, content, model) VALUES(?,?,?,?)",
			convID, "user", req.Message, req.Model)
	}

	// Load history
	rows, err := h.DB.QueryContext(r.Context(),
		"SELECT role, content FROM messages WHERE conversation_id=? ORDER BY id ASC LIMIT 30", convID)
	var history []deepseek.Message
	history = append(history, deepseek.Message{Role: "system", Content: SanitizePrompt()})
	if err == nil && rows != nil {
		for rows.Next() {
			var role, content string
			_ = rows.Scan(&role, &content)
			history = append(history, deepseek.Message{Role: role, Content: content})
		}
		rows.Close()
	}

	maxOut := 1000
	if !isFree {
		maxOut = 6000
		if req.Model == "deepseek-v4-pro" {
			maxOut = 8000
		}
	}

	// Stream from DeepSeek — tokens already reserved, refund on failure.
	var buf bytes.Buffer
	ctx, cancel := context.WithTimeout(r.Context(), 120*time.Second)
	defer cancel()

	err = h.DeepSeek.ChatStream(ctx, history, req.Model, maxOut, &buf)
	if err != nil {
		middleware.TrackChatError()
		slog.Error("deepseek stream", "error", err)
		// Refund reserved tokens
		h.refundReserved(userID, deductModel, deductCost)
		writeJSON(w, 500, "Layanan AI sedang sibuk. Silakan coba lagi.")
		return
	}

	fullResp := extractContent(buf.String())

	if safe, reason := FilterContent(fullResp); !safe {
		slog.Warn("blocked unsafe AI response", "user", userID, "reason", reason)
		fullResp = "Maaf, saya tidak bisa menampilkan jawaban itu karena melanggar aturan konten yang berlaku di Indonesia."
	}

	if fullResp != "" {
		h.DB.ExecContext(r.Context(),
			"INSERT INTO messages(conversation_id, role, content, model) VALUES(?,?,?,?)",
			convID, "assistant", fullResp, req.Model)
	}

	// Adjust deduction: refund over-estimate, charge extra if underestimated.
	// Only applies to non-free users who had tokens deducted.
	if deducted {
		inputEst := int64(len(req.Message) / 2)
		outputEst := int64(len(fullResp) / 2)
		weight := modelWeight[req.Model]
		if weight <= 0 {
			weight = 1
		}
		actualCost := (inputEst + outputEst) * weight
		if actualCost < 50 {
			actualCost = 50
		}

		if deductModel == "flash" {
			// Flash deducted: adjust flash_balance
			diff := deductCost - actualCost
			if diff > 0 {
				// Over-estimated — refund
				h.DB.ExecContext(r.Context(),
					"UPDATE subscriptions SET flash_balance=flash_balance+? WHERE user_id=? AND status=1",
					diff, userID)
			} else if diff < 0 {
				// Under-estimated — charge extra
				extra := -diff
				h.DB.ExecContext(r.Context(),
					"UPDATE subscriptions SET flash_balance=flash_balance-? WHERE user_id=? AND status=1 AND flash_balance>=?",
					extra, userID, extra)
			}
		} else if deductModel == "pro" {
			diff := deductCost - actualCost
			if diff > 0 {
				h.DB.ExecContext(r.Context(),
					"UPDATE subscriptions SET pro_balance=pro_balance+? WHERE user_id=? AND status=1",
					diff, userID)
			} else if diff < 0 {
				extra := -diff
				h.DB.ExecContext(r.Context(),
					"UPDATE subscriptions SET pro_balance=pro_balance-? WHERE user_id=? AND status=1 AND pro_balance>=?",
					extra, userID, extra)
			}
		} else if deductModel == "pro_fallback" {
			// Flash model paid with Pro tokens. Adjust pro_balance.
			// Convert actual Flash cost to Pro tokens (5:1, round up).
			actualProCost := (actualCost + 4) / 5
			if actualProCost < 1 {
				actualProCost = 1
			}
			diff := deductCost - actualProCost
			if diff > 0 {
				h.DB.ExecContext(r.Context(),
					"UPDATE subscriptions SET pro_balance=pro_balance+? WHERE user_id=? AND status=1",
					diff, userID)
			} else if diff < 0 {
				extra := -diff
				h.DB.ExecContext(r.Context(),
					"UPDATE subscriptions SET pro_balance=pro_balance-? WHERE user_id=? AND status=1 AND pro_balance>=?",
					extra, userID, extra)
			}
		}
		TrackCostInChat(req.Model, len(req.Message), len(fullResp))
	}

	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	if _, err := w.Write(buf.Bytes()); err != nil {
		slog.Warn("sse write failed (client disconnected)", "user", userID, "error", err)
		return
	}
	if flusher, ok := w.(http.Flusher); ok {
		flusher.Flush()
	}
}

// refundReserved refunds tokens that were reserved but not used (e.g., DeepSeek API error).
func (h *ChatHandler) refundReserved(userID int64, deductModel string, amount int64) {
	if amount <= 0 {
		return
	}
	switch deductModel {
	case "flash":
		h.DB.ExecContext(context.Background(),
			"UPDATE subscriptions SET flash_balance=flash_balance+? WHERE user_id=? AND status=1",
			amount, userID)
	case "pro":
		h.DB.ExecContext(context.Background(),
			"UPDATE subscriptions SET pro_balance=pro_balance+? WHERE user_id=? AND status=1",
			amount, userID)
	case "pro_fallback":
		h.DB.ExecContext(context.Background(),
			"UPDATE subscriptions SET pro_balance=pro_balance+? WHERE user_id=? AND status=1",
			amount, userID)
	}
}

func (h *ChatHandler) getBalance(ctx context.Context, userID int64) (packType string, flashBal int64, proBal int64, err error) {
	err = h.DB.QueryRowContext(ctx,
		"SELECT COALESCE(pack_type,'gratis'), COALESCE(flash_balance,0), COALESCE(pro_balance,0) FROM subscriptions WHERE user_id=? AND status=1 ORDER BY id DESC LIMIT 1",
		userID).Scan(&packType, &flashBal, &proBal)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return "gratis", 0, 0, nil
		}
		return "", 0, 0, err
	}
	return
}

func (h *ChatHandler) GetBalance(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}
	packType, flashBal, proBal, err := h.getBalance(r.Context(), userID)
	if err != nil {
		writeJSON(w, 500, "Gagal memeriksa saldo")
		return
	}
	today := time.Now().UTC().Format("2006-01-02")
	var freeUsed int
	h.DB.QueryRowContext(r.Context(),
		"SELECT COUNT(*) FROM messages WHERE conversation_id IN (SELECT id FROM conversations WHERE user_id=?) AND role='user' AND created_at>=?",
		userID, today).Scan(&freeUsed)

	writeJSON(w, 200, map[string]interface{}{
		"plan":          packType,
		"flash_balance": flashBal,
		"pro_balance":   proBal,
		"free_used":     freeUsed,
		"free_limit":    3,
		"model_weight":  modelWeight,
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
						Content          string `json:"content"`
						ReasoningContent string `json:"reasoning_content"`
					} `json:"delta"`
				} `json:"choices"`
			}
			if json.Unmarshal([]byte(line[6:]), &chunk) == nil && len(chunk.Choices) > 0 {
				c := chunk.Choices[0].Delta.Content
				full.WriteString(c)
			}
		}
	}
	return full.String()
}
