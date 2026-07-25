#!/usr/bin/env python3
"""Evaluate saved prediction files against golden clinical notes."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TextIO


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from processor.src.domain.evaluation import (  # noqa: E402
    EvaluationError,
    EvaluationResult,
    evaluate_predictions,
    predicted_items_from_json,
)


PREDICTION_SUFFIX = ".predicted.json"


@dataclass(frozen=True)
class AggregateSummary:
    """Aggregate deterministic evaluation counts across documents."""

    notes_evaluated: int = 0
    expected_item_count: int = 0
    predicted_item_count: int = 0
    matched_item_count: int = 0
    missing_item_count: int = 0
    extra_item_count: int = 0
    invalid_trap_hit_count: int = 0
    source_quote_failure_count: int = 0

    def add(self, result: EvaluationResult) -> AggregateSummary:
        return AggregateSummary(
            notes_evaluated=self.notes_evaluated + 1,
            expected_item_count=self.expected_item_count + result.expected_item_count,
            predicted_item_count=self.predicted_item_count + result.predicted_item_count,
            matched_item_count=self.matched_item_count + result.matched_item_count,
            missing_item_count=self.missing_item_count + result.missing_item_count,
            extra_item_count=self.extra_item_count + result.extra_item_count,
            invalid_trap_hit_count=self.invalid_trap_hit_count + result.invalid_trap_hit_count,
            source_quote_failure_count=(
                self.source_quote_failure_count + result.source_quote_failure_count
            ),
        )


def main(argv: list[str] | None = None) -> int:
    """Run the golden-set evaluator CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        prediction_paths = prediction_files(args.predictions_dir, args.document_id)
        results = evaluate_prediction_files(
            prediction_paths=prediction_paths,
            notes_dir=args.notes_dir,
            expected_dir=args.expected_dir,
        )
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print_results(results, sys.stdout)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate saved prediction JSON files against golden notes.",
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
        default=ROOT / "predictions",
        help="Directory containing saved prediction JSON files.",
    )
    parser.add_argument(
        "--document-id",
        help="Optional single document id to evaluate, for example note_001.",
    )
    return parser


def prediction_files(predictions_dir: Path, document_id: str | None) -> tuple[Path, ...]:
    if document_id:
        prediction_path = predictions_dir / f"{document_id}{PREDICTION_SUFFIX}"
        if not prediction_path.exists():
            raise CliError(f"missing prediction file: {prediction_path}")
        return (prediction_path,)

    if not predictions_dir.exists():
        raise CliError(f"missing predictions directory: {predictions_dir}")
    if not predictions_dir.is_dir():
        raise CliError(f"predictions path is not a directory: {predictions_dir}")

    paths = tuple(sorted(predictions_dir.glob(f"*{PREDICTION_SUFFIX}")))
    if not paths:
        raise CliError(f"no prediction files found in {predictions_dir}")
    return paths


def evaluate_prediction_files(
    prediction_paths: Iterable[Path],
    notes_dir: Path,
    expected_dir: Path,
) -> tuple[tuple[str, EvaluationResult], ...]:
    results = []
    for prediction_path in prediction_paths:
        document_id = document_id_from_prediction_path(prediction_path)
        raw_text = read_text_file(notes_dir / f"{document_id}.txt", "note")
        expected_json = read_json_file(
            expected_dir / f"{document_id}.expected.json",
            "expected",
        )
        prediction_json = read_json_file(prediction_path, "prediction")

        try:
            predicted_items = predicted_items_from_json(prediction_json)
            result = evaluate_predictions(raw_text, expected_json, predicted_items)
        except EvaluationError as exc:
            raise CliError(f"{document_id}: evaluation failed: {exc}") from exc

        results.append((document_id, result))

    if not results:
        raise CliError("no prediction files were evaluated")
    return tuple(results)


def document_id_from_prediction_path(prediction_path: Path) -> str:
    filename = prediction_path.name
    if not filename.endswith(PREDICTION_SUFFIX):
        raise CliError(f"invalid prediction filename: {prediction_path}")
    document_id = filename[: -len(PREDICTION_SUFFIX)]
    if not document_id:
        raise CliError(f"invalid empty document id in prediction filename: {prediction_path}")
    return document_id


def read_text_file(path: Path, label: str) -> str:
    if not path.exists():
        raise CliError(f"missing {label} file: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CliError(f"could not read {label} file {path}: {exc}") from exc


def read_json_file(path: Path, label: str) -> dict:
    if not path.exists():
        raise CliError(f"missing {label} file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliError(f"invalid JSON in {label} file {path}: {exc}") from exc
    except OSError as exc:
        raise CliError(f"could not read {label} file {path}: {exc}") from exc

    if not isinstance(value, dict):
        raise CliError(f"{label} file must contain a JSON object: {path}")
    return value


def print_results(results: tuple[tuple[str, EvaluationResult], ...], output: TextIO) -> None:
    aggregate = AggregateSummary()
    for document_id, result in results:
        print_note_result(document_id, result, output)
        aggregate = aggregate.add(result)

    print("Aggregate Summary", file=output)
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


def print_note_result(document_id: str, result: EvaluationResult, output: TextIO) -> None:
    print(f"Document: {document_id}", file=output)
    print(f"  expected_item_count: {result.expected_item_count}", file=output)
    print(f"  predicted_item_count: {result.predicted_item_count}", file=output)
    print(f"  matched_item_count: {result.matched_item_count}", file=output)
    print(f"  missing_item_count: {result.missing_item_count}", file=output)
    print(f"  extra_item_count: {result.extra_item_count}", file=output)
    print(f"  invalid_trap_hit_count: {result.invalid_trap_hit_count}", file=output)
    print(f"  source_quote_failure_count: {result.source_quote_failure_count}", file=output)
    print("", file=output)


class CliError(ValueError):
    """Raised for deterministic CLI input and evaluation failures."""


if __name__ == "__main__":
    raise SystemExit(main())
