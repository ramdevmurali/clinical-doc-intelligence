"""Pure evaluation domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from processor.src.domain.extraction_schema import ExtractedClinicalItem
from processor.src.domain.normalization import (
    NormalizationError,
    normalize_item_type,
    normalize_name,
    normalize_status,
)


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
class EvaluationMatchKey:
    """Normalized conservative comparison key for evaluation matching."""

    item_type: str
    name: str
    status: str | None = None
    source_quote: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty_string(self.item_type, "Evaluation match key item_type")
        _require_non_empty_string(self.name, "Evaluation match key name")
        _validate_optional_string(self.status, "Evaluation match key status")
        _validate_optional_string(self.source_quote, "Evaluation match key source_quote")


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


def make_match_key(
    item_type: str,
    name: str,
    status: str | None = None,
    source_quote: str | None = None,
) -> EvaluationMatchKey:
    """Build a normalized deterministic evaluation match key."""

    try:
        normalized_item_type = normalize_item_type(item_type).value
        normalized_name = normalize_name(name)
        normalized_status = normalize_status(status)
    except NormalizationError as exc:
        raise EvaluationError(f"Could not normalize evaluation match key: {exc}") from exc

    return EvaluationMatchKey(
        item_type=normalized_item_type,
        name=normalized_name,
        status=normalized_status,
        source_quote=source_quote,
    )


def expected_item_match_key(item: ExpectedClinicalItem) -> EvaluationMatchKey:
    """Build a match key from a golden expected item."""

    if not isinstance(item, ExpectedClinicalItem):
        raise EvaluationError("expected_item_match_key requires ExpectedClinicalItem.")

    return make_match_key(
        item_type=item.item_type,
        name=item.name,
        status=item.status,
        source_quote=item.source_quote,
    )


def clinical_item_match_key(item: ExtractedClinicalItem) -> EvaluationMatchKey:
    """Build a match key from a predicted extracted clinical item."""

    if not isinstance(item, ExtractedClinicalItem):
        raise EvaluationError("clinical_item_match_key requires ExtractedClinicalItem.")

    return make_match_key(
        item_type=item.item_type.value,
        name=item.name,
        status=item.status,
        source_quote=item.source_quote,
    )


def match_keys_compatible(expected_key: EvaluationMatchKey, predicted_key: EvaluationMatchKey) -> bool:
    """Return whether a predicted key satisfies an expected key contract."""

    _require_match_key(expected_key, "expected_key")
    _require_match_key(predicted_key, "predicted_key")

    if expected_key.item_type != predicted_key.item_type:
        return False
    if expected_key.name != predicted_key.name:
        return False
    if expected_key.status is not None and expected_key.status != predicted_key.status:
        return False
    if expected_key.source_quote is not None and expected_key.source_quote != predicted_key.source_quote:
        return False
    return True


def match_expected_items(
    expected_items: tuple[ExpectedClinicalItem, ...] | list[ExpectedClinicalItem],
    predicted_items: tuple[ExtractedClinicalItem, ...] | list[ExtractedClinicalItem],
) -> tuple[ItemMatch, ...]:
    """Deterministically match expected items to predicted clinical items."""

    expected_items_tuple = _normalize_tuple(expected_items, "expected_items")
    predicted_items_tuple = _normalize_tuple(predicted_items, "predicted_items")

    for index, expected_item in enumerate(expected_items_tuple):
        if not isinstance(expected_item, ExpectedClinicalItem):
            raise EvaluationError(f"expected_items[{index}] must be an ExpectedClinicalItem.")

    predicted_keys = []
    for index, predicted_item in enumerate(predicted_items_tuple):
        if not isinstance(predicted_item, ExtractedClinicalItem):
            raise EvaluationError(f"predicted_items[{index}] must be an ExtractedClinicalItem.")
        predicted_keys.append(clinical_item_match_key(predicted_item))

    matches = []
    matched_predicted_indexes: set[int] = set()

    for expected_index, expected_item in enumerate(expected_items_tuple):
        expected_key = expected_item_match_key(expected_item)

        for predicted_index, predicted_key in enumerate(predicted_keys):
            if predicted_index in matched_predicted_indexes:
                continue
            if match_keys_compatible(expected_key, predicted_key):
                matches.append(
                    ItemMatch(
                        expected_index=expected_index,
                        predicted_index=predicted_index,
                    )
                )
                matched_predicted_indexes.add(predicted_index)
                break

    return tuple(matches)


def find_missing_expected_indexes(
    expected_items: tuple[ExpectedClinicalItem, ...] | list[ExpectedClinicalItem],
    matches: tuple[ItemMatch, ...] | list[ItemMatch],
) -> tuple[int, ...]:
    """Return expected item indexes that do not appear in matches."""

    expected_items_tuple = _validate_expected_items(expected_items)
    matches_tuple = _validate_matches(matches)

    matched_expected_indexes = set()
    for match in matches_tuple:
        if match.expected_index >= len(expected_items_tuple):
            raise EvaluationError("ItemMatch expected_index is outside expected_items bounds.")
        matched_expected_indexes.add(match.expected_index)

    return tuple(
        expected_index
        for expected_index in range(len(expected_items_tuple))
        if expected_index not in matched_expected_indexes
    )


def find_extra_predicted_indexes(
    predicted_items: tuple[ExtractedClinicalItem, ...] | list[ExtractedClinicalItem],
    matches: tuple[ItemMatch, ...] | list[ItemMatch],
) -> tuple[int, ...]:
    """Return predicted item indexes that do not appear in matches."""

    predicted_items_tuple = _validate_predicted_items(predicted_items)
    matches_tuple = _validate_matches(matches)

    matched_predicted_indexes = set()
    for match in matches_tuple:
        if match.predicted_index >= len(predicted_items_tuple):
            raise EvaluationError("ItemMatch predicted_index is outside predicted_items bounds.")
        matched_predicted_indexes.add(match.predicted_index)

    return tuple(
        predicted_index
        for predicted_index in range(len(predicted_items_tuple))
        if predicted_index not in matched_predicted_indexes
    )


def find_invalid_trap_hits(
    invalid_traps: tuple[InvalidExtractionTrap, ...] | list[InvalidExtractionTrap],
    predicted_items: tuple[ExtractedClinicalItem, ...] | list[ExtractedClinicalItem],
) -> tuple[EvaluationIssue, ...]:
    """Return deterministic issues for predictions that hit invalid extraction traps."""

    traps_tuple = _validate_invalid_traps(invalid_traps)
    predicted_items_tuple = _validate_predicted_items(predicted_items)

    predicted_keys = tuple(clinical_item_match_key(predicted_item) for predicted_item in predicted_items_tuple)
    hits = []

    for trap_index, trap in enumerate(traps_tuple):
        trap_key = make_match_key(
            item_type=trap.item_type,
            name=trap.name,
            status=trap.forbidden_status,
        )

        for predicted_index, predicted_key in enumerate(predicted_keys):
            if match_keys_compatible(trap_key, predicted_key):
                hits.append(
                    EvaluationIssue(
                        issue_type="invalid_trap_hit",
                        message=_invalid_trap_hit_message(trap, predicted_items_tuple[predicted_index]),
                        trap_index=trap_index,
                        predicted_index=predicted_index,
                    )
                )

    return tuple(hits)


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


def _require_match_key(value: object, field_name: str) -> None:
    if not isinstance(value, EvaluationMatchKey):
        raise EvaluationError(f"{field_name} must be an EvaluationMatchKey.")


def _validate_expected_items(values: Iterable[object]) -> tuple[ExpectedClinicalItem, ...]:
    items = _normalize_tuple(values, "expected_items")
    for index, item in enumerate(items):
        if not isinstance(item, ExpectedClinicalItem):
            raise EvaluationError(f"expected_items[{index}] must be an ExpectedClinicalItem.")
    return items


def _validate_predicted_items(values: Iterable[object]) -> tuple[ExtractedClinicalItem, ...]:
    items = _normalize_tuple(values, "predicted_items")
    for index, item in enumerate(items):
        if not isinstance(item, ExtractedClinicalItem):
            raise EvaluationError(f"predicted_items[{index}] must be an ExtractedClinicalItem.")
    return items


def _validate_invalid_traps(values: Iterable[object]) -> tuple[InvalidExtractionTrap, ...]:
    traps = _normalize_tuple(values, "invalid_traps")
    for index, trap in enumerate(traps):
        if not isinstance(trap, InvalidExtractionTrap):
            raise EvaluationError(f"invalid_traps[{index}] must be an InvalidExtractionTrap.")
    return traps


def _validate_matches(values: Iterable[object]) -> tuple[ItemMatch, ...]:
    matches = _normalize_tuple(values, "matches")
    for index, match in enumerate(matches):
        if not isinstance(match, ItemMatch):
            raise EvaluationError(f"matches[{index}] must be an ItemMatch.")
    return matches


def _invalid_trap_hit_message(trap: InvalidExtractionTrap, predicted_item: ExtractedClinicalItem) -> str:
    status_text = f" with forbidden status {trap.forbidden_status}" if trap.forbidden_status else ""
    reason_text = f" Reason: {trap.reason}" if trap.reason else ""
    return (
        f"Predicted {predicted_item.item_type.value} '{predicted_item.name}' matched invalid "
        f"trap {trap.item_type} '{trap.name}'{status_text}.{reason_text}"
    )


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
