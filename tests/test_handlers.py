from __future__ import annotations

import pytest

from telepa3on.handlers import UpdateHandlers, approval_keyboard, approval_text
from telepa3on.openai_client import SuggestionClient


class FakeRepo:
    def __init__(self):
        self.connections = []
        self.messages = []
        self.suggestions = []
        self.memories = []
        self.sent = []
        self.rejected = []

    async def upsert_business_connection(self, connection, raw_update):
        self.connections.append((connection, raw_update))

    async def create_business_message(self, message, raw_update):
        self.messages.append((message, raw_update))
        return 42

    async def save_suggestions(self, business_message_id, suggestions):
        self.suggestions.append((business_message_id, suggestions))

    async def set_owner_approval_message_id(self, business_message_id, owner_message_id):
        self.owner = (business_message_id, owner_message_id)

    async def add_memory(self, business_connection_id, business_message_id, event_type, content):
        self.memories.append((business_connection_id, business_message_id, event_type, content))

    async def get_suggestion_for_approval(self, business_message_id, index):
        return {"text": f"reply {index}", "business_connection_id": "bc_1", "chat_id": 100}

    async def mark_sent(self, business_message_id, index):
        self.sent.append((business_message_id, index))

    async def mark_rejected(self, business_message_id):
        self.rejected.append(business_message_id)


class FakeTelegram:
    def __init__(self):
        self.messages = []
        self.callbacks = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return {"result": {"message_id": 777}}

    async def answer_callback_query(self, callback_query_id, text=None):
        self.callbacks.append((callback_query_id, text))
        return {"ok": True}


class FakeSuggestions:
    async def generate(self, message_text):
        return ["one", "two", "three"]


@pytest.mark.asyncio
async def test_business_message_generates_three_suggestions_and_owner_card():
    repo = FakeRepo()
    telegram = FakeTelegram()
    handlers = UpdateHandlers(repo=repo, telegram=telegram, suggestions=FakeSuggestions(), owner_chat_id=999)

    await handlers.handle_update({
        "business_message": {
            "message_id": 7,
            "business_connection_id": "bc_1",
            "chat": {"id": 100},
            "from": {"id": 200},
            "text": "Need help",
        }
    })

    assert repo.suggestions == [(42, ["one", "two", "three"])]
    assert telegram.messages[0]["chat_id"] == 999
    assert telegram.messages[0]["reply_markup"] == approval_keyboard(42)
    assert repo.owner == (42, 777)
    assert repo.memories[0][2] == "incoming_business_message"


@pytest.mark.asyncio
async def test_send_callback_replies_with_business_connection_id():
    repo = FakeRepo()
    telegram = FakeTelegram()
    handlers = UpdateHandlers(repo=repo, telegram=telegram, suggestions=FakeSuggestions(), owner_chat_id=999)

    await handlers.handle_callback_query({"id": "cb_1", "data": "send:42:2"})

    assert telegram.messages[0] == {"chat_id": 100, "text": "reply 2", "business_connection_id": "bc_1"}
    assert repo.sent == [(42, 2)]
    assert telegram.callbacks == [("cb_1", "Sent suggestion 2")]


@pytest.mark.asyncio
async def test_reject_callback_persists_rejection():
    repo = FakeRepo()
    telegram = FakeTelegram()
    handlers = UpdateHandlers(repo=repo, telegram=telegram, suggestions=FakeSuggestions(), owner_chat_id=999)

    await handlers.handle_callback_query({"id": "cb_2", "data": "reject:42"})

    assert repo.rejected == [42]
    assert repo.memories[0][2] == "reply_rejected"
    assert telegram.callbacks == [("cb_2", "Rejected")]


def test_approval_text_includes_exactly_three_options():
    text = approval_text("hello", ["a", "b", "c"])
    assert "1. a" in text
    assert "2. b" in text
    assert "3. c" in text


def test_suggestion_parser_requires_json_array():
    assert SuggestionClient._parse('["a", "b", "c"]') == ["a", "b", "c"]
