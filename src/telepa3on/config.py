from __future__ import annotations

import json
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_webhook_secret: str
    owner_chat_id: int
    owner_chat_routes: dict[str, int] = Field(default_factory=dict)
    database_url: str = "postgresql://telepa3on:telepa3on@localhost:5432/telepa3on"
    openai_api_key: str
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    telegram_polling_timeout: int = 30
    telegram_polling_retry_delay_seconds: float = 5
    telegram_polling_drop_pending_updates: bool = False

    @field_validator("owner_chat_routes", mode="before")
    @classmethod
    def parse_owner_chat_routes(cls, value: Any) -> dict[str, int]:
        if value in (None, ""):
            return {}
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, dict):
            raise ValueError("OWNER_CHAT_ROUTES must be a JSON object")
        return {str(route_key): int(chat_id) for route_key, chat_id in value.items()}

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
