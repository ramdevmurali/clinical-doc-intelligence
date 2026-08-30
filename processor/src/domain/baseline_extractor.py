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
_LAB_SECTIONS = {"Labs"}
_FAMILY_SECTIONS = {"Family History"}
_ORDER_SECTIONS = {
    "Assessment",
    "Assessment and Plan",
    "Discharge Instructions",
    "Orders",
    "Orders and Referrals",
    "Pending Orders",
}
_LAB_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("white blood cell count", re.compile(r"\bWhite blood cell count\s+.+?\.(?=\s|$)")),
    ("creatinine", re.compile(r"\bCreatinine\s+.+?\.(?=\s|$)")),
    ("potassium", re.compile(r"\bPotassium\s+.+?\.(?=\s|$)")),
    ("bnp", re.compile(r"\bBNP\s+.+?\.(?=\s|$)")),
    ("hemoglobin", re.compile(r"\bHemoglobin(?!\s+A1c)\s+.+?\.(?=\s|$)")),
    ("sodium", re.compile(r"\bSodium\s+.+?\.(?=\s|$)")),
    ("estimated gfr", re.compile(r"\bEstimated GFR\s+.+?\.(?=\s|$)")),
    ("hemoglobin a1c", re.compile(r"\bHemoglobin A1c\s+.+?\.(?=\s|$)")),
    ("ldl cholesterol", re.compile(r"\bLDL cholesterol\s+.+?\.(?=\s|$)")),
)
_ORDER_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "ct abdomen and pelvis",
        "ordered",
        re.compile(r"\bCT abdomen and pelvis ordered\.(?=\s|$)", re.IGNORECASE),
    ),
    ("iv fluids", "ordered", re.compile(r"\bIV fluids ordered\.(?=\s|$)", re.IGNORECASE)),
    (
        "primary care follow-up",
        "planned",
        re.compile(r"\bFollow up with primary care\b[^.]*\.(?=\s|$)", re.IGNORECASE),
    ),
    ("cbc", "planned", re.compile(r"\bRecheck CBC\b[^.]*\.(?=\s|$)", re.IGNORECASE)),
    (
        "outpatient colonoscopy",
        "referred",
        re.compile(r"\bPatient referred for outpatient colonoscopy\.(?=\s|$)", re.IGNORECASE),
    ),
    (
        "iron studies",
        "ordered",
        re.compile(r"\bIron studies ordered\.(?=\s|$)", re.IGNORECASE),
    ),
    (
        "basic metabolic panel",
        "planned",
        re.compile(r"\bRepeat basic metabolic panel\b[^.]*\.(?=\s|$)", re.IGNORECASE),
    ),
    (
        "repeat chest x-ray",
        "planned",
        re.compile(r"\bRepeat chest x-ray\b[^.]*\.(?=\s|$)", re.IGNORECASE),
    ),
    (
        "urine albumin",
        "ordered",
        re.compile(r"\bOrder urine albumin and lipid panel\.(?=\s|$)", re.IGNORECASE),
    ),
    (
        "lipid panel",
        "ordered",
        re.compile(r"\bOrder urine albumin and lipid panel\.(?=\s|$)", re.IGNORECASE),
    ),
    (
        "diabetic eye exam",
        "referred",
        re.compile(r"\bRefer for diabetic eye exam\.(?=\s|$)", re.IGNORECASE),
    ),
    (
        "surgery clinic follow-up",
        "planned",
        re.compile(r"\bFollow up with surgery clinic\b[^.]*\.(?=\s|$)", re.IGNORECASE),
    ),
    (
        "pathology report",
        "pending",
        re.compile(r"\bPathology report pending\.(?=\s|$)", re.IGNORECASE),
    ),
)
_CONDITION_ACTION_PREFIXES = (
    "await ",
    "avoid ",
    "continue ",
    "follow up",
    "monitor ",
    "repeat ",
    "recheck ",
    "remove ",
    "replete ",
    "start ",
    "increase ",
    "order ",
    "refer ",
    "return ",
    "do not ",
    "keep ",
)
_CONDITION_EXCLUSION_PHRASES = (
    "allergy",
    "also possible",
    "low suspicion",
    "medication reconciliation completed",
    "needed to evaluate",
    "not fully excluded",
    "possible ",
    "suggests possible",
    "tolerated the procedure well",
    "versus ",
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
        items.extend(_extract_lab_items(raw_text, section))
        items.extend(_extract_order_items(raw_text, section))
        for sentence, start_char, end_char in _iter_sentence_spans(section):
            items.extend(
                _extract_sentence_items(raw_text, section, sentence, start_char, end_char)
            )

    return tuple(items)


def _extract_lab_items(
    raw_text: str,
    section: DocumentSection,
) -> tuple[ExtractedClinicalItem, ...]:
    if section.name not in _LAB_SECTIONS:
        return ()

    lab_spans: list[tuple[int, int, str, str]] = []
    for lab_name, pattern in _LAB_PATTERNS:
        for match in pattern.finditer(section.text):
            start_char = section.start_char + match.start()
            end_char = section.start_char + match.end()
            lab_spans.append((start_char, end_char, lab_name, match.group(0)))

    return tuple(
        _make_item(
            raw_text,
            section,
            ClinicalItemType.LAB_RESULT,
            lab_name,
            None,
            0.85,
            source_quote,
            start_char,
            end_char,
        )
        for start_char, end_char, lab_name, source_quote in sorted(lab_spans)
    )


def _extract_order_items(
    raw_text: str,
    section: DocumentSection,
) -> tuple[ExtractedClinicalItem, ...]:
    if section.name not in _ORDER_SECTIONS:
        return ()

    order_spans: list[tuple[int, int, int, str, str, str]] = []
    for pattern_index, (order_name, status, pattern) in enumerate(_ORDER_PATTERNS):
        for match in pattern.finditer(section.text):
            start_char = section.start_char + match.start()
            end_char = section.start_char + match.end()
            order_spans.append(
                (start_char, end_char, pattern_index, order_name, status, match.group(0))
            )

    return tuple(
        _make_item(
            raw_text,
            section,
            ClinicalItemType.ORDER,
            order_name,
            status,
            0.85,
            source_quote,
            start_char,
            end_char,
        )
        for start_char, end_char, _, order_name, status, source_quote in sorted(order_spans)
    )


def _extract_sentence_items(
    raw_text: str,
    section: DocumentSection,
    sentence: str,
    start_char: int,
    end_char: int,
) -> tuple[ExtractedClinicalItem, ...]:
    lower_sentence = sentence.lower()

    negative_names = _negative_finding_names(sentence)
    if negative_names:
        return tuple(
            _make_item(
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
            for negative_name in negative_names
        )

    family_name = _family_history_name(sentence)
    if section.name in _FAMILY_SECTIONS or family_name:
        if family_name:
            return (
                _make_item(
                    raw_text,
                    section,
                    ClinicalItemType.FAMILY_HISTORY,
                    family_name,
                    None,
                    0.80,
                    sentence,
                    start_char,
                    end_char,
                ),
            )
        return ()

    if section.name in _MEDICATION_SECTIONS:
        return (
            _make_item(
                raw_text,
                section,
                ClinicalItemType.MEDICATION,
                _medication_name(sentence),
                _medication_status(lower_sentence),
                0.80,
                sentence,
                start_char,
                end_char,
            ),
        )

    if section.name in _PROCEDURE_SECTIONS:
        if lower_sentence.startswith(_NON_PROCEDURE_PREFIXES):
            return ()
        return (
            _make_item(
                raw_text,
                section,
                ClinicalItemType.PROCEDURE,
                _procedure_name(sentence),
                _procedure_status(lower_sentence),
                0.80,
                sentence,
                start_char,
                end_char,
            ),
        )

    if section.name in _CONDITION_SECTIONS and _looks_like_condition_sentence(lower_sentence):
        return (
            _make_item(
                raw_text,
                section,
                ClinicalItemType.CONDITION,
                _condition_name(sentence),
                _condition_status(lower_sentence),
                0.60,
                sentence,
                start_char,
                end_char,
            ),
        )

    return ()


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


def _negative_finding_names(sentence: str) -> tuple[str, ...]:
    names: list[str] = []
    for _, pattern in _NEGATION_PATTERNS:
        match = pattern.search(sentence)
        if match:
            names.extend(_name_fragments(match.group("name")))
            break

    if not names:
        names.extend(_simple_no_negative_names(sentence))

    return tuple(name for name in names if name)


def _simple_no_negative_names(sentence: str) -> tuple[str, ...]:
    if re.search(r"\bno known\b", sentence, re.IGNORECASE):
        return ()
    if re.search(r"\bprocedures?\s+were\s+completed\b", sentence, re.IGNORECASE):
        return ()

    match = re.search(r"^\s*no\s+(?P<name>[^.]+)", sentence, re.IGNORECASE)
    if match:
        return (_first_name_fragment(match.group("name")),)

    match = re.search(r"\bshows\s+no\s+(?P<name>[^.]+)", sentence, re.IGNORECASE)
    if match:
        return (_first_name_fragment(match.group("name")),)

    return ()


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
    fragments = _name_fragments(text)
    text = fragments[0] if fragments else text
    text = _TRAILING_NEGATION_VERB_RE.sub("", text)
    text = _TRAILING_CONTEXT_RE.sub("", text)
    return _clean_name(text)


def _name_fragments(text: str) -> tuple[str, ...]:
    text = re.sub(r"\band\s+denies?\b", ",", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdenies?\b", ",", text, flags=re.IGNORECASE)
    text = re.sub(r"\band\b", ",", text, flags=re.IGNORECASE)
    text = re.sub(r"\bor\b", ",", text, flags=re.IGNORECASE)
    fragments = []
    for fragment in text.split(","):
        fragment = _TRAILING_NEGATION_VERB_RE.sub("", fragment)
        fragment = _TRAILING_CONTEXT_RE.sub("", fragment)
        fragment = _clean_name(fragment)
        if fragment:
            fragments.append(fragment)
    return tuple(fragments)


def _looks_like_condition_sentence(lower_sentence: str) -> bool:
    if lower_sentence.startswith(_CONDITION_ACTION_PREFIXES):
        return False
    if any(phrase in lower_sentence for phrase in _CONDITION_EXCLUSION_PHRASES):
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
