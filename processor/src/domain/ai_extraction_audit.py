"""Audit JSON construction for AI extraction harness runs."""

from __future__ import annotations

import hashlib
import json

from processor.src.domain.ai_extraction_grounding import (
    AiGroundingFailure,
    AiGroundingResult,
    GroundedAiItem,
)
from processor.src.domain.ai_extraction_prompt import PromptMessage
from processor.src.domain.ai_extraction_response import AiCandidateItem
from processor.src.domain.prediction_format import prediction_item_from_extracted_item


def extractor_metadata(
    *,
    provider_name: str,
    model: str,
    extractor_name: str,
    extractor_version: str,
    prompt_version: str,
) -> dict:
    """Build AI extractor metadata shared by predictions and audit sidecars."""

    return {
        "name": extractor_name,
        "version": extractor_version,
        "provider": provider_name,
        "model": model,
        "prompt_version": prompt_version,
    }


def audit_json_for_run(
    *,
    document_id: str,
    extractor: dict,
    messages: tuple[PromptMessage, ...],
    raw_response_content: str,
    latency_ms: int,
    input_tokens: int | None,
    output_tokens: int | None,
    request_id: str | None,
    candidates: tuple[AiCandidateItem, ...],
    grounding_result: AiGroundingResult,
) -> dict:
    """Build the deterministic audit sidecar for one AI extraction run."""

    return {
        "document_id": document_id,
        "extractor": extractor,
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
        "raw_response_sha256": sha256_text(raw_response_content),
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "request_id": request_id,
    }


def audit_json_for_schema_failure(
    *,
    document_id: str,
    extractor: dict,
    messages: tuple[PromptMessage, ...],
    raw_response_content: str,
    latency_ms: int,
    input_tokens: int | None,
    output_tokens: int | None,
    request_id: str | None,
    reason: str,
) -> dict:
    """Build an audit sidecar for an AI response that failed schema parsing."""

    return {
        "document_id": document_id,
        "extractor": extractor,
        "counts": {
            "candidate_count": 0,
            "accepted_count": 0,
            "needs_review_count": 0,
            "rejected_by_schema_count": 1,
            "rejected_by_grounding_count": 0,
            "rejected_by_rules_count": 0,
        },
        "failures": [
            {
                "candidate_index": None,
                "stage": "schema_parse",
                "reason": reason,
            }
        ],
        "validation_findings": [],
        "prompt_sha256": sha256_text(prompt_hash_input(messages)),
        "raw_response_sha256": sha256_text(raw_response_content),
        "latency_ms": latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "request_id": request_id,
    }


def failure_json_for_grounding_failure(failure: AiGroundingFailure) -> dict:
    """Format a rejected AI candidate for the audit sidecar."""

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
    """Format deterministic clinical-rule findings for audit output."""

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
    """Convert a raw AI candidate into audit JSON."""

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
    """Canonicalize prompt messages before hashing."""

    return json.dumps(
        [{"role": message.role, "content": message.content} for message in messages],
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_text(value: str) -> str:
    """Return a hex SHA-256 digest for text audit fingerprints."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()
