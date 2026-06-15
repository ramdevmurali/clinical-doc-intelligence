import unittest

from processor.src.domain.extraction_schema import ClinicalItemType
from processor.src.domain.normalization import (
    NormalizationError,
    normalize_item_type,
    normalize_name,
    normalize_status,
)


EXPECTED_STABLE_STATUSES = {
    "active",
    "historical",
    "resolved",
    "in_remission",
    "performed",
    "not_performed",
    "planned",
    "ordered",
    "referred",
    "pending",
    "administered",
    "started",
    "stopped",
    "discontinued",
    "held",
    "prescribed",
    "none_known",
    "possible",
    "rule_out",
    "unlikely_not_excluded",
    "planned_change",
}


class NormalizationTests(unittest.TestCase):
    def test_normalize_name_trims_collapses_and_lowercases(self) -> None:
        cases = {
            "  Type 2   Diabetes Mellitus ": "type 2 diabetes mellitus",
            " Chest Pain ": "chest pain",
            "Warfarin": "warfarin",
            "Chronic\nKidney\tDisease Stage 3": "chronic kidney disease stage 3",
            "  Right   Lower\nLobe\tOpacity  ": "right lower lobe opacity",
        }

        for raw_name, expected in cases.items():
            with self.subTest(raw_name=raw_name):
                self.assertEqual(expected, normalize_name(raw_name))

    def test_empty_name_is_rejected(self) -> None:
        for raw_name in ["", "\n  \t"]:
            with self.subTest(raw_name=repr(raw_name)):
                with self.assertRaisesRegex(NormalizationError, "name is required"):
                    normalize_name(raw_name)

    def test_exact_item_type_values_normalize_correctly(self) -> None:
        expected_values = {item_type.value for item_type in ClinicalItemType}
        self.assertEqual(
            {
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
            },
            expected_values,
        )

        for item_type in ClinicalItemType:
            with self.subTest(item_type=item_type.value):
                self.assertEqual(item_type, normalize_item_type(item_type.value))

    def test_item_type_aliases_normalize_correctly(self) -> None:
        cases = {
            "diagnosis": ClinicalItemType.CONDITION,
            "problem": ClinicalItemType.CONDITION,
            "drug": ClinicalItemType.MEDICATION,
            "med": ClinicalItemType.MEDICATION,
            "lab": ClinicalItemType.LAB_RESULT,
            "referral": ClinicalItemType.ORDER,
        }

        for raw_type, expected in cases.items():
            with self.subTest(raw_type=raw_type):
                self.assertEqual(expected, normalize_item_type(raw_type))

    def test_item_type_normalization_is_case_and_whitespace_tolerant(self) -> None:
        cases = {
            " Diagnosis ": ClinicalItemType.CONDITION,
            "DRUG": ClinicalItemType.MEDICATION,
            " lab_result ": ClinicalItemType.LAB_RESULT,
            " CONDITION ": ClinicalItemType.CONDITION,
            " Family_History ": ClinicalItemType.FAMILY_HISTORY,
        }

        for raw_type, expected in cases.items():
            with self.subTest(raw_type=raw_type):
                self.assertEqual(expected, normalize_item_type(raw_type))

    def test_empty_item_type_is_rejected(self) -> None:
        for raw_type in ["", " ", "\n\t"]:
            with self.subTest(raw_type=repr(raw_type)):
                with self.assertRaisesRegex(NormalizationError, "item_type is required"):
                    normalize_item_type(raw_type)

    def test_unknown_item_type_is_rejected(self) -> None:
        for raw_type in ["billing_code", "diagnostic_report", "encounter"]:
            with self.subTest(raw_type=raw_type):
                with self.assertRaisesRegex(NormalizationError, "Unknown clinical item type"):
                    normalize_item_type(raw_type)

    def test_none_status_returns_none(self) -> None:
        self.assertIsNone(normalize_status(None))

    def test_empty_status_is_rejected(self) -> None:
        for raw_status in ["", "\n  \t"]:
            with self.subTest(raw_status=repr(raw_status)):
                with self.assertRaisesRegex(NormalizationError, "status is required"):
                    normalize_status(raw_status)

    def test_exact_statuses_normalize_correctly(self) -> None:
        self.assertEqual(21, len(EXPECTED_STABLE_STATUSES))

        for status in sorted(EXPECTED_STABLE_STATUSES):
            with self.subTest(status=status):
                self.assertEqual(status, normalize_status(status))

    def test_status_aliases_normalize_correctly(self) -> None:
        cases = {
            "not performed": "not_performed",
            "not-performed": "not_performed",
            "in remission": "in_remission",
            "rule out": "rule_out",
            "rule-out": "rule_out",
            "no known": "none_known",
            "none known": "none_known",
            "planned change": "planned_change",
            "medication change planned": "planned_change",
        }

        for raw_status, expected in cases.items():
            with self.subTest(raw_status=raw_status):
                self.assertEqual(expected, normalize_status(raw_status))

    def test_status_normalization_is_case_and_whitespace_tolerant(self) -> None:
        cases = {
            " Not Performed ": "not_performed",
            "DISCONTINUED": "discontinued",
            " Rule   Out ": "rule_out",
            " No Known ": "none_known",
            "  In\tRemission  ": "in_remission",
            " Medication   Change\nPlanned ": "planned_change",
        }

        for raw_status, expected in cases.items():
            with self.subTest(raw_status=raw_status):
                self.assertEqual(expected, normalize_status(raw_status))

    def test_unknown_status_is_rejected(self) -> None:
        for raw_status in ["maybe later", "suspected but unclear", "bad_status"]:
            with self.subTest(raw_status=raw_status):
                with self.assertRaisesRegex(NormalizationError, "Unknown clinical status"):
                    normalize_status(raw_status)

    def test_hard_case_statuses_normalize_correctly(self) -> None:
        cases = {
            "not performed": "not_performed",
            "referred": "referred",
            "discontinued": "discontinued",
            "held": "held",
            "rule out": "rule_out",
            "No Known": "none_known",
        }

        for raw_status, expected in cases.items():
            with self.subTest(raw_status=raw_status):
                self.assertEqual(expected, normalize_status(raw_status))


if __name__ == "__main__":
    unittest.main()
