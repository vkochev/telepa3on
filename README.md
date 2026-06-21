# Telepa3on

Telepa3on is a minimal personal Telegram secretary for **Telegram Chat Automation** built on the official Telegram Bot API. It receives Telegram webhook updates for a connected Telegram profile, stores Chat Automation connection and message data in Postgres, generates exactly three reply suggestions with an OpenAI-compatible API, asks an owner to approve one, and sends the selected reply back to the original chat using `sendMessage` with `business_connection_id`.

This project intentionally uses the **official Telegram Bot API only**. It does **not** use Telethon, MTProto, Telegram API ID, or Telegram API hash.

## What the MVP handles

- `business_connection` updates: stores the Telegram Chat Automation connection identifier and raw update payload.
- `business_message` updates: stores incoming messages from selected personal chats, generates three suggestions, sends an owner approval card, and records a minimal memory event.
- `callback_query` updates: handles owner-only `Send 1`, `Send 2`, `Send 3`, and `Reject` approval actions with idempotency checks.
- Approve-before-send flow: suggested replies are never sent to the original chat until the configured owner taps a `Send` button.
- Approved replies: calls Telegram Bot API `sendMessage` with `business_connection_id` so the reply is sent into the original chat.
- Rejected replies: persists rejected status and records the decision in memories.

The app does not currently implement regular owner-control `message` commands. Configure `OWNER_CHAT_ID` locally as the fallback source of truth for who receives approval cards and who is allowed to approve or reject suggestions.

## Learning extractor

After the owner taps `Send 1`, `Send 2`, `Send 3`, or `Reject`, Telepa3on runs a conservative local learning extractor over the incoming message, the generated suggestions, the owner decision, and existing memories. It may write zero or more structured memories as `structured_memory` events with `scope`, `kind`, `content`, and `confidence` fields. Allowed structured memory kinds are `style`, `preference`, `boundary`, and `correction`.

The extractor is intentionally cautious: it looks for lightweight reply-style signals, does not save random sensitive facts by default, does not infer deeply personal facts from one interaction, and returns no memories when the signal is weak. Raw event logs such as `approved_reply_sent` and `reply_rejected` remain separate from these structured memories.

## Requirements

- Docker and Docker Compose
- A Telegram bot token from BotFather
- A Telegram profile with Chat Automation enabled and connected to the bot
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
| `OWNER_CHAT_ROUTES` | Optional local/debug JSON override mapping `business_connection_id` values to owner chat IDs. |
| `OWNER_CHAT_ID` | Telegram chat ID that receives approval cards and is allowed to approve or reject suggestions. |
| `DATABASE_URL` | Async Postgres DSN used by the app. |
| `OPENAI_API_KEY` | API key for an OpenAI-compatible provider. |
| `OPENAI_BASE_URL` | Base URL, for example `https://api.openai.com/v1`. |
| `OPENAI_MODEL` | Chat model used to generate suggestions. |

Owner routing normally uses the stored BusinessConnection `user_chat_id`; `OWNER_CHAT_ID` is only the fallback when no stored owner chat exists. `OWNER_CHAT_ROUTES` is intended for local/debug overrides.

## Local smoke test

Use this checklist from a clean checkout to verify that the local stack starts, migrates Postgres, and exposes the operator inspection view.

1. Copy the example environment file and edit the local copy:

   ```bash
   cp .env.example .env
   ```

2. Fill every required value in `.env`: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `OWNER_CHAT_ID`, `DATABASE_URL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL`. For the Docker Compose stack, keep `DATABASE_URL` pointed at the Compose service name, for example `postgresql://telepa3on:telepa3on@postgres:5432/telepa3on`.
3. Start the webhook app, Postgres, and Adminer:

   ```bash
   docker compose up --build
   ```

4. Check the app health endpoint from another terminal:

   ```bash
   curl http://localhost:8000/health
   ```

   A healthy local app returns an OK health response.
5. Open Adminer at <http://localhost:8080> and connect with:
   - System: `PostgreSQL`
   - Server: `postgres`
   - Username: `telepa3on`
   - Password: `telepa3on`
   - Database: `telepa3on`

   Adminer runs inside the Compose network, so it should use the Postgres service name `postgres`, not `localhost`. Use `localhost:5432` only from tools running on your host machine outside Compose.
6. Verify migrations ran by confirming the MVP tables and the `debug_last_events` view exist. The app container startup command runs `python -m telepa3on.migrate` before starting Uvicorn.
7. Verify the debug timeline view is queryable in Adminer with:

   ```sql
   select * from debug_last_events limit 20;
   ```

Services exposed by the local Compose file:

- App: <http://localhost:8000>
- Adminer: <http://localhost:8080>
- Postgres: `localhost:5432`

For tunnel-free local Telegram debugging, run the long-polling profile instead of the webhook-only app:

