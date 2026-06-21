CREATE OR REPLACE VIEW debug_last_events AS
SELECT *
FROM (
    SELECT
        bc.updated_at AS event_at,
        'business_connection'::TEXT AS source,
        CASE
            WHEN bc.is_enabled IS TRUE THEN 'connection_enabled'
            WHEN bc.is_enabled IS FALSE THEN 'connection_disabled'
            ELSE 'connection_seen'
        END AS event_type,
        bc.business_connection_id,
        NULL::BIGINT AS business_message_id,
        NULL::BIGINT AS telegram_message_id,
        bc.user_chat_id AS chat_id,
        bc.user_chat_id AS owner_chat_id,
        bc.is_enabled::TEXT AS status,
        bc.raw_update AS payload
    FROM business_connections bc

    UNION ALL

    SELECT
        bm.updated_at AS event_at,
        'business_message'::TEXT AS source,
        'message_' || bm.status AS event_type,
        bm.business_connection_id,
        bm.id AS business_message_id,
        bm.telegram_message_id,
        bm.chat_id,
        bm.owner_chat_id,
        bm.status,
        jsonb_build_object(
            'text', bm.text,
            'sender_id', bm.sender_id,
            'raw_update', bm.raw_update
        ) AS payload
    FROM business_messages bm

    UNION ALL

    SELECT
        rs.updated_at AS event_at,
        'reply_suggestion'::TEXT AS source,
        'suggestion_' || rs.status AS event_type,
        bm.business_connection_id,
        rs.business_message_id,
        bm.telegram_message_id,
        bm.chat_id,
        bm.owner_chat_id,
        rs.status,
        jsonb_build_object(
            'suggestion_index', rs.suggestion_index,
            'text', rs.text,
            'owner_approval_message_id', rs.owner_approval_message_id
        ) AS payload
    FROM reply_suggestions rs
    JOIN business_messages bm ON bm.id = rs.business_message_id

    UNION ALL

    SELECT
        m.created_at AS event_at,
        'memory'::TEXT AS source,
        m.event_type,
        m.business_connection_id,
        m.business_message_id,
        bm.telegram_message_id,
        bm.chat_id,
        bm.owner_chat_id,
        NULL::TEXT AS status,
        m.content AS payload
    FROM memories m
    LEFT JOIN business_messages bm ON bm.id = m.business_message_id
) events
ORDER BY event_at DESC
LIMIT 100;
