package handler

import (
	"regexp"
	"strings"
	"sync"
)

// IndonesianContentFilter — blocks AI from generating illegal/culturally-sensitive content.
// Based on UU ITE, KUHP 2026, UU Pornografi, and Indonesian cultural norms.
// Grok was banned Jan 2026 for violating these. We will not be next.

var (
	filterMu    sync.RWMutex
	bannedWords []string
	bannedRegex []*regexp.Regexp
)

func init() {
	bannedWords = []string{
		// === Pornography / Sexual (UU No.44/2008) ===
		"telanjang", "bugil", "porno", "pornografi", "seksual eksplisit",
		"bokep", "jav", "hentai", "onlyfans", "deepfake telanjang",

		// === SARA — Ethnicity/Religion/Race/Inter-group (UU ITE 28) ===
		"cina babi", "cina pelacur", "pribumi bodoh", "jawa malas",
		"batak kasar", "padang pelit",
		"islam teroris", "islam radikal", "islam bodoh",
		"kristen kafir", "hindu penyembah berhala", "buddha ateis",
		"ahlussunnah sesat", "syiah kafir", "nu bodoh", "muhammadiyah ekstrem",

		// === Blasphemy (UU No.1/PNPS/1965) ===
		"allah itu", "muhammad itu", "alquran palsu", "al-quran palsu",
		"tuhan tidak ada", "agama bohong", "nabi palsu",

		// === Insulting President / Government (KUHP 2026) ===
		"presiden bodoh", "presiden goblok", "presiden korup",
		"prabowo bodoh", "prabowo goblok", "jokowi bodoh", "jokowi goblok",
		"pemerintah indonesia bodoh", "pemerintah korup semua",

		// === Separatism / Treason ===
		"papua merdeka", "aceh merdeka", "republic of west papua",
		"indonesia bubar", "ganti pancasila", "pancasila sesat",
		"kalimantan merdeka", "riau merdeka", "reformasi diknas",

		// === Historical Trauma ===
		"g30s pki benar", "pki benar", "komunis benar",
		"1965 pembantaian", "1998 cina dibunuh",

		// === Self-harm / Violence ===
		"bunuh diri", "cara gantung diri", "minum racun",
		"cara membunuh", "cara membuat bom", "cara merakit senjata",
	}

	bannedRegex = []*regexp.Regexp{
		// Phone numbers (prevent doxxing)
		regexp.MustCompile(`(?:\+62|62|0)\s*\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}`),
		// URLs to known malicious/porn sites
		regexp.MustCompile(`(?i)(?:xnxx|pornhub|xvideos|redtube|youporn|onlyfans\.com)`),
		// KTP/NIK numbers (16 digits)
		regexp.MustCompile(`\b\d{16}\b`),
		// Credit card patterns
		regexp.MustCompile(`\b\d[\d -]{12,18}\d\b`),
	}
}

// FilterContent checks AI response for banned Indonesian content.
// Returns (safe, reason). If not safe, the response should be blocked.
func FilterContent(text string) (safe bool, reason string) {
	lower := strings.ToLower(text)
	filterMu.RLock()
	defer filterMu.RUnlock()

	// Check banned words (substring match — conservative, err on safety side)
	for _, word := range bannedWords {
		if strings.Contains(lower, word) {
			return false, "mengandung konten terlarang (kata: " + word + ")"
		}
	}

	// Check banned patterns (PII, doxxing, etc.)
	for _, re := range bannedRegex {
		if re.MatchString(text) {
			return false, "mengandung data pribadi atau konten terlarang"
		}
	}

	return true, ""
}

// SanitizePrompt adds Indonesian safety guardrails to the system prompt.
func SanitizePrompt() string {
	return `Anda adalah asisten AI untuk pengguna Indonesia.

ATURAN MUTLAK — Anda WAJIB mematuhi semua aturan berikut. Melanggar satu saja = tidak dapat diterima:

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

Jika pengguna meminta konten yang melanggar aturan di atas, Anda HARUS menolak dengan sopan dan profesional. Contoh:
"Maaf, saya tidak bisa membantu dengan permintaan itu karena melanggar aturan konten yang berlaku di Indonesia."

Anda adalah asisten yang membantu, ramah, dan profesional. Gunakan Bahasa Indonesia yang natural dan santun. Hormati keberagaman Indonesia.`
}
