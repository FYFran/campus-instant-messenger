import 'package:flutter_test/flutter_test.dart';
import 'package:rewriter_web/main.dart';

void main() {
  testWidgets('App renders', (WidgetTester tester) async {
    await tester.pumpWidget(const RewriterApp());
    expect(find.text('知数 — AI论文降重'), findsOneWidget);
  });
}
