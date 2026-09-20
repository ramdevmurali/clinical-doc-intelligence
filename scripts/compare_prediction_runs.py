#!/usr/bin/env python3
"""Compare two saved clinical prediction runs against the golden set."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TextIO


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.eval_golden import (  # noqa: E402
    AggregateSummary,
    CliError as EvalCliError,
    DocumentEvaluation,
    evaluate_prediction_files,
    prediction_files,
)


@dataclass(frozen=True)
class DerivedMetrics:
    """Metrics derived from existing evaluator counts."""

    precision: float | None
    recall: float | None
    f1: float | None
    valid_source_span_rate: float | None
    invalid_trap_rate: float | None


@dataclass(frozen=True)
class RunEvaluation:
    """Named evaluated prediction run."""

    name: str
    predictions_dir: Path
    evaluations: tuple[DocumentEvaluation, ...]
    aggregate: AggregateSummary
    derived: DerivedMetrics
    missing_by_type: tuple[tuple[str, int], ...]
    extra_by_type: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class DocumentDelta:
    """Per-document metric deltas, calculated as right minus left."""

    document_id: str
    matched_delta: int
    missing_delta: int
    extra_delta: int
    invalid_trap_hit_delta: int
    source_quote_failure_delta: int


@dataclass(frozen=True)
class PredictionRunComparison:
    """Complete comparison between two evaluated prediction runs."""

    left: RunEvaluation
    right: RunEvaluation
    document_deltas: tuple[DocumentDelta, ...]
    missing_by_type_deltas: tuple[tuple[str, int, int, int], ...]
    extra_by_type_deltas: tuple[tuple[str, int, int, int], ...]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        comparison = build_comparison(
            left_name=args.left_name,
            left_dir=args.left_dir,
            right_name=args.right_name,
            right_dir=args.right_dir,
            notes_dir=args.notes_dir,
            expected_dir=args.expected_dir,
            document_id=args.document_id,
        )
    except ComparisonCliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print_comparison(comparison, sys.stdout)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare two saved prediction runs against the golden set.",
    )
    parser.add_argument("--left-name", default="baseline", help="Display name for the left run.")
    parser.add_argument(
        "--left-dir",
        type=Path,
        default=ROOT / "predictions_baseline",
        help="Directory containing left-run prediction JSON files.",
    )
    parser.add_argument("--right-name", default="llm", help="Display name for the right run.")
    parser.add_argument(
        "--right-dir",
        type=Path,
        default=ROOT / "predictions_llm",
        help="Directory containing right-run prediction JSON files.",
    )
    parser.add_argument(
        "--notes-dir",
        type=Path,
        default=ROOT / "golden_set" / "notes",
        help="Directory containing golden note text files.",
    )
    parser.add_argument(
        "--expected-dir",
        type=Path,
        default=ROOT / "golden_set" / "expected",
        help="Directory containing golden expected JSON files.",
    )
    parser.add_argument(
        "--document-id",
        help="Optional single document id to compare, for example note_001.",
    )
    return parser


def build_comparison(
    *,
    left_name: str,
    left_dir: Path,
    right_name: str,
    right_dir: Path,
    notes_dir: Path,
    expected_dir: Path,
    document_id: str | None,
) -> PredictionRunComparison:
    try:
        left_paths, right_paths = aligned_prediction_paths(left_dir, right_dir, document_id)
        left = evaluate_run(left_name, left_dir, left_paths, notes_dir, expected_dir)
        right = evaluate_run(right_name, right_dir, right_paths, notes_dir, expected_dir)
    except EvalCliError as exc:
        raise ComparisonCliError(str(exc)) from exc

    return PredictionRunComparison(
        left=left,
        right=right,
        document_deltas=document_deltas(left.evaluations, right.evaluations),
        missing_by_type_deltas=count_deltas(left.missing_by_type, right.missing_by_type),
        extra_by_type_deltas=count_deltas(left.extra_by_type, right.extra_by_type),
    )


def aligned_prediction_paths(
    left_dir: Path,
    right_dir: Path,
    document_id: str | None,
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    if document_id:
        left_paths = prediction_files(left_dir, document_id)
        right_paths = prediction_files(right_dir, document_id)
        return left_paths, right_paths

    left_paths = prediction_files(left_dir, None)
    right_paths = prediction_files(right_dir, None)
    left_by_document_id = {path.stem.removesuffix(".predicted"): path for path in left_paths}
    right_by_document_id = {path.stem.removesuffix(".predicted"): path for path in right_paths}

    left_document_ids = set(left_by_document_id)
    right_document_ids = set(right_by_document_id)
    missing_right = sorted(left_document_ids - right_document_ids)
    extra_right = sorted(right_document_ids - left_document_ids)
    if missing_right or extra_right:
        details = []
        if missing_right:
            details.append(f"missing right predictions for: {', '.join(missing_right)}")
        if extra_right:
            details.append(f"right predictions without left match: {', '.join(extra_right)}")
        raise ComparisonCliError("; ".join(details))

    ordered_document_ids = sorted(left_document_ids)
    return (
        tuple(left_by_document_id[document_id] for document_id in ordered_document_ids),
        tuple(right_by_document_id[document_id] for document_id in ordered_document_ids),
    )


def evaluate_run(
    name: str,
    predictions_dir: Path,
    prediction_paths: Iterable[Path],
    notes_dir: Path,
    expected_dir: Path,
) -> RunEvaluation:
    evaluations = evaluate_prediction_files(
        prediction_paths=prediction_paths,
        notes_dir=notes_dir,
        expected_dir=expected_dir,
    )
    aggregate = aggregate_evaluations(evaluations)
    return RunEvaluation(
        name=name,
        predictions_dir=predictions_dir,
        evaluations=evaluations,
        aggregate=aggregate,
        derived=derive_metrics(aggregate),
        missing_by_type=missing_counts_by_type(evaluations),
        extra_by_type=extra_counts_by_type(evaluations),
    )


def aggregate_evaluations(evaluations: tuple[DocumentEvaluation, ...]) -> AggregateSummary:
    aggregate = AggregateSummary()
    for evaluation in evaluations:
        aggregate = aggregate.add(evaluation.result)
    return aggregate


def derive_metrics(aggregate: AggregateSummary) -> DerivedMetrics:
    precision = safe_divide(aggregate.matched_item_count, aggregate.predicted_item_count)
    recall = safe_divide(aggregate.matched_item_count, aggregate.expected_item_count)
    if precision is None or recall is None or precision + recall == 0:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return DerivedMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        valid_source_span_rate=safe_divide(
            aggregate.predicted_item_count - aggregate.source_quote_failure_count,
            aggregate.predicted_item_count,
        ),
        invalid_trap_rate=safe_divide(
            aggregate.invalid_trap_hit_count,
            aggregate.predicted_item_count,
        ),
    )


def safe_divide(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def document_deltas(
    left: tuple[DocumentEvaluation, ...],
    right: tuple[DocumentEvaluation, ...],
) -> tuple[DocumentDelta, ...]:
    left_by_document_id = {evaluation.document_id: evaluation for evaluation in left}
    right_by_document_id = {evaluation.document_id: evaluation for evaluation in right}
    if set(left_by_document_id) != set(right_by_document_id):
        raise ComparisonCliError("evaluated document sets do not match")

    deltas = []
    for document_id in sorted(left_by_document_id):
        left_result = left_by_document_id[document_id].result
        right_result = right_by_document_id[document_id].result
        deltas.append(
            DocumentDelta(
                document_id=document_id,
                matched_delta=right_result.matched_item_count - left_result.matched_item_count,
                missing_delta=right_result.missing_item_count - left_result.missing_item_count,
                extra_delta=right_result.extra_item_count - left_result.extra_item_count,
                invalid_trap_hit_delta=(
                    right_result.invalid_trap_hit_count - left_result.invalid_trap_hit_count
                ),
                source_quote_failure_delta=(
                    right_result.source_quote_failure_count - left_result.source_quote_failure_count
                ),
            )
        )
    return tuple(deltas)


def missing_counts_by_type(evaluations: tuple[DocumentEvaluation, ...]) -> tuple[tuple[str, int], ...]:
    counter: Counter[str] = Counter()
    for evaluation in evaluations:
        for index in evaluation.result.missing_expected_indexes:
            counter[expected_item_type(evaluation, index)] += 1
    return sorted_counts(counter)


def extra_counts_by_type(evaluations: tuple[DocumentEvaluation, ...]) -> tuple[tuple[str, int], ...]:
    counter: Counter[str] = Counter()
    for evaluation in evaluations:
        for index in evaluation.result.extra_predicted_indexes:
            counter[predicted_item_type(evaluation, index)] += 1
    return sorted_counts(counter)


def expected_item_type(evaluation: DocumentEvaluation, index: int) -> str:
    if index < 0 or index >= len(evaluation.expected_items):
        return "<unavailable>"
    return evaluation.expected_items[index].item_type


def predicted_item_type(evaluation: DocumentEvaluation, index: int) -> str:
    if index < 0 or index >= len(evaluation.predicted_items):
        return "<unavailable>"
    item_type = evaluation.predicted_items[index].item_type
    if hasattr(item_type, "value"):
        return item_type.value
    return str(item_type)


def sorted_counts(counter: Counter[str]) -> tuple[tuple[str, int], ...]:
    return tuple(sorted(counter.items(), key=lambda item: (-item[1], item[0])))


def count_deltas(
    left_counts: tuple[tuple[str, int], ...],
    right_counts: tuple[tuple[str, int], ...],
) -> tuple[tuple[str, int, int, int], ...]:
    left_map = dict(left_counts)
    right_map = dict(right_counts)
    labels = sorted(set(left_map) | set(right_map))
    deltas = []
    for label in labels:
        left_count = left_map.get(label, 0)
        right_count = right_map.get(label, 0)
        deltas.append((label, left_count, right_count, right_count - left_count))
    return tuple(deltas)


def print_comparison(comparison: PredictionRunComparison, output: TextIO) -> None:
    print("Prediction Run Comparison", file=output)
    print("", file=output)
    print("Runs:", file=output)
    print(f"  left: {comparison.left.name} ({comparison.left.predictions_dir})", file=output)
    print(f"  right: {comparison.right.name} ({comparison.right.predictions_dir})", file=output)
    print("", file=output)
    print_aggregate_comparison(comparison.left, comparison.right, output)
    print_derived_comparison(comparison.left, comparison.right, output)
    print_document_deltas(comparison.document_deltas, output)
    print_count_deltas("Missing By Type Delta:", comparison.missing_by_type_deltas, output)
    print_count_deltas("Extra By Type Delta:", comparison.extra_by_type_deltas, output)


def print_aggregate_comparison(left: RunEvaluation, right: RunEvaluation, output: TextIO) -> None:
    print("Aggregate Counts:", file=output)
    for field_name in (
        "notes_evaluated",
        "expected_item_count",
        "predicted_item_count",
        "matched_item_count",
        "missing_item_count",
        "extra_item_count",
        "invalid_trap_hit_count",
        "source_quote_failure_count",
    ):
        left_value = getattr(left.aggregate, field_name)
        right_value = getattr(right.aggregate, field_name)
        print(
            f"  {field_name}: {left_value} -> {right_value} "
            f"(delta {format_signed_int(right_value - left_value)})",
            file=output,
        )
    print("", file=output)


def print_derived_comparison(left: RunEvaluation, right: RunEvaluation, output: TextIO) -> None:
    print("Derived Metrics:", file=output)
    for field_name in (
        "precision",
        "recall",
        "f1",
        "valid_source_span_rate",
        "invalid_trap_rate",
    ):
        left_value = getattr(left.derived, field_name)
        right_value = getattr(right.derived, field_name)
        print(
            f"  {field_name}: {format_metric(left_value)} -> {format_metric(right_value)} "
            f"(delta {format_metric_delta(left_value, right_value)})",
            file=output,
        )
    print("", file=output)


def print_document_deltas(deltas: tuple[DocumentDelta, ...], output: TextIO) -> None:
    print("Per-Document Deltas:", file=output)
    if not deltas:
        print("  none: 0", file=output)
    for delta in deltas:
        print(
            f"  {delta.document_id}: "
            f"matched={format_signed_int(delta.matched_delta)}, "
            f"missing={format_signed_int(delta.missing_delta)}, "
            f"extra={format_signed_int(delta.extra_delta)}, "
            f"invalid_trap_hits={format_signed_int(delta.invalid_trap_hit_delta)}, "
            f"source_quote_failures={format_signed_int(delta.source_quote_failure_delta)}",
            file=output,
        )
    print("", file=output)


def print_count_deltas(
    title: str,
    deltas: tuple[tuple[str, int, int, int], ...],
    output: TextIO,
) -> None:
    print(title, file=output)
    if not deltas:
        print("  none: 0", file=output)
    for label, left_count, right_count, delta in deltas:
        print(
            f"  {label}: left={left_count}, right={right_count}, "
            f"delta={format_signed_int(delta)}",
            file=output,
        )
    print("", file=output)


def format_metric(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def format_metric_delta(left: float | None, right: float | None) -> str:
    if left is None or right is None:
        return "n/a"
    return format_signed_float(right - left)


def format_signed_int(value: int) -> str:
    return f"{value:+d}"


def format_signed_float(value: float) -> str:
    return f"{value:+.4f}"


class ComparisonCliError(ValueError):
    """Raised for comparison CLI failures."""


if __name__ == "__main__":
    raise SystemExit(main())
