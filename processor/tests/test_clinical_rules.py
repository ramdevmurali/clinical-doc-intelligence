import unittest

from processor.src.domain.clinical_rules import (
    ClinicalRuleId,
    make_finding,
    validate_clinical_item,
)
from processor.src.domain.extraction_schema import ClinicalItemType, ExtractedClinicalItem
from processor.src.domain.validation import ValidationSeverity, ValidationStatus


class ClinicalRulesContractTests(unittest.TestCase):
    def test_clinical_rule_id_values_are_stable(self) -> None:
        self.assertEqual("RULE_NEGATED_CONDITION", ClinicalRuleId.NEGATED_CONDITION.value)
        self.assertEqual(
            "RULE_FAMILY_HISTORY_NOT_PATIENT_CONDITION",
            ClinicalRuleId.FAMILY_HISTORY_NOT_PATIENT_CONDITION.value,
        )
        self.assertEqual("RULE_PROCEDURE_NOT_PERFORMED", ClinicalRuleId.PROCEDURE_NOT_PERFORMED.value)
        self.assertEqual("RULE_REFERRAL_NOT_PROCEDURE", ClinicalRuleId.REFERRAL_NOT_PROCEDURE.value)
        self.assertEqual(
            "RULE_INACTIVE_MEDICATION_NOT_ACTIVE",
            ClinicalRuleId.INACTIVE_MEDICATION_NOT_ACTIVE.value,
        )
        self.assertEqual("RULE_LOW_CONFIDENCE", ClinicalRuleId.LOW_CONFIDENCE.value)

    def test_clinical_rule_id_set_has_no_missing_or_extra_values(self) -> None:
        self.assertEqual(
            {
                "RULE_NEGATED_CONDITION",
                "RULE_FAMILY_HISTORY_NOT_PATIENT_CONDITION",
                "RULE_PROCEDURE_NOT_PERFORMED",
                "RULE_REFERRAL_NOT_PROCEDURE",
                "RULE_INACTIVE_MEDICATION_NOT_ACTIVE",
                "RULE_LOW_CONFIDENCE",
            },
            {rule_id.value for rule_id in ClinicalRuleId},
        )

    def test_validate_clinical_item_accepts_safe_active_condition_by_default(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.CONDITION,
            name="hypertension",
            status="active",
            source_quote="Past medical history includes hypertension.",
        )

        decision = validate_clinical_item(item)

        self.assertEqual(ValidationStatus.ACCEPTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual((), decision.findings)

    def test_make_finding_preserves_rule_id_severity_and_message(self) -> None:
        finding = make_finding(
            ClinicalRuleId.NEGATED_CONDITION,
            ValidationSeverity.ERROR,
            "Negated condition should not be accepted as active.",
        )

        self.assertEqual("RULE_NEGATED_CONDITION", finding.rule_id)
        self.assertEqual(ValidationSeverity.ERROR, finding.severity)
        self.assertEqual("Negated condition should not be accepted as active.", finding.message)

    def valid_item(self, **overrides) -> ExtractedClinicalItem:
        values = {
            "item_type": ClinicalItemType.CONDITION,
            "name": "hypertension",
            "status": "active",
            "confidence": 0.95,
            "source_quote": "Past medical history includes hypertension.",
            "source_start_char": 0,
            "source_end_char": 43,
            "section_id": "note_001:section:003",
            "section_name": "Past Medical History",
        }
        values.update(overrides)
        return ExtractedClinicalItem(**values)


if __name__ == "__main__":
    unittest.main()
