from __future__ import annotations

from typing import Any

from .openai_client import SuggestionClient
from .repository import Repository
from .telegram import TelegramBotApi


def approval_keyboard(message_id: int) -> dict[str, Any]:
    return {
        "inline_keyboard": [[
            {"text": "Send 1", "callback_data": f"send:{message_id}:1"},
            {"text": "Send 2", "callback_data": f"send:{message_id}:2"},
            {"text": "Send 3", "callback_data": f"send:{message_id}:3"},
            {"text": "Reject", "callback_data": f"reject:{message_id}"},
        ]]
    }


def approval_text(message_text: str, suggestions: list[str]) -> str:
    lines = ["New Telegram Business message needs approval:", "", message_text, ""]
    lines.extend(f"{index}. {text}" for index, text in enumerate(suggestions, start=1))
    return "\n".join(lines)


class UpdateHandlers:
    def __init__(self, *, repo: Repository, telegram: TelegramBotApi, suggestions: SuggestionClient, owner_chat_id: int) -> None:
        self.repo = repo
        self.telegram = telegram
        self.suggestions = suggestions
        self.owner_chat_id = owner_chat_id

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
        business_message_id = await self.repo.create_business_message(message, raw_update)
        generated = await self.suggestions.generate(text)
        if len(generated) != 3:
            raise RuntimeError("exactly 3 suggestions are required")
        await self.repo.save_suggestions(business_message_id, generated)
        owner_message = await self.telegram.send_message(
            chat_id=self.owner_chat_id,
            text=approval_text(text, generated),
            reply_markup=approval_keyboard(business_message_id),
        )
        await self.repo.set_owner_approval_message_id(business_message_id, owner_message["result"]["message_id"])
        await self.repo.add_memory(
            message["business_connection_id"],
            business_message_id,
            "incoming_business_message",
            {"text": text, "suggestions": generated},
        )

    async def handle_callback_query(self, callback_query: dict[str, Any]) -> None:
        data = callback_query.get("data", "")
        callback_query_id = callback_query["id"]
        if data.startswith("send:"):
            _, message_id_text, index_text = data.split(":", 2)
            business_message_id = int(message_id_text)
            index = int(index_text)
            suggestion = await self.repo.get_suggestion_for_approval(business_message_id, index)
            if suggestion is None:
                await self.telegram.answer_callback_query(callback_query_id, "Suggestion not found")
                return
            await self.telegram.send_message(
                chat_id=int(suggestion["chat_id"]),
                text=suggestion["text"],
                business_connection_id=suggestion["business_connection_id"],
            )
            await self.repo.mark_sent(business_message_id, index)
            await self.repo.add_memory(
                suggestion["business_connection_id"],
                business_message_id,
                "approved_reply_sent",
                {"selected": index, "text": suggestion["text"]},
            )
            await self.telegram.answer_callback_query(callback_query_id, f"Sent suggestion {index}")
            return
        if data.startswith("reject:"):
            _, message_id_text = data.split(":", 1)
            business_message_id = int(message_id_text)
            await self.repo.mark_rejected(business_message_id)
            await self.repo.add_memory(None, business_message_id, "reply_rejected", {"reason": "owner_rejected"})
            await self.telegram.answer_callback_query(callback_query_id, "Rejected")
