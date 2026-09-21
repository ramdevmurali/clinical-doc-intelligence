#!/usr/bin/env python3
"""Run fixture-backed AI extraction over clinical note files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from processor.src.domain.ai_extraction_grounding import (  # noqa: E402
    AiGroundingFailure,
    AiGroundingResult,
    GroundedAiItem,
    ground_ai_candidates,
)
from processor.src.domain.ai_extraction_prompt import (  # noqa: E402
    AI_EXTRACTION_PROMPT_VERSION,
    PromptMessage,
    build_ai_extraction_messages,
)
from processor.src.domain.ai_extraction_response import (  # noqa: E402
    AiCandidateItem,
    parse_ai_extraction_response,
)
from processor.src.domain.evaluation import predicted_items_from_json  # noqa: E402
from processor.src.domain.extraction_schema import ExtractedClinicalItem  # noqa: E402
from processor.src.domain.sectioning import parse_sections  # noqa: E402
from processor.src.services.llm_provider import LlmProviderError, LlmResponse, provider_for_name  # noqa: E402
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
    audit_path: Path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    load_env_file(args.env_file)

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
    parser.add_argument(
        "--env-file",
        type=Path,
        default=ROOT / ".env.local",
        help="Optional local env file for provider credentials. Existing environment values take precedence.",
    )
    return parser


def load_env_file(path: Path) -> None:
    """Load simple KEY=VALUE entries from an ignored local env file."""

    if not path.exists():
        return
    if not path.is_file():
        raise AiExtractorRunnerError(f"env file is not a file: {path}")

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AiExtractorRunnerError(f"could not read env file {path}: {exc}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            raise AiExtractorRunnerError(f"invalid env file line {line_number}: expected KEY=VALUE")

        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise AiExtractorRunnerError(f"invalid env file line {line_number}: empty key")
        if key in os.environ:
            continue
        os.environ[key] = _clean_env_value(value)


def _clean_env_value(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        return cleaned[1:-1]
    return cleaned


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
        audit_path = output_dir / f"{note_document_id}.audit.json"
        if output_path.exists() and not overwrite:
            raise AiExtractorRunnerError(f"prediction file already exists: {output_path}")
        if audit_path.exists() and not overwrite:
            raise AiExtractorRunnerError(f"audit file already exists: {audit_path}")

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
        audit_json = audit_json_for_run(
            document_id=note_document_id,
            provider_name=response.provider,
            model=response.model,
            messages=messages,
            response=response,
            candidates=candidates,
            grounding_result=grounding_result,
        )
        predicted_items_from_json(prediction_json)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(prediction_json, indent=2) + "\n", encoding="utf-8")
            audit_path.write_text(json.dumps(audit_json, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            raise AiExtractorRunnerError(f"could not write output files for {note_document_id}: {exc}") from exc

        summaries.append(
            RunSummary(
                document_id=note_document_id,
                item_count=len(grounding_result.prediction_items),
                output_path=output_path,
                audit_path=audit_path,
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


def audit_json_for_run(
    *,
    document_id: str,
    provider_name: str,
    model: str,
    messages: tuple[PromptMessage, ...],
    response: LlmResponse,
    candidates: tuple[AiCandidateItem, ...],
    grounding_result: AiGroundingResult,
) -> dict:
    return {
        "document_id": document_id,
        "extractor": extractor_metadata(provider_name=provider_name, model=model),
        "counts": {
            "candidate_count": len(candidates),
            "accepted_count": len(grounding_result.accepted),
            "needs_review_count": len(grounding_result.needs_review),
            "rejected_by_schema_count": 0,
            "rejected_by_grounding_count": len(grounding_result.rejected_by_grounding),
            "rejected_by_rules_count": len(grounding_result.rejected_by_rules),
        },
        "failures": [
            failure_json_for_grounding_failure(failure)
            for failure in grounding_result.rejected_by_grounding + grounding_result.rejected_by_rules
        ],
        "validation_findings": validation_findings_for_grounded_items(
            grounding_result.needs_review,
            grounding_result.rejected_by_rules,
        ),
        "prompt_sha256": sha256_text(prompt_hash_input(messages)),
        "raw_response_sha256": sha256_text(response.content),
        "latency_ms": response.latency_ms,
        "input_tokens": response.input_tokens,
        "output_tokens": response.output_tokens,
        "request_id": response.request_id,
    }


def extractor_metadata(*, provider_name: str, model: str) -> dict:
    return {
        "name": EXTRACTOR_NAME,
        "version": AI_EXTRACTOR_VERSION,
        "provider": provider_name,
        "model": model,
        "prompt_version": AI_EXTRACTION_PROMPT_VERSION,
    }


def failure_json_for_grounding_failure(failure: AiGroundingFailure) -> dict:
    return {
        "candidate_index": failure.candidate_index,
        "stage": failure.stage,
        "reason": failure.reason,
        "candidate": candidate_json(failure.candidate),
    }


def validation_findings_for_grounded_items(
    needs_review: tuple[GroundedAiItem, ...],
    rejected_by_rules: tuple[AiGroundingFailure, ...],
) -> list[dict]:
    findings = []
    for grounded in needs_review:
        for finding in grounded.validation.findings:
            findings.append(
                {
                    "candidate_index": grounded.candidate_index,
                    "stage": "clinical_rules",
                    "decision": grounded.validation.status.value,
                    "rule_id": finding.rule_id,
                    "severity": finding.severity.value,
                    "message": finding.message,
                    "item": prediction_item_from_extracted_item(grounded.item),
                }
            )
    for failure in rejected_by_rules:
        if not failure.findings:
            findings.append(
                {
                    "candidate_index": failure.candidate_index,
                    "stage": "clinical_rules",
                    "decision": "rejected",
                    "message": failure.reason,
                    "candidate": candidate_json(failure.candidate),
                }
            )
            continue

        for finding in failure.findings:
            findings.append(
                {
                    "candidate_index": failure.candidate_index,
                    "stage": "clinical_rules",
                    "decision": "rejected",
                    "rule_id": finding.rule_id,
                    "severity": finding.severity.value,
                    "message": finding.message,
                    "candidate": candidate_json(failure.candidate),
                }
            )
    return findings


def candidate_json(candidate: AiCandidateItem) -> dict:
    item = {
        "type": candidate.item_type.value,
        "name": candidate.name,
        "source_quote": candidate.source_quote,
        "section_id": candidate.section_id,
        "section_name": candidate.section_name,
    }
    if candidate.status is not None:
        item["status"] = candidate.status
    if candidate.confidence is not None:
        item["confidence"] = candidate.confidence
    return item


def prompt_hash_input(messages: tuple[PromptMessage, ...]) -> str:
    return json.dumps(
        [{"role": message.role, "content": message.content} for message in messages],
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class AiExtractorRunnerError(ValueError):
    """Raised for AI extractor runner failures."""


if __name__ == "__main__":
    raise SystemExit(main())
