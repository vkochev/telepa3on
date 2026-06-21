"""Telepa3on Telegram bot scaffold."""

from .bot import BotConfig, build_client, register_echo_handler

__all__ = ["BotConfig", "build_client", "register_echo_handler"]
