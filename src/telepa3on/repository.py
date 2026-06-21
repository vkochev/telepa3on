from __future__ import annotations

from typing import Any
import json

import asyncpg


class Repository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def upsert_business_connection(self, connection: dict[str, Any], raw_update: dict[str, Any]) -> None:
        user = connection.get("user") or {}
        await self.pool.execute(
            """
            INSERT INTO business_connections (business_connection_id, user_id, user_chat_id, is_enabled, raw_update, updated_at)
            VALUES ($1, $2, $3, $4, $5::jsonb, now())
            ON CONFLICT (business_connection_id) DO UPDATE SET
              user_id = EXCLUDED.user_id,
              user_chat_id = EXCLUDED.user_chat_id,
              is_enabled = EXCLUDED.is_enabled,
              raw_update = EXCLUDED.raw_update,
              updated_at = now()
            """,
            connection["id"],
            user.get("id"),
            connection.get("user_chat_id"),
            connection.get("is_enabled"),
            json.dumps(raw_update),
        )

    async def get_business_connection(self, business_connection_id: str) -> asyncpg.Record | None:
        return await self.pool.fetchrow(
            "SELECT business_connection_id, user_id, user_chat_id, is_enabled FROM business_connections WHERE business_connection_id = $1",
            business_connection_id,
        )

    async def create_business_message(self, message: dict[str, Any], raw_update: dict[str, Any], owner_chat_id: int) -> int:
        sender = message.get("from") or {}
        row = await self.pool.fetchrow(
            """
            INSERT INTO business_messages (telegram_message_id, business_connection_id, chat_id, sender_id, text, raw_update, owner_chat_id)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7)
            ON CONFLICT (business_connection_id, telegram_message_id) DO UPDATE SET raw_update = EXCLUDED.raw_update, owner_chat_id = EXCLUDED.owner_chat_id
            RETURNING id
            """,
            message["message_id"],
            message["business_connection_id"],
            message["chat"]["id"],
            sender.get("id"),
            message.get("text") or message.get("caption") or "",
            json.dumps(raw_update),
            owner_chat_id,
        )
        return int(row["id"])

    async def save_suggestions(self, business_message_id: int, suggestions: list[str]) -> None:
        for index, text in enumerate(suggestions, start=1):
            await self.pool.execute(
                """
                INSERT INTO reply_suggestions (business_message_id, suggestion_index, text)
                VALUES ($1, $2, $3)
                ON CONFLICT (business_message_id, suggestion_index) DO UPDATE SET text = EXCLUDED.text, updated_at = now()
                """,
                business_message_id,
                index,
                text,
            )

    async def set_owner_approval_message_id(self, business_message_id: int, owner_message_id: int) -> None:
        await self.pool.execute(
            "UPDATE reply_suggestions SET owner_approval_message_id = $1, updated_at = now() WHERE business_message_id = $2",
            owner_message_id,
            business_message_id,
        )

    async def get_suggestion_for_approval(self, business_message_id: int, index: int) -> asyncpg.Record | None:
        return await self.pool.fetchrow(
            """
            SELECT rs.text, bm.business_connection_id, bm.chat_id, bm.telegram_message_id, bm.status, bm.owner_chat_id
            FROM reply_suggestions rs
            JOIN business_messages bm ON bm.id = rs.business_message_id
            WHERE rs.business_message_id = $1 AND rs.suggestion_index = $2
            """,
            business_message_id,
            index,
        )

    async def get_message_context(self, business_message_id: int) -> asyncpg.Record | None:
        return await self.pool.fetchrow(
            "SELECT business_connection_id, status, owner_chat_id FROM business_messages WHERE id = $1",
            business_message_id,
        )

    async def mark_sent(self, business_message_id: int, index: int) -> None:
        await self.pool.execute("UPDATE business_messages SET status = 'sent', updated_at = now() WHERE id = $1", business_message_id)
        await self.pool.execute(
            "UPDATE reply_suggestions SET status = CASE WHEN suggestion_index = $2 THEN 'sent' ELSE 'not_selected' END, updated_at = now() WHERE business_message_id = $1",
            business_message_id,
            index,
        )

    async def mark_rejected(self, business_message_id: int) -> None:
        await self.pool.execute("UPDATE business_messages SET status = 'rejected', updated_at = now() WHERE id = $1", business_message_id)
        await self.pool.execute(
            "UPDATE reply_suggestions SET status = 'rejected', updated_at = now() WHERE business_message_id = $1",
            business_message_id,
        )

    async def add_memory(self, business_connection_id: str | None, business_message_id: int | None, event_type: str, content: dict[str, Any]) -> None:
        await self.pool.execute(
            "INSERT INTO memories (business_connection_id, business_message_id, event_type, content) VALUES ($1, $2, $3, $4::jsonb)",
            business_connection_id,
            business_message_id,
            event_type,
            json.dumps(content),
        )
