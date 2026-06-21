"""Telethon client setup and message handlers for Telepa3on."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Protocol

from telethon import TelegramClient, events


class EventRegistrar(Protocol):
    """Minimal protocol implemented by Telethon clients for event binding."""

    def on(self, event: object):
        """Return a decorator that registers a callback for an event."""


@dataclass(frozen=True)
class BotConfig:
    """Runtime configuration for the Telegram bot."""

    api_id: int
    api_hash: str
    bot_token: str
    session: str = "telepa3on"

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Load bot credentials from environment variables."""

        missing = [
            name
            for name in ("TELEGRAM_API_ID", "TELEGRAM_API_HASH", "TELEGRAM_BOT_TOKEN")
            if not os.getenv(name)
        ]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing required environment variables: {joined}")

        try:
            api_id = int(os.environ["TELEGRAM_API_ID"])
        except ValueError as exc:
            raise RuntimeError("TELEGRAM_API_ID must be an integer") from exc

        return cls(
            api_id=api_id,
            api_hash=os.environ["TELEGRAM_API_HASH"],
            bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
            session=os.getenv("TELEGRAM_SESSION", "telepa3on"),
        )


def build_client(config: BotConfig) -> TelegramClient:
    """Create a Telethon client for the configured Telegram application."""

    return TelegramClient(config.session, config.api_id, config.api_hash)


def register_echo_handler(client: EventRegistrar) -> None:
    """Register the default /start and echo message handlers."""

    @client.on(events.NewMessage(pattern="/start"))
    async def start(event):
        await event.respond("Telepa3on is online. Send a message and I will echo it back.")

    @client.on(events.NewMessage(incoming=True))
    async def echo(event):
        if event.raw_text and not event.raw_text.startswith("/"):
            await event.respond(event.raw_text)
