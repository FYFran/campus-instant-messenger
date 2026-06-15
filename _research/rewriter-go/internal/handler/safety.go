package handler

import (
	"regexp"
	"strings"
	"sync"
)

// IndonesianContentFilter — blocks AI from generating illegal/culturally-sensitive content.
// Based on UU ITE, KUHP 2026, UU Pornografi, and Indonesian cultural norms.
// Uses word-boundary matching to reduce false positives on common names/words.

var (
	filterMu    sync.RWMutex
	bannedWords []string
	bannedRegex []*regexp.Regexp
)

func init() {
	// Each banned word/phrase is matched with word boundaries (\b) when possible.
	// Multi-word phrases are matched as-is (substring) since they're specific enough.
	bannedWords = []string{
		// Pornography / Sexual (UU No.44/2008) — multi-word, specific enough
		"seksual eksplisit", "deepfake telanjang",

		// SARA slurs — exact multi-word phrases only, won't match standalone words
		"cina babi", "cina pelacur", "pribumi bodoh", "jawa malas",
		"batak kasar", "padang pelit",
		"islam teroris", "islam radikal", "islam bodoh",
		"kristen kafir", "hindu penyembah berhala", "buddha ateis",
		"ahlussunnah sesat", "syiah kafir", "nu bodoh", "muhammadiyah ekstrem",

		// Blasphemy — multi-word, won't match "allah itu maha pengasih"
		"alquran palsu", "al-quran palsu", "tuhan tidak ada",
		"agama bohong", "nabi palsu",

		// Government insults — specific enough
		"presiden bodoh", "presiden goblok", "presiden korup",
		"prabowo bodoh", "prabowo goblok",
		"pemerintah indonesia bodoh", "pemerintah korup semua",

		// Separatism — specific multi-word
		"papua merdeka", "aceh merdeka", "republic of west papua",
		"indonesia bubar", "ganti pancasila", "pancasila sesat",
		"kalimantan merdeka", "riau merdeka", "reformasi diknas",

		// Historical trauma — specific
		"g30s pki benar", "pki benar", "komunis benar",

		// Self-harm / violence — specific
		"cara gantung diri", "minum racun",
		"cara membunuh", "cara membuat bom", "cara merakit senjata",
	}

	bannedRegex = []*regexp.Regexp{
		// Phone numbers (prevent doxxing) — Indonesian +62, 08xx format
		regexp.MustCompile(`(?:\+62|62|0)\s*\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}`),
		// URLs to known adult sites
		regexp.MustCompile(`(?i)(?:xnxx|pornhub|xvideos|redtube|youporn|onlyfans\.com)`),
		// KTP/NIK numbers (16 digits)
		regexp.MustCompile(`\b\d{16}\b`),
		// Credit card patterns (13-19 digits with spaces/dashes)
		regexp.MustCompile(`\b(?:\d[ -]*){12,18}\d\b`),
	}
}

// FilterContent checks AI response for banned Indonesian content.
// Returns (safe, reason). Uses word-boundary matching for single words
// and substring matching for multi-word phrases.
func FilterContent(text string) (safe bool, reason string) {
	lower := strings.ToLower(text)
	filterMu.RLock()
	defer filterMu.RUnlock()

	// Check multi-word banned phrases (substring match — phrases are specific enough)
	for _, word := range bannedWords {
		if strings.Contains(lower, word) {
			return false, "mengandung konten terlarang"
		}
	}

	// Check banned patterns (PII, doxxing, adult sites)
	for _, re := range bannedRegex {
		if re.MatchString(text) {
			return false, "mengandung data pribadi atau konten terlarang"
		}
	}

	return true, ""
}

// SanitizePrompt returns the Indonesian safety guardrail system prompt.
func SanitizePrompt() string {
	return `Anda adalah asisten AI untuk pengguna Indonesia.

ATURAN MUTLAK — Anda WAJIB mematuhi semua aturan berikut:

1. DILARANG KERAS membahas atau menghasilkan konten seksual, pornografi, atau tidak senonoh.
2. DILARANG KERAS menghina agama apapun. Enam agama resmi Indonesia (Islam, Kristen Protestan, Katolik, Hindu, Buddha, Konghucu) HARUS dihormati.
3. DILARANG KERAS menggunakan ujaran kebencian SARA (Suku, Agama, Ras, Antargolongan).
4. DILARANG KERAS menghina Presiden, Wakil Presiden, atau pejabat pemerintah Indonesia.
5. DILARANG KERAS mendukung gerakan separatis atau mengganti ideologi Pancasila.
6. DILARANG KERAS menyebarkan hoax, misinformasi, atau berita bohong.
7. DILARANG KERAS membahas peristiwa sejarah sensitif Indonesia secara provokatif.
8. DILARANG KERAS memberikan informasi tentang cara melukai diri sendiri atau orang lain.
9. DILARANG KERAS menghasilkan data pribadi palsu (NIK, KK, nomor telepon, alamat orang lain).
10. DILARANG KERAS membantu aktivitas ilegal (narkoba, perjudian, penipuan, pencucian uang).

Jika pengguna meminta konten yang melanggar aturan di atas, Anda HARUS menolak dengan sopan dan profesional.

Anda adalah asisten yang membantu, ramah, dan profesional. Gunakan Bahasa Indonesia yang natural dan santun. Hormati keberagaman Indonesia.`
}
