PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    phone TEXT DEFAULT '',
    phone_verified INTEGER DEFAULT 0,
    otp_hash TEXT DEFAULT '',
    otp_expires_at TEXT DEFAULT '',
    name TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    status INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    plan TEXT NOT NULL,
    started_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    daily_used INTEGER DEFAULT 0,
    token_balance INTEGER DEFAULT 0,
    last_reset_date TEXT DEFAULT '',
    status INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    xendit_invoice_id TEXT UNIQUE,
    plan TEXT NOT NULL,
    amount INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now')),
    paid_at TEXT
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT DEFAULT 'New Chat',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    model TEXT DEFAULT 'deepseek-v4-flash',
    tokens INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cost_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model TEXT DEFAULT 'deepseek-v4-flash',
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_micro_usd INTEGER DEFAULT 0,
    requests INTEGER DEFAULT 0,
    tokens INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_cost_log_created ON cost_log(created_at);
