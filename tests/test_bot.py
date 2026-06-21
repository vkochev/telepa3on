from __future__ import annotations

import pytest

from telepa3on.bot import BotConfig, register_echo_handler


class FakeClient:
    def __init__(self):
        self.handlers = []

    def on(self, event):
        def decorator(callback):
            self.handlers.append((event, callback))
            return callback

        return decorator


class FakeEvent:
    def __init__(self, raw_text: str):
        self.raw_text = raw_text
        self.responses = []

    async def respond(self, text: str):
        self.responses.append(text)


def test_config_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "hash")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_SESSION", "custom")

    assert BotConfig.from_env() == BotConfig(12345, "hash", "token", "custom")


def test_config_reports_missing_values(monkeypatch):
    monkeypatch.delenv("TELEGRAM_API_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_API_HASH", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_BOT_TOKEN"):
        BotConfig.from_env()


@pytest.mark.asyncio
async def test_register_echo_handler():
    client = FakeClient()
    register_echo_handler(client)

    assert len(client.handlers) == 2

    start_event = FakeEvent("/start")
    await client.handlers[0][1](start_event)
    assert start_event.responses == ["Telepa3on is online. Send a message and I will echo it back."]

    echo_event = FakeEvent("hello")
    await client.handlers[1][1](echo_event)
    assert echo_event.responses == ["hello"]

    command_event = FakeEvent("/help")
    await client.handlers[1][1](command_event)
    assert command_event.responses == []
