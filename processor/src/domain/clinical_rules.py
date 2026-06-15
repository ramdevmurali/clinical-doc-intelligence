"""Deterministic clinical validation rule contract."""

from __future__ import annotations

from enum import StrEnum

from processor.src.domain.extraction_schema import ExtractedClinicalItem
from processor.src.domain.validation import (
    ValidationDecision,
    ValidationFinding,
    ValidationSeverity,
    accepted,
)


class ClinicalRuleId(StrEnum):
    """Stable identifiers for deterministic clinical validation rules."""

    NEGATED_CONDITION = "RULE_NEGATED_CONDITION"
    FAMILY_HISTORY_NOT_PATIENT_CONDITION = "RULE_FAMILY_HISTORY_NOT_PATIENT_CONDITION"
    PROCEDURE_NOT_PERFORMED = "RULE_PROCEDURE_NOT_PERFORMED"
    REFERRAL_NOT_PROCEDURE = "RULE_REFERRAL_NOT_PROCEDURE"
    INACTIVE_MEDICATION_NOT_ACTIVE = "RULE_INACTIVE_MEDICATION_NOT_ACTIVE"
    LOW_CONFIDENCE = "RULE_LOW_CONFIDENCE"


def validate_clinical_item(item: ExtractedClinicalItem) -> ValidationDecision:
    """Validate one extracted clinical item using deterministic clinical rules.

    Specific clinical safety rules are intentionally not implemented in this
    contract step. The public entrypoint exists so future rules can be composed
    behind a stable API.
    """

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
