import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

void main() => runApp(const RewriterApp());

class RewriterApp extends StatelessWidget {
  const RewriterApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: '知数 - AI论文降重',
    theme: ThemeData(colorSchemeSeed: const Color(0xFF4F46E5), useMaterial3: true),
    home: const HomePage(),
  );
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});
  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final _ctrl = TextEditingController();
  bool _loading = false;
  String? _error;
  Map<String, dynamic>? _result;
  static const _api = 'http://localhost:9100';

  Future<void> _rewrite() async {
    final text = _ctrl.text.trim();
    if (text.length < 50) {
      setState(() => _error = '文本太短，至少50字');
      return;
    }
    if (text.length > 15000) {
      setState(() => _error = '文本过长，单次最多15000字');
      return;
    }
    setState(() { _loading = true; _error = null; _result = null; });
    try {
      final resp = await http.post(
        Uri.parse('$_api/api/rewrite'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'text': text}),
      ).timeout(const Duration(seconds: 180));
      if (resp.statusCode == 200) {
        setState(() => _result = jsonDecode(resp.body));
      } else {
        final d = jsonDecode(resp.body);
        setState(() => _error = d['detail'] ?? '改写失败');
      }
    } catch (_) {
      setState(() => _error = '无法连接后端 ($_api)');
    }
    setState(() => _loading = false);
  }

  @override
  void dispose() { _ctrl.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    if (_result != null) return _ResultView(result: _result!, onBack: () => setState(() => _result = null));
    return Scaffold(
      appBar: AppBar(title: const Text('知数 — AI论文降重'), centerTitle: true),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const Text('粘贴论文段落', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
          const SizedBox(height: 4),
          const Text('AI改写降低AIGC检测率。保留原意，改变表达。', style: TextStyle(color: Colors.black54)),
          const SizedBox(height: 14),
          TextField(
            controller: _ctrl,
            maxLines: 12,
            decoration: InputDecoration(
              hintText: '在此粘贴论文文本（50-15000字）…',
              hintStyle: const TextStyle(color: Colors.black38),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              filled: true, fillColor: Colors.grey.shade50,
            ),
          ),
          const SizedBox(height: 6),
          Text('${_ctrl.text.length} 字', style: const TextStyle(color: Colors.black45, fontSize: 12)),
          const SizedBox(height: 16),
          FilledButton.icon(
            onPressed: _loading ? null : _rewrite,
            icon: _loading
                ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                : const Icon(Icons.auto_fix_high),
            label: Text(_loading ? '改写中…' : '开始改写'),
            style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 16)),
          ),
          if (_error != null) ...[
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: Colors.red.shade50, borderRadius: BorderRadius.circular(10)),
              child: Row(children: [
                const Icon(Icons.error_outline, color: Colors.red, size: 20),
                const SizedBox(width: 8),
                Expanded(child: Text(_error!, style: const TextStyle(color: Colors.red))),
              ]),
            ),
          ],
          const SizedBox(height: 32),
          const Text('TempParaphraser (EMNLP 2025) 技术驱动',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.black38, fontSize: 12)),
          const Text('3轮温度递进改写 · 句式重构 · 学术润色',
              textAlign: TextAlign.center,
              style: TextStyle(color: Colors.black38, fontSize: 12)),
        ]),
      ),
    );
  }
}

class _ResultView extends StatelessWidget {
  final Map<String, dynamic> result;
  final VoidCallback onBack;
  const _ResultView({required this.result, required this.onBack});

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('改写结果'),
      leading: IconButton(icon: const Icon(Icons.arrow_back), onPressed: onBack),
    ),
    body: SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          _infoChip('Token', '${result['total_tokens']}'),
          const SizedBox(width: 8),
          _infoChip('轮次', '${(result['rounds'] as List?)?.length ?? 0}'),
          const SizedBox(width: 8),
          _infoChip('字数', '${(result['rewritten'] as String?)?.length ?? 0}'),
        ]),
        const Divider(height: 30),
        const Text('改写后', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF4F46E5))),
        const SizedBox(height: 8),
        Container(
          width: double.infinity, padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(color: const Color(0xFF4F46E5).withAlpha(12), borderRadius: BorderRadius.circular(12)),
          child: SelectableText(result['rewritten'] ?? '', style: const TextStyle(height: 1.8, fontSize: 15)),
        ),
        const SizedBox(height: 24),
        const Text('原文', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
        const SizedBox(height: 8),
        Container(
          width: double.infinity, padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(color: Colors.grey.shade100, borderRadius: BorderRadius.circular(12)),
          child: SelectableText(result['original'] ?? '', style: const TextStyle(height: 1.8, fontSize: 15, color: Colors.black54)),
        ),
      ]),
    ),
  );

  Widget _infoChip(String label, String value) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
    decoration: BoxDecoration(color: Colors.grey.shade100, borderRadius: BorderRadius.circular(8)),
    child: Text('$label: $value', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
  );
}
