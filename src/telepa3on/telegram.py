from __future__ import annotations

from typing import Any

import httpx


class TelegramBotApi:
    def __init__(self, bot_token: str, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=20)
        self._owns_client = client is None
        self._base_url = f"https://api.telegram.org/bot{bot_token}"

    async def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        business_connection_id: str | None = None,
        reply_markup: dict[str, Any] | None = None,
        reply_parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if business_connection_id:
            payload["business_connection_id"] = business_connection_id
        if reply_markup:
            payload["reply_markup"] = reply_markup
        if reply_parameters:
            payload["reply_parameters"] = reply_parameters
        return await self._post("sendMessage", payload)

    async def delete_webhook(self, drop_pending_updates: bool = False) -> dict[str, Any]:
        return await self._post("deleteWebhook", {"drop_pending_updates": drop_pending_updates})

    async def get_updates(
        self,
        *,
        offset: int | None = None,
        timeout: int,
        allowed_updates: list[str],
    ) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": timeout, "allowed_updates": allowed_updates}
        if offset is not None:
            payload["offset"] = offset
        data = await self._post("getUpdates", payload)
        result = data.get("result", [])
        if not isinstance(result, list):
            raise RuntimeError(f"Telegram Bot API getUpdates returned non-list result: {data}")
        return result

    async def answer_callback_query(self, callback_query_id: str, text: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        return await self._post("answerCallbackQuery", payload)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = await self._client.post(f"{self._base_url}/{method}", json=payload)
        response.raise_for_status()
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram Bot API {method} failed: {data}")
        return data
