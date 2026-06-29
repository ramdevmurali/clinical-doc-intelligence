"""Pure evaluation domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


class EvaluationError(ValueError):
    """Raised when evaluation inputs violate domain contracts."""


@dataclass(frozen=True)
class ExpectedClinicalItem:
    """Expected clinical item from a golden evaluation label."""

    item_type: str
    name: str
    status: str | None = None
    source_quote: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.item_type, "Expected item type")
        _require_non_empty_string(self.name, "Expected item name")
        _validate_optional_string(self.status, "Expected item status")
        _validate_optional_string(self.source_quote, "Expected item source_quote")


@dataclass(frozen=True)
class InvalidExtractionTrap:
    """Known invalid extraction pattern from a golden evaluation label."""

    item_type: str
    name: str
    forbidden_status: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.item_type, "Invalid extraction trap item type")
        _require_non_empty_string(self.name, "Invalid extraction trap name")
        _validate_optional_string(self.forbidden_status, "Invalid extraction trap forbidden_status")
        _validate_optional_string(self.reason, "Invalid extraction trap reason")


@dataclass(frozen=True)
class ItemMatch:
    """One deterministic match between an expected item and a predicted item."""

    expected_index: int
    predicted_index: int

    def __post_init__(self) -> None:
        _require_non_negative_int(self.expected_index, "ItemMatch expected_index")
        _require_non_negative_int(self.predicted_index, "ItemMatch predicted_index")


@dataclass(frozen=True)
class EvaluationIssue:
    """A deterministic evaluation issue with optional item/trap indexes."""

    issue_type: str
    message: str
    expected_index: int | None = None
    predicted_index: int | None = None
    trap_index: int | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.issue_type, "Evaluation issue type")
        _require_non_empty_string(self.message, "Evaluation issue message")
        _validate_optional_non_negative_int(self.expected_index, "Evaluation issue expected_index")
        _validate_optional_non_negative_int(self.predicted_index, "Evaluation issue predicted_index")
        _validate_optional_non_negative_int(self.trap_index, "Evaluation issue trap_index")


@dataclass(frozen=True)
class EvaluationResult:
    """Summary of a deterministic extraction evaluation run."""

    expected_item_count: int
    predicted_item_count: int
    matched_item_count: int
    missing_item_count: int
    extra_item_count: int
    invalid_trap_hit_count: int
    source_quote_failure_count: int
    matches: tuple[ItemMatch, ...] = field(default_factory=tuple)
    missing_expected_indexes: tuple[int, ...] = field(default_factory=tuple)
    extra_predicted_indexes: tuple[int, ...] = field(default_factory=tuple)
    invalid_trap_hits: tuple[EvaluationIssue, ...] = field(default_factory=tuple)
    source_quote_failures: tuple[EvaluationIssue, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        for field_name in (
            "expected_item_count",
            "predicted_item_count",
            "matched_item_count",
            "missing_item_count",
            "extra_item_count",
            "invalid_trap_hit_count",
            "source_quote_failure_count",
        ):
            _require_non_negative_int(getattr(self, field_name), f"EvaluationResult {field_name}")

        matches = _normalize_tuple(self.matches, "EvaluationResult matches")
        missing_expected_indexes = _normalize_tuple(
            self.missing_expected_indexes,
            "EvaluationResult missing_expected_indexes",
        )
        extra_predicted_indexes = _normalize_tuple(
            self.extra_predicted_indexes,
            "EvaluationResult extra_predicted_indexes",
        )
        invalid_trap_hits = _normalize_tuple(
            self.invalid_trap_hits,
            "EvaluationResult invalid_trap_hits",
        )
        source_quote_failures = _normalize_tuple(
            self.source_quote_failures,
            "EvaluationResult source_quote_failures",
        )

        for index in missing_expected_indexes:
            _require_non_negative_int(index, "EvaluationResult missing_expected_indexes item")
        for index in extra_predicted_indexes:
            _require_non_negative_int(index, "EvaluationResult extra_predicted_indexes item")

        object.__setattr__(self, "matches", matches)
        object.__setattr__(self, "missing_expected_indexes", missing_expected_indexes)
        object.__setattr__(self, "extra_predicted_indexes", extra_predicted_indexes)
        object.__setattr__(self, "invalid_trap_hits", invalid_trap_hits)
        object.__setattr__(self, "source_quote_failures", source_quote_failures)


def expected_items_from_json(expected_json: dict) -> tuple[ExpectedClinicalItem, ...]:
    """Parse golden expected items into evaluation domain objects."""

    _require_mapping(expected_json, "expected_json")
    raw_items = _optional_collection(expected_json, "items")
    return tuple(
        ExpectedClinicalItem(
            item_type=_required_field(raw_item, "type", f"items[{index}]"),
            name=_required_field(raw_item, "name", f"items[{index}]"),
            status=raw_item.get("status"),
            source_quote=raw_item.get("source_quote"),
        )
        for index, raw_item in enumerate(raw_items)
    )


def invalid_traps_from_json(expected_json: dict) -> tuple[InvalidExtractionTrap, ...]:
    """Parse golden invalid extraction traps into evaluation domain objects."""

    _require_mapping(expected_json, "expected_json")
    raw_traps = _optional_collection(expected_json, "invalid_extractions")
    return tuple(
        InvalidExtractionTrap(
            item_type=_required_field(raw_trap, "type", f"invalid_extractions[{index}]"),
            name=_required_field(raw_trap, "name", f"invalid_extractions[{index}]"),
            forbidden_status=raw_trap.get("forbidden_status"),
            reason=raw_trap.get("reason"),
        )
        for index, raw_trap in enumerate(raw_traps)
    )


def _optional_collection(expected_json: dict, key: str) -> tuple[dict, ...]:
    raw_values = expected_json.get(key, ())
    if not isinstance(raw_values, (list, tuple)):
        raise EvaluationError(f"expected_json {key} must be a list or tuple when provided.")

    values = []
    for index, raw_value in enumerate(raw_values):
        context = f"{key}[{index}]"
        _require_mapping(raw_value, context)
        values.append(raw_value)
    return tuple(values)


def _required_field(raw_item: dict, field_name: str, context: str) -> str:
    if field_name not in raw_item:
        raise EvaluationError(f"{context} is missing required field {field_name}.")
    value = raw_item[field_name]
    _require_non_empty_string(value, f"{context} {field_name}")
    return value


def _require_mapping(value: object, field_name: str) -> None:
    if not isinstance(value, dict):
        raise EvaluationError(f"{field_name} must be a dictionary.")


def _require_non_empty_string(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"{field_name} is required.")


def _validate_optional_string(value: str | None, field_name: str) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"{field_name} cannot be empty when provided.")


def _require_non_negative_int(value: int, field_name: str) -> None:
    if not isinstance(value, int) or value < 0:
        raise EvaluationError(f"{field_name} must be a non-negative integer.")


def _validate_optional_non_negative_int(value: int | None, field_name: str) -> None:
    if value is None:
        return
    _require_non_negative_int(value, field_name)


def _normalize_tuple(values: Iterable[object], field_name: str) -> tuple[object, ...]:
    try:
        return tuple(values)
    except TypeError as exc:
        raise EvaluationError(f"{field_name} must be iterable.") from exc
