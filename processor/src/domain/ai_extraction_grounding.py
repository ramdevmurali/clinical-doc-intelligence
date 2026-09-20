"""Ground AI candidate items into deterministic extracted clinical items."""

from __future__ import annotations

from dataclasses import dataclass

from processor.src.domain.ai_extraction_response import AiCandidateItem
from processor.src.domain.clinical_rules import validate_clinical_item
from processor.src.domain.extraction_schema import ExtractedClinicalItem, ExtractionSchemaError
from processor.src.domain.sectioning import DocumentSection
from processor.src.domain.source_spans import SourceSpanError, validate_source_span
from processor.src.domain.validation import ValidationDecision, ValidationStatus


@dataclass(frozen=True)
class GroundedAiItem:
    """A grounded candidate with its deterministic validation decision."""

    item: ExtractedClinicalItem
    validation: ValidationDecision
    candidate_index: int


@dataclass(frozen=True)
class AiGroundingFailure:
    """A rejected AI candidate and the local reason it failed."""

    candidate_index: int
    stage: str
    reason: str


@dataclass(frozen=True)
class AiGroundingResult:
    """Buckets produced by local grounding and clinical validation."""

    accepted: tuple[GroundedAiItem, ...]
    needs_review: tuple[GroundedAiItem, ...]
    rejected_by_grounding: tuple[AiGroundingFailure, ...]
    rejected_by_rules: tuple[AiGroundingFailure, ...]

    @property
    def prediction_items(self) -> tuple[ExtractedClinicalItem, ...]:
        """Items that should be written to prediction JSON for evaluation."""

        return tuple(grounded.item for grounded in self.accepted + self.needs_review)


class AiExtractionGroundingError(ValueError):
    """Raised when AI candidate grounding input is invalid."""


def ground_ai_candidates(
    *,
    raw_text: str,
    sections: tuple[DocumentSection, ...] | list[DocumentSection],
    candidates: tuple[AiCandidateItem, ...] | list[AiCandidateItem],
) -> AiGroundingResult:
    """Resolve candidate source quotes against parsed sections and rules."""

    if not raw_text or not raw_text.strip():
        raise AiExtractionGroundingError("raw_text is required")
    section_lookup = {section.section_id: section for section in sections}
    if not section_lookup:
        raise AiExtractionGroundingError("at least one parsed section is required")

    accepted: list[GroundedAiItem] = []
    needs_review: list[GroundedAiItem] = []
    rejected_by_grounding: list[AiGroundingFailure] = []
    rejected_by_rules: list[AiGroundingFailure] = []
    seen_prediction_keys: set[tuple[str, str, str | None, int, int]] = set()

    for index, candidate in enumerate(candidates):
        try:
            item = _ground_candidate(raw_text, section_lookup, candidate)
        except (AiExtractionGroundingError, ExtractionSchemaError, SourceSpanError) as exc:
            rejected_by_grounding.append(
                AiGroundingFailure(candidate_index=index, stage="grounding", reason=str(exc))
            )
            continue

        prediction_key = (
            item.item_type.value,
            item.name,
            item.status,
            item.source_start_char,
            item.source_end_char,
        )
        if prediction_key in seen_prediction_keys:
            continue
        seen_prediction_keys.add(prediction_key)

        decision = validate_clinical_item(item)
        grounded = GroundedAiItem(item=item, validation=decision, candidate_index=index)
        if decision.status == ValidationStatus.ACCEPTED:
            accepted.append(grounded)
        elif decision.status == ValidationStatus.NEEDS_REVIEW:
            needs_review.append(grounded)
        elif decision.status == ValidationStatus.REJECTED:
            rejected_by_rules.append(
                AiGroundingFailure(
                    candidate_index=index,
                    stage="clinical_rules",
                    reason="; ".join(finding.message for finding in decision.findings),
                )
            )
        else:
            needs_review.append(grounded)

    return AiGroundingResult(
        accepted=tuple(accepted),
        needs_review=tuple(needs_review),
        rejected_by_grounding=tuple(rejected_by_grounding),
        rejected_by_rules=tuple(rejected_by_rules),
    )


def _ground_candidate(
    raw_text: str,
    section_lookup: dict[str, DocumentSection],
    candidate: AiCandidateItem,
) -> ExtractedClinicalItem:
    section = section_lookup.get(candidate.section_id)
    if section is None:
        raise AiExtractionGroundingError(f"unknown section_id: {candidate.section_id}")
    if candidate.section_name != section.name:
        raise AiExtractionGroundingError(
            f"section_name mismatch for {candidate.section_id}: {candidate.section_name} != {section.name}"
        )

    first_local_start = section.text.find(candidate.source_quote)
    if first_local_start == -1:
        raise AiExtractionGroundingError("source_quote was not found in declared section")
    second_local_start = section.text.find(candidate.source_quote, first_local_start + 1)
    if second_local_start != -1:
        raise AiExtractionGroundingError("source_quote is ambiguous within declared section")

    start_char = section.start_char + first_local_start
    end_char = start_char + len(candidate.source_quote)
    validate_source_span(raw_text, candidate.source_quote, start_char, end_char)

    return ExtractedClinicalItem(
        item_type=candidate.item_type,
        name=candidate.name,
        status=candidate.status,
        confidence=candidate.confidence,
        source_quote=candidate.source_quote,
        source_start_char=start_char,
        source_end_char=end_char,
        section_id=section.section_id,
        section_name=section.name,
    )
