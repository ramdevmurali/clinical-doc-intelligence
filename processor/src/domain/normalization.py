"""Deterministic clinical normalization helpers."""

from __future__ import annotations

import re

from processor.src.domain.extraction_schema import ClinicalItemType


class NormalizationError(ValueError):
    """Raised when clinical normalization input is invalid or unknown."""


_ITEM_TYPE_ALIASES: dict[str, ClinicalItemType] = {
    "diagnosis": ClinicalItemType.CONDITION,
    "problem": ClinicalItemType.CONDITION,
    "drug": ClinicalItemType.MEDICATION,
    "med": ClinicalItemType.MEDICATION,
    "lab": ClinicalItemType.LAB_RESULT,
    "referral": ClinicalItemType.ORDER,
}

_STATUS_VALUES: frozenset[str] = frozenset(
    {
        "active",
        "historical",
        "resolved",
        "in_remission",
        "performed",
        "not_performed",
        "planned",
        "ordered",
        "referred",
        "pending",
        "administered",
        "started",
        "stopped",
        "discontinued",
        "held",
        "prescribed",
        "none_known",
        "possible",
        "rule_out",
        "unlikely_not_excluded",
        "planned_change",
    }
)

_STATUS_ALIASES: dict[str, str] = {
    "in remission": "in_remission",
    "in-remission": "in_remission",
    "medication change planned": "planned_change",
    "no known": "none_known",
    "none known": "none_known",
    "not performed": "not_performed",
    "not-performed": "not_performed",
    "planned change": "planned_change",
    "rule out": "rule_out",
    "rule-out": "rule_out",
}

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Normalize an ordinary clinical display name."""

    compact = _compact_required_text(name, "name")
    return compact.lower()


def normalize_item_type(item_type: str) -> ClinicalItemType:
    """Normalize an item type or alias to ``ClinicalItemType``."""

    key = _normalize_key(_compact_required_text(item_type, "item_type"))

    try:
        return ClinicalItemType(key)
    except ValueError:
        pass

    alias = _ITEM_TYPE_ALIASES.get(key)
    if alias:
        return alias

    raise NormalizationError(f"Unknown clinical item type: {item_type}")


def normalize_status(status: str | None) -> str | None:
    """Normalize a clinical status string to a stable internal value."""

    if status is None:
        return None

    compact = _compact_required_text(status, "status")
    key = _normalize_key(compact)

    alias = _STATUS_ALIASES.get(key)
    if alias:
        return alias

    stable = key.replace(" ", "_").replace("-", "_")
    if stable in _STATUS_VALUES:
        return stable

    raise NormalizationError(f"Unknown clinical status: {status}")


def _compact_required_text(value: str, field_name: str) -> str:
    if not value or not value.strip():
        raise NormalizationError(f"{field_name} is required.")
    return _WHITESPACE_RE.sub(" ", value.strip())


def _normalize_key(value: str) -> str:
    return value.strip().lower()
