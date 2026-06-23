# C02 Truth

## 分类
C3 - 错误处理

## 位置
某Python handler中的try/except块

## 根因
bare except: pass吞没所有异常(包括KeyboardInterrupt/SystemExit)。错误静默丢失。

## 修复
捕获具体异常类型+记录日志或传播

## 评分
- [ ] Stage2错误处理检查触发？
- [ ] 是否识别为"绝不放过"模式？
- [ ] 修复建议含具体异常类型？
