CREATE TABLE IF NOT EXISTS business_connections (
    business_connection_id TEXT PRIMARY KEY,
    user_id BIGINT,
    user_chat_id BIGINT,
    is_enabled BOOLEAN,
    raw_update JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS business_messages (
    id BIGSERIAL PRIMARY KEY,
    telegram_message_id BIGINT NOT NULL,
    business_connection_id TEXT NOT NULL,
    chat_id BIGINT NOT NULL,
    sender_id BIGINT,
    text TEXT NOT NULL,
    raw_update JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_connection_id, telegram_message_id)
);

CREATE TABLE IF NOT EXISTS reply_suggestions (
    id BIGSERIAL PRIMARY KEY,
    business_message_id BIGINT NOT NULL REFERENCES business_messages(id) ON DELETE CASCADE,
    suggestion_index INTEGER NOT NULL CHECK (suggestion_index BETWEEN 1 AND 3),
    text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    owner_approval_message_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_message_id, suggestion_index)
);

CREATE TABLE IF NOT EXISTS memories (
    id BIGSERIAL PRIMARY KEY,
    business_connection_id TEXT,
    business_message_id BIGINT REFERENCES business_messages(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    content JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
