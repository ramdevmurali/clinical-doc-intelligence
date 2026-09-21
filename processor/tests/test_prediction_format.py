import unittest

from processor.src.domain.extraction_schema import ClinicalItemType, ExtractedClinicalItem
from processor.src.domain.prediction_format import (
    PREDICTION_SCHEMA_VERSION,
    prediction_item_from_extracted_item,
    prediction_json_for_items,
)


class PredictionFormatTests(unittest.TestCase):
    def test_prediction_json_preserves_top_level_contract(self) -> None:
        item = ExtractedClinicalItem(
            item_type=ClinicalItemType.CONDITION,
            name="hypertension",
            status="active",
            confidence=0.8,
            source_quote="Hypertension.",
            source_start_char=10,
            source_end_char=23,
            section_id="note_001:section:001",
            section_name="Past Medical History",
        )
        extractor = {"name": "deterministic-baseline", "version": "baseline-extractor-v1"}

        prediction = prediction_json_for_items("note_001", (item,), extractor=extractor)

        self.assertEqual(PREDICTION_SCHEMA_VERSION, prediction["schema_version"])
        self.assertEqual("note_001", prediction["document_id"])
        self.assertEqual(extractor, prediction["extractor"])
        self.assertEqual([prediction_item_from_extracted_item(item)], prediction["items"])

    def test_optional_status_and_confidence_are_omitted_when_absent(self) -> None:
        item = ExtractedClinicalItem(
            item_type=ClinicalItemType.PROCEDURE,
            name="appendectomy",
            status=None,
            confidence=None,
            source_quote="Appendectomy.",
            source_start_char=0,
            source_end_char=13,
            section_id="note_001:section:001",
            section_name="Surgical History",
        )

        prediction_item = prediction_item_from_extracted_item(item)

        self.assertNotIn("status", prediction_item)
        self.assertNotIn("confidence", prediction_item)
        self.assertEqual("Appendectomy.", prediction_item["source_quote"])

    def test_prediction_items_are_sorted_deterministically(self) -> None:
        later_item = ExtractedClinicalItem(
            item_type=ClinicalItemType.CONDITION,
            name="hypertension",
            status="active",
            confidence=0.8,
            source_quote="Hypertension.",
            source_start_char=20,
            source_end_char=33,
            section_id="note_001:section:001",
            section_name="Past Medical History",
        )
        earlier_item = ExtractedClinicalItem(
            item_type=ClinicalItemType.MEDICATION,
            name="metformin",
            status="active",
            confidence=0.9,
            source_quote="Metformin.",
            source_start_char=5,
            source_end_char=15,
            section_id="note_001:section:002",
            section_name="Medications",
        )

        prediction = prediction_json_for_items(
            "note_001",
            (later_item, earlier_item),
            extractor={"name": "llm-harness", "version": "ai-extractor-v1"},
        )

        self.assertEqual(["metformin", "hypertension"], [item["name"] for item in prediction["items"]])


if __name__ == "__main__":
    unittest.main()
