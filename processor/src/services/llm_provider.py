"""LLM provider abstraction for the AI extraction harness."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Protocol

from processor.src.domain.ai_extraction_prompt import PromptMessage
from processor.src.domain.ai_extraction_response import AI_EXTRACTION_RESPONSE_SCHEMA_VERSION


@dataclass(frozen=True)
class LlmResponse:
    """Raw provider response plus provider metadata."""

    provider: str
    model: str
    content: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_id: str | None = None


class LlmProvider(Protocol):
    """Small provider protocol used by local extraction scripts."""

    name: str

    def complete_json(
        self,
        *,
        model: str,
        messages: tuple[PromptMessage, ...],
        timeout_seconds: float,
    ) -> LlmResponse:
        """Return raw JSON content for a prompt."""


class FixtureLlmProvider:
    """Deterministic provider for local tests and first harness wiring."""

    name = "fixture"

    def __init__(self, responses_by_document_id: dict[str, str] | None = None) -> None:
        self._responses_by_document_id = responses_by_document_id or {}

    def complete_json(
        self,
        *,
        model: str,
        messages: tuple[PromptMessage, ...],
        timeout_seconds: float,
    ) -> LlmResponse:
        document_id = _document_id_from_messages(messages)
        content = self._responses_by_document_id.get(document_id)
        if content is None:
            content = _empty_response(document_id)
        return LlmResponse(
            provider=self.name,
            model=model,
            content=content,
            latency_ms=0,
            input_tokens=None,
            output_tokens=None,
            request_id=f"fixture:{document_id}",
        )


def provider_for_name(name: str) -> LlmProvider:
    """Return a configured provider by stable CLI name."""

    if name == "fixture":
        return FixtureLlmProvider()
    raise LlmProviderError(f"unsupported provider: {name}")


class LlmProviderError(ValueError):
    """Raised for provider configuration failures."""


def _document_id_from_messages(messages: tuple[PromptMessage, ...]) -> str:
    for message in messages:
        match = re.search(r"^Document ID: (?P<document_id>\S+)\s*$", message.content, flags=re.MULTILINE)
        if match:
            return match.group("document_id")
    return "document"


def _empty_response(document_id: str) -> str:
    return json.dumps(
        {
            "schema_version": AI_EXTRACTION_RESPONSE_SCHEMA_VERSION,
            "document_id": document_id,
            "items": [],
        }
    )
