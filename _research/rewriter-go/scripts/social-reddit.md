# TokenLine — Reddit Post Drafts

Date: Juni 2026

---

## Version 1: r/indonesia

**Tone:** Casual, helpful, "I built this" angle
**Style:** No hard selling, follow community guidelines
**Language:** Indonesian with some English (natural r/indonesia style)

---

**Title:** Gw bikin AI writing assistant murah buat bantu nulis skripsi/makalah — free code buat yang mau coba

**Body:**

Jadi gini, gw anak elektro. Gw sadar betapa banyak temen-temen yang pusing nulis skripsi, makalah, atau jurnal — termasuk gw sendiri.

Masalahnya, tools kayak QuillBot lumayan mahal buat kantong mahasiswa (80rb/bulan). Dan rata-rata cuman support English doang. Pas coba parafrase pake tool gratisan, hasilnya kadang kacau.

Akhirnya gw iseng bikin tools sendiri namanya TokenLine. Beberapa highlight:

- **DeepSeek V4** sebagai engine. Parafrasenya akurat, bisa expand atau shorten sesuai konteks. Bukan asal ganti sinonim.
- **3 bahasa:** Indonesia, Inggris, Mandarin. Jadi cocok buat skripsi Bahasa Indonesia, jurnal internasional, atau referensi Mandarin.
- **Harganya Rp 5.000/bln.** 82% lebih murah dari QuillBot. Ada juga free tier kalo mau coba.
- **Security dikerjain.** JWT httpOnly, CSRF, bcrypt, rate limiting. Skripsi lo aman.
- **Udah ada yang pake** buat bantu nulis skripsi dan makalah.

Sekarang lagi nyebar **25 kode redeem gratis** buat pengguna baru. Kalo ada yang minat atau punya pertanyaan, monggo.

Info lengkap: https://rentry.co/tokenline-ai-menulis-id
Website: https://tokenline.top/

Kritik dan saran juga terbuka banget. Ini project iseng yang gw bikin, jadi feedback dari kalian berarti banget.

Makasih 😊

---

## Version 2: r/artificial or r/MachineLearning

**Tone:** Technical, focus on architecture
**Style:** Discussion-worthy, share technical insights
**Language:** English

---

**Title:** Built a multilingual AI writing assistant on DeepSeek V4 — 82% cheaper than QuillBot with comparable quality

**Body:**

I wanted to share a side project I've been working on — an AI writing assistant called TokenLine aimed at the Indonesian academic market.

**Tech stack highlights:**
- Backend: DeepSeek V4 for paraphrasing, expansion, and shortening tasks
- Security: JWT httpOnly cookies, CSRF tokens, bcrypt password hashing, rate limiting on all auth endpoints
- Frontend: PWA with offline support, responsive design
- Multilingual pipeline handling Bahasa Indonesia, English, and Mandarin

**Why I built it:**
Existing options like QuillBot and Grammarly are great but hit two pain points for my target market:
1. Price — $4-15/mo is steep for students where monthly internet costs ~$5
2. Language support — most tools are English-first. Indonesian academic writing mixes BI and English heavily, and there's growing demand for Mandarin support (research translation).

**Performance observations:**
DeepSeek V4 handles the paraphrasing task surprisingly well across all three languages. The main challenge was prompt engineering for Indonesian academic context — academic BI has different formality levels and borrowed terms that generic paraphrasing doesn't handle well. Custom system prompts made a significant difference.

**Key metrics vs QuillBot:**
- Price: Rp 5.000/mo vs Rp 28.000/mo (82% cheaper)
- Languages: 3 (ID/EN/ZH) vs 1 (EN primarily)
- Free tier: Yes vs Limited

I'm doing a small beta with 25 free redemption codes for new users right now.

Full info: https://rentry.co/tokenline-ai-menulis-id
Site: https://tokenline.top/

Would love to hear feedback on the approach, especially from folks working on multilingual NLP or academic writing tools. Anyone else building for underserved language markets?

---

## Alternative Title Options (r/artificial)

- "DeepSeek V4 + Indonesian academic writing — lessons from building a multilingual paraphrasing tool"
- "82% cheaper than QuillBot with 3x language support: my experience building TokenLine on DeepSeek V4"

---

## Subreddit Rules Reminder

| Subreddit | Rules to Watch |
|-----------|---------------|
| r/indonesia | No self-promotion exceeding 10% of activity. Engage with other posts first. Use "I built this" framing, not "buy this". |
| r/artificial | Self-promotion OK if substantive. Include technical details. |
| r/MachineLearning | Strict no self-promotion for commercial tools. Better focus on technical discussion — share prompt engineering approach or multilingual handling. |
