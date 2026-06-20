import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# Fixtures


@pytest.fixture
def mock_stream_chat():
    """Replace the real Ollama call with a fake async generator.

    Captures the messages it was called with in `captured` so tests
    can verify main.py is passing the conversation history through
    correctly, without needing Ollama running at all.
    """
    captured = {}

    async def fake_stream(messages):
        captured["messages"] = messages
        for token in ["Hello", " world", "!"]:
            yield token

    with patch("app.main.stream_chat", fake_stream):
        yield captured


@pytest.fixture
def mock_stream_chat_empty():
    """A fake stream that yields nothing — simulates an empty response."""

    async def fake_stream(messages):
        return
        yield  # pragma: no cover. makes this an async generator

    with patch("app.main.stream_chat", fake_stream):
        yield


@pytest.fixture
def mock_stream_chat_error():
    """A fake stream that raises partway through — simulates Ollama failing mid-stream."""

    async def fake_stream(messages):
        yield "Starting..."
        raise ConnectionError("Ollama connection lost")

    with patch("app.main.stream_chat", fake_stream):
        yield


# Health Check


class TestHealthCheck:
    def test_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_returns_healthy_status(self):
        response = client.get("/health")
        assert response.json() == {"status": "healthy"}


# POST /chat — Happy Path


class TestChatEndpoint:
    def test_returns_200(self, mock_stream_chat):
        response = client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.status_code == 200

    def test_content_type_is_event_stream(self, mock_stream_chat):
        response = client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.headers["content-type"].startswith("text/event-stream")

    def test_streams_all_tokens_in_order(self, mock_stream_chat):
        response = client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.text == "Hello world!"

    def test_calls_stream_chat_with_correct_messages(self, mock_stream_chat):
        client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert mock_stream_chat["messages"] == [{"role": "user", "content": "Hi"}]

    def test_passes_full_conversation_history(self, mock_stream_chat):
        payload = {
            "messages": [
                {"role": "user", "content": "My name is Michael"},
                {"role": "assistant", "content": "Nice to meet you, Michael!"},
                {"role": "user", "content": "What's my name?"},
            ]
        }
        client.post("/chat", json=payload)
        assert mock_stream_chat["messages"] == payload["messages"]

    def test_empty_token_stream_returns_200(self, mock_stream_chat_empty):
        response = client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.status_code == 200

    def test_empty_token_stream_returns_empty_body(self, mock_stream_chat_empty):
        response = client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "Hi"}]},
        )
        assert response.text == ""


# POST /chat — Validation


class TestChatValidation:
    def test_missing_messages_returns_422(self):
        response = client.post("/chat", json={})
        assert response.status_code == 422

    def test_missing_role_returns_422(self):
        response = client.post(
            "/chat",
            json={"messages": [{"content": "Hi"}]},
        )
        assert response.status_code == 422

    def test_missing_content_returns_422(self):
        response = client.post(
            "/chat",
            json={"messages": [{"role": "user"}]},
        )
        assert response.status_code == 422

    def test_invalid_role_returns_422(self):
        response = client.post(
            "/chat",
            json={"messages": [{"role": "system", "content": "Hi"}]},
        )
        assert response.status_code == 422

    def test_non_list_messages_returns_422(self):
        response = client.post(
            "/chat",
            json={"messages": "not a list"},
        )
        assert response.status_code == 422

    def test_empty_string_content_returns_422(self):
        response = client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": ""}]},
        )
        assert response.status_code == 422

    def test_valid_assistant_role_is_accepted(self, mock_stream_chat):
        response = client.post(
            "/chat",
            json={"messages": [{"role": "assistant", "content": "Hi"}]},
        )
        assert response.status_code == 200


# llm.py Unit Tests


class TestStreamChat:
    @pytest.mark.asyncio
    async def test_yields_tokens_from_ollama_response(self):
        """Mock the raw HTTP stream from Ollama and verify stream_chat
        correctly parses each line and yields the content."""
        from app.services.llm import stream_chat
        import json

        fake_lines = [
            json.dumps({"message": {"content": "Hello"}, "done": False}),
            json.dumps({"message": {"content": " world"}, "done": False}),
            json.dumps({"message": {"content": ""}, "done": True}),
        ]

        class FakeResponse:
            async def aiter_lines(self):
                for line in fake_lines:
                    yield line

            def raise_for_status(self):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        class FakeClient:
            def stream(self, method, url, json):
                return FakeResponse()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        with patch("app.services.llm.httpx.AsyncClient", return_value=FakeClient()):
            tokens = []
            async for token in stream_chat([{"role": "user", "content": "Hi"}]):
                tokens.append(token)

        assert tokens == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_stops_on_done_true(self):
        """Verify the generator stops yielding once Ollama signals done."""
        from app.services.llm import stream_chat
        import json

        fake_lines = [
            json.dumps({"message": {"content": "Hello"}, "done": False}),
            json.dumps({"message": {"content": ""}, "done": True}),
            json.dumps({"message": {"content": "Should not appear"}, "done": False}),
        ]

        class FakeResponse:
            async def aiter_lines(self):
                for line in fake_lines:
                    yield line

            def raise_for_status(self):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        class FakeClient:
            def stream(self, method, url, json):
                return FakeResponse()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        with patch("app.services.llm.httpx.AsyncClient", return_value=FakeClient()):
            tokens = []
            async for token in stream_chat([{"role": "user", "content": "Hi"}]):
                tokens.append(token)

        assert "Should not appear" not in tokens
