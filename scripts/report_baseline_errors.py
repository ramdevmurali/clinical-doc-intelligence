#!/usr/bin/env python3
"""Summarize deterministic baseline evaluation failures."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


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
class WorstDocument:
    """Per-document failure totals for report sorting."""

    document_id: str
    missing: int
    extra: int
    invalid_trap_hits: int
    source_quote_failures: int

    @property
    def total_failures(self) -> int:
        return (
            self.missing
            + self.extra
            + self.invalid_trap_hits
            + self.source_quote_failures
        )


@dataclass(frozen=True)
class BaselineErrorReport:
    """Aggregate baseline evaluation diagnostics."""

    aggregate: AggregateSummary
    missing_by_type: tuple[tuple[str, int], ...]
    extra_by_type: tuple[tuple[str, int], ...]
    worst_documents: tuple[WorstDocument, ...]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        paths = prediction_files(args.predictions_dir, args.document_id)
        evaluations = evaluate_prediction_files(
            prediction_paths=paths,
            notes_dir=args.notes_dir,
            expected_dir=args.expected_dir,
        )
        report = build_report(evaluations)
    except EvalCliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print_report(report, sys.stdout)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report error patterns from deterministic baseline predictions.",
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
        "--predictions-dir",
        type=Path,
        default=ROOT / "predictions_baseline",
        help="Directory containing baseline prediction JSON files.",
    )
    parser.add_argument(
        "--document-id",
        help="Optional single document id to report, for example note_001.",
    )
    return parser


def build_report(evaluations: tuple[DocumentEvaluation, ...]) -> BaselineErrorReport:
    aggregate = AggregateSummary()
    missing_counter: Counter[str] = Counter()
    extra_counter: Counter[str] = Counter()
    worst_documents = []

    for evaluation in evaluations:
        result = evaluation.result
        aggregate = aggregate.add(result)

        for index in result.missing_expected_indexes:
            missing_counter[expected_item_type(evaluation, index)] += 1

        for index in result.extra_predicted_indexes:
            extra_counter[predicted_item_type(evaluation, index)] += 1

        worst_document = WorstDocument(
            document_id=evaluation.document_id,
            missing=result.missing_item_count,
            extra=result.extra_item_count,
            invalid_trap_hits=result.invalid_trap_hit_count,
            source_quote_failures=result.source_quote_failure_count,
        )
        if worst_document.total_failures:
            worst_documents.append(worst_document)

    return BaselineErrorReport(
        aggregate=aggregate,
        missing_by_type=sorted_counts(missing_counter),
        extra_by_type=sorted_counts(extra_counter),
        worst_documents=tuple(
            sorted(
                worst_documents,
                key=lambda document: (-document.total_failures, document.document_id),
            )
        ),
    )


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


def print_report(report: BaselineErrorReport, output: TextIO) -> None:
    print("Baseline Error Report", file=output)
    print("", file=output)
    print_aggregate(report.aggregate, output)
    print_count_section("Missing By Type:", report.missing_by_type, output)
    print_count_section("Extra By Type:", report.extra_by_type, output)
    print_worst_documents(report.worst_documents, output)
    print("Source Grounding:", file=output)
    print(f"  failures: {report.aggregate.source_quote_failure_count}", file=output)
    print("", file=output)
    print("Invalid Trap Hits:", file=output)
    print(f"  hits: {report.aggregate.invalid_trap_hit_count}", file=output)


def print_aggregate(aggregate: AggregateSummary, output: TextIO) -> None:
    print("Aggregate:", file=output)
    print(f"  notes_evaluated: {aggregate.notes_evaluated}", file=output)
    print(f"  expected_item_count: {aggregate.expected_item_count}", file=output)
    print(f"  predicted_item_count: {aggregate.predicted_item_count}", file=output)
    print(f"  matched_item_count: {aggregate.matched_item_count}", file=output)
    print(f"  missing_item_count: {aggregate.missing_item_count}", file=output)
    print(f"  extra_item_count: {aggregate.extra_item_count}", file=output)
    print(f"  invalid_trap_hit_count: {aggregate.invalid_trap_hit_count}", file=output)
    print(
        f"  source_quote_failure_count: {aggregate.source_quote_failure_count}",
        file=output,
    )
    print("", file=output)


def print_count_section(
    title: str,
    counts: tuple[tuple[str, int], ...],
    output: TextIO,
) -> None:
    print(title, file=output)
    if not counts:
        print("  none: 0", file=output)
    for item_type, count in counts:
        print(f"  {item_type}: {count}", file=output)
    print("", file=output)


def print_worst_documents(
    worst_documents: tuple[WorstDocument, ...],
    output: TextIO,
) -> None:
    print("Worst Documents:", file=output)
    if not worst_documents:
        print("  none: 0", file=output)
    for document in worst_documents:
        print(
            f"  {document.document_id}: "
            f"missing={document.missing}, "
            f"extra={document.extra}, "
            f"invalid_trap_hits={document.invalid_trap_hits}, "
            f"source_quote_failures={document.source_quote_failures}",
            file=output,
        )
    print("", file=output)


if __name__ == "__main__":
    raise SystemExit(main())
