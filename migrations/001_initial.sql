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
    owner_chat_id BIGINT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_connection_id, chat_id, telegram_message_id)
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

CREATE OR REPLACE VIEW debug_last_events AS
SELECT *
FROM (
    SELECT
        bc.updated_at AS created_at,
        CASE WHEN bc.is_enabled IS TRUE THEN 'connection_enabled' WHEN bc.is_enabled IS FALSE THEN 'connection_disabled' ELSE 'connection_seen' END AS event_type,
        bc.business_connection_id,
        NULL::BIGINT AS business_message_id,
        bc.user_chat_id AS chat_id,
        NULL::BIGINT AS telegram_message_id,
        bc.is_enabled::TEXT AS status,
        bc.raw_update AS details
    FROM business_connections bc
    UNION ALL
    SELECT
        bm.updated_at AS created_at,
        'message_' || bm.status AS event_type,
        bm.business_connection_id,
        bm.id AS business_message_id,
        bm.chat_id,
        bm.telegram_message_id,
        bm.status,
        jsonb_build_object('text', bm.text, 'sender_id', bm.sender_id, 'owner_chat_id', bm.owner_chat_id, 'raw_update', bm.raw_update) AS details
    FROM business_messages bm
    UNION ALL
    SELECT
        rs.updated_at AS created_at,
        'suggestion_' || rs.status AS event_type,
        bm.business_connection_id,
        rs.business_message_id,
        bm.chat_id,
        bm.telegram_message_id,
        rs.status,
        jsonb_build_object('suggestion_index', rs.suggestion_index, 'text', rs.text, 'owner_approval_message_id', rs.owner_approval_message_id) AS details
    FROM reply_suggestions rs
    JOIN business_messages bm ON bm.id = rs.business_message_id
    UNION ALL
    SELECT
        m.created_at AS created_at,
        m.event_type,
        m.business_connection_id,
        m.business_message_id,
        bm.chat_id,
        bm.telegram_message_id,
        NULL::TEXT AS status,
        m.content AS details
    FROM memories m
    LEFT JOIN business_messages bm ON bm.id = m.business_message_id
) events
ORDER BY created_at DESC
LIMIT 100;
