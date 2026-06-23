-- v1.0.5: 刷新token持久化
ALTER TABLE users ADD COLUMN IF NOT EXISTS refresh_token_hash VARCHAR(128);
ALTER TABLE users ADD COLUMN IF NOT EXISTS refresh_token_exp TIMESTAMP;
