-- Tasklet support agent schema.
-- Run via scripts/init_db.py (which also loads seed.sql).
--
-- Teaching notes:
-- * CHECK constraints duplicate the validation in src/models.py. That is
--   intentional — defense in depth, and a useful hint to anyone reading
--   either file alone.
-- * Indexes are on (user_id, ...) because every query in this app is
--   scoped by user_id. There is no query that scans across users.
-- * Conversation history is persisted in `conversations` and `messages`
--   so a Streamlit refresh or a re-launched CLI session can resume where
--   it left off.

CREATE TABLE users (
    id          INTEGER PRIMARY KEY,
    email       TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tickets (
    id           INTEGER PRIMARY KEY,
    user_id      INTEGER NOT NULL,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL,
    category     TEXT NOT NULL CHECK (category IN (
        'bug_report', 'feature_request', 'billing', 'integration_issue', 'how_to_question'
    )),
    priority     TEXT NOT NULL CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
        'open', 'in_progress', 'waiting_on_customer', 'resolved', 'closed'
    )),
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_tickets_user_status  ON tickets(user_id, status);
CREATE INDEX idx_tickets_user_created ON tickets(user_id, created_at);

CREATE TABLE conversations (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_conversations_user_updated ON conversations(user_id, updated_at);

-- `messages.content` is a JSON-encoded AgentMessage payload (see src/models.py).
-- Storing it as a single TEXT blob keeps the schema simple — we treat the
-- conversation log as an append-only event stream and never query inside it.
CREATE TABLE messages (
    id               INTEGER PRIMARY KEY,
    conversation_id  INTEGER NOT NULL,
    role             TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
    content          TEXT NOT NULL,
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, id);

-- Personal finance agent tables.
-- amount is always positive; the type column distinguishes income from expense
-- so arithmetic on amounts is unambiguous and CHECK constraints stay simple.
-- date is stored as ISO 8601 text ('YYYY-MM-DD') — SQLite has no native DATE
-- type, and text sorts correctly for date comparisons.

CREATE TABLE transactions (
    id          INTEGER PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    amount      REAL NOT NULL CHECK (amount > 0),
    type        TEXT NOT NULL CHECK (type IN ('income', 'expense')),
    category    TEXT NOT NULL CHECK (category IN (
        'food', 'shopping', 'transport', 'entertainment', 'housing',
        'healthcare', 'utilities', 'salary', 'transfer', 'other'
    )),
    merchant    TEXT NOT NULL,
    description TEXT,
    date        TEXT NOT NULL,       -- ISO 8601: 'YYYY-MM-DD'
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE INDEX idx_transactions_user_date ON transactions(user_id, date);
CREATE INDEX idx_transactions_user_type ON transactions(user_id, type);
