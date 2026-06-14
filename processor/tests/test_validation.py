import unittest
from dataclasses import FrozenInstanceError

from processor.src.domain.validation import (
    ReviewStatus,
    ValidationDecision,
    ValidationError,
    ValidationFinding,
    ValidationSeverity,
    ValidationStatus,
    accepted,
    contradiction,
    needs_review,
    rejected,
    uncertain,
)


class ValidationPrimitiveTests(unittest.TestCase):
    def test_validation_status_values_match_domain_contract(self) -> None:
        self.assertEqual("accepted", ValidationStatus.ACCEPTED.value)
        self.assertEqual("rejected", ValidationStatus.REJECTED.value)
        self.assertEqual("uncertain", ValidationStatus.UNCERTAIN.value)
        self.assertEqual("contradiction", ValidationStatus.CONTRADICTION.value)
        self.assertEqual("needs_review", ValidationStatus.NEEDS_REVIEW.value)

    def test_review_status_values_match_domain_contract(self) -> None:
        self.assertEqual("pending", ReviewStatus.PENDING.value)
        self.assertEqual("approved", ReviewStatus.APPROVED.value)
        self.assertEqual("rejected", ReviewStatus.REJECTED.value)
        self.assertEqual("edited", ReviewStatus.EDITED.value)

    def test_validation_severity_values_match_domain_contract(self) -> None:
        self.assertEqual("info", ValidationSeverity.INFO.value)
        self.assertEqual("warning", ValidationSeverity.WARNING.value)
        self.assertEqual("error", ValidationSeverity.ERROR.value)

    def test_finding_preserves_rule_id_severity_and_message(self) -> None:
        finding = ValidationFinding(
            rule_id="RULE_NEGATED_CONDITION",
            severity=ValidationSeverity.WARNING,
            message="Negated mention should not be active condition.",
        )

        self.assertEqual("RULE_NEGATED_CONDITION", finding.rule_id)
        self.assertEqual(ValidationSeverity.WARNING, finding.severity)
        self.assertEqual("Negated mention should not be active condition.", finding.message)

    def test_finding_is_immutable(self) -> None:
        finding = self.warning_finding()

        with self.assertRaises(FrozenInstanceError):
            finding.message = "changed"

    def test_finding_requires_rule_id_and_message(self) -> None:
        with self.assertRaisesRegex(ValidationError, "rule_id is required"):
            ValidationFinding(rule_id=" ", severity=ValidationSeverity.INFO, message="Message")

        with self.assertRaisesRegex(ValidationError, "message is required"):
            ValidationFinding(rule_id="RULE_TEST", severity=ValidationSeverity.INFO, message=" ")

    def test_accepted_decision_without_findings(self) -> None:
        decision = accepted()

        self.assertEqual(ValidationDecision(status=ValidationStatus.ACCEPTED), decision)
        self.assertEqual(ValidationStatus.ACCEPTED, decision.status)
        self.assertEqual((), decision.findings)
        self.assertFalse(decision.review_required)

    def test_accepted_decision_allows_info_and_warning_findings(self) -> None:
        info = ValidationFinding("RULE_INFO", ValidationSeverity.INFO, "Informational finding.")
        warning = self.warning_finding()

        decision = accepted([info, warning])

        self.assertEqual(ValidationStatus.ACCEPTED, decision.status)
        self.assertEqual((info, warning), decision.findings)
        self.assertFalse(decision.review_required)

    def test_accepted_decision_rejects_error_findings(self) -> None:
        error = ValidationFinding("RULE_ERROR", ValidationSeverity.ERROR, "Blocking validation issue.")

        with self.assertRaisesRegex(ValidationError, "cannot include error findings"):
            accepted([error])

    def test_rejected_decision_requires_findings_and_does_not_require_review(self) -> None:
        finding = ValidationFinding("RULE_INVALID", ValidationSeverity.ERROR, "Invalid item.")

        decision = rejected([finding])

        self.assertEqual(ValidationStatus.REJECTED, decision.status)
        self.assertEqual((finding,), decision.findings)
        self.assertFalse(decision.review_required)

        with self.assertRaisesRegex(ValidationError, "rejected decisions require"):
            rejected([])

    def test_uncertain_decision_requires_findings_and_review(self) -> None:
        finding = self.warning_finding()

        decision = uncertain([finding])

        self.assertEqual(ValidationStatus.UNCERTAIN, decision.status)
        self.assertEqual((finding,), decision.findings)
        self.assertTrue(decision.review_required)

        with self.assertRaisesRegex(ValidationError, "uncertain decisions require"):
            uncertain([])

    def test_contradiction_decision_requires_findings_and_review(self) -> None:
        finding = ValidationFinding("RULE_CONFLICT", ValidationSeverity.ERROR, "Conflicting mentions.")

        decision = contradiction([finding])

        self.assertEqual(ValidationStatus.CONTRADICTION, decision.status)
        self.assertEqual((finding,), decision.findings)
        self.assertTrue(decision.review_required)

        with self.assertRaisesRegex(ValidationError, "contradiction decisions require"):
            contradiction([])

    def test_needs_review_decision_requires_findings_and_review(self) -> None:
        finding = self.warning_finding()

        decision = needs_review([finding])

        self.assertEqual(ValidationStatus.NEEDS_REVIEW, decision.status)
        self.assertEqual((finding,), decision.findings)
        self.assertTrue(decision.review_required)

        with self.assertRaisesRegex(ValidationError, "needs_review decisions require"):
            needs_review([])

    def warning_finding(self) -> ValidationFinding:
        return ValidationFinding(
            rule_id="RULE_LOW_CONFIDENCE",
            severity=ValidationSeverity.WARNING,
            message="Low confidence item requires review.",
        )


if __name__ == "__main__":
    unittest.main()
