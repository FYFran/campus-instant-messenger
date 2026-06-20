package handler

import (
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"strings"
	"sync"
	"time"

	"tokenline/internal/deepseek"
)

// thesisOutlineDaily tracks per-IP daily usage of the free thesis outline tool.
// Limits to 10/day/IP to prevent API cost abuse.
var (
	thesisOutlineDaily   = sync.Map{} // map[string]int
	thesisOutlineLastDay = time.Now().UTC().Day()
	thesisOutlineMu      sync.Mutex
)

func checkThesisOutlineLimit(ip string) bool {
	thesisOutlineMu.Lock()
	defer thesisOutlineMu.Unlock()
	today := time.Now().UTC().Day()
	if today != thesisOutlineLastDay {
		thesisOutlineDaily = sync.Map{}
		thesisOutlineLastDay = today
	}
	val, _ := thesisOutlineDaily.LoadOrStore(ip, 0)
	count := val.(int)
	if count >= 10 {
		return false
	}
	thesisOutlineDaily.Store(ip, count+1)
	return true
}

// ToolsHandler handles public tool API endpoints (no auth required).
type ToolsHandler struct {
	DeepSeek *deepseek.Client
}

// ThesisOutline generates a structured thesis outline via DeepSeek.
// POST /api/tools/thesis-outline
func (h *ToolsHandler) ThesisOutline(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Topic string `json:"topic"`
		Field string `json:"field"`
		Level string `json:"level"` // S1, S2, S3
		Lang  string `json:"lang"`  // id, en
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.Topic == "" {
		writeJSON(w, 400, "Topik diperlukan. Contoh: Pengaruh media sosial terhadap prestasi mahasiswa")
		return
	}
	req.Topic = strings.TrimSpace(req.Topic)

	// Daily per-IP limit: 10/day to prevent API abuse
	clientIP := r.Header.Get("X-Real-IP")
	if clientIP == "" {
		clientIP = r.RemoteAddr
	}
	if !checkThesisOutlineLimit(clientIP) {
		writeJSON(w, 429, "Batas harian 10 outline tercapai. Silakan coba lagi besok atau gunakan akun terdaftar.")
		return
	}
	if safe, reason := FilterContent(req.Topic); !safe {
		writeJSON(w, 400, reason)
		return
	}
	if len(req.Topic) < 10 {
		writeJSON(w, 400, "Topik terlalu pendek. Jelaskan lebih detail (min 10 karakter).")
		return
	}
	if len(req.Topic) > 500 {
		writeJSON(w, 400, "Topik terlalu panjang. Maksimal 300 karakter.")
		return
	}
	if req.Level == "" {
		req.Level = "S1"
	}
	if req.Lang == "" {
		req.Lang = "id"
	}
	if req.Lang != "id" && req.Lang != "en" {
		req.Lang = "id"
	}

	safetyPrompt := SanitizePrompt(req.Lang)
	systemPrompt := buildThesisPrompt(req.Lang)
	userPrompt := fmt.Sprintf("Topik: %s\nBidang: %s\nJenjang: %s", req.Topic, req.Field, req.Level)

	messages := []deepseek.Message{
		{Role: "system", Content: safetyPrompt},
		{Role: "system", Content: systemPrompt},
		{Role: "user", Content: userPrompt},
	}

	result, err := h.DeepSeek.Chat(r.Context(), messages, "deepseek-v4-flash", 3000)
	if err != nil {
		slog.Error("thesis outline generation failed", "error", err)
		writeJSON(w, 500, "Gagal menghasilkan outline. Silakan coba lagi.")
		return
	}

	if result == "" {
		writeJSON(w, 500, "Model tidak menghasilkan output. Coba topik yang lebih spesifik.")
		return
	}

	slog.Info("thesis outline generated", "topic", req.Topic[:min(50, len(req.Topic))], "len", len(result))
	writeJSON(w, 200, map[string]interface{}{
		"outline": result,
		"topic":   req.Topic,
		"level":   req.Level,
	})
}

func buildThesisPrompt(lang string) string {
	if lang == "en" {
		return `You are a university thesis advisor with 20 years of experience. Generate a detailed, structured thesis outline in ENGLISH.

		The outline must include:
		1. TITLE — A specific, academic title (max 20 words)
		2. CHAPTER 1: INTRODUCTION
		   - 1.1 Background (context + research gap)
		   - 1.2 Problem Statement (3 research questions)
		   - 1.3 Research Objectives
		   - 1.4 Research Benefits (theoretical + practical)
		   - 1.5 Scope and Limitations
		3. CHAPTER 2: LITERATURE REVIEW
		   - 2.1 Key theories (3-4 theories with citations)
		   - 2.2 Previous Research (at least 5 studies)
		   - 2.3 Conceptual Framework
		   - 2.4 Hypotheses (if quantitative research)
		4. CHAPTER 3: RESEARCH METHODOLOGY
		   - 3.1 Research Design
		   - 3.2 Population and Sample
		   - 3.3 Data Collection Techniques
		   - 3.4 Research Instruments
		   - 3.5 Data Analysis Methods
		5. CHAPTER 4: RESULTS AND DISCUSSION (outline only)
		6. CHAPTER 5: CONCLUSION AND SUGGESTIONS (outline only)
		7. REFERENCES — 10 suggested key references (APA 7th format)

		Format with clear numbering. Use academic tone. Make it specific to the user's topic — no generic placeholders.`
	}

	return `Anda adalah dosen pembimbing skripsi dengan pengalaman 20 tahun. Buatkan outline skripsi terstruktur dan detail dalam BAHASA INDONESIA.

	Outline harus mencakup:
	1. JUDUL — Judul akademik yang spesifik (maks 20 kata)
	2. BAB 1: PENDAHULUAN
	   - 1.1 Latar Belakang (konteks + celah penelitian)
	   - 1.2 Rumusan Masalah (3 pertanyaan penelitian)
	   - 1.3 Tujuan Penelitian
	   - 1.4 Manfaat Penelitian (teoritis + praktis)
	   - 1.5 Batasan Penelitian
	3. BAB 2: TINJAUAN PUSTAKA
	   - 2.1 Teori Utama (3-4 teori dengan sitasi)
	   - 2.2 Penelitian Terdahulu (minimal 5 studi)
	   - 2.3 Kerangka Berpikir
	   - 2.4 Hipotesis (jika penelitian kuantitatif)
	4. BAB 3: METODOLOGI PENELITIAN
	   - 3.1 Desain Penelitian
	   - 3.2 Populasi dan Sampel
	   - 3.3 Teknik Pengumpulan Data
	   - 3.4 Instrumen Penelitian
	   - 3.5 Metode Analisis Data
	5. BAB 4: HASIL DAN PEMBAHASAN (outline saja)
	6. BAB 5: KESIMPULAN DAN SARAN (outline saja)
	7. DAFTAR PUSTAKA — 10 referensi kunci yang disarankan (format APA 7th)

	Gunakan penomoran yang jelas. Nada akademik formal. Buat spesifik sesuai topik — jangan placeholder generik.`
}
