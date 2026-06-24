-- v1.0.6: 账户禁用 — 管理员可停用违规账户
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
