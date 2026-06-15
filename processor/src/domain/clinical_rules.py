"""Deterministic clinical validation rules."""

from __future__ import annotations

from enum import StrEnum
import re

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
_FAMILY_HISTORY_RELATION_TERMS: tuple[str, ...] = (
    "mother",
    "father",
    "sister",
    "brother",
    "family history",
)
_PROCEDURE_NOT_PERFORMED_PHRASES: tuple[str, ...] = (
    "not performed",
    "was not performed",
    "declined",
    "cancelled",
    "planned",
)
_REFERRAL_NOT_PROCEDURE_PHRASES: tuple[str, ...] = (
    "referred for",
    "referral for",
    "referred to",
    "outpatient",
    "ordered",
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

    if _is_family_history_patient_condition(item):
        return rejected(
            [
                make_finding(
                    ClinicalRuleId.FAMILY_HISTORY_NOT_PATIENT_CONDITION,
                    ValidationSeverity.ERROR,
                    "Family-history mention must not be accepted as a patient condition.",
                )
            ]
        )

    if _is_performed_procedure_not_performed(item):
        return rejected(
            [
                make_finding(
                    ClinicalRuleId.PROCEDURE_NOT_PERFORMED,
                    ValidationSeverity.ERROR,
                    "Not-performed, declined, cancelled, or planned procedure must not be accepted as performed.",
                )
            ]
        )

    if _is_referral_incorrectly_performed_procedure(item):
        return rejected(
            [
                make_finding(
                    ClinicalRuleId.REFERRAL_NOT_PROCEDURE,
                    ValidationSeverity.ERROR,
                    "Referral, order, or outpatient plan must not be accepted as a performed procedure.",
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


def _is_family_history_patient_condition(item: ExtractedClinicalItem) -> bool:
    if item.item_type != ClinicalItemType.CONDITION:
        return False

    if item.section_name.lower() == "family history":
        return True

    source_quote = item.source_quote.lower()
    return any(_contains_term(source_quote, term) for term in _FAMILY_HISTORY_RELATION_TERMS)


def _contains_term(text: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", text) is not None


def _is_performed_procedure_not_performed(item: ExtractedClinicalItem) -> bool:
    if not _is_performed_procedure(item):
        return False

    source_quote = item.source_quote.lower()
    return any(phrase in source_quote for phrase in _PROCEDURE_NOT_PERFORMED_PHRASES)


def _is_referral_incorrectly_performed_procedure(item: ExtractedClinicalItem) -> bool:
    if not _is_performed_procedure(item):
        return False

    source_quote = item.source_quote.lower()
    return any(phrase in source_quote for phrase in _REFERRAL_NOT_PROCEDURE_PHRASES)


def _is_performed_procedure(item: ExtractedClinicalItem) -> bool:
    return item.item_type == ClinicalItemType.PROCEDURE and item.status == "performed"