```bash
docker compose --profile polling up --build
```

The `poller` service runs migrations, calls Telegram `deleteWebhook` without dropping pending updates by default, then consumes `getUpdates` for `business_connection`, `business_message`, `edited_business_message`, `deleted_business_messages`, and `callback_query`. Long polling removes the need for an HTTPS tunnel during local debug, but webhook delivery and polling are mutually exclusive: after using polling, set the webhook again before returning to `/telegram/webhook` mode. Configure polling with `TELEGRAM_POLLING_TIMEOUT`, `TELEGRAM_POLLING_RETRY_DELAY_SECONDS`, and `TELEGRAM_POLLING_DROP_PENDING_UPDATES`.

Use Adminer to inspect the local Postgres database while developing. The MVP stores Chat Automation connections, messages from selected personal chats, generated reply suggestions, and memory events in the tables created by the initial migration. For a quick local timeline, open the `debug_last_events` view; it combines the latest connection, message, suggestion, and memory events into one Adminer-friendly list.

Apply migrations manually if you are not using the app container startup command:

```bash
python -m telepa3on.migrate
```

## Single-host Docker Compose deployment

A single-host deployment can use the same app, Postgres, and Adminer services as local development, with a public HTTPS reverse proxy in front of the app. Telegram webhooks require a publicly reachable HTTPS URL; plain HTTP, private LAN hostnames, and untrusted certificates are not suitable for production webhook delivery.

Recommended shape:

- Run `docker compose up --build -d` on the host after creating a production `.env`.
- Put a reverse proxy such as Caddy, nginx, Traefik, or a managed load balancer on public ports `80` and `443`. Terminate TLS there and forward HTTPS webhook traffic to the app container on Compose port `8000`.
- Do not expose Postgres (`5432`) or Adminer (`8080`) publicly. If Adminer is enabled on a server, restrict it to a private network, SSH tunnel, VPN, or temporary maintenance window.
- Keep the app's `DATABASE_URL` compose-internal. Inside Compose it should use the Postgres service DNS name, for example `postgresql://telepa3on:telepa3on@postgres:5432/telepa3on`, not `localhost`.
- Use a long random `TELEGRAM_WEBHOOK_SECRET`. Telegram sends it in the `X-Telegram-Bot-Api-Secret-Token` header and the app validates it before processing webhook updates. Treat this secret like a password and rotate it if it is exposed.

Register the webhook after DNS and HTTPS are working:

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://YOUR_PUBLIC_HOST/telegram/webhook","secret_token":"'"$TELEGRAM_WEBHOOK_SECRET"'","allowed_updates":["business_connection","business_message","edited_business_message","deleted_business_messages","callback_query"]}'
```

To verify webhook delivery:

1. Confirm the public health endpoint works through the reverse proxy, for example `curl https://YOUR_PUBLIC_HOST/health`.
2. Call Telegram `getWebhookInfo` and check that the configured URL is correct and that Telegram is not reporting a recent delivery error:

   ```bash
   curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"
   ```

3. Connect the bot to Telegram Chat Automation, send or receive a selected-chat event, and inspect container logs plus `debug_last_events` in Postgres to confirm updates are arriving.

Keep these values secret in production: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `OPENAI_API_KEY`, database credentials and backups, `.env`, and any raw webhook payloads or database exports containing personal chat data.


## Manual Telegram test

Use this manual end-to-end test to verify the real product loop with Telegram Chat Automation, owner approval, and Postgres inspection. This is a real Telegram test: it requires a bot from BotFather and a Telegram profile that can enable Chat Automation. You can run it either with the production-style HTTPS webhook path or with the local long-polling debug profile.

Before starting, remember the owner-control model:

- Telepa3on sends generated suggestions to the **owner control chat**, not to the original personal chat.
- Telepa3on never sends a suggestion to the original personal chat until the owner taps `Send 1`, `Send 2`, or `Send 3` on the approval card.
- Tapping `Reject` marks the suggestion rejected and sends nothing to the original personal chat.
- The owner control chat is normally determined from Telegram `BusinessConnection.user_chat_id` when that value is available. `OWNER_CHAT_ID` is the fallback when no stored owner chat exists, and `OWNER_CHAT_ROUTES` can override routing for local/debug scenarios by mapping a `business_connection_id` to an owner chat ID.
- Which personal chats the bot can see is controlled on the Telegram side in Telegram Chat Automation settings. Telepa3on only receives Bot API updates for chats selected there; the app code does not select, grant, or expand Telegram-side chat access.

Checklist:

1. Create a new Telegram bot with BotFather, or use an existing bot dedicated to this test, and put its token in `TELEGRAM_BOT_TOKEN`.
2. Choose a delivery mode:
   - **Webhook/tunnel mode:** run Telepa3on locally through a public HTTPS tunnel, or deploy it on a public HTTPS host. Telegram must be able to reach `https://YOUR_PUBLIC_HOST/telegram/webhook`; a plain local `localhost` URL is not enough.
   - **Local polling mode:** run `docker compose --profile polling up --build`. This uses `getUpdates`, so it does not need an HTTPS tunnel and it calls `deleteWebhook` before polling.
