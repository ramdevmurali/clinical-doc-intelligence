"""Validate golden clinical notes and expected extraction labels."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GOLDEN_SET = ROOT / "golden_set"
NOTES_DIR = GOLDEN_SET / "notes"
EXPECTED_DIR = GOLDEN_SET / "expected"


def main() -> None:
    errors: list[str] = []
    expected_paths = sorted(EXPECTED_DIR.glob("note_*.expected.json"))

    for expected_path in expected_paths:
        try:
            expected = json.loads(expected_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{expected_path}: invalid JSON: {exc}")
            continue

        document_id = expected.get("document_id")
        if not document_id:
            errors.append(f"{expected_path}: missing document_id")
            continue

        note_path = NOTES_DIR / f"{document_id}.txt"
        if not note_path.exists():
            errors.append(f"{expected_path}: missing note file {note_path}")
            continue

        note_text = note_path.read_text(encoding="utf-8")
        items = expected.get("items", [])
        if not isinstance(items, list) or not items:
            errors.append(f"{expected_path}: items must be a non-empty list")
            continue

        for index, item in enumerate(items, start=1):
            item_type = item.get("type")
            source_quote = item.get("source_quote")
            if not item_type:
                errors.append(f"{expected_path}: item {index} missing type")
            if not source_quote:
                errors.append(f"{expected_path}: item {index} missing source_quote")
            elif source_quote not in note_text:
                errors.append(
                    f"{expected_path}: item {index} source_quote not found: {source_quote}"
                )

        invalid_extractions = expected.get("invalid_extractions", [])
        if not isinstance(invalid_extractions, list) or not invalid_extractions:
            errors.append(f"{expected_path}: invalid_extractions must be a non-empty list")
        else:
            for index, invalid in enumerate(invalid_extractions, start=1):
                if not invalid.get("type"):
                    errors.append(f"{expected_path}: invalid_extractions {index} missing type")
                if not invalid.get("name"):
                    errors.append(f"{expected_path}: invalid_extractions {index} missing name")
                if not invalid.get("reason"):
                    errors.append(f"{expected_path}: invalid_extractions {index} missing reason")
                if "status" in invalid:
                    errors.append(
                        f"{expected_path}: invalid_extractions {index} must use forbidden_status, not status"
                    )

    note_count = len(list(NOTES_DIR.glob("note_*.txt")))
    expected_count = len(expected_paths)
    if note_count != expected_count:
        errors.append(
            f"note/expected count mismatch: {note_count} notes, {expected_count} expected files"
        )

    if errors:
        raise SystemExit("\n".join(errors))

    print(f"Validated {note_count} golden notes and {expected_count} expected files.")


if __name__ == "__main__":
    main()
