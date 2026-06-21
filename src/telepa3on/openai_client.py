from __future__ import annotations

import json
import re

import httpx


class SuggestionClient:
    def __init__(self, *, api_key: str, base_url: str, model: str, client: httpx.AsyncClient | None = None) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._client = client or httpx.AsyncClient(timeout=30)
        self._owns_client = client is None

    async def generate(self, message_text: str) -> list[str]:
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": "Generate exactly three concise, helpful Telegram business reply suggestions. Return JSON array of strings only.",
                },
                {"role": "user", "content": message_text},
            ],
            "temperature": 0.4,
        }
        response = await self._client.post(
            f"{self._base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json=payload,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return self._parse(content)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @staticmethod
    def _parse(content: str) -> list[str]:
        cleaned = content.strip()
        fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
        if fence:
            cleaned = fence.group(1).strip()
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            parsed = parsed.get("suggestions")
        if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
            raise RuntimeError("Suggestion response must be a JSON array of strings")
        suggestions = [item.strip() for item in parsed if item.strip()]
        if len(suggestions) != 3:
            raise RuntimeError("OpenAI-compatible API must return exactly 3 suggestions")
        return suggestions
