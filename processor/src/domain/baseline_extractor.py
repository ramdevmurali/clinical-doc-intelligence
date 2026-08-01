"""Deterministic non-LLM baseline clinical extractor."""

from __future__ import annotations

import re

from processor.src.domain.extraction_schema import ClinicalItemType, ExtractedClinicalItem
from processor.src.domain.sectioning import DocumentSection, SectionParseError, parse_sections
from processor.src.domain.source_spans import SourceSpanError, validate_source_span


BASELINE_EXTRACTOR_VERSION = "baseline-extractor-v1"


class BaselineExtractionError(ValueError):
    """Raised when deterministic baseline extraction cannot run."""


_SENTENCE_RE = re.compile(r"[^.\n]+(?:\.|$)")
_DOSE_OR_STATUS_RE = re.compile(
    r"\b("
    r"\d+|mg|mcg|g|units?|daily|twice|weekly|nightly|every|as needed|iv|po|"
    r"discontinued|stopped|held|prescribed|started|active|was|is"
    r")\b",
    re.IGNORECASE,
)
_NEGATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("denies", re.compile(r"\bdenies?\s+(?P<name>[^.]+)", re.IGNORECASE)),
    ("no evidence of", re.compile(r"\bno evidence of\s+(?P<name>[^.]+)", re.IGNORECASE)),
    ("negative for", re.compile(r"\bnegative for\s+(?P<name>[^.]+)", re.IGNORECASE)),
    ("no history of", re.compile(r"\bno history of\s+(?P<name>[^.]+)", re.IGNORECASE)),
    ("without", re.compile(r"\bwithout\s+(?P<name>[^.]+)", re.IGNORECASE)),
)
_FAMILY_PATTERN = re.compile(
    r"\b(?:mother|father|sister|brother)\b\s+(?:had|has|died of)\s+(?P<name>[^.]+)",
    re.IGNORECASE,
)
_TRAILING_CONTEXT_RE = re.compile(
    r"\b(?:as a child|at age \d+|today|yesterday|during admission|before discharge)\b.*$",
    re.IGNORECASE,
)
_TRAILING_NEGATION_VERB_RE = re.compile(r"\b(?:was|were|is|are)\s+(?:found|seen|noted)\b.*$", re.IGNORECASE)

_CONDITION_SECTIONS = {
    "Past Medical History",
    "Assessment",
    "Assessment and Plan",
    "Hospital Course",
}
_MEDICATION_SECTIONS = {
    "Medications",
    "Medications on Discharge",
    "Current Medications",
}
_PROCEDURE_SECTIONS = {
    "Past Surgical History",
    "Procedures",
}
_FAMILY_SECTIONS = {"Family History"}
_CONDITION_ACTION_PREFIXES = (
    "continue ",
    "follow up",
    "monitor ",
    "repeat ",
    "start ",
    "increase ",
    "order ",
    "refer ",
    "return ",
    "do not ",
    "keep ",
)
_NON_PROCEDURE_PREFIXES = ("no ", "patient referred", "refer ", "referral ", "ordered ", "order ")


def extract_baseline_items(raw_text: str, document_id: str) -> tuple[ExtractedClinicalItem, ...]:
    """Extract conservative source-grounded clinical candidates from raw note text."""

    if not isinstance(raw_text, str) or not raw_text.strip():
        raise BaselineExtractionError("raw_text is required for baseline extraction.")
    if not isinstance(document_id, str) or not document_id.strip():
        raise BaselineExtractionError("document_id is required for baseline extraction.")

    try:
        sections = parse_sections(raw_text, document_id=document_id)
    except SectionParseError as exc:
        raise BaselineExtractionError(f"could not parse sections: {exc}") from exc

    items: list[ExtractedClinicalItem] = []
    for section in sections:
        for sentence, start_char, end_char in _iter_sentence_spans(section):
            item = _extract_sentence_item(raw_text, section, sentence, start_char, end_char)
            if item is not None:
                items.append(item)

    return tuple(items)


def _extract_sentence_item(
    raw_text: str,
    section: DocumentSection,
    sentence: str,
    start_char: int,
    end_char: int,
) -> ExtractedClinicalItem | None:
    lower_sentence = sentence.lower()

    negative_name = _negative_finding_name(sentence)
    if negative_name:
        return _make_item(
            raw_text,
            section,
            ClinicalItemType.NEGATIVE_FINDING,
            negative_name,
            None,
            0.80,
            sentence,
            start_char,
            end_char,
        )

    family_name = _family_history_name(sentence)
    if section.name in _FAMILY_SECTIONS or family_name:
        if family_name:
            return _make_item(
                raw_text,
                section,
                ClinicalItemType.FAMILY_HISTORY,
                family_name,
                None,
                0.80,
                sentence,
                start_char,
                end_char,
            )
        return None

    if section.name in _MEDICATION_SECTIONS:
        return _make_item(
            raw_text,
            section,
            ClinicalItemType.MEDICATION,
            _medication_name(sentence),
            _medication_status(lower_sentence),
            0.80,
            sentence,
            start_char,
            end_char,
        )

    if section.name in _PROCEDURE_SECTIONS:
        if lower_sentence.startswith(_NON_PROCEDURE_PREFIXES):
            return None
        return _make_item(
            raw_text,
            section,
            ClinicalItemType.PROCEDURE,
            _procedure_name(sentence),
            _procedure_status(lower_sentence),
            0.80,
            sentence,
            start_char,
            end_char,
        )

    if section.name in _CONDITION_SECTIONS and _looks_like_condition_sentence(lower_sentence):
        return _make_item(
            raw_text,
            section,
            ClinicalItemType.CONDITION,
            _condition_name(sentence),
            _condition_status(lower_sentence),
            0.60,
            sentence,
            start_char,
            end_char,
        )

    return None


