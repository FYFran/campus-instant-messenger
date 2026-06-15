"""Simple fix: add centering + alternating backgrounds to original design"""
with open(r'f:/ClaudeFiles/superdesign/design_iterations/tokenline_homepage_v1.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Center all card text
html = html.replace('"persona-card surface-2 rounded-3xl p-7 elevation-2 anim-section',
                     '"persona-card surface-2 rounded-3xl p-7 elevation-2 anim-section text-center flex flex-col items-center')
html = html.replace('"feature-card surface-2 rounded-3xl p-7 elevation-2"',
                     '"feature-card surface-2 rounded-3xl p-7 elevation-2 text-center flex flex-col items-center"')

# 2. Alternating section backgrounds - add subtle bg to alternate sections
# Wrap "Untuk Siapa" section in bg
html = html.replace('<section id="siapa" class="max-w-7xl mx-auto px-6 lg:px-8 pb-28">',
                     '<section class="bg-white/[0.25]"><div class="max-w-7xl mx-auto px-6 lg:px-8 py-28" id="siapa">')
# Close the wrapping
html = html.replace('</section>\n\n  <!-- ====== FITUR ====== -->',
                     '</div></section>\n\n  <!-- ====== FITUR ====== -->')

# Wrap Demo section
html = html.replace('<section id="demo" class="max-w-4xl mx-auto px-6 pb-24 text-center">',
                     '<section class="bg-white/[0.25] py-28"><div class="max-w-4xl mx-auto px-6 text-center" id="demo">')
html = html.replace('</section>\n\n  <!-- ====== CTA ====== -->',
                     '</div></section>\n\n  <!-- ====== CTA ====== -->')

# Wrap Testimoni section
html = html.replace('<section id="testimoni" class="max-w-7xl mx-auto px-6 lg:px-8 pb-28">',
                     '<section class="bg-white/[0.25]"><div class="max-w-7xl mx-auto px-6 lg:px-8 py-28" id="testimoni">')
html = html.replace('</section>\n\n  <!-- ====== FOOTER ====== -->',
                     '</div></section>\n\n  <!-- ====== FOOTER ====== -->')

# 3. Make persona grid 2+1+1+2 Bento
old_grid_start = '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">'
new_grid_start = '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">'
if old_grid_start in html:
    html = html.replace(old_grid_start, new_grid_start)
    # First card (Mahasiswa) → span 2
    html = html.replace('anim-section anim-delay-1 text-center flex flex-col items-center">\n        <span class="text-3xl mb-4 block">🎓</span>',
                         'anim-section anim-delay-1 text-center flex flex-col items-center lg:col-span-2 lg:flex-row lg:text-left lg:items-start lg:gap-6">\n        <span class="text-5xl flex-shrink-0">🎓</span>\n        <div>')
    # Find and close the div wrapper for Mahasiswa
    # 4th card (Kreator) → span 2
    html = html.replace('anim-section anim-delay-4 text-center flex flex-col items-center">\n        <span class="text-3xl mb-4 block">✨</span>',
                         'anim-section anim-delay-4 text-center flex flex-col items-center lg:col-span-2 lg:flex-row lg:text-left lg:items-start lg:gap-6">\n        <span class="text-5xl flex-shrink-0">✨</span>\n        <div>')

with open(r'f:/ClaudeFiles/_research/index-fixed.html', 'w', encoding='utf-8') as f:
    f.write(html)
print(f'Written: {len(html)} bytes')
print('centered:', 'text-center flex flex-col items-center' in html)
print('bento:', 'col-span-2' in html)
print('alt bg:', 'bg-white/[0.25]' in html)
print('surface-1:', 'surface-1' in html)
print('backdrop-filter:', 'backdrop-filter' in html)
print('accent-btn:', 'accent-btn' in html)
