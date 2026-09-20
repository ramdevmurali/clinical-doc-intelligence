"""Strict parsing for raw AI extraction candidate responses."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from processor.src.domain.extraction_schema import ClinicalItemType
from processor.src.domain.normalization import (
    NormalizationError,
    normalize_item_type,
    normalize_name,
    normalize_status,
)


AI_EXTRACTION_RESPONSE_SCHEMA_VERSION = "ai-extraction-response-v1"

_TOP_LEVEL_FIELDS = frozenset({"schema_version", "document_id", "items"})
_ITEM_FIELDS = frozenset(
    {
        "type",
        "name",
        "status",
        "confidence",
        "source_quote",
        "section_id",
        "section_name",
    }
)
_REQUIRED_ITEM_FIELDS = frozenset({"type", "name", "source_quote", "section_id", "section_name"})


@dataclass(frozen=True)
class AiCandidateItem:
    """A model-proposed clinical item before local source grounding."""

    item_type: ClinicalItemType
    name: str
    status: str | None
    confidence: float | None
    source_quote: str
    section_id: str
    section_name: str

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "name")
        _require_non_empty(self.source_quote, "source_quote")
        _require_non_empty(self.section_id, "section_id")
        _require_non_empty(self.section_name, "section_name")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise AiExtractionResponseError("confidence must be between 0.0 and 1.0")


class AiExtractionResponseError(ValueError):
    """Raised when a raw AI response violates the candidate contract."""


def parse_ai_extraction_response(raw_content: str, *, document_id: str) -> tuple[AiCandidateItem, ...]:
    """Parse strict candidate JSON emitted by an AI provider."""

    if not raw_content or not raw_content.strip():
        raise AiExtractionResponseError("response content is empty")
    stripped = raw_content.strip()
    if stripped.startswith("```") or stripped.endswith("```"):
        raise AiExtractionResponseError("response must be raw JSON, not markdown fenced JSON")

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise AiExtractionResponseError(f"response is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise AiExtractionResponseError("response must be a JSON object")
    _reject_unknown_fields(payload, _TOP_LEVEL_FIELDS, "response")

    schema_version = payload.get("schema_version")
    if schema_version != AI_EXTRACTION_RESPONSE_SCHEMA_VERSION:
        raise AiExtractionResponseError(
            f"response schema_version must be {AI_EXTRACTION_RESPONSE_SCHEMA_VERSION}"
        )
    if payload.get("document_id") != document_id:
        raise AiExtractionResponseError("response document_id does not match requested document")

    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise AiExtractionResponseError("response items must be a list")

    return tuple(_candidate_from_mapping(raw_item, index) for index, raw_item in enumerate(raw_items))


def _candidate_from_mapping(raw_item: object, index: int) -> AiCandidateItem:
    context = f"items[{index}]"
    if not isinstance(raw_item, dict):
        raise AiExtractionResponseError(f"{context} must be an object")
    _reject_unknown_fields(raw_item, _ITEM_FIELDS, context)
    missing = sorted(field for field in _REQUIRED_ITEM_FIELDS if field not in raw_item)
    if missing:
        raise AiExtractionResponseError(f"{context} missing required fields: {', '.join(missing)}")

    try:
        return AiCandidateItem(
            item_type=normalize_item_type(_required_string(raw_item["type"], "type", context)),
            name=normalize_name(_required_string(raw_item["name"], "name", context)),
            status=normalize_status(_optional_string(raw_item.get("status"), "status", context)),
            confidence=_optional_confidence(raw_item.get("confidence"), context),
            source_quote=_required_string(raw_item["source_quote"], "source_quote", context),
            section_id=_required_string(raw_item["section_id"], "section_id", context),
            section_name=_required_string(raw_item["section_name"], "section_name", context),
        )
    except NormalizationError as exc:
        raise AiExtractionResponseError(f"{context} normalization failed: {exc}") from exc


def _reject_unknown_fields(payload: dict[str, Any], allowed_fields: frozenset[str], context: str) -> None:
    unknown_fields = sorted(set(payload) - allowed_fields)
    if unknown_fields:
        raise AiExtractionResponseError(f"{context} has unknown fields: {', '.join(unknown_fields)}")


def _required_string(value: object, field_name: str, context: str) -> str:
    if not isinstance(value, str):
        raise AiExtractionResponseError(f"{context} {field_name} must be a string")
    _require_non_empty(value, f"{context} {field_name}")
    return value


def _optional_string(value: object, field_name: str, context: str) -> str | None:
    if value is None:
        return None
    return _required_string(value, field_name, context)


def _optional_confidence(value: object, context: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AiExtractionResponseError(f"{context} confidence must be a number")
    confidence = float(value)
    if not 0.0 <= confidence <= 1.0:
        raise AiExtractionResponseError(f"{context} confidence must be between 0.0 and 1.0")
    return confidence


def _require_non_empty(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise AiExtractionResponseError(f"{field_name} is required")
