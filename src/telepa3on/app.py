from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import asyncpg
from fastapi import FastAPI, Header, HTTPException, Request

from .config import Settings
from .handlers import UpdateHandlers
from .openai_client import SuggestionClient
from .repository import Repository
from .telegram import TelegramBotApi


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings()
    pool = await asyncpg.create_pool(settings.database_url)
    app.state.settings = settings
    app.state.pool = pool
    telegram = TelegramBotApi(settings.telegram_bot_token)
    suggestions = SuggestionClient(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model,
    )
    app.state.telegram = telegram
    app.state.suggestions = suggestions
    app.state.handlers = UpdateHandlers(
        repo=Repository(pool),
        telegram=telegram,
        suggestions=suggestions,
        owner_chat_id=settings.owner_chat_id,
        owner_chat_routes=settings.owner_chat_routes,
    )
    try:
        yield
    finally:
        await app.state.telegram.aclose()
        await app.state.suggestions.aclose()
        await pool.close()


app = FastAPI(title="Telepa3on", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, bool]:
    settings: Settings = request.app.state.settings
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=401, detail="invalid webhook secret")
    update: dict[str, Any] = await request.json()
    await request.app.state.handlers.handle_update(update)
    return {"ok": True}
