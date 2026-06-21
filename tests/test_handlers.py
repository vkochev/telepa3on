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
        self.status = "pending"
        self.owner_chat_id = 999
        self.business_connections = {}
        self.recent_dialog = [{"sender_id": 200, "text": "Earlier question"}]
        self.loaded_dialog_requests = []
        self.loaded_memory_requests = []
        self.loaded_memories = [{"event_type": "preference", "content": {"tone": "friendly"}}]
        self.reply_suggestions = ["Thanks, I can help.", "I can help with that.", "Sure, happy to help."]

    async def upsert_business_connection(self, connection, raw_update):
        self.connections.append((connection, raw_update))

    async def get_business_connection(self, business_connection_id):
        return self.business_connections.get(business_connection_id)

    async def create_business_message(self, message, raw_update, owner_chat_id):
        self.owner_chat_id = owner_chat_id
        self.messages.append((message, raw_update, owner_chat_id))
        return 42

    async def get_recent_dialog(self, business_connection_id, chat_id, limit=10):
        self.loaded_dialog_requests.append((business_connection_id, chat_id, limit))
        return self.recent_dialog

    async def get_memories(self, business_connection_id, chat_id=None, limit=10):
        self.loaded_memory_requests.append((business_connection_id, chat_id, limit))
        return self.loaded_memories

    async def save_suggestions(self, business_message_id, suggestions):
        self.suggestions.append((business_message_id, suggestions))

    async def set_owner_approval_message_id(self, business_message_id, owner_message_id):
        self.owner = (business_message_id, owner_message_id)

    async def add_memory(self, business_connection_id, business_message_id, event_type, content):
        self.memories.append((business_connection_id, business_message_id, event_type, content))

    async def get_suggestion_for_approval(self, business_message_id, index):
        return {
            "text": f"reply {index}",
            "incoming_text": "Need help",
            "business_connection_id": "bc_1",
            "chat_id": 100,
            "telegram_message_id": 7,
            "status": self.status,
            "owner_chat_id": self.owner_chat_id,
        }

    async def get_reply_suggestions(self, business_message_id):
        return self.reply_suggestions

    async def get_message_context(self, business_message_id):
        return {
            "business_connection_id": "bc_1",
            "chat_id": 100,
            "text": "Need help",
            "status": self.status,
            "owner_chat_id": self.owner_chat_id,
        }

    async def mark_sent(self, business_message_id, index):
        self.sent.append((business_message_id, index))
        self.status = "sent"

    async def mark_rejected(self, business_message_id):
        self.rejected.append(business_message_id)
        self.status = "rejected"


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
    def __init__(self):
        self.calls = []

    async def generate_reply_suggestions(self, incoming_text, recent_dialog, memories):
        self.calls.append((incoming_text, recent_dialog, memories))
        return ["one", "two", "three"]


def callback(data: str, user_id: int = 999):
    return {"id": "cb_1", "data": data, "from": {"id": user_id}, "message": {"chat": {"id": 999}}}


@pytest.mark.asyncio
async def test_business_connection_is_stored():
    repo = FakeRepo()
    handlers = UpdateHandlers(repo=repo, telegram=FakeTelegram(), suggestions=FakeSuggestions(), owner_chat_id=999)

    update = {"business_connection": {"id": "bc_1", "is_enabled": True}}
    await handlers.handle_update(update)

    assert repo.connections == [(update["business_connection"], update)]


@pytest.mark.asyncio
async def test_business_message_generates_three_suggestions_and_owner_card():
    repo = FakeRepo()
    telegram = FakeTelegram()
    suggestions = FakeSuggestions()
    handlers = UpdateHandlers(repo=repo, telegram=telegram, suggestions=suggestions, owner_chat_id=999)

    await handlers.handle_update({
        "business_message": {
            "message_id": 7,
            "business_connection_id": "bc_1",
            "chat": {"id": 100},
            "from": {"id": 200},
            "text": "Need help",
        }
    })

    assert repo.loaded_dialog_requests == [("bc_1", 100, 10)]
    assert repo.loaded_memory_requests == [("bc_1", 100, 10)]
    assert suggestions.calls == [("Need help", repo.recent_dialog, repo.loaded_memories)]
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

    await handlers.handle_callback_query(callback("send:42:2"))

    assert telegram.messages[0] == {
        "chat_id": 100,
        "text": "reply 2",
        "business_connection_id": "bc_1",
        "reply_parameters": {"message_id": 7},
    }
    assert repo.sent == [(42, 2)]
    assert telegram.callbacks == [("cb_1", "Sent suggestion 2")]


