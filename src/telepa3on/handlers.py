from __future__ import annotations

from typing import Any

from .openai_client import SuggestionClient
from .repository import Repository
from .telegram import TelegramBotApi


def record_get(record: Any, key: str, default: Any = None) -> Any:
    if hasattr(record, "get"):
        return record.get(key, default)
    try:
        return record[key]
    except (KeyError, TypeError):
        return default


def approval_keyboard(message_id: int) -> dict[str, Any]:
    return {
        "inline_keyboard": [
            [
                {"text": "Send 1", "callback_data": f"send:{message_id}:1"},
                {"text": "Send 2", "callback_data": f"send:{message_id}:2"},
                {"text": "Send 3", "callback_data": f"send:{message_id}:3"},
            ],
            [{"text": "Reject", "callback_data": f"reject:{message_id}"}],
        ]
    }


def approval_text(message_text: str, suggestions: list[str]) -> str:
    lines = ["New Telegram Business message needs approval:", "", message_text, ""]
    lines.extend(f"{index}. {text}" for index, text in enumerate(suggestions, start=1))
    return "\n".join(lines)


class UpdateHandlers:
    def __init__(
        self,
        *,
        repo: Repository,
        telegram: TelegramBotApi,
        suggestions: SuggestionClient,
        owner_chat_id: int,
        owner_chat_routes: dict[str, int] | None = None,
    ) -> None:
        self.repo = repo
        self.telegram = telegram
        self.suggestions = suggestions
        self.owner_chat_id = owner_chat_id
        self.owner_chat_routes = owner_chat_routes or {}

    async def handle_update(self, update: dict[str, Any]) -> None:
        if "business_connection" in update:
            await self.repo.upsert_business_connection(update["business_connection"], update)
            return
        if "business_message" in update:
            await self.handle_business_message(update["business_message"], update)
            return
        if "callback_query" in update:
            await self.handle_callback_query(update["callback_query"])

    async def handle_business_message(self, message: dict[str, Any], raw_update: dict[str, Any]) -> None:
        text = message.get("text") or message.get("caption") or ""
        if not text:
            return
        owner_chat_id = await self._owner_chat_id_for_message(message)
        business_message_id = await self.repo.create_business_message(message, raw_update, owner_chat_id=owner_chat_id)
        generated = await self.suggestions.generate(text)
        await self.repo.save_suggestions(business_message_id, generated)
        owner_message = await self.telegram.send_message(
            chat_id=owner_chat_id,
            text=approval_text(text, generated),
            reply_markup=approval_keyboard(business_message_id),
        )
        await self.repo.set_owner_approval_message_id(business_message_id, owner_message["result"]["message_id"])
        await self.repo.add_memory(
            message["business_connection_id"],
            business_message_id,
            "incoming_business_message",
            {"text": text, "suggestions": generated, "owner_chat_id": owner_chat_id},
        )

    async def handle_callback_query(self, callback_query: dict[str, Any]) -> None:
        callback_query_id = callback_query["id"]
        data = callback_query.get("data", "")
        if data.startswith("send:"):
            await self._handle_send_callback(callback_query, callback_query_id, data)
            return
        if data.startswith("reject:"):
            await self._handle_reject_callback(callback_query, callback_query_id, data)
            return
        await self.telegram.answer_callback_query(callback_query_id, "Unsupported action")

    async def _handle_send_callback(self, callback_query: dict[str, Any], callback_query_id: str, data: str) -> None:
        try:
            _, message_id_text, index_text = data.split(":", 2)
            business_message_id = int(message_id_text)
            index = int(index_text)
        except ValueError:
            await self.telegram.answer_callback_query(callback_query_id, "Invalid approval action")
            return
        if index not in {1, 2, 3}:
            await self.telegram.answer_callback_query(callback_query_id, "Invalid suggestion number")
            return

        suggestion = await self.repo.get_suggestion_for_approval(business_message_id, index)
        if suggestion is None:
            await self.telegram.answer_callback_query(callback_query_id, "Suggestion not found")
            return
        if not self._is_owner_callback(callback_query, record_get(suggestion, "owner_chat_id")):
            await self.telegram.answer_callback_query(callback_query_id, "Only the routed owner can approve this reply")
            return
        if suggestion["status"] != "pending":
            await self.telegram.answer_callback_query(callback_query_id, "This message was already processed")
            return

        await self.telegram.send_message(
            chat_id=int(suggestion["chat_id"]),
            text=suggestion["text"],
            business_connection_id=suggestion["business_connection_id"],
            reply_parameters={"message_id": int(suggestion["telegram_message_id"])},
        )
        await self.repo.mark_sent(business_message_id, index)
        await self.repo.add_memory(
            suggestion["business_connection_id"],
            business_message_id,
            "approved_reply_sent",
            {"selected": index, "text": suggestion["text"], "owner_chat_id": record_get(suggestion, "owner_chat_id")},
        )
        await self.telegram.answer_callback_query(callback_query_id, f"Sent suggestion {index}")

    async def _handle_reject_callback(self, callback_query: dict[str, Any], callback_query_id: str, data: str) -> None:
        try:
            _, message_id_text = data.split(":", 1)
            business_message_id = int(message_id_text)
        except ValueError:
            await self.telegram.answer_callback_query(callback_query_id, "Invalid rejection action")
            return
        context = await self.repo.get_message_context(business_message_id)
        if context is None:
            await self.telegram.answer_callback_query(callback_query_id, "Message not found")
            return
        if not self._is_owner_callback(callback_query, record_get(context, "owner_chat_id")):
            await self.telegram.answer_callback_query(callback_query_id, "Only the routed owner can approve this reply")
            return
        if context["status"] != "pending":
            await self.telegram.answer_callback_query(callback_query_id, "This message was already processed")
            return
        await self.repo.mark_rejected(business_message_id)
        await self.repo.add_memory(
            context["business_connection_id"],
            business_message_id,
            "reply_rejected",
            {"reason": "owner_rejected", "owner_chat_id": record_get(context, "owner_chat_id")},
        )
        await self.telegram.answer_callback_query(callback_query_id, "Rejected")

    async def _owner_chat_id_for_message(self, message: dict[str, Any]) -> int:
        business_connection_id = message.get("business_connection_id")
        if business_connection_id in self.owner_chat_routes:
            return self.owner_chat_routes[business_connection_id]
        if business_connection_id is not None:
            connection = await self.repo.get_business_connection(business_connection_id)
            if connection is not None and record_get(connection, "user_chat_id") is not None:
                return int(record_get(connection, "user_chat_id"))
        return self.owner_chat_id

    def _is_owner_callback(self, callback_query: dict[str, Any], owner_chat_id: int | None = None) -> bool:
        expected_owner_chat_id = owner_chat_id or self.owner_chat_id
        sender = callback_query.get("from") or {}
        if sender.get("id") is not None:
            return sender.get("id") == expected_owner_chat_id
        message = callback_query.get("message") or {}
        return (message.get("chat") or {}).get("id") == expected_owner_chat_id
