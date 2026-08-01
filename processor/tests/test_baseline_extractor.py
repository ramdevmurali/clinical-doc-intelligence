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


if __name__ == "__main__":
    unittest.main()
