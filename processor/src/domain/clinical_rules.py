"""Deterministic clinical validation rules."""

from __future__ import annotations

from enum import StrEnum

from processor.src.domain.extraction_schema import ClinicalItemType, ExtractedClinicalItem
from processor.src.domain.validation import (
    ValidationDecision,
    ValidationFinding,
    ValidationSeverity,
    accepted,
    rejected,
)


class ClinicalRuleId(StrEnum):
    """Stable identifiers for deterministic clinical validation rules."""

    NEGATED_CONDITION = "RULE_NEGATED_CONDITION"
    FAMILY_HISTORY_NOT_PATIENT_CONDITION = "RULE_FAMILY_HISTORY_NOT_PATIENT_CONDITION"
    PROCEDURE_NOT_PERFORMED = "RULE_PROCEDURE_NOT_PERFORMED"
    REFERRAL_NOT_PROCEDURE = "RULE_REFERRAL_NOT_PROCEDURE"
    INACTIVE_MEDICATION_NOT_ACTIVE = "RULE_INACTIVE_MEDICATION_NOT_ACTIVE"
    LOW_CONFIDENCE = "RULE_LOW_CONFIDENCE"


_NEGATED_CONDITION_PHRASES: tuple[str, ...] = (
    "denies",
    "denied",
    "no evidence of",
    "negative for",
    "no history of",
    "without",
)


def validate_clinical_item(item: ExtractedClinicalItem) -> ValidationDecision:
    """Validate one extracted clinical item using deterministic clinical rules."""

    if _is_negated_active_condition(item):
        return rejected(
            [
                make_finding(
                    ClinicalRuleId.NEGATED_CONDITION,
                    ValidationSeverity.ERROR,
                    "Negated mention must not be accepted as an active condition.",
                )
            ]
        )

    return accepted()


def make_finding(
    rule_id: ClinicalRuleId,
    severity: ValidationSeverity,
    message: str,
) -> ValidationFinding:
    """Create a validation finding with a stable clinical rule identifier."""

    return ValidationFinding(
        rule_id=rule_id.value,
        severity=severity,
        message=message,
    )


def _is_negated_active_condition(item: ExtractedClinicalItem) -> bool:
    if item.item_type != ClinicalItemType.CONDITION:
        return False
    if item.status != "active":
        return False

    source_quote = item.source_quote.lower()
    return any(phrase in source_quote for phrase in _NEGATED_CONDITION_PHRASES)
