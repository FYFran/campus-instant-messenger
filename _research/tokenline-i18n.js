/**
 * TokenLine i18n — Indonesian (default) / English / 中文
 * Usage: <script src="tokenline-i18n.js"></script>
 *        All elements with data-i18n="key" get translated.
 *        Language saved to localStorage('tl_lang').
 */
const TL_I18N = {
  lang: localStorage.getItem('tl_lang') || 'id',

  dict: {
    // ====== NAV ======
    nav_home:         { id: 'Beranda',       en: 'Home',         zh: '首页' },
    nav_for:          { id: 'Untuk Siapa',    en: 'Who Is It For', zh: '适用人群' },
    nav_features:     { id: 'Fitur',          en: 'Features',     zh: '功能' },
    nav_pricing:      { id: 'Harga',          en: 'Pricing',      zh: '价格' },
    nav_testimonials: { id: 'Testimoni',      en: 'Testimonials', zh: '用户评价' },
    nav_login:        { id: 'Masuk',          en: 'Sign In',      zh: '登录' },
    nav_start:        { id: 'Mulai Gratis',   en: 'Start Free',   zh: '免费开始' },
    nav_demo:         { id: 'Lihat Demo',     en: 'See Demo',     zh: '查看演示' },

    // ====== HERO ======
    hero_badge:       { id: 'DeepSeek V4 · Harga Indonesia · 100% Bahasa alami',
                        en: 'DeepSeek V4 · Indonesian Pricing · 100% Natural Language',
                        zh: 'DeepSeek V4 · 印尼本地定价 · 100% 自然语言' },
    hero_problem:     { id: 'Tugas menumpuk? Deadline mepet? Bingung mulai dari mana?',
                        en: 'Assignments piling up? Deadlines looming? Not sure where to start?',
                        zh: '作业堆积？截止日期逼近？不知从何下手？' },
    hero_title:       { id: 'Tulis apa pun — skripsi, jurnal, proposal, email bisnis — dalam Bahasa Indonesia alami',
                        en: 'Write anything — thesis, journal, proposal, business email — in natural language',
                        zh: '写任何东西——论文、期刊、提案、商业邮件——用自然语言' },
    hero_subtitle:    { id: 'Asisten AI yang mengerti konteks Indonesia. Bukan chatbot biasa — dirancang khusus untuk penulis, peneliti, profesional, dan kreator.',
                        en: 'AI assistant that understands your context. Not just a chatbot — designed for writers, researchers, professionals, and creators.',
                        zh: '懂你语境的AI助手。不是普通聊天机器人——专为写作者、研究者、职场人士和创作者设计。' },
    hero_cta1:        { id: 'Mulai Gratis — 3 percakapan/hari',
                        en: 'Start Free — 3 conversations/day',
                        zh: '免费开始 — 每天3次对话' },
    hero_cta2:        { id: 'Lihat Demo →',
                        en: 'See Demo →',
                        zh: '查看演示 →' },
    hero_nocc:        { id: 'Tanpa kartu kredit · 30 detik daftar · Batal kapan saja',
                        en: 'No credit card · 30s signup · Cancel anytime',
                        zh: '无需信用卡 · 30秒注册 · 随时取消' },

    // ====== SOCIAL PROOF ======
    stat_active:      { id: 'Penulis Aktif',   en: 'Active Writers',    zh: '活跃写作者' },
    stat_docs:        { id: 'Dokumen Dibuat',  en: 'Documents Created', zh: '已创建文档' },
    stat_rating:      { id: 'Rating Pengguna', en: 'User Rating',       zh: '用户评分' },
    stat_ontime:      { id: 'Tepat Waktu',     en: 'On Time',           zh: '准时交付' },

    // ====== PERSONAS ======
    persona_title:    { id: 'Satu alat. Banyak kebutuhan.',
                        en: 'One tool. Many needs.',
                        zh: '一个工具。多种需求。' },
    persona_sub:      { id: 'Dirancang untuk siapa pun yang perlu menulis — dari mahasiswa hingga CEO.',
                        en: 'Designed for anyone who needs to write — from students to CEOs.',
                        zh: '为需要写作的人设计——从学生到CEO。' },
    p1_title:         { id: 'Mahasiswa',          en: 'Students',            zh: '学生' },
    p1_desc:          { id: 'Skripsi, tesis, makalah, jurnal, abstrak. Sitasi akademik lengkap. Bimbingan menulis 24/7.',
                        en: 'Thesis, papers, journals, abstracts. Complete academic citations. 24/7 writing guidance.',
                        zh: '论文、报告、期刊、摘要。完整学术引用。全天候写作指导。' },
    p2_title:         { id: 'Dosen & Peneliti',   en: 'Researchers',         zh: '研究者' },
    p2_desc:          { id: 'Jurnal internasional, proposal hibah, laporan penelitian. Format IEEE/APA siap submit.',
                        en: 'International journals, grant proposals, research reports. IEEE/APA ready to submit.',
                        zh: '国际期刊、基金申请、研究报告。IEEE/APA格式即交。' },
    p3_title:         { id: 'Profesional',        en: 'Professionals',       zh: '职场人士' },
    p3_desc:          { id: 'Email klien, proposal bisnis, laporan tahunan, presentasi. Bahasa formal & persuasif.',
                        en: 'Client emails, business proposals, annual reports, presentations. Formal & persuasive.',
                        zh: '客户邮件、商业提案、年报、演示文稿。正式且有说服力。' },
    p4_title:         { id: 'Kreator & Penulis',  en: 'Creators & Writers',  zh: '创作者与写作者' },
    p4_desc:          { id: 'Artikel blog, naskah video, caption, cerpen, buku. Gaya bahasa fleksibel & kreatif.',
                        en: 'Blog articles, video scripts, captions, short stories, books. Flexible & creative style.',
                        zh: '博客文章、视频脚本、文案、短篇小说、书籍。灵活且有创意。' },

    // ====== FEATURES ======
    feat_title:       { id: 'Lebih dari sekadar chat.',
                        en: 'More than just chat.',
                        zh: '不止于聊天。' },
    feat_sub:         { id: 'Alat tulis lengkap yang mengerti cara Anda bekerja.',
                        en: 'Complete writing tools that understand how you work.',
                        zh: '懂你工作方式的完整写作工具。' },
    f1_title:         { id: '6 Mode Menulis',         en: '6 Writing Modes',       zh: '6种写作模式' },
    f1_desc:          { id: 'Tulis, Perbaiki, Terjemahkan, Ringkas, Lanjutkan, Analisis — semua dalam satu tempat.',
                        en: 'Write, Improve, Translate, Summarize, Continue, Analyze — all in one place.',
                        zh: '写作、润色、翻译、摘要、续写、分析——一站式完成。' },
    f2_title:         { id: '20+ Template Profesional', en: '20+ Professional Templates', zh: '20+专业模板' },
    f2_desc:          { id: 'Skripsi, jurnal, proposal bisnis, email, CV — pilih template, isi konteks, langsung jadi.',
                        en: 'Thesis, journal, business proposal, email, CV — pick a template, fill context, done.',
                        zh: '论文、期刊、商业提案、邮件、简历——选模板、填内容、即完成。' },
    f3_title:         { id: 'Export Multi-Format',    en: 'Multi-Format Export',    zh: '多格式导出' },
    f3_desc:          { id: 'Langsung export ke DOCX, PDF, Markdown. Siap kirim, siap submit, siap cetak.',
                        en: 'Export directly to DOCX, PDF, Markdown. Ready to send, submit, print.',
                        zh: '直接导出为DOCX、PDF、Markdown。随时发送、提交、打印。' },
    f4_title:         { id: 'Riset & Sitasi Otomatis', en: 'Auto Research & Citation', zh: '自动研究引用' },
    f4_desc:          { id: 'AI mencari sumber akademik terbaru, menyitasi otomatis dalam format APA/IEEE/MLA.',
                        en: 'AI finds latest academic sources, auto-cites in APA/IEEE/MLA format.',
                        zh: 'AI查找最新学术资源，自动以APA/IEEE/MLA格式引用。' },
    f5_title:         { id: 'Indonesia-Native',        en: 'Indonesia-Native',       zh: '印尼原生' },
    f5_desc:          { id: 'Prompt dalam Bahasa Indonesia alami. Paham konteks lokal, istilah akademik, dan budaya.',
                        en: 'Prompt in natural language. Understands local context, academic terms, and culture.',
                        zh: '自然语言提示。理解本地语境、学术术语和文化。' },
    f6_title:         { id: 'Dashboard Pribadi',       en: 'Personal Dashboard',     zh: '个人仪表盘' },
    f6_desc:          { id: 'Pantau penggunaan, produktivitas, penghematan waktu. Data visual yang bisa ditindaklanjuti.',
                        en: 'Track usage, productivity, time saved. Actionable visual data.',
                        zh: '追踪使用量、生产力、节省时间。可执行的可视化数据。' },

    // ====== PRICING ======
    price_title:      { id: 'Mulai gratis. Upgrade saat butuh.',
                        en: 'Start free. Upgrade when needed.',
                        zh: '免费开始。需要时升级。' },
    price_sub:        { id: 'Harga Indonesia. Bukan harga Silicon Valley.',
                        en: 'Indonesian pricing. Not Silicon Valley pricing.',
                        zh: '印尼本地价格。不是硅谷价格。' },
    price_popular:    { id: '⭐ PALING POPULER',       en: '⭐ MOST POPULAR',         zh: '⭐ 最受欢迎' },
    free_name:        { id: 'Gratis',                   en: 'Free',                    zh: '免费版' },
    free_price:       { id: 'Rp 0',                     en: 'Rp 0',                    zh: 'Rp 0' },
    free_period:      { id: 'selamanya',               en: 'forever',                 zh: '永久' },
    free_f1:          { id: '3 percakapan/hari',       en: '3 conversations/day',     zh: '每天3次对话' },
    free_f2:          { id: 'Model Flash (cepat)',     en: 'Flash model (fast)',      zh: 'Flash模型(快速)' },
    free_f3:          { id: '6 mode menulis',          en: '6 writing modes',         zh: '6种写作模式' },
    free_btn:         { id: 'Mulai Gratis',            en: 'Start Free',              zh: '免费开始' },
    flash_name:       { id: 'Flash 1.5M',              en: 'Flash 1.5M',              zh: 'Flash 1.5M' },
    flash_price:      { id: 'Rp 49.900',               en: 'Rp 49,900',               zh: 'Rp 49,900' },
    flash_period:     { id: '1.500.000 token',         en: '1,500,000 tokens',        zh: '1,500,000 token' },
    flash_f1:         { id: 'Semua fitur Gratis',      en: 'All Free features',       zh: '所有免费功能' },
    flash_f2:         { id: '1.5M token (≈ 750 halaman)', en: '1.5M tokens (~750 pages)', zh: '1.5M token (≈750页)' },
    flash_f3:         { id: 'Export DOCX / PDF',       en: 'Export DOCX / PDF',       zh: '导出DOCX/PDF' },
    flash_f4:         { id: '20+ template premium',    en: '20+ premium templates',   zh: '20+高级模板' },
    flash_btn:        { id: 'Pilih Flash 1.5M',        en: 'Choose Flash 1.5M',       zh: '选择 Flash 1.5M' },
    pro_name:         { id: 'Pro 2M',                  en: 'Pro 2M',                  zh: 'Pro 2M' },
    pro_price:        { id: 'Rp 399.000',              en: 'Rp 399,000',              zh: 'Rp 399,000' },
    pro_period:       { id: '2.000.000 token',         en: '2,000,000 tokens',        zh: '2,000,000 token' },
    pro_f1:           { id: 'Semua fitur Flash 1.5M',  en: 'All Flash features',      zh: '所有Flash功能' },
    pro_f2:           { id: 'Model Pro (paling cerdas)', en: 'Pro model (smartest)',  zh: 'Pro模型(最智能)' },
    pro_f3:           { id: 'Riset & sitasi otomatis', en: 'Auto research & citation', zh: '自动研究引用' },
    pro_f4:           { id: 'Upload & analisis dokumen', en: 'Document upload & analysis', zh: '文档上传分析' },
    pro_btn:          { id: 'Pilih Pro 2M',            en: 'Choose Pro 2M',           zh: '选择 Pro 2M' },

    // ====== TESTIMONIALS ======
    test_title:       { id: 'Dipercaya penulis di seluruh Indonesia.',
                        en: 'Trusted by writers across Indonesia.',
                        zh: '全印尼写作者信赖。' },
    t1_text:          { id: '"Ngerjain Bab 1 skripsi yang biasanya seminggu, sekarang 2 hari beres. Sitasi otomatisnya ngebantu banget."',
                        en: '"Chapter 1 of my thesis that usually takes a week was done in 2 days. The auto-citation helped tremendously."',
                        zh: '"论文第一章通常要一周，现在两天完成。自动引用帮了大忙。"' },
    t1_role:          { id: 'Mahasiswi S1, Univ. Indonesia',
                        en: 'Undergraduate, University of Indonesia',
                        zh: '本科生，印尼大学' },
    t2_text:          { id: '"Saya pakai TokenLine buat nulis manuscript jurnal ke Scopus. Terjemahan akademiknya jauh lebih natural."',
                        en: '"I use TokenLine for Scopus journal manuscripts. The academic translation is far more natural."',
                        zh: '"我用TokenLine写Scopus期刊手稿。学术翻译自然得多。"' },
    t2_role:          { id: 'Dosen, Universitas Brawijaya',
                        en: 'Lecturer, Brawijaya University',
                        zh: '讲师，布拉维贾亚大学' },
    t3_text:          { id: '"Buat proposal klien yang biasanya 3 jam, sekarang 20 menit. Udah 4 klien baru dapet gara-gara proposal yang lebih profesional."',
                        en: '"Client proposals that took 3 hours now take 20 minutes. Got 4 new clients thanks to more professional proposals."',
                        zh: '"客户提案从3小时缩短到20分钟。更专业的提案带来了4个新客户。"' },
    t3_role:          { id: 'CEO, Startup EdTech Jakarta',
                        en: 'CEO, EdTech Startup Jakarta',
                        zh: 'CEO，雅加达教育科技创业公司' },

    // ====== CTA ======
    cta_title:        { id: 'Siap menulis lebih cepat & lebih baik?',
                        en: 'Ready to write faster & better?',
                        zh: '准备好更快更好地写作了吗？' },
    cta_sub:          { id: 'Gabung dengan ribuan penulis Indonesia yang sudah menggunakan TokenLine.',
                        en: 'Join thousands of Indonesian writers already using TokenLine.',
                        zh: '加入成千上万已经在使用TokenLine的印尼写作者。' },
    cta_btn:          { id: 'Mulai Gratis Sekarang',
                        en: 'Start Free Now',
                        zh: '立即免费开始' },
    cta_nocc:         { id: 'Tanpa kartu kredit. 30 detik daftar.',
                        en: 'No credit card. 30 second signup.',
                        zh: '无需信用卡。30秒注册。' },

    // ====== FOOTER ======
    footer_about:     { id: 'Tentang',    en: 'About',       zh: '关于' },
    footer_privacy:   { id: 'Privasi',    en: 'Privacy',     zh: '隐私' },
    footer_terms:     { id: 'Syarat',     en: 'Terms',       zh: '条款' },
    footer_contact:   { id: 'Kontak',     en: 'Contact',     zh: '联系' },
    footer_tagline:   { id: 'Dibuat dengan ❤️ di Indonesia',
                        en: 'Made with ❤️ in Indonesia',
                        zh: '在印尼用❤️制作' },

    // ====== DASHBOARD ======
    dash_title:       { id: 'Dashboard',               en: 'Dashboard',               zh: '仪表盘' },
    dash_sub:         { id: 'Ringkasan aktivitas menulis Anda', en: 'Your writing activity summary', zh: '您的写作活动摘要' },
    dash_words:       { id: 'Kata Ditulis',            en: 'Words Written',            zh: '已写字数' },
    dash_docs:        { id: 'Dokumen Dibuat',          en: 'Documents Created',        zh: '已创建文档' },
    dash_time:        { id: 'Waktu Hemat',             en: 'Time Saved',               zh: '节省时间' },
    dash_tokens:      { id: 'Sisa Token',              en: 'Remaining Tokens',         zh: '剩余Token' },
    dash_activity:    { id: 'Aktivitas Menulis',       en: 'Writing Activity',         zh: '写作活动' },
    dash_templates:   { id: 'Template Terpakai',       en: 'Templates Used',           zh: '已用模板' },
    dash_recent:      { id: 'Aktivitas Terbaru',       en: 'Recent Activity',          zh: '最近活动' },
    dash_export:      { id: 'Export Laporan',          en: 'Export Report',            zh: '导出报告' },
    dash_7d:          { id: '7 hari terakhir',         en: 'Last 7 days',              zh: '最近7天' },
    dash_30d:         { id: '30 hari terakhir',        en: 'Last 30 days',             zh: '最近30天' },

    // ====== CHAT ======
    chat_new:         { id: 'Percakapan Baru',          en: 'New Conversation',        zh: '新建对话' },
    chat_modes:       { id: 'Mode Menulis',             en: 'Writing Modes',           zh: '写作模式' },
    chat_history:     { id: 'Riwayat',                  en: 'History',                 zh: '历史记录' },
    chat_templates:   { id: 'Template Cepat',           en: 'Quick Templates',         zh: '快速模板' },
    chat_export_docx: { id: 'Export DOCX',              en: 'Export DOCX',             zh: '导出DOCX' },
    chat_export_pdf:  { id: 'Export PDF',               en: 'Export PDF',              zh: '导出PDF' },
    chat_share:       { id: 'Bagikan',                  en: 'Share',                   zh: '分享' },
    chat_upgrade:     { id: 'Upgrade Pro',              en: 'Upgrade Pro',             zh: '升级专业版' },
    chat_placeholder: { id: 'Mulai menulis... pilih mode di sidebar kiri untuk hasil terbaik',
                        en: 'Start writing... select a mode in the left sidebar for best results',
                        zh: '开始写作...在左侧边栏选择模式以获得最佳效果' },
    chat_disclaimer:  { id: 'TokenLine bisa membuat kesalahan. Verifikasi informasi penting.',
                        en: 'TokenLine can make mistakes. Verify important information.',
                        zh: 'TokenLine可能出错。请核实重要信息。' },
    chat_writing:     { id: 'TokenLine menulis...',     en: 'TokenLine is writing...', zh: 'TokenLine正在写作...' },
    chat_mode_write:  { id: 'Tulis Baru',               en: 'Write New',               zh: '新写作' },
    chat_mode_improve:{ id: 'Perbaiki & Poles',         en: 'Improve & Polish',        zh: '润色优化' },
    chat_mode_trans:  { id: 'Terjemahkan',              en: 'Translate',               zh: '翻译' },
    chat_mode_summary:{ id: 'Ringkas Dokumen',          en: 'Summarize Document',      zh: '摘要文档' },
    chat_mode_analyze:{ id: 'Analisis Data',            en: 'Analyze Data',            zh: '数据分析' },
    chat_mode_ideas:  { id: 'Cari Ide & Riset',         en: 'Find Ideas & Research',   zh: '寻找创意与研究' },

    // ====== SETTINGS ======
    settings_title:   { id: 'Pengaturan',               en: 'Settings',                zh: '设置' },
    settings_profile: { id: 'Profil',                   en: 'Profile',                 zh: '个人资料' },
    settings_password:{ id: 'Ubah Password',            en: 'Change Password',         zh: '修改密码' },
    settings_phone:   { id: 'Verifikasi Telepon',       en: 'Phone Verification',      zh: '电话验证' },
    settings_theme:   { id: 'Tema',                     en: 'Theme',                   zh: '主题' },
    settings_lang:    { id: 'Bahasa',                   en: 'Language',                zh: '语言' },
    settings_logout:  { id: 'Keluar',                   en: 'Log Out',                 zh: '退出登录' },
  },

  // Apply translations to all [data-i18n] elements
  apply() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      const text = this.dict[key]?.[this.lang];
      if (text) {
        if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
          el.placeholder = text;
        } else {
          el.textContent = text;
        }
      }
    });
    // Update html lang attr
    document.documentElement.lang = this.lang === 'zh' ? 'zh-CN' : this.lang;
    // Save
    localStorage.setItem('tl_lang', this.lang);
    // Update all lang switchers
    document.querySelectorAll('.lang-switch').forEach(sw => {
      sw.querySelectorAll('button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.lang === this.lang);
      });
    });
  },

  // Switch language
  switch(lang) {
    this.lang = lang;
    this.apply();
  },

  // Get a single translation (for JS use)
  t(key) {
    return this.dict[key]?.[this.lang] || key;
  }
};

// Auto-apply on DOM ready
document.addEventListener('DOMContentLoaded', () => TL_I18N.apply());
