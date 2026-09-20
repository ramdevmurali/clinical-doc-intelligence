"""Prompt construction for the source-grounded AI extraction harness."""

from __future__ import annotations

from dataclasses import dataclass

from processor.src.domain.extraction_schema import ClinicalItemType
from processor.src.domain.sectioning import DocumentSection


AI_EXTRACTION_PROMPT_VERSION = "ai-extraction-prompt-v1"

SUPPORTED_STATUSES: tuple[str, ...] = (
    "active",
    "historical",
    "resolved",
    "in_remission",
    "performed",
    "not_performed",
    "planned",
    "ordered",
    "referred",
    "pending",
    "present",
    "administered",
    "started",
    "stopped",
    "discontinued",
    "held",
    "prescribed",
    "removed_incorrect",
    "none_known",
    "possible",
    "rule_out",
    "unlikely_not_excluded",
    "planned_change",
)


@dataclass(frozen=True)
class PromptMessage:
    """Provider-neutral prompt message."""

    role: str
    content: str

    def __post_init__(self) -> None:
        if self.role not in {"system", "user"}:
            raise AiExtractionPromptError(f"unsupported prompt role: {self.role}")
        if not self.content or not self.content.strip():
            raise AiExtractionPromptError("prompt message content is required")


class AiExtractionPromptError(ValueError):
    """Raised when an AI extraction prompt cannot be constructed."""


def build_ai_extraction_messages(
    *,
    document_id: str,
    raw_text: str,
    sections: tuple[DocumentSection, ...] | list[DocumentSection],
) -> tuple[PromptMessage, ...]:
    """Build schema-first extraction messages for one clinical note."""

    if not document_id or not document_id.strip():
        raise AiExtractionPromptError("document_id is required")
    if not raw_text or not raw_text.strip():
        raise AiExtractionPromptError("raw_text is required")
    if not sections:
        raise AiExtractionPromptError("at least one parsed section is required")

    return (
        PromptMessage(role="system", content=_system_prompt()),
        PromptMessage(
            role="user",
            content="\n\n".join(
                (
                    f"Document ID: {document_id}",
                    _schema_contract(),
                    _section_inventory(tuple(sections)),
                    "Return only the strict JSON object. Do not include markdown fences.",
                )
            ),
        ),
    )


def _system_prompt() -> str:
    item_types = ", ".join(item_type.value for item_type in ClinicalItemType)
    statuses = ", ".join(SUPPORTED_STATUSES)
    return "\n".join(
        (
            "You extract source-grounded clinical facts from synthetic/demo clinical notes.",
            "This is not medical advice, diagnosis, treatment, or a medical device workflow.",
            "Extract only facts explicitly stated in the supplied note.",
            "Do not infer missing diagnoses, treatments, medication changes, or unstated facts.",
            "Every item must include one exact verbatim source_quote copied from a supplied section.",
            "Do not emit source_start_char or source_end_char; local code computes offsets.",
            "Do not include validation status, review status, diagnosis advice, or treatment recommendations.",
            f"Supported item types: {item_types}.",
            f"Supported statuses: {statuses}.",
            "Use negative_finding for negated symptoms, family_history for family mentions, "
            "order for planned/referred procedures, and uncertain_mention for possible/rule-out findings.",
        )
    )


def _schema_contract() -> str:
    return """Output JSON schema:
{
  "schema_version": "ai-extraction-response-v1",
  "document_id": "<document id>",
  "items": [
    {
      "type": "condition | procedure | medication | allergy | observation | lab_result | order | care_need | negative_finding | uncertain_mention | family_history",
      "name": "<normalized clinical fact name>",
      "status": "<optional supported status>",
      "confidence": 0.0,
      "source_quote": "<exact quote copied from the section text>",
      "section_id": "<section id from the inventory>",
      "section_name": "<section name from the inventory>"
    }
  ]
}"""


def _section_inventory(sections: tuple[DocumentSection, ...]) -> str:
    rendered_sections = []
    for section in sections:
        rendered_sections.append(
            "\n".join(
                (
                    f"Section ID: {section.section_id}",
                    f"Section Name: {section.name}",
                    "Section Text:",
                    section.text,
                )
            )
        )
    return "Sections:\n\n" + "\n\n---\n\n".join(rendered_sections)
