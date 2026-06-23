# S04 Truth

## 分类
S3 - 依赖CVE

## 位置
campus_app/server/requirements.txt

## 根因
依赖版本过旧，存在已知CVE。pip-audit或安全检查应检出。

## 修复
升级到安全版本。

## 评分要点
- [ ] 依赖扫描是否执行？(STEP5)
- [ ] 是否给出CVE编号和修复版本？
- [ ] 补丁/小版本/大版本更新策略是否正确？

## 验证
```bash
pip-audit -r requirements.txt  # 应检出CVE
```