@pytest.mark.asyncio
async def test_callback_from_non_owner_is_rejected():
    repo = FakeRepo()
    telegram = FakeTelegram()
    handlers = UpdateHandlers(repo=repo, telegram=telegram, suggestions=FakeSuggestions(), owner_chat_id=999)

    await handlers.handle_callback_query(callback("send:42:1", user_id=123))

    assert telegram.messages == []
    assert repo.sent == []
    assert telegram.callbacks == [("cb_1", "Only the routed owner can approve this reply")]


@pytest.mark.asyncio
async def test_already_processed_callback_is_idempotent():
    repo = FakeRepo()
    repo.status = "sent"
    telegram = FakeTelegram()
    handlers = UpdateHandlers(repo=repo, telegram=telegram, suggestions=FakeSuggestions(), owner_chat_id=999)

    await handlers.handle_callback_query(callback("send:42:1"))

    assert telegram.messages == []
    assert telegram.callbacks == [("cb_1", "This message was already processed")]


@pytest.mark.asyncio
async def test_reject_callback_persists_rejection_with_business_connection_memory():
    repo = FakeRepo()
    telegram = FakeTelegram()
    handlers = UpdateHandlers(repo=repo, telegram=telegram, suggestions=FakeSuggestions(), owner_chat_id=999)

    await handlers.handle_callback_query(callback("reject:42"))

    assert repo.rejected == [42]
    assert repo.memories[0][0] == "bc_1"
    assert repo.memories[0][2] == "reply_rejected"
    assert telegram.callbacks == [("cb_1", "Rejected")]


@pytest.mark.asyncio
async def test_business_message_routes_approval_to_stored_business_connection_user_chat_id():
    repo = FakeRepo()
    repo.business_connections["bc_2"] = {"business_connection_id": "bc_2", "user_chat_id": 555}
    telegram = FakeTelegram()
    handlers = UpdateHandlers(repo=repo, telegram=telegram, suggestions=FakeSuggestions(), owner_chat_id=999)

    await handlers.handle_update({
        "business_message": {
            "message_id": 8,
            "business_connection_id": "bc_2",
            "chat": {"id": 100},
            "from": {"id": 200},
            "text": "Route me",
        }
    })

    assert repo.messages[0][2] == 555
    assert telegram.messages[0]["chat_id"] == 555
    assert repo.memories[0][3]["owner_chat_id"] == 555


@pytest.mark.asyncio
async def test_owner_chat_routes_override_stored_business_connection_user_chat_id():
    repo = FakeRepo()
    repo.business_connections["bc_2"] = {"business_connection_id": "bc_2", "user_chat_id": 555}
    telegram = FakeTelegram()
    handlers = UpdateHandlers(
        repo=repo,
        telegram=telegram,
        suggestions=FakeSuggestions(),
        owner_chat_id=999,
        owner_chat_routes={"bc_2": 777},
    )

    await handlers.handle_update({
        "business_message": {
            "message_id": 8,
            "business_connection_id": "bc_2",
            "chat": {"id": 100},
            "from": {"id": 200},
            "text": "Route me",
        }
    })

    assert repo.messages[0][2] == 777
    assert telegram.messages[0]["chat_id"] == 777
    assert repo.memories[0][3]["owner_chat_id"] == 777


@pytest.mark.asyncio
async def test_owner_chat_id_is_used_when_no_route_or_stored_user_chat_id_exists():
    repo = FakeRepo()
    telegram = FakeTelegram()
    handlers = UpdateHandlers(repo=repo, telegram=telegram, suggestions=FakeSuggestions(), owner_chat_id=999)

    await handlers.handle_update({
        "business_message": {
            "message_id": 8,
            "business_connection_id": "bc_missing",
            "chat": {"id": 100},
            "from": {"id": 200},
            "text": "Route me",
        }
    })

    assert repo.messages[0][2] == 999
    assert telegram.messages[0]["chat_id"] == 999
    assert repo.memories[0][3]["owner_chat_id"] == 999


@pytest.mark.asyncio
async def test_callback_from_default_owner_is_rejected_for_routed_message():
    repo = FakeRepo()
    repo.owner_chat_id = 555
    telegram = FakeTelegram()
    handlers = UpdateHandlers(repo=repo, telegram=telegram, suggestions=FakeSuggestions(), owner_chat_id=999)

    await handlers.handle_callback_query(callback("send:42:1", user_id=999))

    assert telegram.messages == []
    assert repo.sent == []
    assert telegram.callbacks == [("cb_1", "Only the routed owner can approve this reply")]


def test_approval_text_includes_exactly_three_options():
    text = approval_text("hello", ["a", "b", "c"])
    assert "1. a" in text
    assert "2. b" in text
    assert "3. c" in text