3. For webhook/tunnel mode, register the webhook with the existing `setWebhook` command, using the same `TELEGRAM_WEBHOOK_SECRET` configured in `.env`:

   ```bash
   curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
     -H 'Content-Type: application/json' \
     -d '{"url":"https://YOUR_PUBLIC_HOST/telegram/webhook","secret_token":"'"$TELEGRAM_WEBHOOK_SECRET"'","allowed_updates":["business_connection","business_message","edited_business_message","deleted_business_messages","callback_query"]}'
   ```

4. In Telegram, connect the bot to your Telegram profile through Telegram Chat Automation.
5. In the Telegram Chat Automation UI, select one personal chat/contact for the bot to access. This selection is controlled by Telegram settings, not by Telepa3on code.
6. Send or receive a new message in that selected personal chat so Telegram emits a Chat Automation `business_message` update to the active delivery mode.
7. Expect an approval card with exactly three suggested replies in the owner control chat. The suggestions should appear only in this owner control chat at this point.
8. Click `Send 1`, `Send 2`, or `Send 3` on the approval card.
9. Verify that the selected reply appears in the original selected personal chat.
10. Repeat with another incoming selected-chat message, click `Reject`, and verify that no suggestion is sent to the original personal chat.
11. Open Adminer and inspect `debug_last_events` to confirm the received message, generated suggestions, owner decision, and memory event were recorded:

   ```sql
   select *
   from debug_last_events
   order by created_at desc
   limit 50;
   ```

If the approval card does not appear in webhook mode, first check Telegram `getWebhookInfo`, app container logs, `business_connections` rows, and whether the selected personal chat is enabled in Telegram Chat Automation settings. In polling mode, check poller logs and remember that switching back to webhook mode requires calling `setWebhook` again. If a reply does not appear in the original personal chat after `Send N`, confirm the bot is still connected to the Telegram profile and that the original chat remains selected for Chat Automation access.

## Persistent Postgres data

The Compose stack stores Postgres data in the named Docker volume `postgres_data`. This volume persists database state across app and database container restarts, including `docker compose restart` and `docker compose down` without `--volumes`.

Deleting the named volume deletes the local database state. For example, `docker compose down --volumes` removes `postgres_data` along with the containers and network, so the next startup creates an empty database and reruns migrations.

Production deployments should back up Postgres or the underlying volume regularly before upgrades, host maintenance, or destructive Compose commands. Treat backups as sensitive because they may contain Telegram connection metadata, message text, suggestions, decisions, and memories.

## Development

From a clean checkout, contributors and Codex should run the full developer test bootstrap command:

```bash
make test
```

This installs Telepa3on in editable mode with development dependencies and then runs the test suite with `pytest -q`.

## Telegram webhook setup

The production FastAPI endpoint is `POST /telegram/webhook` on the `app` service. For local webhook testing, expose the app through an HTTPS tunnel, use the tunnel host in `setWebhook`, include the secret token and allowed updates, then verify with `getWebhookInfo`:

```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://YOUR_PUBLIC_HOST/telegram/webhook","secret_token":"'"$TELEGRAM_WEBHOOK_SECRET"'","allowed_updates":["business_connection","business_message","edited_business_message","deleted_business_messages","callback_query"]}'
```

Telegram will POST updates to `/telegram/webhook`. If you previously ran the polling profile, run `setWebhook` again because the poller calls `deleteWebhook` before `getUpdates`. The app validates the webhook secret header before processing updates.

The current MVP processes `business_connection`, `business_message`, `edited_business_message`, `deleted_business_messages`, and `callback_query`. Edited and deleted Telegram Chat Automation message updates are handled minimally by recording a memory event with the raw update payload; they do not regenerate reply suggestions or change approval routing. Do not include regular `message` in `allowed_updates` unless owner-control message commands are added.

## Telegram API terminology

Telepa3on is framed as personal chat automation: a personal Telegram secretary for selected personal chats on a connected Telegram profile. The Telegram Bot API exposes this Chat Automation mechanism with `business_*` names, so the README keeps exact API terms such as `business_connection`, `business_message`, `edited_business_message`, `deleted_business_messages`, `business_connection_id`, and `BusinessConnection.user_chat_id` only when referring to Telegram update or field names.

## Telegram Chat Automation notes

Telegram Chat Automation updates are delivered through the official Bot API when the bot is connected to a Telegram profile with Chat Automation enabled. Replies to selected personal chats must include the `business_connection_id`; otherwise the message is sent as a normal bot message instead of through the connected Telegram profile.
