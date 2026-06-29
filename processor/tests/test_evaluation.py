import copy
import json
from pathlib import Path
import unittest
from dataclasses import FrozenInstanceError

from processor.src.domain.extraction_schema import ClinicalItemType, ExtractedClinicalItem
from processor.src.domain.evaluation import (
    EvaluationError,
    EvaluationIssue,
    EvaluationMatchKey,
    EvaluationResult,
    ExpectedClinicalItem,
    InvalidExtractionTrap,
    ItemMatch,
    clinical_item_match_key,
    expected_items_from_json,
    expected_item_match_key,
    find_extra_predicted_indexes,
    find_missing_expected_indexes,
    invalid_traps_from_json,
    make_match_key,
    match_expected_items,
    match_keys_compatible,
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

    def test_make_match_key_normalizes_name(self) -> None:
        key = make_match_key("condition", " Chest Pain ")

        self.assertEqual(EvaluationMatchKey(item_type="condition", name="chest pain"), key)

    def test_make_match_key_normalizes_item_type_alias(self) -> None:
        key = make_match_key("diagnosis", "Hypertension")

        self.assertEqual("condition", key.item_type)
        self.assertEqual("hypertension", key.name)

    def test_make_match_key_normalizes_status_alias(self) -> None:
        key = make_match_key("procedure", "Circumcision", "not performed")

        self.assertEqual("procedure", key.item_type)
        self.assertEqual("circumcision", key.name)
        self.assertEqual("not_performed", key.status)

    def test_make_match_key_preserves_source_quote_exactly(self) -> None:
        source_quote = " Patient Denies Chest Pain. "

        key = make_match_key("condition", "chest pain", source_quote=source_quote)

        self.assertEqual(source_quote, key.source_quote)

    def test_make_match_key_rejects_unknown_item_type_status_and_empty_name(self) -> None:
        with self.assertRaises(EvaluationError):
            make_match_key("unknown_type", "hypertension")
        with self.assertRaises(EvaluationError):
            make_match_key("condition", "hypertension", "unknown_status")
        with self.assertRaises(EvaluationError):
            make_match_key("condition", "")

    def test_expected_item_match_key_builds_from_expected_item(self) -> None:
        item = ExpectedClinicalItem(
            item_type="condition",
            name=" Chest Pain ",
            source_quote=" Patient denies chest pain. ",
        )

        key = expected_item_match_key(item)

        self.assertEqual("condition", key.item_type)
        self.assertEqual("chest pain", key.name)
        self.assertIsNone(key.status)
        self.assertEqual(" Patient denies chest pain. ", key.source_quote)

    def test_expected_item_match_key_rejects_wrong_shape(self) -> None:
        with self.assertRaises(EvaluationError):
            expected_item_match_key(object())

    def test_clinical_item_match_key_builds_from_extracted_item(self) -> None:
        item = self.clinical_item(
            item_type=ClinicalItemType.PROCEDURE,
            name=" Circumcision ",
            status="not performed",
            source_quote="Circumcision was not performed.",
        )

        key = clinical_item_match_key(item)

        self.assertEqual("procedure", key.item_type)
        self.assertEqual("circumcision", key.name)
        self.assertEqual("not_performed", key.status)
        self.assertEqual("Circumcision was not performed.", key.source_quote)

    def test_clinical_item_match_key_rejects_wrong_shape(self) -> None:
        with self.assertRaises(EvaluationError):
            clinical_item_match_key(object())

    def test_match_keys_compatible_with_same_normalized_values(self) -> None:
        expected_key = make_match_key(
            "condition",
            " Chest Pain ",
            "active",
            "Patient reports chest pain.",
        )
        predicted_key = make_match_key(
            "diagnosis",
            "chest pain",
            "active",
            "Patient reports chest pain.",
        )

        self.assertTrue(match_keys_compatible(expected_key, predicted_key))

    def test_match_keys_compatible_with_status_alias(self) -> None:
        expected_key = make_match_key("procedure", "circumcision", "not performed")
        predicted_key = make_match_key("procedure", "circumcision", "not_performed")

        self.assertTrue(match_keys_compatible(expected_key, predicted_key))

    def test_match_keys_incompatible_when_expected_source_quote_differs(self) -> None:
        expected_key = make_match_key("condition", "chest pain", source_quote="Patient denies chest pain.")
        predicted_key = make_match_key("condition", "chest pain", source_quote="Patient reports chest pain.")

        self.assertFalse(match_keys_compatible(expected_key, predicted_key))

    def test_match_keys_ignore_predicted_source_quote_when_expected_source_quote_absent(self) -> None:
        expected_key = make_match_key("condition", "chest pain")
        predicted_key = make_match_key("condition", "chest pain", source_quote="Patient reports chest pain.")

        self.assertTrue(match_keys_compatible(expected_key, predicted_key))

    def test_match_keys_incompatible_when_expected_status_differs(self) -> None:
        expected_key = make_match_key("medication", "warfarin", "discontinued")
        predicted_key = make_match_key("medication", "warfarin", "active")

        self.assertFalse(match_keys_compatible(expected_key, predicted_key))

    def test_match_keys_ignore_predicted_status_when_expected_status_absent(self) -> None:
        expected_key = make_match_key("medication", "warfarin")
        predicted_key = make_match_key("medication", "warfarin", "active")

        self.assertTrue(match_keys_compatible(expected_key, predicted_key))

    def test_match_keys_incompatible_for_different_item_type_or_name(self) -> None:
        expected_key = make_match_key("condition", "chest pain")

        self.assertFalse(match_keys_compatible(expected_key, make_match_key("procedure", "chest pain")))
        self.assertFalse(match_keys_compatible(expected_key, make_match_key("condition", "fever")))

    def test_match_keys_compatible_rejects_wrong_shapes(self) -> None:
        key = make_match_key("condition", "chest pain")

        with self.assertRaises(EvaluationError):
            match_keys_compatible(object(), key)
        with self.assertRaises(EvaluationError):
            match_keys_compatible(key, object())

    def test_match_expected_items_matches_one_expected_to_one_prediction(self) -> None:
        expected_items = (ExpectedClinicalItem(item_type="condition", name="hypertension", status="active"),)
        predicted_items = (self.clinical_item(name="hypertension", status="active"),)

        matches = match_expected_items(expected_items, predicted_items)

        self.assertEqual((ItemMatch(expected_index=0, predicted_index=0),), matches)

    def test_match_expected_items_returns_empty_when_expected_item_missing(self) -> None:
        expected_items = (ExpectedClinicalItem(item_type="condition", name="hypertension"),)
        predicted_items = (self.clinical_item(name="diabetes"),)

        matches = match_expected_items(expected_items, predicted_items)

        self.assertEqual((), matches)

    def test_match_expected_items_leaves_extra_prediction_unmatched(self) -> None:
        expected_items = (ExpectedClinicalItem(item_type="condition", name="hypertension"),)
        predicted_items = (
            self.clinical_item(name="hypertension"),
            self.clinical_item(name="diabetes"),
        )

        matches = match_expected_items(expected_items, predicted_items)

        self.assertEqual((ItemMatch(expected_index=0, predicted_index=0),), matches)

    def test_match_expected_items_duplicate_predictions_match_once_to_first_prediction(self) -> None:
        expected_items = (ExpectedClinicalItem(item_type="condition", name="hypertension"),)
        predicted_items = (
            self.clinical_item(name="hypertension"),
            self.clinical_item(name="hypertension"),
        )

        matches = match_expected_items(expected_items, predicted_items)

        self.assertEqual((ItemMatch(expected_index=0, predicted_index=0),), matches)

    def test_match_expected_items_duplicate_expected_items_require_distinct_predictions(self) -> None:
        expected_items = (
            ExpectedClinicalItem(item_type="condition", name="hypertension"),
            ExpectedClinicalItem(item_type="condition", name="hypertension"),
        )
        predicted_items = (
            self.clinical_item(name="hypertension"),
            self.clinical_item(name="hypertension"),
        )

        matches = match_expected_items(expected_items, predicted_items)

        self.assertEqual(
            (
                ItemMatch(expected_index=0, predicted_index=0),
                ItemMatch(expected_index=1, predicted_index=1),
            ),
            matches,
        )

    def test_match_expected_items_duplicate_expected_items_with_one_prediction_match_once(self) -> None:
        expected_items = (
            ExpectedClinicalItem(item_type="condition", name="hypertension"),
            ExpectedClinicalItem(item_type="condition", name="hypertension"),
        )
        predicted_items = (self.clinical_item(name="hypertension"),)

        matches = match_expected_items(expected_items, predicted_items)

        self.assertEqual((ItemMatch(expected_index=0, predicted_index=0),), matches)

    def test_match_expected_items_status_mismatch_prevents_match_when_expected_status_exists(self) -> None:
        expected_items = (ExpectedClinicalItem(item_type="condition", name="hypertension", status="active"),)
        predicted_items = (self.clinical_item(name="hypertension", status="resolved"),)

        matches = match_expected_items(expected_items, predicted_items)

        self.assertEqual((), matches)

    def test_match_expected_items_predicted_status_can_differ_when_expected_status_absent(self) -> None:
        expected_items = (ExpectedClinicalItem(item_type="condition", name="hypertension"),)
        predicted_items = (self.clinical_item(name="hypertension", status="active"),)

        matches = match_expected_items(expected_items, predicted_items)

        self.assertEqual((ItemMatch(expected_index=0, predicted_index=0),), matches)

    def test_match_expected_items_source_quote_mismatch_prevents_match_when_expected_quote_exists(self) -> None:
        expected_items = (
            ExpectedClinicalItem(
                item_type="condition",
                name="hypertension",
                source_quote="Past medical history includes hypertension.",
            ),
        )
        predicted_items = (
            self.clinical_item(
                name="hypertension",
                source_quote="Assessment includes hypertension.",
            ),
        )

        matches = match_expected_items(expected_items, predicted_items)

        self.assertEqual((), matches)

    def test_match_expected_items_predicted_source_quote_can_differ_when_expected_quote_absent(self) -> None:
        expected_items = (ExpectedClinicalItem(item_type="condition", name="hypertension"),)
        predicted_items = (
            self.clinical_item(
                name="hypertension",
                source_quote="Assessment includes hypertension.",
            ),
        )

        matches = match_expected_items(expected_items, predicted_items)

        self.assertEqual((ItemMatch(expected_index=0, predicted_index=0),), matches)

    def test_match_expected_items_uses_normalization_for_type_name_and_status(self) -> None:
        expected_items = (
            ExpectedClinicalItem(
                item_type="diagnosis",
                name="  Circumcision ",
                status="not performed",
            ),
        )
        predicted_items = (
            self.clinical_item(
                item_type=ClinicalItemType.CONDITION,
                name="circumcision",
                status="not_performed",
            ),
        )

        matches = match_expected_items(expected_items, predicted_items)

        self.assertEqual((ItemMatch(expected_index=0, predicted_index=0),), matches)

    def test_match_expected_items_rejects_invalid_collections_and_entries(self) -> None:
        expected_item = ExpectedClinicalItem(item_type="condition", name="hypertension")
        predicted_item = self.clinical_item(name="hypertension")

        with self.assertRaises(EvaluationError):
            match_expected_items(None, [predicted_item])
        with self.assertRaises(EvaluationError):
            match_expected_items([expected_item], None)
        with self.assertRaises(EvaluationError):
            match_expected_items([object()], [predicted_item])
        with self.assertRaises(EvaluationError):
            match_expected_items([expected_item], [object()])

    def test_find_missing_expected_indexes_returns_empty_for_perfect_match(self) -> None:
        expected_items = (
            self.expected_item(name="hypertension"),
            self.expected_item(name="diabetes"),
        )
        matches = (
            ItemMatch(expected_index=0, predicted_index=0),
            ItemMatch(expected_index=1, predicted_index=1),
        )

        missing_indexes = find_missing_expected_indexes(expected_items, matches)

        self.assertEqual((), missing_indexes)

    def test_find_missing_expected_indexes_returns_single_missing_index(self) -> None:
        expected_items = (
            self.expected_item(name="hypertension"),
            self.expected_item(name="diabetes"),
            self.expected_item(name="asthma"),
        )
        matches = (
            ItemMatch(expected_index=0, predicted_index=0),
            ItemMatch(expected_index=2, predicted_index=1),
        )

        missing_indexes = find_missing_expected_indexes(expected_items, matches)

        self.assertEqual((1,), missing_indexes)

    def test_find_missing_expected_indexes_preserves_multiple_missing_indexes_order(self) -> None:
        expected_items = (
            self.expected_item(name="hypertension"),
            self.expected_item(name="diabetes"),
            self.expected_item(name="asthma"),
            self.expected_item(name="pneumonia"),
        )
        matches = (ItemMatch(expected_index=2, predicted_index=0),)

        missing_indexes = find_missing_expected_indexes(expected_items, matches)

        self.assertEqual((0, 1, 3), missing_indexes)

    def test_find_extra_predicted_indexes_returns_empty_for_perfect_match(self) -> None:
        predicted_items = (
            self.clinical_item(name="hypertension"),
            self.clinical_item(name="diabetes"),
        )
        matches = (
            ItemMatch(expected_index=0, predicted_index=0),
            ItemMatch(expected_index=1, predicted_index=1),
        )

        extra_indexes = find_extra_predicted_indexes(predicted_items, matches)

        self.assertEqual((), extra_indexes)

    def test_find_extra_predicted_indexes_returns_single_extra_index(self) -> None:
        predicted_items = (
            self.clinical_item(name="hypertension"),
            self.clinical_item(name="diabetes"),
            self.clinical_item(name="asthma"),
        )
        matches = (
            ItemMatch(expected_index=0, predicted_index=0),
            ItemMatch(expected_index=1, predicted_index=2),
        )

        extra_indexes = find_extra_predicted_indexes(predicted_items, matches)

        self.assertEqual((1,), extra_indexes)

    def test_find_extra_predicted_indexes_preserves_multiple_extra_indexes_order(self) -> None:
        predicted_items = (
            self.clinical_item(name="hypertension"),
            self.clinical_item(name="diabetes"),
            self.clinical_item(name="asthma"),
            self.clinical_item(name="pneumonia"),
        )
        matches = (ItemMatch(expected_index=0, predicted_index=2),)

        extra_indexes = find_extra_predicted_indexes(predicted_items, matches)

        self.assertEqual((0, 1, 3), extra_indexes)

    def test_missing_and_extra_index_helpers_accept_list_inputs(self) -> None:
        expected_items = [
            self.expected_item(name="hypertension"),
            self.expected_item(name="diabetes"),
        ]
        predicted_items = [
            self.clinical_item(name="hypertension"),
            self.clinical_item(name="diabetes"),
        ]
        matches = [ItemMatch(expected_index=0, predicted_index=0)]

        self.assertEqual((1,), find_missing_expected_indexes(expected_items, matches))
        self.assertEqual((1,), find_extra_predicted_indexes(predicted_items, matches))

    def test_find_missing_expected_indexes_rejects_invalid_expected_collection_or_entries(self) -> None:
        match = ItemMatch(expected_index=0, predicted_index=0)

        with self.assertRaises(EvaluationError):
            find_missing_expected_indexes(None, [match])
        with self.assertRaises(EvaluationError):
            find_missing_expected_indexes([object()], [match])

    def test_find_extra_predicted_indexes_rejects_invalid_predicted_collection_or_entries(self) -> None:
        match = ItemMatch(expected_index=0, predicted_index=0)

        with self.assertRaises(EvaluationError):
            find_extra_predicted_indexes(None, [match])
        with self.assertRaises(EvaluationError):
            find_extra_predicted_indexes([object()], [match])

    def test_missing_and_extra_index_helpers_reject_invalid_matches_collection_or_entries(self) -> None:
        expected_items = [self.expected_item()]
        predicted_items = [self.clinical_item()]

        with self.assertRaises(EvaluationError):
            find_missing_expected_indexes(expected_items, None)
        with self.assertRaises(EvaluationError):
            find_extra_predicted_indexes(predicted_items, None)
        with self.assertRaises(EvaluationError):
            find_missing_expected_indexes(expected_items, [object()])
        with self.assertRaises(EvaluationError):
            find_extra_predicted_indexes(predicted_items, [object()])

    def test_find_missing_expected_indexes_rejects_out_of_bounds_expected_match_index(self) -> None:
        expected_items = (self.expected_item(name="hypertension"),)
        matches = (ItemMatch(expected_index=1, predicted_index=0),)

        with self.assertRaises(EvaluationError):
            find_missing_expected_indexes(expected_items, matches)

    def test_find_extra_predicted_indexes_rejects_out_of_bounds_predicted_match_index(self) -> None:
        predicted_items = (self.clinical_item(name="hypertension"),)
        matches = (ItemMatch(expected_index=0, predicted_index=1),)

        with self.assertRaises(EvaluationError):
            find_extra_predicted_indexes(predicted_items, matches)

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

    def expected_item(self, **overrides) -> ExpectedClinicalItem:
        values = {
            "item_type": "condition",
            "name": "hypertension",
            "status": "active",
            "source_quote": "Hypertension.",
        }
        values.update(overrides)
        return ExpectedClinicalItem(**values)

    def clinical_item(self, **overrides) -> ExtractedClinicalItem:
        values = {
            "item_type": ClinicalItemType.CONDITION,
            "name": "hypertension",
            "status": "active",
            "confidence": 0.95,
            "source_quote": "Hypertension.",
            "source_start_char": 0,
            "source_end_char": len("Hypertension."),
            "section_id": "note_001:section:001",
            "section_name": "Assessment",
        }
        values.update(overrides)
        return ExtractedClinicalItem(**values)


if __name__ == "__main__":
    unittest.main()
