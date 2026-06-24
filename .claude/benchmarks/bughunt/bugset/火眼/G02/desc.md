# G02: 火眼 — API错误响应不一致

## Bug描述
campus_go返回错误用`{"detail": "..."}`格式，campus_app/server返回错误用`{"error": "..."}`格式。两个后端API错误格式不统一。

## 难度
medium

## 维度
架构/API设计
