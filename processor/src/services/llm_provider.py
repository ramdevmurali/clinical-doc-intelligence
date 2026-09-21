"""LLM provider abstraction for the AI extraction harness."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import time
from urllib.parse import quote, urlencode
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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


class GeminiGenerateContentProvider:
    """Gemini generateContent provider for opt-in local synthetic-note runs."""

    name = "gemini"
    default_endpoint = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str | None = None,
        urlopen_func=urlopen,
    ) -> None:
        if not api_key or not api_key.strip():
            raise LlmProviderError("GEMINI_API_KEY or GOOGLE_API_KEY is required for provider gemini")
        self._api_key = api_key
        self._endpoint = endpoint or self.default_endpoint
        self._urlopen = urlopen_func

    def complete_json(
        self,
        *,
        model: str,
        messages: tuple[PromptMessage, ...],
        timeout_seconds: float,
    ) -> LlmResponse:
        if not model or not model.strip():
            raise LlmProviderError("model is required for provider gemini")
        if timeout_seconds <= 0:
            raise LlmProviderError("timeout_seconds must be positive")

        payload = _gemini_payload(messages=messages)
        request = Request(
            _gemini_generate_content_url(self._endpoint, model, self._api_key),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        started = time.perf_counter()
        try:
            with self._urlopen(request, timeout=timeout_seconds) as response:
                raw_body = response.read().decode("utf-8")
        except HTTPError as exc:
            raise LlmProviderError(f"gemini provider request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise LlmProviderError(f"gemini provider request failed: {exc.reason}") from exc
        except TimeoutError as exc:
            raise LlmProviderError("gemini provider request timed out") from exc
        except OSError as exc:
            raise LlmProviderError(f"gemini provider request failed: {exc}") from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as exc:
            raise LlmProviderError("gemini provider returned invalid JSON") from exc
        if not isinstance(body, dict):
            raise LlmProviderError("gemini provider returned a non-object response")

        return LlmResponse(
            provider=self.name,
            model=model,
            content=_gemini_output_text(body),
            latency_ms=latency_ms,
            input_tokens=_gemini_usage_token(body, "promptTokenCount"),
            output_tokens=_gemini_usage_token(body, "candidatesTokenCount"),
            request_id=_optional_string(body.get("responseId")),
        )


def provider_for_name(name: str) -> LlmProvider:
    """Return a configured provider by stable CLI name."""

    if name == "fixture":
        return FixtureLlmProvider()
    if name == "gemini":
        return GeminiGenerateContentProvider(
            api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", ""),
            endpoint=os.environ.get("GEMINI_API_ENDPOINT") or None,
        )
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


def _gemini_generate_content_url(endpoint: str, model: str, api_key: str) -> str:
    base = endpoint.rstrip("/")
    quoted_model = quote(model.strip(), safe="")
    query = urlencode({"key": api_key})
    return f"{base}/models/{quoted_model}:generateContent?{query}"


def _gemini_payload(messages: tuple[PromptMessage, ...]) -> dict:
    system_parts = [{"text": message.content} for message in messages if message.role == "system"]
    user_parts = [{"text": message.content} for message in messages if message.role == "user"]
    if not user_parts:
        raise LlmProviderError("gemini provider requires at least one user prompt message")

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": user_parts,
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": _candidate_response_schema(),
        },
    }
    if system_parts:
        payload["systemInstruction"] = {"parts": system_parts}
    return payload


def _candidate_response_schema() -> dict:
    item_schema = {
        "type": "OBJECT",
        "properties": {
            "type": {"type": "STRING"},
            "name": {"type": "STRING"},
            "status": {"type": "STRING", "nullable": True},
            "confidence": {"type": "NUMBER", "nullable": True},
            "source_quote": {"type": "STRING"},
            "section_id": {"type": "STRING"},
            "section_name": {"type": "STRING"},
        },
        "required": [
            "type",
            "name",
            "source_quote",
            "section_id",
            "section_name",
        ],
    }
    return {
        "type": "OBJECT",
        "properties": {
            "schema_version": {"type": "STRING"},
            "document_id": {"type": "STRING"},
            "items": {"type": "ARRAY", "items": item_schema},
        },
        "required": ["schema_version", "document_id", "items"],
    }


def _gemini_output_text(body: dict) -> str:
    candidates = body.get("candidates")
    if not isinstance(candidates, list):
        raise LlmProviderError("gemini provider response did not include candidates")

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        rendered_parts = []
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                rendered_parts.append(text)
        if rendered_parts:
            return "".join(rendered_parts)

    raise LlmProviderError("gemini provider response did not include output text")


def _gemini_usage_token(body: dict, field_name: str) -> int | None:
    usage = body.get("usageMetadata")
    if not isinstance(usage, dict):
        return None
    value = usage.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None
