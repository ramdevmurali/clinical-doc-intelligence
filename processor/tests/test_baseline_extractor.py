from pathlib import Path
import unittest

from processor.src.domain.baseline_extractor import (
    BASELINE_EXTRACTOR_VERSION,
    BaselineExtractionError,
    extract_baseline_items,
)
from processor.src.domain.extraction_schema import ClinicalItemType


ROOT = Path(__file__).resolve().parents[2]
GOLDEN_NOTES = ROOT / "golden_set" / "notes"


class BaselineExtractorTests(unittest.TestCase):
    def test_empty_raw_text_is_rejected(self) -> None:
        with self.assertRaisesRegex(BaselineExtractionError, "raw_text is required"):
            extract_baseline_items("", "note")

    def test_empty_document_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(BaselineExtractionError, "document_id is required"):
            extract_baseline_items("Past Medical History:\nHypertension.\n", " ")

    def test_version_constant_is_stable_and_non_empty(self) -> None:
        self.assertEqual("baseline-extractor-v1", BASELINE_EXTRACTOR_VERSION)

    def test_extracts_active_condition_from_past_medical_history(self) -> None:
        raw_text = "Past Medical History:\nHypertension.\n"

        items = extract_baseline_items(raw_text, "simple")

        self.assertEqual(1, len(items))
        item = items[0]
        self.assertEqual(ClinicalItemType.CONDITION, item.item_type)
        self.assertEqual("hypertension", item.name)
        self.assertEqual("active", item.status)
        self.assertEqual("Hypertension.", item.source_quote)

    def test_extracts_active_medication_from_medication_section(self) -> None:
        raw_text = "Medications:\nMetformin 500 mg twice daily.\n"

        items = extract_baseline_items(raw_text, "meds")

        self.assertEqual(1, len(items))
        item = items[0]
        self.assertEqual(ClinicalItemType.MEDICATION, item.item_type)
        self.assertEqual("metformin", item.name)
        self.assertEqual("active", item.status)

    def test_extracts_inactive_medication_statuses_when_explicit(self) -> None:
        raw_text = (
            "Medications:\n"
            "Warfarin discontinued due to bleeding risk.\n"
            "Prednisone stopped yesterday.\n"
            "Lisinopril held due to acute kidney injury.\n"
        )

        items = extract_baseline_items(raw_text, "inactive_meds")

        self.assertEqual(
            [
                ("warfarin", "discontinued"),
                ("prednisone", "stopped"),
                ("lisinopril", "held"),
            ],
            [(item.name, item.status) for item in items],
        )

    def test_extracts_multiple_lab_results_from_labs_section(self) -> None:
        raw_text = (
            "Labs:\n"
            "White blood cell count 13.2 K/uL. Creatinine 0.8 mg/dL.\n"
        )

        items = extract_baseline_items(raw_text, "labs")

        self.assertEqual(
            [
                (ClinicalItemType.LAB_RESULT, "white blood cell count", None),
                (ClinicalItemType.LAB_RESULT, "creatinine", None),
            ],
            [(item.item_type, item.name, item.status) for item in items],
        )
        self.assertEqual(
            [
                "White blood cell count 13.2 K/uL.",
                "Creatinine 0.8 mg/dL.",
            ],
            [item.source_quote for item in items],
        )
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_extracts_lab_results_with_units_and_internal_decimal(self) -> None:
        raw_text = (
            "Labs:\n"
            "Estimated GFR 34 mL/min/1.73m2. Hemoglobin A1c 5.6 percent.\n"
        )

        items = extract_baseline_items(raw_text, "decimal_labs")

        self.assertEqual(
            [
                (ClinicalItemType.LAB_RESULT, "estimated gfr"),
                (ClinicalItemType.LAB_RESULT, "hemoglobin a1c"),
            ],
            [(item.item_type, item.name) for item in items],
        )
        self.assertEqual(
            [
                "Estimated GFR 34 mL/min/1.73m2.",
                "Hemoglobin A1c 5.6 percent.",
            ],
            [item.source_quote for item in items],
        )
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_lab_like_wording_outside_labs_section_is_not_lab_result(self) -> None:
        raw_text = "Assessment and Plan:\nRecheck CBC in one week.\n"

        items = extract_baseline_items(raw_text, "not_lab")

        self.assertFalse(any(item.item_type == ClinicalItemType.LAB_RESULT for item in items))

    def test_extracts_ordered_imaging_order(self) -> None:
        raw_text = "Orders:\nCT abdomen and pelvis ordered.\n"

        items = extract_baseline_items(raw_text, "ordered_imaging")

        self.assert_order(items[0], "ct abdomen and pelvis", "ordered")
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_extracts_ordered_support_order(self) -> None:
        raw_text = "Orders:\nIV fluids ordered.\n"

        items = extract_baseline_items(raw_text, "ordered_support")

        self.assert_order(items[0], "iv fluids", "ordered")
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_extracts_planned_primary_care_follow_up(self) -> None:
        raw_text = "Assessment and Plan:\nFollow up with primary care in one week.\n"

        items = extract_baseline_items(raw_text, "primary_care_follow_up")

        self.assert_order(items[0], "primary care follow-up", "planned")
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_extracts_referred_outpatient_colonoscopy(self) -> None:
        raw_text = "Orders and Referrals:\nPatient referred for outpatient colonoscopy.\n"

        items = extract_baseline_items(raw_text, "outpatient_colonoscopy")

        self.assert_order(items[0], "outpatient colonoscopy", "referred")
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_extracts_planned_repeat_imaging(self) -> None:
        raw_text = "Orders:\nRepeat chest x-ray in six weeks.\n"

        items = extract_baseline_items(raw_text, "repeat_imaging")

        self.assert_order(items[0], "repeat chest x-ray", "planned")
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_extracts_pending_pathology_report(self) -> None:
        raw_text = "Pending Orders:\nPathology report pending.\n"

        items = extract_baseline_items(raw_text, "pending_pathology")

        self.assert_order(items[0], "pathology report", "pending")
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_extracts_planned_basic_metabolic_panel(self) -> None:
        raw_text = "Assessment and Plan:\nRepeat basic metabolic panel in two weeks.\n"

        items = extract_baseline_items(raw_text, "basic_metabolic_panel")

        self.assert_order(items[0], "basic metabolic panel", "planned")
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_extracts_two_orders_from_shared_source_quote(self) -> None:
        raw_text = "Assessment and Plan:\nOrder urine albumin and lipid panel.\n"

        items = extract_baseline_items(raw_text, "shared_order_quote")

        self.assertEqual(
            [
                (ClinicalItemType.ORDER, "urine albumin", "ordered"),
                (ClinicalItemType.ORDER, "lipid panel", "ordered"),
            ],
            [(item.item_type, item.name, item.status) for item in items],
        )
        self.assertEqual(
            ["Order urine albumin and lipid panel."] * 2,
            [item.source_quote for item in items],
        )
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_extracts_diabetic_eye_exam_referral(self) -> None:
        raw_text = "Assessment and Plan:\nRefer for diabetic eye exam.\n"

        items = extract_baseline_items(raw_text, "eye_exam_referral")

        self.assert_order(items[0], "diabetic eye exam", "referred")
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_extracts_surgery_clinic_follow_up(self) -> None:
        raw_text = "Discharge Instructions:\nFollow up with surgery clinic in 10 days.\n"

        items = extract_baseline_items(raw_text, "surgery_follow_up")

        self.assert_order(items[0], "surgery clinic follow-up", "planned")
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_does_not_extract_vague_await_text_as_order(self) -> None:
        raw_text = "Assessment and Plan:\nAwait CT results before surgical consultation.\n"

        items = extract_baseline_items(raw_text, "vague_await")

        self.assertFalse(any(item.item_type == ClinicalItemType.ORDER for item in items))

    def test_extracts_performed_procedure_from_surgical_history(self) -> None:
        raw_text = "Past Surgical History:\nAppendectomy in 2018.\n"

        items = extract_baseline_items(raw_text, "surgery")

        self.assertEqual(1, len(items))
        self.assertEqual(ClinicalItemType.PROCEDURE, items[0].item_type)
        self.assertEqual("appendectomy", items[0].name)
        self.assertEqual("performed", items[0].status)

    def test_extracts_not_performed_procedure_from_explicit_quote(self) -> None:
        raw_text = "Procedures:\nCircumcision was not performed.\n"

        items = extract_baseline_items(raw_text, "procedure")

        self.assertEqual(1, len(items))
        self.assertEqual(ClinicalItemType.PROCEDURE, items[0].item_type)
        self.assertEqual("circumcision", items[0].name)
        self.assertEqual("not_performed", items[0].status)

    def test_extracts_negative_finding_from_denies_quote(self) -> None:
        raw_text = "History of Present Illness:\nPatient denies chest pain.\n"

        items = extract_baseline_items(raw_text, "negative")

        self.assertEqual(1, len(items))
        self.assertEqual(ClinicalItemType.NEGATIVE_FINDING, items[0].item_type)
        self.assertEqual("chest pain", items[0].name)
        self.assertIsNone(items[0].status)

    def test_extracts_multiple_negative_findings_from_repeated_denies_quote(self) -> None:
        raw_text = (
            "History of Present Illness:\n"
            "The patient denies fever, denies vomiting, and denies dysuria.\n"
        )

        items = extract_baseline_items(raw_text, "multi_negative")

        self.assertEqual(
            [
                (ClinicalItemType.NEGATIVE_FINDING, "fever"),
                (ClinicalItemType.NEGATIVE_FINDING, "vomiting"),
                (ClinicalItemType.NEGATIVE_FINDING, "dysuria"),
            ],
            [(item.item_type, item.name) for item in items],
        )
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_extracts_multiple_negative_findings_from_denies_list(self) -> None:
        raw_text = "Review of Systems:\nDenies dizziness, syncope, and leg swelling.\n"

        items = extract_baseline_items(raw_text, "negative_list")

        self.assertEqual(
            [
                "dizziness",
                "syncope",
                "leg swelling",
            ],
            [item.name for item in items],
        )
        self.assertTrue(all(item.item_type == ClinicalItemType.NEGATIVE_FINDING for item in items))
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_extracts_simple_no_negative_finding(self) -> None:
        raw_text = "History of Present Illness:\nNo chest pain.\n"

        items = extract_baseline_items(raw_text, "simple_no")

        self.assertEqual(1, len(items))
        self.assertEqual(ClinicalItemType.NEGATIVE_FINDING, items[0].item_type)
        self.assertEqual("chest pain", items[0].name)
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_simple_no_negative_finding_uses_first_or_fragment(self) -> None:
        raw_text = "History of Present Illness:\nNo fever or chills.\n"

        items = extract_baseline_items(raw_text, "simple_no_or")

        self.assertEqual(1, len(items))
        self.assertEqual(ClinicalItemType.NEGATIVE_FINDING, items[0].item_type)
        self.assertEqual("fever", items[0].name)
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_extracts_imaging_shows_no_negative_finding(self) -> None:
        raw_text = "Results:\nRenal ultrasound shows no hydronephrosis.\n"

        items = extract_baseline_items(raw_text, "shows_no")

        self.assertEqual(1, len(items))
        self.assertEqual(ClinicalItemType.NEGATIVE_FINDING, items[0].item_type)
        self.assertEqual("hydronephrosis", items[0].name)
        self.assert_all_source_spans_are_exact(raw_text, items)

    def test_does_not_extract_no_known_allergies_as_negative_finding(self) -> None:
        raw_text = "Allergies:\nNo known drug allergies.\n"

        items = extract_baseline_items(raw_text, "no_known")

        self.assertFalse(
            any(item.item_type == ClinicalItemType.NEGATIVE_FINDING for item in items)
        )

    def test_does_not_extract_no_completed_procedures_as_negative_finding(self) -> None:
        raw_text = "Procedures:\nNo inpatient procedures were completed.\n"

        items = extract_baseline_items(raw_text, "no_procedures_completed")

        self.assertFalse(
            any(item.item_type == ClinicalItemType.NEGATIVE_FINDING for item in items)
        )

    def test_does_not_extract_denied_symptom_as_active_condition(self) -> None:
        raw_text = "Past Medical History:\nPatient denies chest pain.\n"

        items = extract_baseline_items(raw_text, "negative_condition")

        self.assertFalse(
            any(
                item.item_type == ClinicalItemType.CONDITION
                and item.name == "chest pain"
                and item.status == "active"
                for item in items
            )
        )

    def test_extracts_family_history_item_from_relation_quote(self) -> None:
        raw_text = "Family History:\nMother had breast cancer.\n"

        items = extract_baseline_items(raw_text, "family")

        self.assertEqual(1, len(items))
        self.assertEqual(ClinicalItemType.FAMILY_HISTORY, items[0].item_type)
        self.assertEqual("breast cancer", items[0].name)

    def test_does_not_extract_family_history_as_patient_condition(self) -> None:
        raw_text = "Family History:\nMother had breast cancer.\n"

        items = extract_baseline_items(raw_text, "family_condition")

        self.assertFalse(
            any(
                item.item_type == ClinicalItemType.CONDITION
                and item.name == "breast cancer"
                and item.status == "active"
                for item in items
            )
        )

    def test_does_not_extract_plan_action_sentences_as_conditions(self) -> None:
        raw_text = (
            "Assessment and Plan:\n"
            "Await CT results before surgical consultation.\n"
            "Replete potassium.\n"
            "Recheck CBC in one week.\n"
            "Avoid NSAIDs.\n"
            "Remove iodine allergy from chart.\n"
        )

        items = extract_baseline_items(raw_text, "plan_actions")

        self.assertFalse(
            any(item.item_type == ClinicalItemType.CONDITION for item in items)
        )

    def test_does_not_extract_uncertain_mentions_as_active_conditions(self) -> None:
        raw_text = (
            "Assessment:\n"
            "CT chest suggests possible early pneumonia versus atelectasis.\n"
            "Atelectasis also possible.\n"
            "Low suspicion for malignancy.\n"
        )

        items = extract_baseline_items(raw_text, "uncertain_mentions")

        self.assertFalse(
            any(item.item_type == ClinicalItemType.CONDITION for item in items)
        )

    def test_does_not_extract_allergy_statements_as_conditions(self) -> None:
        raw_text = (
            "Assessment:\n"
            "Amoxicillin allergy with hives.\n"
            "Shellfish allergy with throat itching.\n"
        )

        items = extract_baseline_items(raw_text, "allergy_statements")

        self.assertFalse(
            any(item.item_type == ClinicalItemType.CONDITION for item in items)
        )

    def test_does_not_extract_admin_or_normal_course_text_as_conditions(self) -> None:
        raw_text = (
            "Hospital Course:\n"
            "Medication reconciliation completed.\n"
            "Patient tolerated the procedure well.\n"
        )

        items = extract_baseline_items(raw_text, "admin_normal_course")

        self.assertFalse(
            any(item.item_type == ClinicalItemType.CONDITION for item in items)
        )

    def test_every_extracted_item_has_exact_source_span(self) -> None:
        raw_text = (
            "Past Medical History:\nHypertension.\n\n"
            "Medications:\nMetformin 500 mg twice daily.\n\n"
            "Procedures:\nCircumcision was not performed.\n"
        )

        items = extract_baseline_items(raw_text, "spans")

        self.assertGreater(len(items), 0)
        for item in items:
            with self.subTest(item=item):
                self.assertEqual(
                    item.source_quote,
                    raw_text[item.source_start_char : item.source_end_char],
                )
                self.assertTrue(item.section_id.startswith("spans:section:"))
                self.assertTrue(item.section_name)

    def test_extractor_is_deterministic_for_same_input(self) -> None:
        raw_text = (
            "Past Medical History:\nHypertension.\n\n"
            "Medications:\nMetformin 500 mg twice daily.\n"
        )

        first = extract_baseline_items(raw_text, "deterministic")
        second = extract_baseline_items(raw_text, "deterministic")

        self.assertEqual(first, second)

    def test_note_001_returns_non_empty_source_grounded_items(self) -> None:
        raw_text = (GOLDEN_NOTES / "note_001.txt").read_text(encoding="utf-8")

        items = extract_baseline_items(raw_text, "note_001")

        self.assertGreater(len(items), 0)
        self.assert_all_source_spans_are_exact(raw_text, items)
        self.assertFalse(
            any(
                item.item_type == ClinicalItemType.CONDITION
                and item.name in {"chest pain", "breast cancer"}
                and item.status == "active"
                for item in items
            )
        )

    def test_additional_golden_notes_return_only_source_grounded_items(self) -> None:
        for note_id in ("note_003", "note_007"):
            with self.subTest(note_id=note_id):
                raw_text = (GOLDEN_NOTES / f"{note_id}.txt").read_text(encoding="utf-8")

                items = extract_baseline_items(raw_text, note_id)

                self.assert_all_source_spans_are_exact(raw_text, items)

    def assert_all_source_spans_are_exact(self, raw_text, items) -> None:
        for item in items:
            with self.subTest(item=item):
                self.assertEqual(
                    item.source_quote,
                    raw_text[item.source_start_char : item.source_end_char],
                )

    def assert_order(self, item, name: str, status: str) -> None:
        self.assertEqual(ClinicalItemType.ORDER, item.item_type)
        self.assertEqual(name, item.name)
        self.assertEqual(status, item.status)


if __name__ == "__main__":
    unittest.main()
