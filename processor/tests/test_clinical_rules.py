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


    def test_negated_active_condition_denies_is_rejected(self) -> None:
        item = self.valid_item(name="chest pain", source_quote="Patient denies chest pain.")

        decision = validate_clinical_item(item)

        self.assert_negated_condition_rejected(decision)

    def test_negated_active_condition_no_evidence_is_rejected(self) -> None:
        item = self.valid_item(
            name="diabetic ketoacidosis",
            source_quote="No evidence of diabetic ketoacidosis.",
        )

        decision = validate_clinical_item(item)

        self.assert_negated_condition_rejected(decision)

    def test_negated_active_condition_negative_for_is_rejected(self) -> None:
        item = self.valid_item(name="pneumonia", source_quote="Review is negative for pneumonia.")

        decision = validate_clinical_item(item)

        self.assert_negated_condition_rejected(decision)

    def test_negated_active_condition_no_history_of_is_rejected(self) -> None:
        item = self.valid_item(name="seizure", source_quote="No history of seizure.")

        decision = validate_clinical_item(item)

        self.assert_negated_condition_rejected(decision)

    def test_negated_active_condition_without_is_rejected(self) -> None:
        item = self.valid_item(name="fever", source_quote="Patient is without fever.")

        decision = validate_clinical_item(item)

        self.assert_negated_condition_rejected(decision)

    def test_negated_active_condition_matching_is_case_insensitive(self) -> None:
        item = self.valid_item(name="chest pain", source_quote="Patient DENIED chest pain.")

        decision = validate_clinical_item(item)

        self.assert_negated_condition_rejected(decision)

    def test_negative_finding_with_negated_quote_is_accepted(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.NEGATIVE_FINDING,
            name="chest pain",
            status=None,
            source_quote="Patient denies chest pain.",
        )

        decision = validate_clinical_item(item)

        self.assertEqual(ValidationStatus.ACCEPTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual((), decision.findings)

    def test_non_active_condition_with_negated_quote_is_not_rejected_by_negation_rule(self) -> None:
        item = self.valid_item(
            name="chest pain",
            status="resolved",
            source_quote="Patient denies chest pain.",
        )

        decision = validate_clinical_item(item)

        self.assertEqual(ValidationStatus.ACCEPTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual((), decision.findings)


    def test_condition_from_family_history_section_is_rejected(self) -> None:
        item = self.valid_item(
            name="breast cancer",
            source_quote="Breast cancer noted in family history.",
            section_name="Family History",
        )

        decision = validate_clinical_item(item)

        self.assert_family_history_condition_rejected(decision)

    def test_condition_with_mother_relation_is_rejected(self) -> None:
        item = self.valid_item(name="breast cancer", source_quote="Mother had breast cancer.")

        decision = validate_clinical_item(item)

        self.assert_family_history_condition_rejected(decision)

    def test_condition_with_father_relation_is_rejected(self) -> None:
        item = self.valid_item(name="coronary artery disease", source_quote="Father has coronary artery disease.")

        decision = validate_clinical_item(item)

        self.assert_family_history_condition_rejected(decision)

    def test_condition_with_sister_relation_is_rejected(self) -> None:
        item = self.valid_item(name="thyroid cancer", source_quote="Sister has thyroid cancer.")

        decision = validate_clinical_item(item)

        self.assert_family_history_condition_rejected(decision)

    def test_condition_with_brother_relation_is_rejected(self) -> None:
        item = self.valid_item(name="myocardial infarction", source_quote="Brother died of myocardial infarction.")

        decision = validate_clinical_item(item)

        self.assert_family_history_condition_rejected(decision)

    def test_condition_with_family_history_phrase_is_rejected(self) -> None:
        item = self.valid_item(name="colon cancer", source_quote="Family history is notable for colon cancer.")

        decision = validate_clinical_item(item)

        self.assert_family_history_condition_rejected(decision)

    def test_family_history_matching_is_case_insensitive(self) -> None:
        item = self.valid_item(name="breast cancer", source_quote="MOTHER had breast cancer.")

        decision = validate_clinical_item(item)

        self.assert_family_history_condition_rejected(decision)

    def test_family_history_item_with_relation_quote_is_accepted(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.FAMILY_HISTORY,
            name="breast cancer",
            status="historical",
            source_quote="Mother had breast cancer.",
            section_name="Family History",
        )

        decision = validate_clinical_item(item)

        self.assertEqual(ValidationStatus.ACCEPTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual((), decision.findings)

    def test_safe_active_condition_outside_family_history_is_accepted(self) -> None:
        item = self.valid_item(
            name="hypertension",
            source_quote="Past medical history includes hypertension.",
            section_name="Past Medical History",
        )

        decision = validate_clinical_item(item)

        self.assertEqual(ValidationStatus.ACCEPTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual((), decision.findings)

    def test_negation_rule_runs_before_family_history_rule(self) -> None:
        item = self.valid_item(
            name="seizure",
            source_quote="No history of seizure in mother.",
            section_name="Family History",
        )

        decision = validate_clinical_item(item)

        self.assert_negated_condition_rejected(decision)


    def test_performed_procedure_not_performed_quote_is_rejected(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.PROCEDURE,
            name="circumcision",
            status="performed",
            source_quote="Circumcision was not performed.",
            section_name="Procedures",
        )

        decision = validate_clinical_item(item)

        self.assert_procedure_not_performed_rejected(decision)

    def test_performed_procedure_not_performed_phrase_is_rejected(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.PROCEDURE,
            name="biopsy",
            status="performed",
            source_quote="The biopsy was not performed due to patient preference.",
            section_name="Procedures",
        )

        decision = validate_clinical_item(item)

        self.assert_procedure_not_performed_rejected(decision)

    def test_performed_procedure_declined_phrase_is_rejected(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.PROCEDURE,
            name="colonoscopy",
            status="performed",
            source_quote="Patient declined colonoscopy.",
            section_name="Procedures",
        )

        decision = validate_clinical_item(item)

        self.assert_procedure_not_performed_rejected(decision)

    def test_performed_procedure_cancelled_phrase_is_rejected(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.PROCEDURE,
            name="surgery",
            status="performed",
            source_quote="Surgery was cancelled before incision.",
            section_name="Procedures",
        )

        decision = validate_clinical_item(item)

        self.assert_procedure_not_performed_rejected(decision)

    def test_performed_procedure_planned_phrase_is_rejected(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.PROCEDURE,
            name="knee replacement",
            status="performed",
            source_quote="Knee replacement is planned for next month.",
            section_name="Procedures",
        )

        decision = validate_clinical_item(item)

        self.assert_procedure_not_performed_rejected(decision)

    def test_procedure_not_performed_matching_is_case_insensitive(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.PROCEDURE,
            name="circumcision",
            status="performed",
            source_quote="Circumcision was NOT PERFORMED.",
            section_name="Procedures",
        )

        decision = validate_clinical_item(item)

        self.assert_procedure_not_performed_rejected(decision)

    def test_performed_procedure_referred_for_quote_is_rejected(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.PROCEDURE,
            name="outpatient colonoscopy",
            status="performed",
            source_quote="Patient referred for outpatient colonoscopy.",
            section_name="Orders and Referrals",
        )

        decision = validate_clinical_item(item)

        self.assert_referral_not_procedure_rejected(decision)

    def test_performed_procedure_referral_for_phrase_is_rejected(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.PROCEDURE,
            name="colonoscopy",
            status="performed",
            source_quote="Referral for colonoscopy was placed.",
            section_name="Orders and Referrals",
        )

        decision = validate_clinical_item(item)

        self.assert_referral_not_procedure_rejected(decision)

    def test_performed_procedure_referred_to_phrase_is_rejected(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.PROCEDURE,
            name="cardiac catheterization",
            status="performed",
            source_quote="Patient was referred to cardiology for cardiac catheterization.",
            section_name="Orders and Referrals",
        )

        decision = validate_clinical_item(item)

        self.assert_referral_not_procedure_rejected(decision)

    def test_performed_procedure_ordered_phrase_is_rejected(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.PROCEDURE,
            name="CT abdomen and pelvis",
            status="performed",
            source_quote="CT abdomen and pelvis ordered.",
            section_name="Orders",
        )

        decision = validate_clinical_item(item)

        self.assert_referral_not_procedure_rejected(decision)

    def test_not_performed_procedure_with_not_performed_status_is_accepted(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.PROCEDURE,
            name="circumcision",
            status="not_performed",
            source_quote="Circumcision was not performed.",
            section_name="Procedures",
        )

        decision = validate_clinical_item(item)

        self.assertEqual(ValidationStatus.ACCEPTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual((), decision.findings)

    def test_referred_order_is_accepted(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.ORDER,
            name="outpatient colonoscopy",
            status="referred",
            source_quote="Patient referred for outpatient colonoscopy.",
            section_name="Orders and Referrals",
        )

        decision = validate_clinical_item(item)

        self.assertEqual(ValidationStatus.ACCEPTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual((), decision.findings)

    def test_safe_performed_procedure_is_accepted(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.PROCEDURE,
            name="appendectomy",
            status="performed",
            source_quote="Appendectomy was performed in 2018.",
            section_name="Past Surgical History",
        )

        decision = validate_clinical_item(item)

        self.assertEqual(ValidationStatus.ACCEPTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual((), decision.findings)

    def test_active_medication_discontinued_quote_is_rejected(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.MEDICATION,
            name="warfarin",
            status="active",
            source_quote="Warfarin discontinued due to bleeding risk.",
            section_name="Medications",
        )

        decision = validate_clinical_item(item)

        self.assert_inactive_medication_not_active_rejected(decision)

    def test_active_medication_stopped_phrase_is_rejected(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.MEDICATION,
            name="aspirin",
            status="active",
            source_quote="Aspirin stopped after gastrointestinal bleed.",
            section_name="Medications",
        )

        decision = validate_clinical_item(item)

        self.assert_inactive_medication_not_active_rejected(decision)

    def test_active_medication_was_stopped_phrase_is_rejected(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.MEDICATION,
            name="lisinopril",
            status="active",
            source_quote="Lisinopril was stopped due to hypotension.",
            section_name="Medications",
        )

        decision = validate_clinical_item(item)

        self.assert_inactive_medication_not_active_rejected(decision)

    def test_active_medication_held_phrase_is_rejected(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.MEDICATION,
            name="metformin",
            status="active",
            source_quote="Metformin held while creatinine is elevated.",
            section_name="Medications",
        )

        decision = validate_clinical_item(item)

        self.assert_inactive_medication_not_active_rejected(decision)

    def test_active_medication_avoid_phrase_is_rejected(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.MEDICATION,
            name="nsaids",
            status="active",
            source_quote="Avoid NSAIDs due to kidney disease.",
            section_name="Medications",
        )

        decision = validate_clinical_item(item)

        self.assert_inactive_medication_not_active_rejected(decision)

    def test_inactive_medication_matching_is_case_insensitive(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.MEDICATION,
            name="warfarin",
            status="active",
            source_quote="WARFARIN DISCONTINUED due to bleeding risk.",
            section_name="Medications",
        )

        decision = validate_clinical_item(item)

        self.assert_inactive_medication_not_active_rejected(decision)

    def test_discontinued_medication_status_is_accepted(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.MEDICATION,
            name="warfarin",
            status="discontinued",
            source_quote="Warfarin discontinued due to bleeding risk.",
            section_name="Medications",
        )

        decision = validate_clinical_item(item)

        self.assertEqual(ValidationStatus.ACCEPTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual((), decision.findings)

    def test_held_medication_status_is_accepted(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.MEDICATION,
            name="metformin",
            status="held",
            source_quote="Metformin held while creatinine is elevated.",
            section_name="Medications",
        )

        decision = validate_clinical_item(item)

        self.assertEqual(ValidationStatus.ACCEPTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual((), decision.findings)

    def test_stopped_medication_status_is_accepted(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.MEDICATION,
            name="aspirin",
            status="stopped",
            source_quote="Aspirin stopped after gastrointestinal bleed.",
            section_name="Medications",
        )

        decision = validate_clinical_item(item)

        self.assertEqual(ValidationStatus.ACCEPTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual((), decision.findings)

    def test_safe_active_medication_is_accepted(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.MEDICATION,
            name="metformin",
            status="active",
            source_quote="Patient takes metformin 500 mg twice daily.",
            section_name="Medications",
        )

        decision = validate_clinical_item(item)

        self.assertEqual(ValidationStatus.ACCEPTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual((), decision.findings)

    def test_non_medication_with_inactive_medication_wording_is_accepted(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.ORDER,
            name="warfarin clinic follow-up",
            status="ordered",
            source_quote="Warfarin discontinued; follow-up ordered with anticoagulation clinic.",
            section_name="Orders",
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




    def assert_inactive_medication_not_active_rejected(self, decision) -> None:
        self.assertEqual(ValidationStatus.REJECTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual(1, len(decision.findings))
        finding = decision.findings[0]
        self.assertEqual("RULE_INACTIVE_MEDICATION_NOT_ACTIVE", finding.rule_id)
        self.assertEqual(ValidationSeverity.ERROR, finding.severity)
        self.assertIn("medication", finding.message)
        self.assertIn("active", finding.message)

    def assert_procedure_not_performed_rejected(self, decision) -> None:
        self.assertEqual(ValidationStatus.REJECTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual(1, len(decision.findings))
        finding = decision.findings[0]
        self.assertEqual("RULE_PROCEDURE_NOT_PERFORMED", finding.rule_id)
        self.assertEqual(ValidationSeverity.ERROR, finding.severity)
        self.assertIn("must not be accepted as performed", finding.message)

    def assert_referral_not_procedure_rejected(self, decision) -> None:
        self.assertEqual(ValidationStatus.REJECTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual(1, len(decision.findings))
        finding = decision.findings[0]
        self.assertEqual("RULE_REFERRAL_NOT_PROCEDURE", finding.rule_id)
        self.assertEqual(ValidationSeverity.ERROR, finding.severity)
        self.assertIn("must not be accepted as a performed procedure", finding.message)

    def assert_family_history_condition_rejected(self, decision) -> None:
        self.assertEqual(ValidationStatus.REJECTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual(1, len(decision.findings))
        finding = decision.findings[0]
        self.assertEqual("RULE_FAMILY_HISTORY_NOT_PATIENT_CONDITION", finding.rule_id)
        self.assertEqual(ValidationSeverity.ERROR, finding.severity)
        self.assertIn("Family-history mention", finding.message)
        self.assertIn("patient condition", finding.message)

    def assert_negated_condition_rejected(self, decision) -> None:
        self.assertEqual(ValidationStatus.REJECTED, decision.status)
        self.assertFalse(decision.review_required)
        self.assertEqual(1, len(decision.findings))
        finding = decision.findings[0]
        self.assertEqual("RULE_NEGATED_CONDITION", finding.rule_id)
        self.assertEqual(ValidationSeverity.ERROR, finding.severity)
        self.assertIn("Negated mention", finding.message)
        self.assertIn("active condition", finding.message)

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
