from __future__ import annotations

import asyncio
import logging

import asyncpg

from .config import Settings
from .handlers import UpdateHandlers
from .openai_client import SuggestionClient
from .repository import Repository
from .telegram import TelegramBotApi

LOGGER = logging.getLogger(__name__)
ALLOWED_UPDATES = [
    "business_connection",
    "business_message",
    "edited_business_message",
    "deleted_business_messages",
    "callback_query",
]


def next_update_offset(current_offset: int | None, update: dict) -> int | None:
    update_id = update.get("update_id")
    if not isinstance(update_id, int):
        return current_offset
    candidate = update_id + 1
    return candidate if current_offset is None else max(current_offset, candidate)


async def poll_updates(
    *,
    telegram: TelegramBotApi,
    handlers: UpdateHandlers,
    timeout: int,
    retry_delay_seconds: float,
    drop_pending_updates: bool = False,
) -> None:
    await telegram.delete_webhook(drop_pending_updates=drop_pending_updates)
    offset: int | None = None
    while True:
        try:
            updates = await telegram.get_updates(offset=offset, timeout=timeout, allowed_updates=ALLOWED_UPDATES)
            for update in updates:
                await handlers.handle_update(update)
                offset = next_update_offset(offset, update)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("Telegram polling failed; retrying in %s seconds", retry_delay_seconds)
            await asyncio.sleep(retry_delay_seconds)


async def amain() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = Settings()
    pool = await asyncpg.create_pool(settings.database_url)
    telegram = TelegramBotApi(settings.telegram_bot_token)
    suggestions = SuggestionClient(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model,
    )
    handlers = UpdateHandlers(
        repo=Repository(pool),
        telegram=telegram,
        suggestions=suggestions,
        owner_chat_id=settings.owner_chat_id,
        owner_chat_routes=settings.owner_chat_routes,
    )
    try:
        await poll_updates(
            telegram=telegram,
            handlers=handlers,
            timeout=settings.telegram_polling_timeout,
            retry_delay_seconds=settings.telegram_polling_retry_delay_seconds,
            drop_pending_updates=settings.telegram_polling_drop_pending_updates,
        )
    finally:
        await telegram.aclose()
        await suggestions.aclose()
        await pool.close()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
