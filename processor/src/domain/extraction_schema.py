"""Pure clinical extraction schema primitives."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ExtractionSchemaError(ValueError):
    """Raised when an extracted clinical item violates schema contracts."""


class ClinicalItemType(StrEnum):
    """Supported extracted clinical item types."""

    CONDITION = "condition"
    PROCEDURE = "procedure"
    MEDICATION = "medication"
    ALLERGY = "allergy"
    OBSERVATION = "observation"
    LAB_RESULT = "lab_result"
    ORDER = "order"
    CARE_NEED = "care_need"
    NEGATIVE_FINDING = "negative_finding"
    UNCERTAIN_MENTION = "uncertain_mention"
    FAMILY_HISTORY = "family_history"


@dataclass(frozen=True)
class ExtractedClinicalItem:
    """A source-grounded extracted clinical fact.

    This schema validates item shape only. It does not verify that the source
    quote exists in the raw document; source quote grounding belongs in
    ``source_spans.py``.
    """

    item_type: ClinicalItemType
    name: str
    status: str | None
    confidence: float | None
    source_quote: str
    source_start_char: int
    source_end_char: int
    section_id: str
    section_name: str

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "name")
        _require_non_empty(self.source_quote, "source_quote")
        _require_non_empty(self.section_id, "section_id")
        _require_non_empty(self.section_name, "section_name")
        _validate_offsets(self.source_start_char, self.source_end_char)
        _validate_confidence(self.confidence)


def _require_non_empty(value: str, field_name: str) -> None:
    if not value or not value.strip():
        raise ExtractionSchemaError(f"{field_name} is required.")


def _validate_offsets(start_char: int, end_char: int) -> None:
    if start_char < 0:
        raise ExtractionSchemaError("source_start_char cannot be negative.")
    if end_char < start_char:
        raise ExtractionSchemaError("source_end_char cannot be before source_start_char.")


def _validate_confidence(confidence: float | None) -> None:
    if confidence is None:
        return
    if confidence < 0.0 or confidence > 1.0:
        raise ExtractionSchemaError("confidence must be between 0.0 and 1.0 inclusive.")
