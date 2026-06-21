# Telepa3on

Telepa3on is a minimal async Telegram echo bot scaffold using [Telethon](https://docs.telethon.dev/).

## Configuration

Create a Telegram application to obtain `api_id` and `api_hash`, and create a bot with BotFather to obtain a bot token. Export those values before running:

```bash
export TELEGRAM_API_ID=12345
export TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef
export TELEGRAM_BOT_TOKEN=123456:bot-token
```

Optional:

```bash
export TELEGRAM_SESSION=telepa3on
```

## Run

```bash
python -m telepa3on.cli
```

or, after installing the package:

```bash
telepa3on
```

The bot responds to `/start` and echoes non-command messages.
