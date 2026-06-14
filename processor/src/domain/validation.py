"""Pure validation decision primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Iterable


class ValidationError(ValueError):
    """Raised when a validation decision violates domain contracts."""


class ValidationStatus(StrEnum):
    """Allowed validation statuses for extracted clinical items."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"
    CONTRADICTION = "contradiction"
    NEEDS_REVIEW = "needs_review"


class ReviewStatus(StrEnum):
    """Allowed human review statuses for extracted clinical items."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EDITED = "edited"


class ValidationSeverity(StrEnum):
    """Allowed severities for validation findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class ValidationFinding:
    """A deterministic validation rule finding."""

    rule_id: str
    severity: ValidationSeverity
    message: str

    def __post_init__(self) -> None:
        if not self.rule_id or not self.rule_id.strip():
            raise ValidationError("Validation finding rule_id is required.")
        if not self.message or not self.message.strip():
            raise ValidationError("Validation finding message is required.")


@dataclass(frozen=True)
class ValidationDecision:
    """A validation decision returned by clinical validation logic."""

    status: ValidationStatus
    findings: tuple[ValidationFinding, ...] = field(default_factory=tuple)
    review_required: bool = False


def accepted(findings: Iterable[ValidationFinding] | None = None) -> ValidationDecision:
    """Create an accepted decision.

    Accepted items may carry informational or warning findings, but not error
    findings. Accepted items do not require review by default.
    """

    normalized_findings = _normalize_findings(findings)
    if _has_error_finding(normalized_findings):
        raise ValidationError("Accepted decisions cannot include error findings.")
    return ValidationDecision(
        status=ValidationStatus.ACCEPTED,
        findings=normalized_findings,
        review_required=False,
    )


def rejected(findings: Iterable[ValidationFinding]) -> ValidationDecision:
    """Create a rejected decision that does not require review by default."""

    return ValidationDecision(
        status=ValidationStatus.REJECTED,
        findings=_require_findings(findings, ValidationStatus.REJECTED),
        review_required=False,
    )


def uncertain(findings: Iterable[ValidationFinding]) -> ValidationDecision:
    """Create an uncertain decision that requires review."""

    return ValidationDecision(
        status=ValidationStatus.UNCERTAIN,
        findings=_require_findings(findings, ValidationStatus.UNCERTAIN),
        review_required=True,
    )


def contradiction(findings: Iterable[ValidationFinding]) -> ValidationDecision:
    """Create a contradiction decision that requires review."""

    return ValidationDecision(
        status=ValidationStatus.CONTRADICTION,
        findings=_require_findings(findings, ValidationStatus.CONTRADICTION),
        review_required=True,
    )


def needs_review(findings: Iterable[ValidationFinding]) -> ValidationDecision:
    """Create a needs-review decision that requires review."""

    return ValidationDecision(
        status=ValidationStatus.NEEDS_REVIEW,
        findings=_require_findings(findings, ValidationStatus.NEEDS_REVIEW),
        review_required=True,
    )


def _normalize_findings(findings: Iterable[ValidationFinding] | None) -> tuple[ValidationFinding, ...]:
    if findings is None:
        return ()
    return tuple(findings)


def _require_findings(
    findings: Iterable[ValidationFinding],
    status: ValidationStatus,
) -> tuple[ValidationFinding, ...]:
    normalized_findings = _normalize_findings(findings)
    if not normalized_findings:
        raise ValidationError(f"{status.value} decisions require at least one finding.")
    return normalized_findings


def _has_error_finding(findings: tuple[ValidationFinding, ...]) -> bool:
    return any(finding.severity == ValidationSeverity.ERROR for finding in findings)
