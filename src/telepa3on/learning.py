from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Literal

MemoryKind = Literal["style", "preference", "boundary", "correction"]
ALLOWED_KINDS: set[str] = {"style", "preference", "boundary", "correction"}


@dataclass(frozen=True)
class StructuredMemory:
    scope: str
    kind: MemoryKind
    content: str
    confidence: float

    def asdict(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "kind": self.kind,
            "content": self.content,
            "confidence": self.confidence,
        }


class LearningExtractor:
    """Conservative deterministic extractor for owner approval decisions."""

    def extract(
        self,
        *,
        incoming_message: str,
        suggestions: list[str],
        selected_suggestion: str | None = None,
        rejected: bool = False,
        existing_memories: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        if rejected:
            return self._extract_rejected(incoming_message, suggestions, existing_memories or [])
        if selected_suggestion is None:
            return []
        return self._extract_selected(selected_suggestion, existing_memories or [])

    def _extract_selected(self, selected_suggestion: str, existing_memories: list[dict[str, Any]]) -> list[dict[str, Any]]:
        selected = selected_suggestion.strip()
        if not selected:
            return []

        memories: list[StructuredMemory] = []
        if self._is_brief(selected) and not self._already_has(existing_memories, "style", "brief"):
            memories.append(StructuredMemory("chat", "style", "Owner tends to approve concise replies.", 0.62))
        if self._has_warm_tone(selected) and not self._already_has(existing_memories, "style", "warm"):
            memories.append(StructuredMemory("chat", "style", "Owner tends to approve warm, friendly wording.", 0.61))
        return [memory.asdict() for memory in memories[:1]]

    def _extract_rejected(
        self,
        incoming_message: str,
        suggestions: list[str],
        existing_memories: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized = [suggestion.strip() for suggestion in suggestions if suggestion and suggestion.strip()]
        if len(normalized) < 3 or not incoming_message.strip():
            return []
        if self._all_too_similar(normalized) and not self._already_has(existing_memories, "correction", "varied"):
            return [
                StructuredMemory(
                    "chat",
                    "correction",
                    "Owner rejected a set of very similar suggestions; offer more varied options next time.",
                    0.66,
                ).asdict()
            ]
        if all(self._is_brief(suggestion) for suggestion in normalized) and not self._already_has(existing_memories, "style", "detail"):
            return [
                StructuredMemory(
                    "chat",
                    "style",
                    "Owner rejected only very short suggestions; include at least one more specific option.",
                    0.6,
                ).asdict()
            ]
        return []

    @staticmethod
    def _is_brief(text: str) -> bool:
        return len(text.split()) <= 12

    @staticmethod
    def _has_warm_tone(text: str) -> bool:
        lower = text.lower()
        return any(token in lower for token in ("thanks", "thank you", "happy to", "glad", "please"))

    @staticmethod
    def _all_too_similar(suggestions: list[str]) -> bool:
        for left_index, left in enumerate(suggestions):
            for right in suggestions[left_index + 1 :]:
                if SequenceMatcher(None, left.lower(), right.lower()).ratio() < 0.72:
                    return False
        return True

    @staticmethod
    def _already_has(existing_memories: list[dict[str, Any]], kind: str, needle: str) -> bool:
        for memory in existing_memories:
            content = memory.get("content") if isinstance(memory, dict) else None
            event_type = memory.get("event_type") if isinstance(memory, dict) else None
            haystack = f"{event_type} {content}".lower()
            if kind in haystack and needle in haystack:
                return True
        return False
