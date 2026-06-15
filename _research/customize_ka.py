import re

# 1. CUSTOMIZE CSS
with open(r'f:/ClaudeFiles/_research/ka-template/assets/css/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

# CSS variable replacements for TokenLine
replacements = {
    '--bg: 248 250 252;': '--bg: 250 249 246;',
    '--fg: 15 23 42;': '--fg: 26 26 44;',
    '--muted: 71 85 105;': '--muted: 100 100 120;',
    '--surface-soft: 241 245 249;': '--surface-soft: 245 244 241;',
    '--primary: 99 102 241;': '--primary: 26 26 44;',
    '--secondary: 139 92 246;': '--secondary: 184 151 90;',
    '--accent: 6 182 212;': '--accent: 184 151 90;',
}
for old, new in replacements.items():
    css = css.replace(old, new)

# Replace color references in rgba/rgb
css = re.sub(r'rgba\(99,\s*102,\s*241', 'rgba(26, 26, 44', css)
css = re.sub(r'rgba\(139,\s*92,\s*246', 'rgba(184, 151, 90', css)
css = re.sub(r'rgba\(6,\s*182,\s*212', 'rgba(184, 151, 90', css)
css = re.sub(r'rgb\(99,\s*102,\s*241\)', 'rgb(26, 26, 44)', css)
css = re.sub(r'rgb\(139,\s*92,\s*246\)', 'rgb(184, 151, 90)', css)
css = re.sub(r'rgb\(6,\s*182,\s*212\)', 'rgb(184, 151, 90)', css)

# Dark mode
css = css.replace('--bg: 11 17 32;', '--bg: 18 18 28;')
css = css.replace('--fg: 226 232 240;', '--fg: 235 235 245;')
css = css.replace('--surface: 15 23 42;', '--surface: 24 24 36;')
css = css.replace('--surface-soft: 15 23 42;', '--surface-soft: 22 22 32;')
css = css.replace('--surface-strong: 30 41 59;', '--surface-strong: 32 32 48;')

# Font
css = css.replace('"Plus Jakarta Sans", "Inter", sans-serif', '"Inter", system-ui, sans-serif')

with open(r'f:/ClaudeFiles/_research/ka-template/assets/css/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
print('CSS done')

# 2. CUSTOMIZE INDEX.HTML
with open(r'f:/ClaudeFiles/_research/ka-template/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace indigo classes with our primary
html = html.replace('bg-indigo-500', 'bg-[#1a1a2c]')
html = html.replace('text-indigo-500', 'text-[#1a1a2c]')
html = html.replace('bg-indigo-50', 'bg-[#1a1a2c]/[0.06]')
html = html.replace('text-indigo-600', 'text-[#1a1a2c]')
html = html.replace('hover:bg-indigo-500', 'hover:bg-[#2a2a44]')
html = html.replace('ring-indigo-500', 'ring-[#1a1a2c]')

# Replace branding
html = html.replace('KA-Launchly', 'TokenLine')
html = html.replace('Startup Template', 'AI Writing')
html = html.replace('ka-theme', 'tl-theme')

# Replace title and meta
html = html.replace('<title>Home Landing | KA-Launchly</title>', '<title>TokenLine — Asisten Menulis AI Premium</title>')
html = html.replace('KA-Launchly home landing page for startup, SaaS and AI products', 'Asisten AI untuk menulis skripsi, jurnal, proposal, dan email bisnis dalam Bahasa Indonesia alami')
html = html.replace('<meta name="theme-color" content="#0B1120" />', '<meta name="theme-color" content="#faf9f6" />')

# Replace nav links
html = html.replace('./pages/features.html', '#fitur')
html = html.replace('./pages/product-overview.html', '#cara-kerja')
html = html.replace('./pages/pricing.html', '#harga')
html = html.replace('./pages/blog/grid.html', 'dashboard.html')
html = html.replace('./pages/docs/index.html', 'chat-pro.html')
html = html.replace('./pages/contact.html', '#testimoni')
html = html.replace('./pages/auth/login.html', 'login.html')
html = html.replace('./pages/auth/register.html', 'register.html')

# Replace hero content
old_hero_badge = 'Premium multi-page startup system'
new_hero_badge = 'DeepSeek V4 · Harga Indonesia · 100% Bahasa Alami'
html = html.replace(old_hero_badge, new_hero_badge)

old_kicker = 'Startup &amp; SaaS Website Template'
new_kicker = 'Asisten Menulis AI'
html = html.replace(old_kicker, new_kicker)

old_h1 = 'Launch a premium startup website with the polish of a funded product brand.'
new_h1 = 'Tulis apa pun. Cukup bilang mau apa.'
html = html.replace(old_h1, new_h1)

old_p = 'KA-Launchly is a multi-page HTML template for SaaS companies, AI tools, software products and ambitious startups that want a modern, marketplace-grade web presence.'
new_p = 'Skripsi, jurnal, proposal bisnis, email klien — AI yang ngerti konteks Indonesia. Bukan chatbot biasa. Dirancang khusus untuk penulis, peneliti, profesional, dan kreator.'
html = html.replace(old_p, new_p)

# CTA buttons
html = html.replace('>Get Started<', '>Mulai Gratis<')
html = html.replace('>Watch Demo<', '>Lihat Demo<')
html = html.replace('>Login<', '>Masuk<')

# Remove announcement bar using simple string match
ann_start = '<!--'
# Just remove the announcement div by matching its start
old_ann = html.find('announcement mb-3')
if old_ann > 0:
    # Find the closing </div> of announcement
    start = html.rfind('<div', 0, old_ann)
    depth = 1
    i = old_ann
    while depth > 0 and i < len(html):
        if html[i:i+4] == '<div':
            depth += 1
            i += 4
        elif html[i:i+5] == '</div':
            depth -= 1
            if depth == 0:
                html = html[:start] + html[i+6:]
                break
            i += 6
        else:
            i += 1
    print('Announcement removed')

# Replace stat cards
html = html.replace("30+ pages ready", "12.000+ Penulis Aktif")
html = html.replace("Landing, product, pricing, blog, docs, auth, support and utility pages included.", "Dipercaya mahasiswa, dosen, profesional, dan kreator di seluruh Indonesia.")
html = html.replace("Tailwind + Vanilla JS", "85.000+ Dokumen Dibuat")
html = html.replace("Easy to customize without framework lock-in or bloated interaction layers.", "Skripsi, jurnal, proposal bisnis, email -- semua selesai lebih cepat.")

with open(r'f:/ClaudeFiles/_research/ka-template/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('HTML customized')
print(f'Total bytes: {len(html)}')
"