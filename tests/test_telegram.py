from __future__ import annotations

import httpx
import pytest

from telepa3on.telegram import TelegramBotApi


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class FakeClient:
    def __init__(self, data=None):
        self.calls = []
        self.data = data or {"ok": True, "result": True}

    async def post(self, url, json):
        self.calls.append((url, json))
        return FakeResponse(self.data)


@pytest.mark.asyncio
async def test_delete_webhook_payload():
    client = FakeClient()
    telegram = TelegramBotApi("token", client=client)  # type: ignore[arg-type]

    await telegram.delete_webhook(drop_pending_updates=True)

    assert client.calls == [("https://api.telegram.org/bottoken/deleteWebhook", {"drop_pending_updates": True})]


@pytest.mark.asyncio
async def test_get_updates_payload_with_offset_timeout_and_allowed_updates():
    client = FakeClient({"ok": True, "result": [{"update_id": 7}]})
    telegram = TelegramBotApi("token", client=client)  # type: ignore[arg-type]

    updates = await telegram.get_updates(offset=5, timeout=30, allowed_updates=["business_message", "callback_query"])

    assert updates == [{"update_id": 7}]
    assert client.calls == [
        (
            "https://api.telegram.org/bottoken/getUpdates",
            {"offset": 5, "timeout": 30, "allowed_updates": ["business_message", "callback_query"]},
        )
    ]
