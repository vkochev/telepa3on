ALTER TABLE business_messages
ADD COLUMN IF NOT EXISTS owner_chat_id BIGINT;
