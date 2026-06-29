import copy
import json
from pathlib import Path
import unittest
from dataclasses import FrozenInstanceError

from processor.src.domain.evaluation import (
    EvaluationError,
    EvaluationIssue,
    EvaluationResult,
    ExpectedClinicalItem,
    InvalidExtractionTrap,
    ItemMatch,
    expected_items_from_json,
    invalid_traps_from_json,
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

    def test_expected_items_from_json_parses_full_item(self) -> None:
        expected_json = {
            "items": [
                {
                    "type": "condition",
                    "name": "hypertension",
                    "status": "active",
                    "source_quote": "Hypertension.",
                }
            ]
        }

        items = expected_items_from_json(expected_json)

        self.assertEqual(
            (
                ExpectedClinicalItem(
                    item_type="condition",
                    name="hypertension",
                    status="active",
                    source_quote="Hypertension.",
                ),
            ),
            items,
        )

    def test_expected_items_from_json_parses_minimal_item(self) -> None:
        items = expected_items_from_json({"items": [{"type": "condition", "name": "hypertension"}]})

        self.assertEqual((ExpectedClinicalItem(item_type="condition", name="hypertension"),), items)

    def test_expected_items_from_json_rejects_family_history_condition_without_name(self) -> None:
        with self.assertRaises(EvaluationError):
            expected_items_from_json(
                {
                    "items": [
                        {
                            "type": "family_history",
                            "condition": "breast cancer",
                            "relation": "mother",
                            "source_quote": "Mother had breast cancer.",
                        }
                    ]
                }
            )

    def test_expected_items_from_json_missing_or_empty_items_returns_empty_tuple(self) -> None:
        self.assertEqual((), expected_items_from_json({}))
        self.assertEqual((), expected_items_from_json({"items": []}))

    def test_expected_items_from_json_ignores_extra_fields_without_mutating_input(self) -> None:
        expected_json = {
            "items": [
                {
                    "type": "family_history",
                    "name": "breast cancer",
                    "relation": "mother",
                    "confidence": 0.9,
                }
            ]
        }
        original = copy.deepcopy(expected_json)

        items = expected_items_from_json(expected_json)

        self.assertEqual((ExpectedClinicalItem(item_type="family_history", name="breast cancer"),), items)
        self.assertEqual(original, expected_json)

    def test_expected_items_from_json_rejects_non_dict_expected_json(self) -> None:
        with self.assertRaises(EvaluationError):
            expected_items_from_json([])

    def test_expected_items_from_json_rejects_non_collection_items(self) -> None:
        with self.assertRaises(EvaluationError):
            expected_items_from_json({"items": "not a list"})

    def test_expected_items_from_json_rejects_non_dict_item_entry(self) -> None:
        with self.assertRaises(EvaluationError):
            expected_items_from_json({"items": ["not a dict"]})

    def test_expected_items_from_json_rejects_item_missing_type(self) -> None:
        with self.assertRaises(EvaluationError):
            expected_items_from_json({"items": [{"name": "hypertension"}]})

    def test_expected_items_from_json_rejects_item_missing_name(self) -> None:
        with self.assertRaises(EvaluationError):
            expected_items_from_json({"items": [{"type": "condition"}]})

    def test_expected_items_from_json_rejects_empty_or_whitespace_type_and_name(self) -> None:
        with self.assertRaises(EvaluationError):
            expected_items_from_json({"items": [{"type": "", "name": "hypertension"}]})
        with self.assertRaises(EvaluationError):
            expected_items_from_json({"items": [{"type": "condition", "name": "   "}]})

    def test_invalid_traps_from_json_parses_full_trap(self) -> None:
        expected_json = {
            "invalid_extractions": [
                {
                    "type": "procedure",
                    "name": "circumcision",
                    "forbidden_status": "performed",
                    "reason": "Explicitly not performed",
                }
            ]
        }

        traps = invalid_traps_from_json(expected_json)

        self.assertEqual(
            (
                InvalidExtractionTrap(
                    item_type="procedure",
                    name="circumcision",
                    forbidden_status="performed",
                    reason="Explicitly not performed",
                ),
            ),
            traps,
        )

    def test_invalid_traps_from_json_parses_minimal_trap(self) -> None:
        traps = invalid_traps_from_json(
            {"invalid_extractions": [{"type": "condition", "name": "chest pain"}]}
        )

        self.assertEqual((InvalidExtractionTrap(item_type="condition", name="chest pain"),), traps)

    def test_invalid_traps_from_json_missing_or_empty_traps_returns_empty_tuple(self) -> None:
        self.assertEqual((), invalid_traps_from_json({}))
        self.assertEqual((), invalid_traps_from_json({"invalid_extractions": []}))

    def test_invalid_traps_from_json_ignores_extra_fields_without_mutating_input(self) -> None:
        expected_json = {
            "invalid_extractions": [
                {
                    "type": "condition",
                    "name": "breast cancer",
                    "reason": "Family history only",
                    "extra": "ignored",
                }
            ]
        }
        original = copy.deepcopy(expected_json)

        traps = invalid_traps_from_json(expected_json)

        self.assertEqual(
            (
                InvalidExtractionTrap(
                    item_type="condition",
                    name="breast cancer",
                    reason="Family history only",
                ),
            ),
            traps,
        )
        self.assertEqual(original, expected_json)

    def test_invalid_traps_from_json_rejects_non_dict_expected_json(self) -> None:
        with self.assertRaises(EvaluationError):
            invalid_traps_from_json([])

    def test_invalid_traps_from_json_rejects_non_collection_traps(self) -> None:
        with self.assertRaises(EvaluationError):
            invalid_traps_from_json({"invalid_extractions": "not a list"})

    def test_invalid_traps_from_json_rejects_non_dict_trap_entry(self) -> None:
        with self.assertRaises(EvaluationError):
            invalid_traps_from_json({"invalid_extractions": ["not a dict"]})

    def test_invalid_traps_from_json_rejects_trap_missing_type(self) -> None:
        with self.assertRaises(EvaluationError):
            invalid_traps_from_json({"invalid_extractions": [{"name": "chest pain"}]})

    def test_invalid_traps_from_json_rejects_trap_missing_name(self) -> None:
        with self.assertRaises(EvaluationError):
            invalid_traps_from_json({"invalid_extractions": [{"type": "condition"}]})

    def test_invalid_traps_from_json_rejects_empty_or_whitespace_type_and_name(self) -> None:
        with self.assertRaises(EvaluationError):
            invalid_traps_from_json({"invalid_extractions": [{"type": "", "name": "chest pain"}]})
        with self.assertRaises(EvaluationError):
            invalid_traps_from_json({"invalid_extractions": [{"type": "condition", "name": "   "}]})

    def test_current_golden_expected_json_files_parse_without_errors(self) -> None:
        expected_paths = sorted((self.repo_root() / "golden_set" / "expected").glob("*.expected.json"))
        self.assertTrue(expected_paths)

        for expected_path in expected_paths:
            with self.subTest(expected_path=expected_path.name):
                with expected_path.open() as expected_file:
                    expected_json = json.load(expected_file)

                expected_items = expected_items_from_json(expected_json)
                invalid_traps = invalid_traps_from_json(expected_json)

                for item in expected_items:
                    self.assertTrue(item.item_type.strip())
                    self.assertTrue(item.name.strip())
                for trap in invalid_traps:
                    self.assertTrue(trap.item_type.strip())
                    self.assertTrue(trap.name.strip())

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

    def repo_root(self) -> Path:
        return Path(__file__).resolve().parents[2]


if __name__ == "__main__":
    unittest.main()