def test_suggestion_parser_accepts_json_array_object_or_fence():
    assert SuggestionClient._parse('["a", "b", "c"]') == ["a", "b", "c"]
    assert SuggestionClient._parse('{"suggestions": ["a", "b", "c"]}') == ["a", "b", "c"]
    assert SuggestionClient._parse('```json\n["a", "b", "c"]\n```') == ["a", "b", "c"]


def test_suggestion_parser_requires_exactly_three():
    with pytest.raises(RuntimeError, match="exactly 3"):
        SuggestionClient._parse('["a", "b"]')


@pytest.mark.asyncio
async def test_edited_business_message_records_minimal_memory_only():
    repo = FakeRepo()
    telegram = FakeTelegram()
    handlers = UpdateHandlers(repo=repo, telegram=telegram, suggestions=FakeSuggestions(), owner_chat_id=999)

    update = {
        "edited_business_message": {
            "message_id": 9,
            "business_connection_id": "bc_1",
            "chat": {"id": 100},
            "text": "Edited text",
        }
    }
    await handlers.handle_update(update)

    assert repo.messages == []
    assert repo.suggestions == []
    assert telegram.messages == []
    assert repo.memories == [
        (
            "bc_1",
            None,
            "edited_business_message",
            {"message_id": 9, "chat_id": 100, "text": "Edited text", "raw_update": update},
        )
    ]


@pytest.mark.asyncio
async def test_deleted_business_messages_records_minimal_memory_only():
    repo = FakeRepo()
    telegram = FakeTelegram()
    handlers = UpdateHandlers(repo=repo, telegram=telegram, suggestions=FakeSuggestions(), owner_chat_id=999)

    update = {
        "deleted_business_messages": {
            "business_connection_id": "bc_1",
            "chat": {"id": 100},
            "message_ids": [9, 10],
        }
    }
    await handlers.handle_update(update)

    assert repo.messages == []
    assert repo.suggestions == []
    assert telegram.messages == []
    assert repo.memories == [
        (
            "bc_1",
            None,
            "deleted_business_messages",
            {"chat_id": 100, "message_ids": [9, 10], "raw_update": update},
        )
    ]

@pytest.mark.asyncio
async def test_suggestion_client_prompt_includes_recent_dialog_and_memories():
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '["a", "b", "c"]'}}]}

    class FakeHttpClient:
        def __init__(self):
            self.payload = None

        async def post(self, url, headers, json):
            self.payload = json
            return FakeResponse()

    http_client = FakeHttpClient()
    client = SuggestionClient(api_key="key", base_url="https://example.test", model="model", client=http_client)
    recent_dialog = [{"sender_id": 1, "text": "likes short answers"}]
    memories = [{"event_type": "approved_reply_sent", "content": {"text": "Sure thing"}}]

    assert await client.generate_reply_suggestions("Can you help?", recent_dialog, memories) == ["a", "b", "c"]

    user_content = http_client.payload["messages"][1]["content"]
    assert "Can you help?" in user_content
    assert "likes short answers" in user_content
    assert "approved_reply_sent" in user_content
    assert "Sure thing" in user_content


@pytest.mark.asyncio
async def test_send_callback_persists_approved_structured_memory():
    repo = FakeRepo()
    repo.reply_suggestions = [
        "Longer alternative with lots of extra details",
        "Thanks, I can help.",
        "Another detailed alternative",
    ]
    telegram = FakeTelegram()
    handlers = UpdateHandlers(repo=repo, telegram=telegram, suggestions=FakeSuggestions(), owner_chat_id=999)

    await handlers.handle_callback_query(callback("send:42:2"))

    structured = [memory for memory in repo.memories if memory[2] == "structured_memory"]
    assert structured == [
        (
            "bc_1",
            42,
            "structured_memory",
            {
                "scope": "chat",
                "kind": "style",
                "content": "Owner tends to approve concise replies.",
                "confidence": 0.62,
            },
        )
    ]


@pytest.mark.asyncio
async def test_reject_callback_persists_rejected_structured_memory():
    repo = FakeRepo()
    repo.reply_suggestions = [
        "I can help with that today.",
        "I can help with that now.",
        "I can help with that here.",
    ]
    telegram = FakeTelegram()
    handlers = UpdateHandlers(repo=repo, telegram=telegram, suggestions=FakeSuggestions(), owner_chat_id=999)

    await handlers.handle_callback_query(callback("reject:42"))

    structured = [memory for memory in repo.memories if memory[2] == "structured_memory"]
    assert structured == [
        (
            "bc_1",
            42,
            "structured_memory",
            {
                "scope": "chat",
                "kind": "correction",
                "content": "Owner rejected a set of very similar suggestions; offer more varied options next time.",
                "confidence": 0.66,
            },
        )
    ]
