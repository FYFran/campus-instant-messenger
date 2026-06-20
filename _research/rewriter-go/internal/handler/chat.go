package handler

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
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
	ConversationID string `json:"conversation_id"`
	Lang           string `json:"lang"`
}

func (h *ChatHandler) Chat(w http.ResponseWriter, r *http.Request) {
	userID, ok := userIDFrom(r)
	if !ok {
		writeJSON(w, 401, "Silakan login terlebih dahulu")
		return
	}
	var req chatReq
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || strings.TrimSpace(req.Message) == "" {
		if err != nil {
			slog.Warn("chat bad request", "error", err, "remote", r.RemoteAddr)
		}
		writeJSON(w, 400, "Pesan tidak boleh kosong")
		return
	}
	if req.Model == "" {
		req.Model = "deepseek-v4-flash"
	}
	if safe, reason := FilterContent(req.Message); !safe {
		writeJSON(w, 400, reason)
		return
	}
	// Academic quality boost: inject format instructions into user message
	msgLower := strings.ToLower(req.Message)
	isAcademic := strings.Contains(msgLower, "skripsi") || strings.Contains(msgLower, "tesis") ||
		strings.Contains(msgLower, "makalah") || strings.Contains(msgLower, "jurnal") ||
		strings.Contains(msgLower, "bab ") || strings.Contains(msgLower, "sub-bab") ||
		strings.Contains(msgLower, "thesis") || strings.Contains(msgLower, "dissertation") ||
		strings.Contains(msgLower, "academic paper") || strings.Contains(msgLower, "tulis") ||
		strings.Contains(msgLower, "write") || strings.Contains(msgLower, "lanjutkan") ||
		strings.Contains(msgLower, "lanjut") || strings.Contains(msgLower, "continue") ||
		strings.Contains(msgLower, "sambung") || strings.Contains(msgLower, "sambungan") ||
		strings.Contains(msgLower, "teruskan")
	isOutline := strings.Contains(msgLower, "outline") || strings.Contains(msgLower, "daftar isi") ||
		strings.Contains(msgLower, "kerangka") || strings.Contains(msgLower, "table of contents") ||
		strings.Contains(msgLower, "struktur bab") || strings.Contains(msgLower, "rancangan bab")
	isPolish := strings.Contains(msgLower, "perbaiki") || strings.Contains(msgLower, "polish") ||
		strings.Contains(msgLower, "revisi") || strings.Contains(msgLower, "sempurnakan") ||
		strings.Contains(msgLower, "tingkatkan") || strings.Contains(msgLower, "improve") ||
		strings.Contains(msgLower, "enhance") || strings.Contains(msgLower, "refine") ||
		strings.Contains(msgLower, "perhalus")
	isCode := strings.Contains(msgLower, "code") || strings.Contains(msgLower, "coding") ||
		strings.Contains(msgLower, "program") || strings.Contains(msgLower, "debug") ||
		strings.Contains(msgLower, "python") || strings.Contains(msgLower, "javascript") ||
		strings.Contains(msgLower, "golang") || strings.Contains(msgLower, "rust") ||
		strings.Contains(msgLower, "java") || strings.Contains(msgLower, "c++") ||
		strings.Contains(msgLower, "typescript") || strings.Contains(msgLower, "react") ||
		strings.Contains(msgLower, "algorithm") || strings.Contains(msgLower, "function") ||
		strings.Contains(msgLower, "api") || strings.Contains(msgLower, "sql") ||
		strings.Contains(msgLower, "html") || strings.Contains(msgLower, "css") ||
		strings.Contains(msgLower, "kode") || strings.Contains(msgLower, "pemrograman") ||
		strings.Contains(msgLower, "bug") || strings.Contains(msgLower, "error") ||
		strings.Contains(msgLower, "fix this") || strings.Contains(msgLower, "perbaiki kode")
	isReference := strings.Contains(msgLower, "referensi") || strings.Contains(msgLower, "reference") ||
		strings.Contains(msgLower, "daftar pustaka") || strings.Contains(msgLower, "bibliography") ||
		strings.Contains(msgLower, "rujukan") || strings.Contains(msgLower, "sitasi") ||
		strings.Contains(msgLower, "cari jurnal") || strings.Contains(msgLower, "cari paper")
	isPerfect := strings.Contains(msgLower, "sempurna") || strings.Contains(msgLower, "maksimal") ||
		strings.Contains(msgLower, "perfect") || strings.Contains(msgLower, "maximum quality")

	if isOutline {
		req.Message += "\n\n[OUTLINE GENERATION PROTOCOL]\n" +
			"Generate a COMPLETE thesis/dissertation outline with ALL chapters and sub-sections.\n" +
			"Format each chapter as: BAB X: [Title] (estimated 5000-8000 words)\n" +
			"Each sub-section: X.X [Title] (estimated 2000-3000 words)\n" +
			"Include: Bab 1 Pendahuluan, Bab 2 Tinjauan Pustaka, Bab 3 Metodologi, Bab 4 Hasil dan Pembahasan, Bab 5 Kesimpulan.\n" +
			"End with: [Ketik \"mulai dari bab 1\" untuk memulai penulisan]"
	} else if isPolish {
		req.Message += "\n\n[POLISH PROTOCOL — SELF-CRITIQUE + REWRITE]\n" +
			"STEP 1 — CRITIQUE: Analyze the text above for: (a) weak arguments, (b) missing evidence, (c) repetitive ideas, (d) shallow analysis, (e) informal language, (f) structural issues. List specific problems found.\n" +
			"STEP 2 — REWRITE: Rewrite the ENTIRE section addressing ALL problems. Maintain or increase length. Add deeper analysis, better examples, stronger theoretical grounding. This is for a university thesis — quality must be publication-ready.\n" +
			"END: [BERSAMBUNG — ketik lanjutkan]"
	} else if isPerfect {
		req.Message += "\n\n[MAXIMUM QUALITY PROTOCOL]\n" +
			"Before writing, internally consider: optimal argument structure, 2-3 key theories, strongest evidence angles, and potential counter-arguments. Then write the FINAL version incorporating all of this. Do NOT output your analysis — output ONLY the polished academic text.\n" +
			"REQUIREMENTS: 3000-5000 words, 5-7 sentence paragraphs (claim-evidence-analysis-counterargument-synthesis), minimum 4 ### subsections, 2 markdown tables, formal academic register, [Author, Year] placeholders only, ZERO repetition.\n" +
			"END: [BERSAMBUNG — ketik lanjutkan]"
	} else if isCode {
		req.Message += "\n\n[CODING MODE — powered by DeepSeek V4 (#1 in competitive programming)]\n" +
			"Output clean, production-ready code with:\n" +
			"- Complete implementation (no placeholders, no \"// TODO\")\n" +
			"- Error handling and edge cases covered\n" +
			"- Clear comments in the same language as the code\n" +
			"- Time/space complexity analysis for algorithms\n" +
			"- Example usage or test cases\n" +
			"- Best practices and design patterns where applicable\n" +
			"Format: Use ```language code blocks. Explain approach first, then show code, then explain key decisions."
	} else if isReference {
		// Search CrossRef for real citations and inject them
		searchQuery := req.Message
		if len(searchQuery) > 200 {
			searchQuery = searchQuery[:200]
		}
		citations, err := QueryCrossRef(searchQuery)
		var refList string
		if err == nil && len(citations) > 0 {
			refList = "\nREAL VERIFIED CITATIONS (use these in your response):\n"
			for i, c := range citations {
				if i >= 5 {
					break
				}
				refList += fmt.Sprintf("%d. %s\n", i+1, c.APA)
			}
		}
		req.Message = "Tulis tinjauan pustaka tentang: " + req.Message + "\n\n" +
			refList +
			"\n[INSTRUKSI: Tulis sub-bab tinjauan pustaka akademik yang mengintegrasikan referensi di atas secara alami. " +
			"Gunakan format APA dalam teks. 2000-3000 kata. 3+ sub-bagian dengan ###. Sertakan tabel perbandingan studi. " +
			"JANGAN mengarang referensi lain — gunakan HANYA yang disediakan di atas atau placeholder [Nama, Tahun]. " +
			"END: [BERSAMBUNG]]"
	} else if isAcademic {
		req.Message += "\n\n[ACADEMIC WRITING PROTOCOL — TIER 1 QUALITY]\n" +
			"LENGTH: 3000-5000 words for this section. Write until every argument is fully exhausted.\n" +
			"STRUCTURE: Minimum 4 subsections with ### headings. Use #### for sub-points within subsections.\n" +
			"TABLES: Include 2 markdown tables — one comparison table, one classification or data table.\n" +
			"PARAGRAPHS: 5-7 sentences each. Every paragraph must contain: claim → evidence → analysis → counter-argument → synthesis.\n" +
			"DEPTH: Explore each concept from multiple perspectives. Connect to established theories. Provide concrete examples. Discuss limitations and implications.\n" +
			"TONE: Formal academic register. Use field-specific terminology correctly. No colloquial language.\n" +
			"CITATIONS: Use ONLY placeholder format [Author, Year]. NEVER fabricate specific author names, journal titles, DOIs, or page numbers.\n" +
			"PROHIBITED: Summarizing content instead of writing it fully. Repeating ideas. Using bullet points as substitute for paragraphs. Leaving arguments incomplete. Fake references.\n" +
			"END: [BERSAMBUNG — ketik lanjutkan]"
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

	if (req.Model == "deepseek-v4-pro" || req.Model == "deepseek-v4-ultimate") && proBal <= 0 {
		writeJSON(w, 403, "Pro token habis. Upgrade ke Ultimate atau Pro untuk akses model Pro/满血.")
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
			deductCost += 400 * weight // Pro/Ultimate: lower estimate
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
		} else if req.Model == "deepseek-v4-ultimate" {
			// 满血 = Pro model with reasoning. Deduct from Pro balance.
			res, err := h.DB.ExecContext(r.Context(),
				"UPDATE subscriptions SET pro_balance=pro_balance-? WHERE user_id=? AND status=1 AND pro_balance>=?",
				deductCost, userID, deductCost)
			if err != nil {
				slog.Error("deduct ultimate reserve", "user", userID, "error", err)
				writeJSON(w, 500, "Gagal memproses token")
				return
			}
			n, _ := res.RowsAffected()
			if n == 0 {
				writeJSON(w, 403, "Pro token habis. Upgrade ke Ultimate atau Pro untuk akses 满血.")
				return
			}
			deducted = true
			deductModel = "pro"
		}
	}

	// Find or create conversation
	convID := req.ConversationID
	if convID == "" {
		h.DB.QueryRowContext(r.Context(),
			"INSERT INTO conversations(user_id, title) VALUES(?,?) RETURNING id",
			userID, truncate(req.Message, 40)).Scan(&convID)
	} else {
		var ownerID int64
		err := h.DB.QueryRowContext(r.Context(),
			"SELECT user_id FROM conversations WHERE id=?", convID).Scan(&ownerID)
		if err != nil {
			// Client-generated ID (e.g. "new_123") — create with auto-generated integer ID
			err2 := h.DB.QueryRowContext(r.Context(),
				"INSERT INTO conversations(user_id, title) VALUES(?,?) RETURNING id",
				userID, truncate(req.Message, 40)).Scan(&convID)
			if err2 != nil {
				h.refundReserved(userID, deductModel, deductCost)
				writeJSON(w, 500, "Gagal membuat percakapan")
				return
			}
			// Update req.ConversationID so frontend can sync with the real ID
			req.ConversationID = convID
		} else if ownerID != userID {
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
	// Academic writing instruction — short, structured, research-backed
	academicRules := ""
	switch req.Lang {
	case "id", "":
		academicRules = `<academic_writing>
<role>Asisten penulisan akademik untuk mahasiswa Indonesia</role>
<rules>
- Tulis HANYA SATU sub-bab per respons, 2500-4000 kata
- Gunakan ### sub-judul untuk struktur bertingkat
- Sertakan minimal 1 tabel markdown per sub-bab
- Tulis paragraf 4-6 kalimat, elaborasi penuh, jangan meringkas
- Akhiri dengan: [BERSAMBUNG ke [sub-bab berikutnya] — ketik lanjutkan]
- Bahasa Indonesia akademik formal, bukan gaul
- JANGAN mengarang referensi — gunakan placeholder [Nama, Tahun]
- JANGAN ulang kalimat atau paragraf
</rules>
</academic_writing>
`
	case "en":
		academicRules = `<academic_writing>
<role>Academic writing assistant for Southeast Asian university students</role>
<rules>
- Write ONLY ONE subsection per response, 2500-4000 words
- Use ### sub-headings for hierarchical structure
- Include at least 1 markdown table per subsection
- Write full paragraphs of 4-6 sentences, elaborate fully, never summarize
- End with: [TO BE CONTINUED — type continue for [next section]]
- Formal academic English
- NEVER fabricate references — use placeholder [Author, Year]
- NEVER repeat sentences or paragraphs
</rules>
</academic_writing>
`
	case "ms":
		academicRules = `<academic_writing>
<role>Pembantu penulisan akademik untuk pelajar universiti Malaysia</role>
<rules>
- Tulis HANYA SATU sub-seksyen setiap respons, 2500-4000 patah perkataan
- Gunakan ### sub-tajuk untuk struktur berhierarki
- Sertakan sekurang-kurangnya 1 jadual markdown setiap sub-seksyen
- Tulis perenggan penuh 4-6 ayat, elaborasi lengkap, jangan meringkaskan
- Akhiri dengan: [AKAN BERSAMBUNG ke [sub-seksyen berikutnya] — taip sambung]
- Bahasa Melayu akademik formal
- JANGAN mereka-reka rujukan — gunakan placeholder [Nama, Tahun]
- JANGAN ulang ayat atau perenggan
</rules>
</academic_writing>
`
	}
	history = append(history,
		deepseek.Message{Role: "system", Content: academicRules + SanitizePrompt(req.Lang)})
	if err == nil && rows != nil {
		for rows.Next() {
			var role, content string
			_ = rows.Scan(&role, &content)
			history = append(history, deepseek.Message{Role: role, Content: content})
		}
		rows.Close()
	}

	maxOut := 4000
	if !isFree {
		maxOut = 16000
		if req.Model == "deepseek-v4-pro" || req.Model == "deepseek-v4-ultimate" {
			maxOut = 32000
		}
	}

	// Stream from DeepSeek — tokens already reserved, refund on failure.
	var buf bytes.Buffer
	ctx, cancel := context.WithTimeout(r.Context(), 600*time.Second)
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
	// Send conversation ID so frontend can sync client-generated IDs with real DB IDs
	fmt.Fprintf(w, "event: conv_id\ndata: %s\n\n", convID)
	if flusher, ok := w.(http.Flusher); ok {
		flusher.Flush()
	}
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
