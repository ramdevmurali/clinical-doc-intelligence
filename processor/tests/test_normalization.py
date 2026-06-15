import unittest

from processor.src.domain.extraction_schema import ClinicalItemType
from processor.src.domain.normalization import (
    NormalizationError,
    normalize_item_type,
    normalize_name,
    normalize_status,
)


class NormalizationTests(unittest.TestCase):
    def test_normalize_name_trims_collapses_and_lowercases(self) -> None:
        self.assertEqual("type 2 diabetes mellitus", normalize_name("  Type 2   Diabetes Mellitus "))
        self.assertEqual("chest pain", normalize_name(" Chest Pain "))
        self.assertEqual("warfarin", normalize_name("Warfarin"))
        self.assertEqual("chronic kidney disease stage 3", normalize_name("Chronic\nKidney\tDisease Stage 3"))

    def test_empty_name_is_rejected(self) -> None:
        with self.assertRaisesRegex(NormalizationError, "name is required"):
            normalize_name("")

        with self.assertRaisesRegex(NormalizationError, "name is required"):
            normalize_name("\n  \t")

    def test_exact_item_type_values_normalize_correctly(self) -> None:
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
        self.assertEqual(ClinicalItemType.CONDITION, normalize_item_type(" Diagnosis "))
        self.assertEqual(ClinicalItemType.MEDICATION, normalize_item_type("DRUG"))
        self.assertEqual(ClinicalItemType.LAB_RESULT, normalize_item_type(" lab_result "))

    def test_unknown_item_type_is_rejected(self) -> None:
        with self.assertRaisesRegex(NormalizationError, "Unknown clinical item type"):
            normalize_item_type("billing_code")

    def test_empty_item_type_is_rejected(self) -> None:
        with self.assertRaisesRegex(NormalizationError, "item_type is required"):
            normalize_item_type(" ")

    def test_none_status_returns_none(self) -> None:
        self.assertIsNone(normalize_status(None))

    def test_empty_status_is_rejected(self) -> None:
        with self.assertRaisesRegex(NormalizationError, "status is required"):
            normalize_status("")

        with self.assertRaisesRegex(NormalizationError, "status is required"):
            normalize_status("\n  \t")

    def test_exact_statuses_normalize_correctly(self) -> None:
        statuses = [
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
        ]

        for status in statuses:
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
        self.assertEqual("not_performed", normalize_status(" Not Performed "))
        self.assertEqual("discontinued", normalize_status("DISCONTINUED"))
        self.assertEqual("rule_out", normalize_status(" Rule   Out "))

    def test_unknown_status_is_rejected(self) -> None:
        with self.assertRaisesRegex(NormalizationError, "Unknown clinical status"):
            normalize_status("maybe later")

    def test_hard_case_statuses_normalize_correctly(self) -> None:
        self.assertEqual("not_performed", normalize_status("not performed"))
        self.assertEqual("referred", normalize_status("referred"))
        self.assertEqual("discontinued", normalize_status("discontinued"))
        self.assertEqual("held", normalize_status("held"))
        self.assertEqual("rule_out", normalize_status("rule out"))


if __name__ == "__main__":
    unittest.main()
