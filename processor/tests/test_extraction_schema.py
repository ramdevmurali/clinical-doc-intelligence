import unittest
from dataclasses import FrozenInstanceError

from processor.src.domain.extraction_schema import (
    ClinicalItemType,
    ExtractedClinicalItem,
    ExtractionSchemaError,
)


EXPECTED_ITEM_TYPES = {
    "condition",
    "procedure",
    "medication",
    "allergy",
    "observation",
    "lab_result",
    "order",
    "care_need",
    "negative_finding",
    "uncertain_mention",
    "family_history",
}


class ExtractionSchemaTests(unittest.TestCase):
    def test_clinical_item_type_values_match_master_plan_exactly(self) -> None:
        actual_values = {item_type.value for item_type in ClinicalItemType}

        self.assertEqual(EXPECTED_ITEM_TYPES, actual_values)

    def test_valid_condition_item_can_be_created(self) -> None:
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

    def test_valid_medication_item_can_be_created(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.MEDICATION,
            name="warfarin",
            status="discontinued",
            source_quote="Warfarin discontinued due to bleeding risk.",
            section_name="Medications",
        )

        self.assertEqual(ClinicalItemType.MEDICATION, item.item_type)
        self.assertEqual("warfarin", item.name)
        self.assertEqual("discontinued", item.status)

    def test_valid_not_performed_procedure_item_can_be_created(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.PROCEDURE,
            name="circumcision",
            status="not_performed",
            source_quote="Circumcision was not performed.",
            section_name="Procedures",
        )

        self.assertEqual(ClinicalItemType.PROCEDURE, item.item_type)
        self.assertEqual("not_performed", item.status)

    def test_valid_negative_finding_item_can_be_created(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.NEGATIVE_FINDING,
            name="chest pain",
            status=None,
            source_quote="Patient denies chest pain.",
            section_name="Review of Systems",
        )

        self.assertEqual(ClinicalItemType.NEGATIVE_FINDING, item.item_type)
        self.assertIsNone(item.status)

    def test_valid_family_history_item_can_be_created(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.FAMILY_HISTORY,
            name="breast cancer",
            status="historical",
            source_quote="Mother had breast cancer.",
            section_name="Family History",
        )

        self.assertEqual(ClinicalItemType.FAMILY_HISTORY, item.item_type)
        self.assertEqual("breast cancer", item.name)

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

    def test_equal_start_and_end_offsets_are_allowed_by_current_contract(self) -> None:
        item = self.valid_item(source_start_char=10, source_end_char=10)

        self.assertEqual(10, item.source_start_char)
        self.assertEqual(10, item.source_end_char)

    def test_quote_existence_is_not_validated_by_schema(self) -> None:
        item = self.valid_item(
            source_quote="This quote may not exist in the raw document.",
            source_start_char=0,
            source_end_char=44,
        )

        self.assertEqual("This quote may not exist in the raw document.", item.source_quote)

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

    def test_hard_case_negative_finding_shape(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.NEGATIVE_FINDING,
            name="chest pain",
            status=None,
            source_quote="Patient denies chest pain.",
            section_name="Review of Systems",
        )

        self.assertEqual(ClinicalItemType.NEGATIVE_FINDING, item.item_type)
        self.assertEqual("chest pain", item.name)

    def test_hard_case_family_history_shape(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.FAMILY_HISTORY,
            name="breast cancer",
            status="historical",
            source_quote="Mother had breast cancer.",
            section_name="Family History",
        )

        self.assertEqual(ClinicalItemType.FAMILY_HISTORY, item.item_type)
        self.assertEqual("Family History", item.section_name)

    def test_hard_case_not_performed_procedure_shape(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.PROCEDURE,
            name="circumcision",
            status="not_performed",
            source_quote="Circumcision was not performed.",
            section_name="Procedures",
        )

        self.assertEqual(ClinicalItemType.PROCEDURE, item.item_type)
        self.assertEqual("not_performed", item.status)

    def test_hard_case_referred_order_shape(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.ORDER,
            name="outpatient colonoscopy",
            status="referred",
            source_quote="Patient referred for outpatient colonoscopy.",
            section_name="Orders and Referrals",
        )

        self.assertEqual(ClinicalItemType.ORDER, item.item_type)
        self.assertEqual("referred", item.status)

    def test_hard_case_discontinued_medication_shape(self) -> None:
        item = self.valid_item(
            item_type=ClinicalItemType.MEDICATION,
            name="warfarin",
            status="discontinued",
            source_quote="Warfarin discontinued due to bleeding risk.",
            section_name="Medications",
        )

        self.assertEqual(ClinicalItemType.MEDICATION, item.item_type)
        self.assertEqual("discontinued", item.status)

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
