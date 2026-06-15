import unittest
from dataclasses import FrozenInstanceError

from processor.src.domain.extraction_schema import (
    ClinicalItemType,
    ExtractedClinicalItem,
    ExtractionSchemaError,
)


class ExtractionSchemaTests(unittest.TestCase):
    def test_clinical_item_type_values_match_master_plan(self) -> None:
        self.assertEqual("condition", ClinicalItemType.CONDITION.value)
        self.assertEqual("procedure", ClinicalItemType.PROCEDURE.value)
        self.assertEqual("medication", ClinicalItemType.MEDICATION.value)
        self.assertEqual("allergy", ClinicalItemType.ALLERGY.value)
        self.assertEqual("observation", ClinicalItemType.OBSERVATION.value)
        self.assertEqual("lab_result", ClinicalItemType.LAB_RESULT.value)
        self.assertEqual("order", ClinicalItemType.ORDER.value)
        self.assertEqual("care_need", ClinicalItemType.CARE_NEED.value)
        self.assertEqual("negative_finding", ClinicalItemType.NEGATIVE_FINDING.value)
        self.assertEqual("uncertain_mention", ClinicalItemType.UNCERTAIN_MENTION.value)
        self.assertEqual("family_history", ClinicalItemType.FAMILY_HISTORY.value)

    def test_valid_clinical_item_can_be_created(self) -> None:
        item = self.valid_item()

        self.assertEqual(ClinicalItemType.CONDITION, item.item_type)
        self.assertEqual("type 2 diabetes", item.name)
        self.assertEqual("active", item.status)
        self.assertEqual(0.91, item.confidence)
        self.assertEqual("Past medical history includes type 2 diabetes.", item.source_quote)
        self.assertEqual(10, item.source_start_char)
        self.assertEqual(56, item.source_end_char)
        self.assertEqual("note_001:section:003", item.section_id)
        self.assertEqual("Past Medical History", item.section_name)

    def test_item_is_immutable(self) -> None:
        item = self.valid_item()

        with self.assertRaises(FrozenInstanceError):
            item.name = "changed"

    def test_empty_name_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExtractionSchemaError, "name is required"):
            self.valid_item(name="  ")

    def test_empty_source_quote_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExtractionSchemaError, "source_quote is required"):
            self.valid_item(source_quote="\n\t ")

    def test_empty_section_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExtractionSchemaError, "section_id is required"):
            self.valid_item(section_id=" ")

    def test_empty_section_name_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExtractionSchemaError, "section_name is required"):
            self.valid_item(section_name="")

    def test_negative_source_start_char_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExtractionSchemaError, "source_start_char cannot be negative"):
            self.valid_item(source_start_char=-1)

    def test_source_end_char_before_start_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExtractionSchemaError, "source_end_char cannot be before"):
            self.valid_item(source_start_char=20, source_end_char=10)

    def test_confidence_none_is_allowed(self) -> None:
        item = self.valid_item(confidence=None)

        self.assertIsNone(item.confidence)

    def test_confidence_boundary_values_are_allowed(self) -> None:
        self.assertEqual(0.0, self.valid_item(confidence=0.0).confidence)
        self.assertEqual(1.0, self.valid_item(confidence=1.0).confidence)

    def test_confidence_below_zero_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExtractionSchemaError, "confidence must be between"):
            self.valid_item(confidence=-0.01)

    def test_confidence_above_one_is_rejected(self) -> None:
        with self.assertRaisesRegex(ExtractionSchemaError, "confidence must be between"):
            self.valid_item(confidence=1.01)

    def valid_item(self, **overrides) -> ExtractedClinicalItem:
        values = {
            "item_type": ClinicalItemType.CONDITION,
            "name": "type 2 diabetes",
            "status": "active",
            "confidence": 0.91,
            "source_quote": "Past medical history includes type 2 diabetes.",
            "source_start_char": 10,
            "source_end_char": 56,
            "section_id": "note_001:section:003",
            "section_name": "Past Medical History",
        }
        values.update(overrides)
        return ExtractedClinicalItem(**values)


if __name__ == "__main__":
    unittest.main()
