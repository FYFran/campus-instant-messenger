-- v1.0.8: 临时密码 + 强制修改标记 (教师辅助密码重置)
ALTER TABLE users ADD COLUMN IF NOT EXISTS temp_password_hash VARCHAR(128);
ALTER TABLE users ADD COLUMN IF NOT EXISTS temp_password_exp TIMESTAMP;
ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN DEFAULT FALSE;
