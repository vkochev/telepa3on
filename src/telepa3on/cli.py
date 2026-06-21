"""Command line entry point for running the Telepa3on bot."""

from __future__ import annotations

from .bot import BotConfig, build_client, register_echo_handler


def run() -> None:
    """Start the bot and run until disconnected."""

    config = BotConfig.from_env()
    client = build_client(config)
    register_echo_handler(client)
    client.start(bot_token=config.bot_token)
    print("Telepa3on is running. Press Ctrl+C to stop.")
    client.run_until_disconnected()


def main() -> None:
    """Console script wrapper."""

    run()


if __name__ == "__main__":
    main()
