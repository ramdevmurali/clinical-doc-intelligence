#!/usr/bin/env python3
"""Run deterministic baseline extraction over clinical note files."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from processor.src.domain.baseline_extractor import (  # noqa: E402
    BASELINE_EXTRACTOR_VERSION,
    BaselineExtractionError,
    extract_baseline_items,
)
from processor.src.domain.extraction_schema import ExtractedClinicalItem  # noqa: E402


SCHEMA_VERSION = "prediction-format-v1"
EXTRACTOR_NAME = "deterministic-baseline"


@dataclass(frozen=True)
class RunSummary:
    """Summary for one generated baseline prediction file."""

    document_id: str
    item_count: int
    output_path: Path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        summaries = run_baseline_extractor(
            notes_dir=args.notes_dir,
            output_dir=args.output_dir,
            document_id=args.document_id,
            overwrite=args.overwrite,
        )
    except BaselineRunnerError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    total_items = 0
    for summary in summaries:
        total_items += summary.item_count
        print(
            f"document_id: {summary.document_id}, "
            f"item_count: {summary.item_count}, "
            f"output_path: {summary.output_path}"
        )
    print(f"documents_processed: {len(summaries)}")
    print(f"total_items: {total_items}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run deterministic baseline extraction and write prediction JSON files.",
    )
    parser.add_argument(
        "--document-id",
        help="Optional single document id to extract, for example note_001.",
    )
    parser.add_argument(
        "--notes-dir",
        type=Path,
        default=ROOT / "golden_set" / "notes",
        help="Directory containing note text files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "predictions_baseline",
        help="Directory for generated baseline prediction JSON files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing prediction files.",
    )
    return parser


def run_baseline_extractor(
    *,
    notes_dir: Path,
    output_dir: Path,
    document_id: str | None,
    overwrite: bool,
) -> tuple[RunSummary, ...]:
    note_paths = resolve_note_paths(notes_dir, document_id)
    summaries = []
    for note_path in note_paths:
        note_document_id = note_path.stem
        output_path = output_dir / f"{note_document_id}.predicted.json"
        if output_path.exists() and not overwrite:
            raise BaselineRunnerError(f"prediction file already exists: {output_path}")

        raw_text = read_text_file(note_path)
        try:
            items = extract_baseline_items(raw_text, note_document_id)
        except BaselineExtractionError as exc:
            raise BaselineRunnerError(f"{note_document_id}: baseline extraction failed: {exc}") from exc

        prediction_json = prediction_json_for_items(note_document_id, items)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(prediction_json, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            raise BaselineRunnerError(f"could not write prediction file {output_path}: {exc}") from exc

        summaries.append(
            RunSummary(
                document_id=note_document_id,
                item_count=len(items),
                output_path=output_path,
            )
        )

    return tuple(summaries)


def resolve_note_paths(notes_dir: Path, document_id: str | None) -> tuple[Path, ...]:
    if document_id:
        note_path = notes_dir / f"{document_id}.txt"
        if not note_path.exists():
            raise BaselineRunnerError(f"missing note file: {note_path}")
        if not note_path.is_file():
            raise BaselineRunnerError(f"note path is not a file: {note_path}")
        return (note_path,)

    if not notes_dir.exists():
        raise BaselineRunnerError(f"missing notes directory: {notes_dir}")
    if not notes_dir.is_dir():
        raise BaselineRunnerError(f"notes path is not a directory: {notes_dir}")

    note_paths = tuple(sorted(notes_dir.glob("*.txt")))
    if not note_paths:
        raise BaselineRunnerError(f"no note files found in {notes_dir}")
    return note_paths


def read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise BaselineRunnerError(f"could not read note file {path}: {exc}") from exc


def prediction_json_for_items(document_id: str, items: tuple[ExtractedClinicalItem, ...]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "document_id": document_id,
        "extractor": {
            "name": EXTRACTOR_NAME,
            "version": BASELINE_EXTRACTOR_VERSION,
        },
        "items": [prediction_item_from_extracted_item(item) for item in items],
    }


def prediction_item_from_extracted_item(item: ExtractedClinicalItem) -> dict:
    prediction_item = {
        "type": item.item_type.value,
        "name": item.name,
    }
    if item.status is not None:
        prediction_item["status"] = item.status
    if item.confidence is not None:
        prediction_item["confidence"] = item.confidence
    prediction_item.update(
        {
            "source_quote": item.source_quote,
            "source_start_char": item.source_start_char,
            "source_end_char": item.source_end_char,
            "section_id": item.section_id,
            "section_name": item.section_name,
        }
    )
    return prediction_item


class BaselineRunnerError(ValueError):
    """Raised for deterministic baseline runner failures."""


if __name__ == "__main__":
    raise SystemExit(main())
