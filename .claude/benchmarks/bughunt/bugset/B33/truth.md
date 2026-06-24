# B33 — Ground Truth

**Type:** T0（稳定复现 — 慢网络或空 API 响应必白屏）

**根因:** Flutter 首页 `home_page.dart` 在 `initState` 或 `FutureBuilder` 中调用 API 获取活动列表。当 API 响应慢或返回 null 时，`FutureBuilder` 的 `snapshot.data` 为 null。代码直接在 `ListView.builder` 中使用 `snapshot.data.length` 或 `snapshot.data!`（null-assertion），导致 null 错误被 Flutter 框架捕获但未显示错误界面——页面渲染失败，显示空白。

具体模式：
```dart
FutureBuilder(
  future: fetchActivities(),
  builder: (context, snapshot) {
    if (snapshot.connectionState == ConnectionState.waiting) {
      return CircularProgressIndicator();
    }
    return ListView.builder(
      itemCount: snapshot.data!.length,  // null assertion → error → white screen
      ...
    );
  },
)
```

`snapshot.data!` 如果 data 是 null（网络错误或 JSON 解析失败但未 throw），null assertion 触发异常，Flutter 的 ErrorWidget 可能因为 build 方法无错误边界而显示空白。

**正确修复:**
```dart
if (snapshot.hasError || !snapshot.hasData) {
  return Center(child: Text('加载失败，下拉重试'));
}
final data = snapshot.data!;
return ListView.builder(itemCount: data.length, ...);
```

**文件:** `campus_app/lib/pages/home_page.dart`

**评分要点:**
- 分类: T0 — 慢网络/null 响应必白屏 (1pt)
- 证据: 白屏只在慢网络复现 + snapshot.data null 无检查 (1pt)
- 根因: home_page.dart — snapshot.data! 无 hasData 检查 → null assertion 异常 (2pt)
- CF: 加 hasData + hasError 检查 → 显示错误提示而非白屏 (1pt)
- 修复: 检查 snapshot.hasData 和 snapshot.hasError (1pt)
