"""Pure clinical document sectioning logic."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable


PARSER_VERSION = "section-parser-v1"


class SectionParseError(ValueError):
    """Raised when a document cannot be parsed into sections."""


@dataclass(frozen=True)
class DocumentSection:
    """A contiguous section body span within a raw clinical document."""

    section_id: str
    name: str
    heading: str
    text: str
    start_char: int
    end_char: int
    page_number: int | None
    ordinal: int


CANONICAL_HEADINGS: dict[str, str] = {
    "allergies": "Allergies",
    "allergies and adverse reactions": "Allergies and Adverse Reactions",
    "assessment": "Assessment",
    "assessment and plan": "Assessment and Plan",
    "chief complaint": "Chief Complaint",
    "discharge instructions": "Discharge Instructions",
    "family history": "Family History",
    "history": "History",
    "history of present illness": "History of Present Illness",
    "hospital course": "Hospital Course",
    "imaging": "Imaging",
    "labs": "Labs",
    "medication history": "Medication History",
    "medications": "Medications",
    "medications on discharge": "Medications on Discharge",
    "orders": "Orders",
    "orders and referrals": "Orders and Referrals",
    "past medical history": "Past Medical History",
    "past surgical history": "Past Surgical History",
    "pending orders": "Pending Orders",
    "physical exam": "Physical Exam",
    "procedures": "Procedures",
    "reason for consult": "Reason for Consult",
    "reason for referral": "Reason for Referral",
    "reason for visit": "Reason for Visit",
    "social history": "Social History",
    "subjective": "Subjective",
    "vitals": "Vitals",
}
KNOWN_HEADINGS: frozenset[str] = frozenset(CANONICAL_HEADINGS)

_HEADING_LINE_RE = re.compile(r"^(?P<heading>[^\n:][^\n:]{0,120}):[ \t]*$", re.MULTILINE)
_NON_NAME_CHARS_RE = re.compile(r"[^a-z0-9]+")


def parse_sections(raw_text: str, *, document_id: str = "document") -> list[DocumentSection]:
    """Parse raw clinical text into ordered document sections.

    Offsets are zero-based character offsets into ``raw_text``. Section ``text`` is
    exactly ``raw_text[start_char:end_char]``.
    """

    if not raw_text or not raw_text.strip():
        raise SectionParseError("Document text is empty or whitespace-only.")

    headings = list(_iter_heading_matches(raw_text))
    if not headings:
        return [
            DocumentSection(
                section_id=f"{document_id}:section:001",
                name="Unsectioned",
                heading="Unsectioned",
                text=raw_text,
                start_char=0,
                end_char=len(raw_text),
                page_number=None,
                ordinal=1,
            )
        ]

    sections: list[DocumentSection] = []
    for index, match in enumerate(headings):
        ordinal = index + 1
        heading = match.group("heading").strip()
        start_char = match.end()
        end_char = headings[index + 1].start() if index + 1 < len(headings) else len(raw_text)
        text = raw_text[start_char:end_char]
        sections.append(
            DocumentSection(
                section_id=f"{document_id}:section:{ordinal:03d}",
                name=normalize_heading(heading),
                heading=heading,
                text=text,
                start_char=start_char,
                end_char=end_char,
                page_number=None,
                ordinal=ordinal,
            )
        )

    return sections


def normalize_heading(heading: str) -> str:
    """Normalize a section heading for stable downstream use."""

    compact = " ".join(heading.strip().split())
    if not compact:
        return "Unknown"

    normalized = _normalize_heading_key(compact)
    canonical = CANONICAL_HEADINGS.get(normalized)
    if canonical:
        return canonical

    return f"Unknown: {compact}"


def _iter_heading_matches(raw_text: str) -> Iterable[re.Match[str]]:
    for match in _HEADING_LINE_RE.finditer(raw_text):
        heading = match.group("heading").strip()
        if _looks_like_heading(heading):
            yield match


def _looks_like_heading(heading: str) -> bool:
    normalized = _normalize_heading_key(heading)
    if normalized in KNOWN_HEADINGS:
        return True

    words = normalized.split()
    if not words or len(words) > 8:
        return False

    slug = _NON_NAME_CHARS_RE.sub("", normalized)
    return bool(slug) and not any(char.isdigit() for char in heading)


def _normalize_heading_key(heading: str) -> str:
    return " ".join(heading.lower().split())
