"""Pure source quote and span validation utilities."""

from __future__ import annotations

from dataclasses import dataclass


class SourceSpanError(ValueError):
    """Raised when source grounding cannot be established."""


@dataclass(frozen=True)
class SourceSpan:
    """A source quote and its exact character span in a document."""

    source_quote: str
    start_char: int
    end_char: int


def find_source_span(raw_text: str, source_quote: str) -> SourceSpan:
    """Find the first exact occurrence of ``source_quote`` in ``raw_text``.

    Offsets are zero-based, with ``start_char`` inclusive and ``end_char``
    exclusive. Repeated quotes resolve to the first occurrence deterministically.
    """

    _require_non_empty_raw_text(raw_text)
    _require_non_empty_source_quote(source_quote)

    start_char = raw_text.find(source_quote)
    if start_char == -1:
        raise SourceSpanError("Source quote was not found in document text.")

    end_char = start_char + len(source_quote)
    return SourceSpan(source_quote=source_quote, start_char=start_char, end_char=end_char)


def validate_source_span(
    raw_text: str,
    source_quote: str,
    start_char: int,
    end_char: int,
) -> SourceSpan:
    """Validate that a proposed source span exactly maps to ``source_quote``."""

    _require_non_empty_raw_text(raw_text)
    _require_non_empty_source_quote(source_quote)

    if start_char < 0:
        raise SourceSpanError("Source span start_char cannot be negative.")
    if end_char < 0:
        raise SourceSpanError("Source span end_char cannot be negative.")
    if end_char < start_char:
        raise SourceSpanError("Source span end_char cannot be before start_char.")
    if end_char > len(raw_text):
        raise SourceSpanError("Source span is outside document text bounds.")

    span_text = raw_text[start_char:end_char]
    if span_text != source_quote:
        raise SourceSpanError("Source span text does not match source quote.")

    return SourceSpan(source_quote=source_quote, start_char=start_char, end_char=end_char)


def _require_non_empty_raw_text(raw_text: str) -> None:
    if not raw_text or not raw_text.strip():
        raise SourceSpanError("Document text is empty or whitespace-only.")


def _require_non_empty_source_quote(source_quote: str) -> None:
    if not source_quote or not source_quote.strip():
        raise SourceSpanError("Source quote is empty or whitespace-only.")
