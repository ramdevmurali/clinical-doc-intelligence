import unittest
from dataclasses import FrozenInstanceError

from processor.src.domain.evaluation import (
    EvaluationError,
    EvaluationIssue,
    EvaluationResult,
    ExpectedClinicalItem,
    InvalidExtractionTrap,
    ItemMatch,
)


class EvaluationModelTests(unittest.TestCase):
    def test_empty_evaluation_result_can_be_constructed(self) -> None:
        result = self.empty_result()

        self.assertEqual(0, result.expected_item_count)
        self.assertEqual(0, result.predicted_item_count)
        self.assertEqual(0, result.matched_item_count)
        self.assertEqual(0, result.missing_item_count)
        self.assertEqual(0, result.extra_item_count)
        self.assertEqual(0, result.invalid_trap_hit_count)
        self.assertEqual(0, result.source_quote_failure_count)
        self.assertEqual((), result.matches)
        self.assertEqual((), result.missing_expected_indexes)
        self.assertEqual((), result.extra_predicted_indexes)
        self.assertEqual((), result.invalid_trap_hits)
        self.assertEqual((), result.source_quote_failures)

    def test_evaluation_result_preserves_count_fields(self) -> None:
        result = EvaluationResult(
            expected_item_count=5,
            predicted_item_count=6,
            matched_item_count=3,
            missing_item_count=2,
            extra_item_count=3,
            invalid_trap_hit_count=1,
            source_quote_failure_count=4,
        )

        self.assertEqual(5, result.expected_item_count)
        self.assertEqual(6, result.predicted_item_count)
        self.assertEqual(3, result.matched_item_count)
        self.assertEqual(2, result.missing_item_count)
        self.assertEqual(3, result.extra_item_count)
        self.assertEqual(1, result.invalid_trap_hit_count)
        self.assertEqual(4, result.source_quote_failure_count)

    def test_evaluation_result_normalizes_iterables_to_tuples(self) -> None:
        match = ItemMatch(expected_index=0, predicted_index=1)
        trap_hit = EvaluationIssue(
            issue_type="invalid_trap_hit",
            message="Predicted forbidden item.",
            trap_index=0,
            predicted_index=1,
        )
        source_failure = EvaluationIssue(
            issue_type="source_quote_failure",
            message="Source quote did not resolve.",
            predicted_index=2,
        )

        result = EvaluationResult(
            expected_item_count=2,
            predicted_item_count=3,
            matched_item_count=1,
            missing_item_count=1,
            extra_item_count=2,
            invalid_trap_hit_count=1,
            source_quote_failure_count=1,
            matches=[match],
            missing_expected_indexes=[1],
            extra_predicted_indexes=[0, 2],
            invalid_trap_hits=[trap_hit],
            source_quote_failures=[source_failure],
        )

        self.assertEqual((match,), result.matches)
        self.assertEqual((1,), result.missing_expected_indexes)
        self.assertEqual((0, 2), result.extra_predicted_indexes)
        self.assertEqual((trap_hit,), result.invalid_trap_hits)
        self.assertEqual((source_failure,), result.source_quote_failures)

    def test_expected_clinical_item_preserves_fields(self) -> None:
        item = ExpectedClinicalItem(
            item_type="condition",
            name="chest pain",
            status="active",
            source_quote="Patient reports chest pain.",
        )

        self.assertEqual("condition", item.item_type)
        self.assertEqual("chest pain", item.name)
        self.assertEqual("active", item.status)
        self.assertEqual("Patient reports chest pain.", item.source_quote)

    def test_invalid_extraction_trap_preserves_fields(self) -> None:
        trap = InvalidExtractionTrap(
            item_type="procedure",
            name="circumcision",
            forbidden_status="performed",
            reason="Explicitly not performed.",
        )

        self.assertEqual("procedure", trap.item_type)
        self.assertEqual("circumcision", trap.name)
        self.assertEqual("performed", trap.forbidden_status)
        self.assertEqual("Explicitly not performed.", trap.reason)

    def test_item_match_preserves_indexes(self) -> None:
        match = ItemMatch(expected_index=2, predicted_index=4)

        self.assertEqual(2, match.expected_index)
        self.assertEqual(4, match.predicted_index)

    def test_evaluation_issue_preserves_fields(self) -> None:
        issue = EvaluationIssue(
            issue_type="extra_prediction",
            message="Prediction did not match expected item.",
            expected_index=1,
            predicted_index=2,
            trap_index=3,
        )

        self.assertEqual("extra_prediction", issue.issue_type)
        self.assertEqual("Prediction did not match expected item.", issue.message)
        self.assertEqual(1, issue.expected_index)
        self.assertEqual(2, issue.predicted_index)
        self.assertEqual(3, issue.trap_index)

    def test_dataclasses_are_immutable(self) -> None:
        cases = [
            ExpectedClinicalItem(item_type="condition", name="hypertension"),
            InvalidExtractionTrap(item_type="condition", name="chest pain"),
            ItemMatch(expected_index=0, predicted_index=0),
            EvaluationIssue(issue_type="missing", message="Missing expected item."),
            self.empty_result(),
        ]

        for instance in cases:
            with self.subTest(instance=type(instance).__name__):
                with self.assertRaises(FrozenInstanceError):
                    instance.__setattr__("name", "changed")

    def test_expected_clinical_item_rejects_empty_required_fields(self) -> None:
        with self.assertRaises(EvaluationError):
            ExpectedClinicalItem(item_type="", name="hypertension")
        with self.assertRaises(EvaluationError):
            ExpectedClinicalItem(item_type="condition", name="")

    def test_expected_clinical_item_rejects_whitespace_required_fields(self) -> None:
        with self.assertRaises(EvaluationError):
            ExpectedClinicalItem(item_type="   ", name="hypertension")
        with self.assertRaises(EvaluationError):
            ExpectedClinicalItem(item_type="condition", name="   ")

    def test_expected_clinical_item_rejects_empty_optional_strings_when_provided(self) -> None:
        with self.assertRaises(EvaluationError):
            ExpectedClinicalItem(item_type="condition", name="hypertension", status="")
        with self.assertRaises(EvaluationError):
            ExpectedClinicalItem(item_type="condition", name="hypertension", source_quote="   ")

    def test_invalid_extraction_trap_rejects_empty_required_fields(self) -> None:
        with self.assertRaises(EvaluationError):
            InvalidExtractionTrap(item_type="", name="chest pain")
        with self.assertRaises(EvaluationError):
            InvalidExtractionTrap(item_type="condition", name="")

    def test_invalid_extraction_trap_rejects_empty_optional_strings_when_provided(self) -> None:
        with self.assertRaises(EvaluationError):
            InvalidExtractionTrap(item_type="condition", name="chest pain", forbidden_status="")
        with self.assertRaises(EvaluationError):
            InvalidExtractionTrap(item_type="condition", name="chest pain", reason="   ")

    def test_item_match_rejects_negative_indexes(self) -> None:
        with self.assertRaises(EvaluationError):
            ItemMatch(expected_index=-1, predicted_index=0)
        with self.assertRaises(EvaluationError):
            ItemMatch(expected_index=0, predicted_index=-1)

    def test_evaluation_issue_rejects_empty_required_strings(self) -> None:
        with self.assertRaises(EvaluationError):
            EvaluationIssue(issue_type="", message="Missing expected item.")
        with self.assertRaises(EvaluationError):
            EvaluationIssue(issue_type="missing", message="   ")

    def test_evaluation_issue_rejects_negative_optional_indexes(self) -> None:
        with self.assertRaises(EvaluationError):
            EvaluationIssue(issue_type="missing", message="Missing.", expected_index=-1)
        with self.assertRaises(EvaluationError):
            EvaluationIssue(issue_type="extra", message="Extra.", predicted_index=-1)
        with self.assertRaises(EvaluationError):
            EvaluationIssue(issue_type="trap", message="Trap.", trap_index=-1)

    def test_evaluation_result_rejects_negative_counts(self) -> None:
        count_fields = (
            "expected_item_count",
            "predicted_item_count",
            "matched_item_count",
            "missing_item_count",
            "extra_item_count",
            "invalid_trap_hit_count",
            "source_quote_failure_count",
        )
        for field_name in count_fields:
            values = {
                "expected_item_count": 0,
                "predicted_item_count": 0,
                "matched_item_count": 0,
                "missing_item_count": 0,
                "extra_item_count": 0,
                "invalid_trap_hit_count": 0,
                "source_quote_failure_count": 0,
            }
            values[field_name] = -1

            with self.subTest(field_name=field_name):
                with self.assertRaises(EvaluationError):
                    EvaluationResult(**values)

    def test_evaluation_result_rejects_negative_missing_or_extra_indexes(self) -> None:
        with self.assertRaises(EvaluationError):
            self.empty_result(missing_expected_indexes=[-1])
        with self.assertRaises(EvaluationError):
            self.empty_result(extra_predicted_indexes=[-1])

    def empty_result(self, **overrides) -> EvaluationResult:
        values = {
            "expected_item_count": 0,
            "predicted_item_count": 0,
            "matched_item_count": 0,
            "missing_item_count": 0,
            "extra_item_count": 0,
            "invalid_trap_hit_count": 0,
            "source_quote_failure_count": 0,
        }
        values.update(overrides)
        return EvaluationResult(**values)


if __name__ == "__main__":
    unittest.main()
