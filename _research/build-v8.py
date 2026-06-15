html = '''<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TokenLine — Asisten Menulis AI Premium</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="lang-switcher.css">
<style>
  * { font-family: "Inter", system-ui, sans-serif; }
  body { background: #fafaf8; }

  .glass { background: rgba(255,255,255,0.7); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid rgba(0,0,0,0.04); }
  .card { background: #fff; border: 1px solid rgba(0,0,0,0.05); border-radius: 20px; transition: all 0.3s cubic-bezier(0.4,0,0.2,1); }
  .card:hover { transform: translateY(-3px); box-shadow: 0 8px 30px rgba(0,0,0,0.06); }

  .btn-primary { background: #1a1a28; color: #fff; border-radius: 14px; font-weight: 600; transition: all 0.25s ease; box-shadow: 0 2px 8px rgba(26,26,40,0.15); }
  .btn-primary:hover { background: #2a2a42; transform: translateY(-1px); box-shadow: 0 6px 20px rgba(26,26,40,0.2); }
  .btn-secondary { border: 1px solid rgba(0,0,0,0.12); border-radius: 14px; font-weight: 500; transition: all 0.25s ease; }
  .btn-secondary:hover { border-color: rgba(0,0,0,0.25); background: rgba(0,0,0,0.02); }

  .text-gradient { background: linear-gradient(175deg, #1a1a28 0%, #3d3d5c 55%, #5a5a78 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }
  .text-gold { color: #b8975a; }

  .section-white { background: #fff; }
  .section-warm { background: #fafaf8; }
  .section-dark { background: #1a1a28; color: #fff; }

  @keyframes fadeIn { from { opacity: 0; transform: translateY(24px); } to { opacity: 1; transform: translateY(0); } }
  .reveal { animation: fadeIn 0.7s cubic-bezier(0.22,0.61,0.36,1) both; }
  .reveal-1 { animation-delay: 0.1s; } .reveal-2 { animation-delay: 0.2s; } .reveal-3 { animation-delay: 0.3s; }

  .pricing-featured { border: 1.5px solid rgba(184,151,90,0.3); background: linear-gradient(180deg, #fff 0%, #fdfcfa 100%); box-shadow: 0 4px 24px rgba(0,0,0,0.06); }

  ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-thumb { background: rgba(0,0,0,0.08); border-radius: 10px; }
</style>
</head>
<body class="antialiased">

<nav class="glass fixed top-4 left-1/2 -translate-x-1/2 z-50 w-[95%] max-w-5xl flex items-center justify-between h-14 px-6 rounded-2xl shadow-md">
  <a href="/" class="flex items-center gap-2.5 shrink-0">
    <div class="w-7 h-7 rounded-lg bg-[#1a1a28] flex items-center justify-center"><span class="text-white text-[10px] font-bold">TL</span></div>
    <span class="font-bold text-sm tracking-tight">TokenLine</span>
  </a>
  <div class="hidden md:flex items-center gap-6 text-[13px] font-medium text-black/35">
    <a href="#features" class="hover:text-black/70 transition-colors">Fitur</a>
    <a href="#how" class="hover:text-black/70 transition-colors">Cara Kerja</a>
    <a href="#pricing" class="hover:text-black/70 transition-colors">Harga</a>
  </div>
  <div class="flex items-center gap-3">
    <div class="lang-switcher">
      <button data-lang="id" class="active" onclick="TL_I18N.switch('id')">ID</button>
      <button data-lang="en" onclick="TL_I18N.switch('en')">EN</button>
      <button data-lang="zh" onclick="TL_I18N.switch('zh')">中文</button>
    </div>
    <a href="login.html" class="text-[12px] font-medium text-black/40 hover:text-black/70 transition-colors">Masuk</a>
    <a href="register.html" class="btn-primary text-[12px] px-4 py-2.5">Mulai Gratis</a>
  </div>
</nav>

<section class="section-white pt-36 pb-20">
  <div class="max-w-3xl mx-auto px-6 text-center reveal">
    <div class="inline-flex items-center gap-2 rounded-full border border-black/5 bg-white px-4 py-2 mb-10 text-[12px] font-medium text-black/40 shadow-sm">
      <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span> DeepSeek V4 · Harga Indonesia
    </div>
    <h1 class="text-[54px] lg:text-[72px] font-extrabold leading-[1.03] tracking-[-0.04em] mb-8 text-gradient">
      Tulis apa pun.<br>Cukup bilang mau apa.
    </h1>
    <p class="text-lg text-black/30 leading-relaxed mb-10 max-w-lg mx-auto">
      Skripsi, jurnal, proposal, email — AI yang ngerti Indonesia.<br>Bukan chatbot biasa.
    </p>
    <div class="flex flex-col sm:flex-row items-center justify-center gap-4 mb-6">
      <a href="register.html" class="btn-primary text-base px-10 py-4 w-full sm:w-auto text-center">Mulai Gratis — 3 percakapan/hari</a>
      <a href="#demo" class="btn-secondary text-base px-10 py-4 w-full sm:w-auto text-center">Lihat Demo</a>
    </div>
    <p class="text-xs text-black/18">Tanpa kartu kredit · 30 detik daftar</p>
    <div class="grid grid-cols-4 gap-12 mt-20 max-w-xl mx-auto text-center reveal reveal-1">
      <div><p class="text-[28px] font-extrabold text-gradient">12K+</p><p class="text-xs text-black/30 mt-1">Penulis</p></div>
      <div><p class="text-[28px] font-extrabold text-gradient">85K+</p><p class="text-xs text-black/30 mt-1">Dokumen</p></div>
      <div><p class="text-[28px] font-extrabold text-gradient">4.8</p><p class="text-xs text-black/30 mt-1">Rating</p></div>
      <div><p class="text-[28px] font-extrabold text-gradient">98%</p><p class="text-xs text-black/30 mt-1">Puass</p></div>
    </div>
  </div>
</section>

<section id="features" class="section-warm py-28">
  <div class="max-w-5xl mx-auto px-6">
    <div class="text-center mb-16 reveal">
      <p class="text-[11px] font-bold text-black/20 uppercase tracking-[0.15em] mb-3">Untuk Siapa</p>
      <h2 class="text-[38px] font-bold tracking-[-0.02em] mb-3">Satu alat. Semua kebutuhan.</h2>
      <p class="text-[15px] text-black/30 max-w-lg mx-auto">Dari mahasiswa sampai CEO — semua bisa nulis lebih cepat.</p>
    </div>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
      <div class="card p-8 flex flex-col items-center text-center gap-4 reveal"><span class="text-4xl">🎓</span><h3 class="text-lg font-bold">Mahasiswa</h3><p class="text-[13px] text-black/35 leading-relaxed">Skripsi, tesis, makalah. Sitasi otomatis.</p></div>
      <div class="card p-8 flex flex-col items-center text-center gap-4 reveal reveal-1"><span class="text-4xl">🔬</span><h3 class="text-lg font-bold">Peneliti</h3><p class="text-[13px] text-black/35 leading-relaxed">Jurnal Scopus, proposal hibah. IEEE/APA.</p></div>
      <div class="card p-8 flex flex-col items-center text-center gap-4 reveal reveal-2"><span class="text-4xl">💼</span><h3 class="text-lg font-bold">Profesional</h3><p class="text-[13px] text-black/35 leading-relaxed">Email klien, proposal, laporan tahunan.</p></div>
      <div class="card p-8 flex flex-col items-center text-center gap-4 reveal reveal-3"><span class="text-4xl">✨</span><h3 class="text-lg font-bold">Kreator</h3><p class="text-[13px] text-black/35 leading-relaxed">Blog, naskah video, caption, cerpen.</p></div>
    </div>
  </div>
</section>

<section class="section-white py-28">
  <div class="max-w-5xl mx-auto px-6">
    <div class="text-center mb-16 reveal">
      <p class="text-[11px] font-bold text-black/20 uppercase tracking-[0.15em] mb-3">Fitur</p>
      <h2 class="text-[38px] font-bold tracking-[-0.02em] mb-3">Lebih dari sekadar chat.</h2>
      <p class="text-[15px] text-black/30 max-w-lg mx-auto">Tool menulis lengkap dalam satu tempat.</p>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
      <div class="card p-10 flex flex-col items-center text-center gap-4 reveal"><span class="text-3xl">✏️</span><h3 class="text-lg font-bold">6 Mode Menulis</h3><p class="text-sm text-black/35">Tulis, Perbaiki, Terjemahkan, Ringkas, Lanjutkan, Analisis.</p></div>
      <div class="card p-10 flex flex-col items-center text-center gap-4 reveal reveal-1"><span class="text-3xl">📋</span><h3 class="text-lg font-bold">20+ Template</h3><p class="text-sm text-black/35">Skripsi, jurnal, email, CV. Pilih — AI kerjakan sisanya.</p></div>
      <div class="card p-10 flex flex-col items-center text-center gap-4 reveal reveal-2"><span class="text-3xl">📤</span><h3 class="text-lg font-bold">Export DOCX/PDF</h3><p class="text-sm text-black/35">Langsung export. Siap submit, siap kirim.</p></div>
    </div>
  </div>
</section>

<section id="how" class="section-warm py-28">
  <div class="max-w-3xl mx-auto px-6">
    <div class="text-center mb-20 reveal">
      <p class="text-[11px] font-bold text-black/20 uppercase tracking-[0.15em] mb-3">Cara Kerja</p>
      <h2 class="text-[38px] font-bold tracking-[-0.02em]">Dari ide ke dokumen.<br>Tiga langkah.</h2>
    </div>
    <div class="space-y-16">
      <div class="flex flex-col items-center text-center gap-5 reveal"><div class="w-12 h-12 rounded-2xl bg-[#1a1a28] flex items-center justify-center text-white text-lg font-bold shadow-lg">1</div><h3 class="text-xl font-bold">Pilih template atau tulis bebas</h3><p class="text-[15px] text-black/30 max-w-sm">20+ template siap pakai. Atau langsung tulis apa yang kamu butuhkan.</p></div>
      <div class="flex flex-col items-center text-center gap-5 reveal reveal-1"><div class="w-12 h-12 rounded-2xl bg-[#1a1a28] flex items-center justify-center text-white text-lg font-bold shadow-lg">2</div><h3 class="text-xl font-bold">AI menulis, kamu mengarahkan</h3><p class="text-[15px] text-black/30 max-w-sm">Kasih konteks — AI tulis draf lengkap. Mau revisi? Tinggal bilang.</p></div>
      <div class="flex flex-col items-center text-center gap-5 reveal reveal-2"><div class="w-12 h-12 rounded-2xl bg-[#b8975a] flex items-center justify-center text-white text-lg font-bold shadow-lg">3</div><h3 class="text-xl font-bold">Export, kirim, selesai</h3><p class="text-[15px] text-black/30 max-w-sm">Langsung DOCX, PDF, atau Markdown. Satu klik.</p></div>
    </div>
  </div>
</section>

<section id="demo" class="section-white py-28">
  <div class="max-w-3xl mx-auto px-6 reveal">
    <div class="card p-10 lg:p-14 shadow-lg">
      <div class="text-center mb-10"><h2 class="text-[28px] font-bold tracking-[-0.02em] mb-2">Lihat sendiri</h2><p class="text-[15px] text-black/30">Dari "tolong buatin" ke dokumen jadi.</p></div>
      <div class="max-w-xl mx-auto space-y-5">
        <div class="flex justify-end"><div class="bg-[#1a1a28] text-white/90 rounded-2xl rounded-br-md px-5 py-3.5 text-sm max-w-[75%] shadow-lg">Buat pendahuluan skripsi tentang dampak AI pada pembelajaran Bahasa Inggris di universitas Indonesia. Pakai bahasa akademik + sitasi.</div></div>
        <div class="flex gap-3"><div class="w-7 h-7 rounded-lg bg-[#1a1a28] flex-shrink-0 flex items-center justify-center shadow"><span class="text-white text-[9px] font-bold">T</span></div><div class="bg-gray-50 rounded-2xl rounded-bl-md px-5 py-4 text-sm text-black/60 max-w-[82%] border border-black/[0.04]"><p class="font-semibold text-black/70 text-[12px] mb-2">1.1 Latar Belakang</p><p>Perkembangan kecerdasan buatan dalam satu dekade terakhir telah mentransformasi lanskap pendidikan tinggi secara fundamental...</p><p class="text-black/20 text-[11px] mt-3">AI sedang menulis...</p></div></div>
      </div>
    </div>
  </div>
</section>

<section id="pricing" class="section-warm py-28">
  <div class="max-w-4xl mx-auto px-6">
    <div class="text-center mb-16 reveal">
      <p class="text-[11px] font-bold text-black/20 uppercase tracking-[0.15em] mb-3">Harga</p>
      <h2 class="text-[38px] font-bold tracking-[-0.02em] mb-3">Mulai gratis. Upgrade saat butuh.</h2>
      <p class="text-[15px] text-black/30 max-w-lg mx-auto">Harga Indonesia. Bukan harga Silicon Valley.</p>
    </div>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-5 items-start">
      <div class="card p-8 flex flex-col items-center text-center reveal">
        <p class="text-lg font-bold mb-1">Gratis</p><p class="text-[42px] font-extrabold tracking-[-0.02em] mb-1">Rp 0</p><p class="text-xs text-black/30 mb-8">selamanya</p>
        <ul class="space-y-2.5 mb-8 text-[13px] text-black/40 w-full"><li>3 percakapan/hari</li><li>Flash (cepat)</li><li>6 mode menulis</li><li class="text-black/20">Export premium</li></ul>
        <a href="register.html" class="btn-secondary w-full py-3 text-sm">Mulai Gratis</a>
      </div>
      <div class="pricing-featured card p-8 flex flex-col items-center text-center reveal reveal-1 scale-[1.04]">
        <div class="bg-[#b8975a]/10 rounded-full px-3 py-1 mb-3"><span class="text-[10px] text-gold font-bold">PALING POPULER</span></div>
        <p class="text-lg font-bold mb-1">Flash 1.5M</p><p class="text-[42px] font-extrabold tracking-[-0.02em] mb-1">Rp 49.900</p><p class="text-xs text-black/30 mb-8">1.500.000 token</p>
        <ul class="space-y-2.5 mb-8 text-[13px] text-black/40 w-full"><li>Semua fitur Gratis</li><li>1.5M token (750 hal)</li><li>Export DOCX/PDF</li><li>20+ template premium</li></ul>
        <a href="register.html" class="btn-primary w-full py-3 text-sm">Pilih Flash 1.5M</a>
      </div>
      <div class="card p-8 flex flex-col items-center text-center reveal reveal-2">
        <p class="text-lg font-bold mb-1">Pro 2M</p><p class="text-[42px] font-extrabold tracking-[-0.02em] mb-1">Rp 399.000</p><p class="text-xs text-black/30 mb-8">2.000.000 token</p>
        <ul class="space-y-2.5 mb-8 text-[13px] text-black/40 w-full"><li>Semua fitur Flash</li><li>Model Pro (cerdas)</li><li>Riset & sitasi</li><li>Upload dokumen</li></ul>
        <a href="register.html" class="btn-secondary w-full py-3 text-sm">Pilih Pro 2M</a>
      </div>
    </div>
  </div>
</section>

<section class="section-white py-28">
  <div class="max-w-5xl mx-auto px-6">
    <div class="text-center mb-16 reveal"><p class="text-[11px] font-bold text-black/20 uppercase tracking-[0.15em] mb-3">Testimoni</p><h2 class="text-[38px] font-bold tracking-[-0.02em]">Dipercaya penulis Indonesia.</h2></div>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-5">
      <div class="card p-8 flex flex-col items-center text-center gap-3 reveal"><div class="text-amber-400 text-sm">★★★★★</div><p class="text-sm text-black/50 italic">"Bab 1 skripsi yang seminggu jadi 2 hari. Sitasi otomatisnya gila."</p><p class="text-xs font-semibold mt-2">Rina F.</p><p class="text-[11px] text-black/30">Mahasiswi, UI</p></div>
      <div class="card p-8 flex flex-col items-center text-center gap-3 reveal reveal-1"><div class="text-amber-400 text-sm">★★★★★</div><p class="text-sm text-black/50 italic">"Terjemahan akademiknya jauh lebih natural dari Google Translate."</p><p class="text-xs font-semibold mt-2">Dr. Dewi P.</p><p class="text-[11px] text-black/30">Dosen, UB</p></div>
      <div class="card p-8 flex flex-col items-center text-center gap-3 reveal reveal-2"><div class="text-amber-400 text-sm">★★★★★</div><p class="text-sm text-black/50 italic">"Proposal klien 3 jam jadi 20 menit. 4 klien baru dapet."</p><p class="text-xs font-semibold mt-2">Andi R.</p><p class="text-[11px] text-black/30">CEO, EdTech</p></div>
    </div>
  </div>
</section>

<section class="section-warm py-28">
  <div class="max-w-2xl mx-auto px-6 text-center reveal">
    <div class="card p-14 shadow-lg">
      <h2 class="text-[34px] font-extrabold tracking-[-0.02em] mb-4">Siap nulis lebih cepat?</h2>
      <p class="text-base text-black/30 mb-8">Gabung dengan ribuan penulis Indonesia.</p>
      <a href="register.html" class="btn-primary inline-block text-base px-12 py-4">Mulai Gratis Sekarang</a>
      <p class="text-xs text-black/18 mt-4">Tanpa kartu kredit. 30 detik daftar.</p>
    </div>
  </div>
</section>

<footer class="section-dark py-8">
  <div class="max-w-5xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
    <div class="flex items-center gap-2.5"><div class="w-6 h-6 rounded-md bg-white/20 flex items-center justify-center"><span class="text-white text-[9px] font-bold">T</span></div><span class="text-xs font-semibold text-white/40">TokenLine 2026</span></div>
    <div class="flex items-center gap-6 text-xs text-white/30"><a href="about.html" class="hover:text-white/60 transition-colors">Tentang</a><a href="privacy.html" class="hover:text-white/60 transition-colors">Privasi</a><a href="tos.html" class="hover:text-white/60 transition-colors">Syarat</a></div>
  </div>
</footer>

<script src="tokenline-i18n.js"></script>
</body>
</html>'''

with open('f:/ClaudeFiles/_research/index-v8.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f'Written v8: {len(html)} bytes')
