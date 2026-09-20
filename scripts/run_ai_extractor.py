#!/usr/bin/env python3
"""Run fixture-backed AI extraction over clinical note files."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from processor.src.domain.ai_extraction_grounding import ground_ai_candidates  # noqa: E402
from processor.src.domain.ai_extraction_prompt import (  # noqa: E402
    AI_EXTRACTION_PROMPT_VERSION,
    build_ai_extraction_messages,
)
from processor.src.domain.ai_extraction_response import parse_ai_extraction_response  # noqa: E402
from processor.src.domain.evaluation import predicted_items_from_json  # noqa: E402
from processor.src.domain.extraction_schema import ExtractedClinicalItem  # noqa: E402
from processor.src.domain.sectioning import parse_sections  # noqa: E402
from processor.src.services.llm_provider import LlmProviderError, provider_for_name  # noqa: E402
from scripts.run_baseline_extractor import (  # noqa: E402
    prediction_item_from_extracted_item,
    read_text_file,
    resolve_note_paths,
)


SCHEMA_VERSION = "prediction-format-v1"
AI_EXTRACTOR_VERSION = "ai-extractor-v1"
EXTRACTOR_NAME = "llm-harness"
DEFAULT_MODEL = "fixture-model"


@dataclass(frozen=True)
class RunSummary:
    """Summary for one generated AI prediction file."""

    document_id: str
    item_count: int
    output_path: Path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        summaries = run_ai_extractor(
            notes_dir=args.notes_dir,
            output_dir=args.output_dir,
            document_id=args.document_id,
            provider_name=args.provider,
            model=args.model,
            overwrite=args.overwrite,
            timeout_seconds=args.timeout_seconds,
        )
    except AiExtractorRunnerError as exc:
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
        description="Run AI extraction and write prediction JSON files.",
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
        default=ROOT / "predictions_llm",
        help="Directory for generated AI prediction JSON files.",
    )
    parser.add_argument(
        "--provider",
        default="fixture",
        help="LLM provider name. Initial supported value: fixture.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Provider model name.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=30.0,
        help="Provider timeout in seconds.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing prediction files.",
    )
    return parser


def run_ai_extractor(
    *,
    notes_dir: Path,
    output_dir: Path,
    document_id: str | None,
    provider_name: str,
    model: str,
    overwrite: bool,
    timeout_seconds: float,
) -> tuple[RunSummary, ...]:
    try:
        provider = provider_for_name(provider_name)
    except LlmProviderError as exc:
        raise AiExtractorRunnerError(str(exc)) from exc

    note_paths = resolve_note_paths(notes_dir, document_id)
    summaries = []
    for note_path in note_paths:
        note_document_id = note_path.stem
        output_path = output_dir / f"{note_document_id}.predicted.json"
        if output_path.exists() and not overwrite:
            raise AiExtractorRunnerError(f"prediction file already exists: {output_path}")

        raw_text = read_text_file(note_path)
        try:
            sections = tuple(parse_sections(raw_text, document_id=note_document_id))
            messages = build_ai_extraction_messages(
                document_id=note_document_id,
                raw_text=raw_text,
                sections=sections,
            )
            response = provider.complete_json(
                model=model,
                messages=messages,
                timeout_seconds=timeout_seconds,
            )
            candidates = parse_ai_extraction_response(response.content, document_id=note_document_id)
            grounding_result = ground_ai_candidates(
                raw_text=raw_text,
                sections=sections,
                candidates=candidates,
            )
        except Exception as exc:
            raise AiExtractorRunnerError(f"{note_document_id}: AI extraction failed: {exc}") from exc

        prediction_json = prediction_json_for_items(
            note_document_id,
            grounding_result.prediction_items,
            provider_name=response.provider,
            model=response.model,
        )
        predicted_items_from_json(prediction_json)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(prediction_json, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            raise AiExtractorRunnerError(f"could not write prediction file {output_path}: {exc}") from exc

        summaries.append(
            RunSummary(
                document_id=note_document_id,
                item_count=len(grounding_result.prediction_items),
                output_path=output_path,
            )
        )

    return tuple(summaries)


def prediction_json_for_items(
    document_id: str,
    items: tuple[ExtractedClinicalItem, ...],
    *,
    provider_name: str,
    model: str,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "document_id": document_id,
        "extractor": {
            "name": EXTRACTOR_NAME,
            "version": AI_EXTRACTOR_VERSION,
            "provider": provider_name,
            "model": model,
            "prompt_version": AI_EXTRACTION_PROMPT_VERSION,
        },
        "items": [prediction_item_from_extracted_item(item) for item in items],
    }


class AiExtractorRunnerError(ValueError):
    """Raised for AI extractor runner failures."""


if __name__ == "__main__":
    raise SystemExit(main())
