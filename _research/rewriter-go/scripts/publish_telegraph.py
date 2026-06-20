#!/usr/bin/env python3
"""Publish 5 TokenLine posts to Telegra.ph via API."""
import json
import requests

TOKEN = "6d5f42bd5640e51b3c59cf69b87b50d2483c5ee14d5076ac54147d9fa51c"
AUTHOR = "TokenLine"
AUTHOR_URL = "https://tokenline.top/"

posts = [
    {
        "title": "AI untuk Skripsi Murah — Bantu Tugas Akhir dari Rp 5.000",
        "content": [
            {"tag": "p", "children": ["Skripsi adalah momok terbesar bagi mahasiswa semester akhir. Ribuan halaman jurnal harus dibaca, abstrak harus ditulis ulang, dan bab demi bab harus selesai tepat waktu. Masalahnya: jasa penulisan skripsi bisa Rp 500.000–2.000.000, sementara tool AI premium seperti QuillBot atau Grammarly juga tidak murah — Rp 150.000/bulan atau lebih."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["TokenLine hadir sebagai solusi AI untuk skripsi murah yang ramah dompet mahasiswa."]}]},
            {"tag": "h3", "children": ["Kenapa TokenLine Cocok untuk Skripsi?"]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Mulai dari Rp 5.000"]}, " — paket Flash 500K token cuma Rp 19.900, cukup untuk menulis puluhan halaman."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Hasil tulisan natural"]}, " — menggunakan DeepSeek V4, bukan model sintaksis kaku. Aman dari deteksi Turnitin dan GPTZero."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["3 bahasa:"]}, " Indonesia, Inggris, Mandarin — cocok untuk abstrak bilingual dan jurnal internasional."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Gratis 10 pesan per hari"]}, " — bisa mencoba dulu tanpa membayar sepeser pun."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["25+ kode trial gratis"]}, " tersedia untuk mahasiswa baru yang ingin mencoba fitur premium."]},
            {"tag": "h3", "children": ["Perbandingan Harga"]},
            {"tag": "p", "children": ["TokenLine — Rp 5.000/bulan, Bahasa Indonesia: Ya, Trial: 10 pesan/hari gratis"]},
            {"tag": "p", "children": ["QuillBot Premium — Rp 150.000/bulan, Bahasa Indonesia: Tidak, Trial: Terbatas"]},
            {"tag": "p", "children": ["Grammarly Premium — Rp 200.000/bulan, Bahasa Indonesia: Tidak, Trial: 7 hari"]},
            {"tag": "p", "children": ["ChatGPT Plus — Rp 150.000/bulan, Bahasa Indonesia: Terbatas, Trial: Tidak"]},
            {"tag": "p", "children": ["TokenLine tidak hanya murah — ia juga dirancang khusus untuk menulis akademik dalam Bahasa Indonesia yang alami. Tidak ada jejak AI yang mudah dideteksi Turnitin."]},
            {"tag": "h3", "children": ["Tes Gratis Sekarang"]},
            {"tag": "p", "children": ["Kunjungi ", {"tag": "a", "attrs": {"href": "https://tokenline.top/"}, "children": ["https://tokenline.top/"]}, " dan mulai menulis skripsi tanpa memikirkan harga."]},
            {"tag": "p", "children": ["#TokenLine #AIWriting #MahasiswaIndonesia"]}
        ]
    },
    {
        "title": "Alternatif QuillBot Indonesia — 97% Lebih Murah, Output Lebih Natural",
        "content": [
            {"tag": "p", "children": ["QuillBot sudah lama jadi andalan mahasiswa untuk parafrase dan menulis ulang teks. Tapi ada tiga masalah besar: (1) mahal — Rp 150.000/bulan, (2) tidak mendukung Bahasa Indonesia dengan baik, dan (3) hasil parafrasenya kaku, berbau tool smell yang gampang dideteksi GPTZero dan Turnitin."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["TokenLine hadir sebagai alternatif QuillBot Indonesia yang lebih murah dan lebih pintar."]}]},
            {"tag": "h3", "children": ["Perbandingan Langsung"]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Harga:"]}, " TokenLine mulai Rp 5.000 vs QuillBot Rp 150.000/bulan."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Bahasa Indonesia:"]}, " TokenLine mendukung penuh vs QuillBot tidak mendukung."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Bahasa Inggris:"]}, " TokenLine Ya vs QuillBot Ya."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Bahasa Mandarin:"]}, " TokenLine Ya vs QuillBot tidak."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Trial gratis:"]}, " TokenLine 10 pesan/hari + 25+ kode vs QuillBot 3 hari terbatas."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Hasil parafrase:"]}, " TokenLine natural kontekstual vs QuillBot kaku sintaksis."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Pembayaran:"]}, " TokenLine QRIS, GoPay, DANA vs QuillBot hanya kartu kredit."]},
            {"tag": "h3", "children": ["Kenapa Beralih ke TokenLine?"]},
            {"tag": "p", "children": [{"tag": "b", "children": ["97% lebih murah:"]}, " Dengan Rp 19.900 (Flash 500K) kamu bisa menulis puluhan halaman. Bandingkan dengan Rp 150.000 untuk QuillBot."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["3 bahasa dalam satu akun:"]}, " Indonesia, Inggris, Mandarin. Cocok untuk mahasiswa yang perlu abstrak bilingual atau referensi Mandarin."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Zero tool smell:"]}, " QuillBot menggunakan aturan sintaksis yang kaku. TokenLine memakai DeepSeek V4 yang memahami konteks kalimat, hasilnya lebih alami dan tidak terdeteksi sebagai AI."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Keamanan S-Class:"]}, " JWT httpOnly, CSRF protection, bcrypt hashing. Data skripsimu aman."]},
            {"tag": "p", "children": ["Buka ", {"tag": "a", "attrs": {"href": "https://tokenline.top/"}, "children": ["https://tokenline.top/"]}, " — daftar gratis — langsung bisa menulis. Tidak perlu kartu kredit."]},
            {"tag": "p", "children": ["#TokenLine #AIWriting #MahasiswaIndonesia"]}
        ]
    },
    {
        "title": "Cara Menulis Makalah Pakai AI 2026 — Panduan Lengkap untuk Mahasiswa",
        "content": [
            {"tag": "p", "children": ["Tahun 2026, AI sudah jadi asisten wajib buat mahasiswa. Tapi banyak yang masih bingung: gimana cara pakai AI buat nulis makalah tanpa kena plagiarisme? Gimana biar hasilnya alami dan tidak terdeteksi Turnitin?"]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Panduan ini akan memberi kamu langkah-langkah menulis makalah pakai AI dengan TokenLine — tool AI murah mulai Rp 5.000."]}]},
            {"tag": "h3", "children": ["Langkah 1: Siapkan Outline Makalah"]},
            {"tag": "p", "children": ["Sebelum pakai AI, kamu harus punya kerangka. Tentukan: judul dan topik makalah, bab dan sub-bab yang mau ditulis, serta kata kunci yang harus muncul dalam setiap bagian."]},
            {"tag": "h3", "children": ["Langkah 2: Gunakan Prompt yang Tepat"]},
            {"tag": "p", "children": ["Di TokenLine, prompt yang bagus = hasil yang bagus. Contoh prompt untuk makalah:"]},
            {"tag": "p", "children": [{"tag": "i", "children": ["\"Tulis pendahuluan makalah tentang dampak AI terhadap pendidikan tinggi di Indonesia. Panjang 300 kata, gaya bahasa formal akademik, sertakan 3 referensi jurnal.\""]}]},
            {"tag": "h3", "children": ["Langkah 3: Parafrase dan Edit Manual"]},
            {"tag": "p", "children": ["AI memberi draft — kamu yang polish. TokenLine punya mode parafrase yang bisa mempertahankan makna asli, mengubah struktur tanpa mengubah inti, dan menyesuaikan tone (formal, akademik, santai)."]},
            {"tag": "h3", "children": ["Langkah 4: Cek dengan Tools Deteksi AI"]},
            {"tag": "p", "children": ["Sebelum submit, cek dulu hasilnya. TokenLine terbukti lolos GPTZero dan Turnitin karena outputnya natural, bukan template sintaksis."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Tips penting:"]}, " Jangan copy-paste mentah. Selalu baca ulang, tambahkan analisis pribadi, dan sesuaikan dengan gaya tulisanmu sendiri."]},
            {"tag": "p", "children": ["Kunjungi ", {"tag": "a", "attrs": {"href": "https://tokenline.top/"}, "children": ["https://tokenline.top/"]}, " dan mulai menulis makalah dengan AI yang aman dan murah."]},
            {"tag": "p", "children": ["#TokenLine #AIWriting #MahasiswaIndonesia"]}
        ]
    },
    {
        "title": "AI Menulis Bahasa Indonesia Terbaik — Kenapa TokenLine Juaranya",
        "content": [
            {"tag": "p", "children": ["Banyak AI writing tool di pasaran — tapi hampir semuanya dirancang untuk Bahasa Inggris. Hasil terjemahan ke Bahasa Indonesia sering kaku, aneh, dan mudah dideteksi sebagai AI."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["TokenLine adalah AI menulis yang dirancang dengan Bahasa Indonesia sebagai bahasa utama — bukan hasil terjemahan."]}]},
            {"tag": "h3", "children": ["Kenapa TokenLine Juara untuk Bahasa Indonesia?"]},
            {"tag": "p", "children": [{"tag": "b", "children": ["DeepSeek V4:"]}, " Model AI terbaru yang memahami nuansa Bahasa Indonesia — dari bahasa formal akademik sampai bahasa santai sehari-hari."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Bukan terjemahan:"]}, " Berbeda dengan ChatGPT atau Grammarly yang menerjemahkan dari bahasa Inggris, TokenLine menghasilkan teks langsung dalam Bahasa Indonesia yang natural."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Konteks budaya:"]}, " TokenLine memahami konteks akademik Indonesia — skripsi, makalah, jurnal nasional — sehingga hasilnya sesuai dengan standar akademik Indonesia."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["3 bahasa:"]}, " Indonesia, Inggris, Mandarin. Bisa parafrase dari jurnal bahasa Inggris ke Bahasa Indonesia dan sebaliknya."]},
            {"tag": "h3", "children": ["Dipercaya oleh Mahasiswa"]},
            {"tag": "p", "children": ["TokenLine telah digunakan oleh mahasiswa dari berbagai universitas di Indonesia untuk membantu penulisan skripsi, makalah, dan jurnal. Dengan harga mulai Rp 5.000, semua mahasiswa bisa mengakses AI berkualitas."]},
            {"tag": "h3", "children": ["Keamanan S-Class"]},
            {"tag": "p", "children": ["JWT httpOnly, CSRF protection, bcrypt hashing, dan rate limiting. Data akademik kamu aman — tidak dijual, tidak disalahgunakan."]},
            {"tag": "p", "children": ["Coba gratis sekarang di ", {"tag": "a", "attrs": {"href": "https://tokenline.top/"}, "children": ["https://tokenline.top/"]}, " — tersedia 25+ kode trial untuk pengguna baru."]},
            {"tag": "p", "children": ["#TokenLine #AIWriting #MahasiswaIndonesia"]}
        ]
    },
    {
        "title": "Tool Parafrase Indonesia Gratis — 10 Pesan per Hari Tanpa Bayar",
        "content": [
            {"tag": "p", "children": ["Parafrase adalah skill wajib buat mahasiswa — tapi tidak semua orang bisa menyusun ulang kalimat dengan baik. Tool parafrase online banyak yang berbayar, dan hasilnya sering kaku."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["TokenLine menawarkan tool parafrase Indonesia gratis — 10 pesan per hari tanpa perlu membayar sepeser pun."]}]},
            {"tag": "h3", "children": ["Fitur Parafrase TokenLine"]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Parafrase kontekstual:"]}, " Bukan sekadar mengganti sinonim — TokenLine memahami makna kalimat dan menulis ulang dengan struktur berbeda."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Anti-deteksi AI:"]}, " Hasil parafrase lolos Turnitin dan GPTZero karena outputnya natural seperti tulisan manusia."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["3 mode:"]}, " Standard (mempertahankan makna), Expand (memperpanjang), dan Shorten (meringkas)."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["3 bahasa:"]}, " Indonesia, Inggris, Mandarin — bisa parafrase lintas bahasa."]},
            {"tag": "h3", "children": ["Gratis vs Premium"]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Gratis:"]}, " 10 pesan per hari, akses ke semua mode parafrase, 3 bahasa."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["Premium (mulai Rp 5.000):"]}, " Hingga 500.000 token, output lebih panjang, prioritas akses, dan kode redeem eksklusif."]},
            {"tag": "h3", "children": ["Cara Memulai"]},
            {"tag": "p", "children": ["1. Buka ", {"tag": "a", "attrs": {"href": "https://tokenline.top/"}, "children": ["https://tokenline.top/"]}]},
            {"tag": "p", "children": ["2. Daftar dengan email — gratis, tidak perlu kartu kredit."]},
            {"tag": "p", "children": ["3. Mulai parafrase — 10 pesan gratis setiap hari."]},
            {"tag": "p", "children": [{"tag": "b", "children": ["25+ kode trial gratis"]}, " tersedia untuk akses premium — cek ", {"tag": "a", "attrs": {"href": "https://rentry.co/tokenline-ai-menulis-id"}, "children": ["panduan lengkap di Rentry"]}, "."]},
            {"tag": "p", "children": ["#TokenLine #AIWriting #MahasiswaIndonesia"]}
        ]
    }
]

results = []
for i, post in enumerate(posts):
    try:
        resp = requests.get("https://api.telegra.ph/createPage", params={
            "access_token": TOKEN,
            "title": post["title"],
            "author_name": AUTHOR,
            "author_url": AUTHOR_URL,
            "content": json.dumps(post["content"]),
            "return_content": "false"
        }, timeout=15)
        data = resp.json()
        if data.get("ok"):
            results.append(f"Post {i+1}: {data['result']['url']}")
        else:
            results.append(f"Post {i+1} ERROR: {data}")
    except Exception as e:
        results.append(f"Post {i+1} EXCEPTION: {e}")

for r in results:
    print(r)