def _iter_sentence_spans(section: DocumentSection) -> tuple[tuple[str, int, int], ...]:
    spans = []
    for match in _SENTENCE_RE.finditer(section.text):
        raw_sentence = match.group(0)
        if not raw_sentence.strip():
            continue
        leading_trim = len(raw_sentence) - len(raw_sentence.lstrip())
        trailing_trim = len(raw_sentence.rstrip())
        sentence = raw_sentence.strip()
        start_char = section.start_char + match.start() + leading_trim
        end_char = section.start_char + match.start() + trailing_trim
        spans.append((sentence, start_char, end_char))
    return tuple(spans)


def _make_item(
    raw_text: str,
    section: DocumentSection,
    item_type: ClinicalItemType,
    name: str,
    status: str | None,
    confidence: float,
    source_quote: str,
    start_char: int,
    end_char: int,
) -> ExtractedClinicalItem:
    try:
        validate_source_span(raw_text, source_quote, start_char, end_char)
    except SourceSpanError as exc:
        raise BaselineExtractionError(f"generated source span failed validation: {exc}") from exc

    return ExtractedClinicalItem(
        item_type=item_type,
        name=_clean_name(name),
        status=status,
        confidence=confidence,
        source_quote=source_quote,
        source_start_char=start_char,
        source_end_char=end_char,
        section_id=section.section_id,
        section_name=section.name,
    )


def _negative_finding_name(sentence: str) -> str | None:
    for _, pattern in _NEGATION_PATTERNS:
        match = pattern.search(sentence)
        if match:
            return _first_name_fragment(match.group("name"))
    return None


def _family_history_name(sentence: str) -> str | None:
    match = _FAMILY_PATTERN.search(sentence)
    if not match:
        return None
    return _first_name_fragment(match.group("name"))


def _medication_status(lower_sentence: str) -> str:
    if "discontinued" in lower_sentence:
        return "discontinued"
    if "was stopped" in lower_sentence or " stopped" in lower_sentence:
        return "stopped"
    if "held" in lower_sentence:
        return "held"
    if "prescribed" in lower_sentence:
        return "prescribed"
    if "start " in lower_sentence or lower_sentence.startswith("start "):
        return "started"
    return "active"


def _procedure_status(lower_sentence: str) -> str:
    if "not performed" in lower_sentence:
        return "not_performed"
    if "planned" in lower_sentence:
        return "planned"
    return "performed"


def _condition_status(lower_sentence: str) -> str:
    if " in remission" in lower_sentence:
        return "in_remission"
    if "resolved" in lower_sentence:
        return "resolved"
    if "former " in lower_sentence or "history of " in lower_sentence:
        return "historical"
    return "active"


def _medication_name(sentence: str) -> str:
    text = sentence.rstrip(".")
    if text.lower().startswith("start "):
        text = text[6:]
    match = _DOSE_OR_STATUS_RE.search(text)
    if match:
        text = text[: match.start()]
    return _clean_name(text)


def _procedure_name(sentence: str) -> str:
    text = sentence.rstrip(".")
    lower_text = text.lower()
    for marker in (" was not performed", " not performed", " performed", " in ", " planned"):
        index = lower_text.find(marker)
        if index > 0:
            text = text[:index]
            break
    return _clean_name(text)


def _condition_name(sentence: str) -> str:
    text = sentence.rstrip(".")
    for marker in (" is active", " uncontrolled", " resolved", " in remission"):
        index = text.lower().find(marker)
        if index > 0:
            text = text[:index]
            break
    return _clean_name(text)


def _first_name_fragment(text: str) -> str:
    text = text.replace(" and denies ", ", ")
    text = text.replace(" and ", ", ")
    text = text.replace(" or ", ", ")
    text = text.split(",")[0]
    text = _TRAILING_NEGATION_VERB_RE.sub("", text)
    text = _TRAILING_CONTEXT_RE.sub("", text)
    return _clean_name(text)


def _looks_like_condition_sentence(lower_sentence: str) -> bool:
    if lower_sentence.startswith(_CONDITION_ACTION_PREFIXES):
        return False
    if any(phrase in lower_sentence for phrase, _ in _NEGATION_PATTERNS):
        return False
    if any(term in lower_sentence for term in ("mother", "father", "sister", "brother", "family history")):
        return False
    return lower_sentence.endswith(".")


def _clean_name(value: str) -> str:
    value = value.strip().strip(".:;")
    value = re.sub(r"\s+", " ", value)
    return value.lower()
