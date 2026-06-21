# Telepa3on

Telepa3on is a minimal Telegram **Business Chat Automation** approval workflow built on the official Telegram Bot API. It receives Telegram webhook updates for a connected Telegram Business account, stores business connection and message data in Postgres, generates exactly three reply suggestions with an OpenAI-compatible API, asks an owner to approve one, and sends the selected reply back to the original business chat using `sendMessage` with `business_connection_id`.

This project intentionally uses the **official Telegram Bot API only**. It does **not** use Telethon, MTProto, Telegram API ID, or Telegram API hash.

## What the MVP handles

- `business_connection` updates: stores the Telegram business connection identifier and raw update payload.
- `business_message` updates: stores incoming business messages, generates three suggestions, sends an owner approval card, and records a minimal memory event.
- `callback_query` updates: handles owner-only `Send 1`, `Send 2`, `Send 3`, and `Reject` approval actions with idempotency checks.
- Approve-before-send flow: suggested replies are never sent to the business chat until the configured owner taps a `Send` button.
- Approved replies: calls Telegram Bot API `sendMessage` with `business_connection_id` so the reply is sent into the original business chat.
- Rejected replies: persists rejected status and records the decision in memories.

The app does not currently implement regular owner-control `message` commands. Configure `OWNER_CHAT_ID` locally as the fallback source of truth for who receives approval cards and who is allowed to approve or reject suggestions.

## Requirements

- Docker and Docker Compose
- A Telegram bot token from BotFather
- A Telegram Business account connected to the bot for Business Chat Automation
- An OpenAI-compatible chat completions endpoint and API key

## Environment variables

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

| Variable | Description |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | BotFather token used for official Telegram Bot API calls. |
| `TELEGRAM_WEBHOOK_SECRET` | Secret token Telegram sends in `X-Telegram-Bot-Api-Secret-Token`. |
| `OWNER_CHAT_ID` | Telegram chat ID that receives approval cards and is allowed to approve or reject suggestions. |
| `DATABASE_URL` | Async Postgres DSN used by the app. |
| `OPENAI_API_KEY` | API key for an OpenAI-compatible provider. |
| `OPENAI_BASE_URL` | Base URL, for example `https://api.openai.com/v1`. |
| `OPENAI_MODEL` | Chat model used to generate suggestions. |

## Run locally

```bash
docker compose up --build
```

Services:

- App: <http://localhost:8000>
- Adminer: <http://localhost:8080>
- Postgres: `localhost:5432`

Use Adminer to inspect the local Postgres database while developing. The MVP stores business connections, business messages, generated reply suggestions, and memory events in the tables created by the initial migration.

Apply migrations manually if you are not using the app container startup command:

```bash
python -m telepa3on.migrate
```

## Telegram webhook setup

Expose the app publicly, for example with a tunnel, then register the webhook:

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://YOUR_PUBLIC_HOST/telegram/webhook","secret_token":"'"$TELEGRAM_WEBHOOK_SECRET"'","allowed_updates":["business_connection","business_message","edited_business_message","deleted_business_messages","callback_query"]}'
```

Telegram will POST updates to `/telegram/webhook`. The app validates the webhook secret header before processing updates.

The current MVP processes `business_connection`, `business_message`, and `callback_query`. The webhook registration also asks Telegram to deliver `edited_business_message` and `deleted_business_messages` so the deployment is ready for those Business Chat Automation update types, even though they are not handled yet. Do not include regular `message` in `allowed_updates` unless owner-control message commands are added.

## Telegram Chat Automation notes

Telegram Business Chat Automation updates are delivered through the official Bot API when the bot is connected to a Telegram Business account. Replies to business chats must include the `business_connection_id`; otherwise the message is sent as a normal bot message instead of on behalf of the business connection.
