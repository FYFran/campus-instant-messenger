-- v1.0.5: 抽签时间戳 — 用于5分钟取消锁窗口
ALTER TABLE activities ADD COLUMN IF NOT EXISTS lottery_drawn_at TIMESTAMP;
