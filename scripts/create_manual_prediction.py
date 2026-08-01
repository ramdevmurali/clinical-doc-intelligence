#!/usr/bin/env python3
"""Create manual-baseline prediction files from golden expected labels."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from processor.src.domain.sectioning import SectionParseError, parse_sections  # noqa: E402


SCHEMA_VERSION = "prediction-format-v1"
EXTRACTOR_NAME = "manual-baseline"
EXTRACTOR_VERSION = "0.1.0"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        output_path, item_count = create_manual_prediction(
            document_id=args.document_id,
            notes_dir=args.notes_dir,
            expected_dir=args.expected_dir,
            predictions_dir=args.predictions_dir,
            overwrite=args.overwrite,
        )
    except ManualPredictionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"document_id: {args.document_id}")
    print(f"item_count: {item_count}")
    print(f"output_path: {output_path}")
    print("all spans ok")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate manual-baseline prediction JSON from golden expected labels.",
    )
    parser.add_argument("--document-id", required=True)
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
        help="Directory for generated prediction JSON files.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite an existing prediction file.",
    )
    return parser


def create_manual_prediction(
    *,
    document_id: str,
    notes_dir: Path,
    expected_dir: Path,
    predictions_dir: Path,
    overwrite: bool,
) -> tuple[Path, int]:
    note_path = notes_dir / f"{document_id}.txt"
    expected_path = expected_dir / f"{document_id}.expected.json"
    output_path = predictions_dir / f"{document_id}.predicted.json"

    if output_path.exists() and not overwrite:
        raise ManualPredictionError(f"prediction file already exists: {output_path}")

    raw_text = read_text_file(note_path, "note")
    expected_json = read_json_file(expected_path, "expected")
    items = prediction_items_from_expected(raw_text, expected_json, document_id)

    prediction_json = {
        "schema_version": SCHEMA_VERSION,
        "document_id": document_id,
        "extractor": {
            "name": EXTRACTOR_NAME,
            "version": EXTRACTOR_VERSION,
        },
        "items": items,
    }
    validate_generated_spans(raw_text, items)

    try:
        predictions_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(prediction_json, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        raise ManualPredictionError(f"could not write prediction file {output_path}: {exc}") from exc

    return output_path, len(items)


def prediction_items_from_expected(
    raw_text: str,
    expected_json: dict,
    document_id: str,
) -> list[dict]:
    raw_items = expected_items(expected_json)
    try:
        sections = parse_sections(raw_text, document_id=document_id)
    except SectionParseError as exc:
        raise ManualPredictionError(f"could not parse note sections: {exc}") from exc

    prediction_items = []
    for index, raw_item in enumerate(raw_items):
        item_type = required_field(raw_item, "type", index)
        name = required_field(raw_item, "name", index)
        source_quote = required_field(raw_item, "source_quote", index)
        start_char, end_char = exact_span(raw_text, source_quote, index)
        section = containing_section(sections, start_char, end_char, index)

        prediction_item = {
            "type": item_type,
            "name": name,
        }
        if "status" in raw_item:
            prediction_item["status"] = raw_item["status"]
        prediction_item.update(
            {
                "confidence": 1.0,
                "source_quote": source_quote,
                "source_start_char": start_char,
                "source_end_char": end_char,
                "section_id": section.section_id,
                "section_name": section.name,
            }
        )
        prediction_items.append(prediction_item)

    return prediction_items


def expected_items(expected_json: dict) -> list:
    if not isinstance(expected_json, dict):
        raise ManualPredictionError("expected JSON must be an object")
    raw_items = expected_json.get("items")
    if not isinstance(raw_items, list):
        raise ManualPredictionError("expected JSON items must be a list")
    return raw_items


def required_field(raw_item: object, field_name: str, item_index: int) -> str:
    if not isinstance(raw_item, dict):
        raise ManualPredictionError(f"expected item {item_index} must be an object")
    value = raw_item.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ManualPredictionError(f"expected item {item_index} missing required {field_name}")
    return value


def exact_span(raw_text: str, source_quote: str, item_index: int) -> tuple[int, int]:
    starts = [index for index in range(len(raw_text)) if raw_text.startswith(source_quote, index)]
    if not starts:
        raise ManualPredictionError(f"expected item {item_index} source_quote not found")
    if len(starts) > 1:
        raise ManualPredictionError(f"expected item {item_index} source_quote is ambiguous")
    start_char = starts[0]
    return start_char, start_char + len(source_quote)


def containing_section(sections: list, start_char: int, end_char: int, item_index: int):
    for section in sections:
        if section.start_char <= start_char and end_char <= section.end_char:
            return section
    raise ManualPredictionError(f"expected item {item_index} source span does not map to a section")


def validate_generated_spans(raw_text: str, items: list[dict]) -> None:
    for index, item in enumerate(items):
        start_char = item["source_start_char"]
        end_char = item["source_end_char"]
        if raw_text[start_char:end_char] != item["source_quote"]:
            raise ManualPredictionError(f"generated item {index} source span failed validation")


def read_text_file(path: Path, label: str) -> str:
    if not path.exists():
        raise ManualPredictionError(f"missing {label} file: {path}")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManualPredictionError(f"could not read {label} file {path}: {exc}") from exc


def read_json_file(path: Path, label: str) -> dict:
    if not path.exists():
        raise ManualPredictionError(f"missing {label} file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManualPredictionError(f"malformed {label} JSON {path}: {exc}") from exc
    except OSError as exc:
        raise ManualPredictionError(f"could not read {label} file {path}: {exc}") from exc

    if not isinstance(value, dict):
        raise ManualPredictionError(f"{label} JSON must be an object: {path}")
    return value


class ManualPredictionError(ValueError):
    """Raised for deterministic manual prediction generation failures."""


if __name__ == "__main__":
    raise SystemExit(main())
