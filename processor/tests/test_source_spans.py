import json
from pathlib import Path
import unittest

from processor.src.domain.source_spans import (
    SourceSpan,
    SourceSpanError,
    find_source_span,
    validate_source_span,
)


ROOT = Path(__file__).resolve().parents[2]
GOLDEN_SET = ROOT / "golden_set"


class SourceSpanTests(unittest.TestCase):
    def test_find_source_span_returns_exact_quote_offsets(self) -> None:
        raw_text = "Past Medical History:\nHypertension and type 2 diabetes.\n"
        source_quote = "Hypertension and type 2 diabetes."

        span = find_source_span(raw_text, source_quote)

        self.assertEqual(SourceSpan(source_quote=source_quote, start_char=22, end_char=55), span)
        self.assertEqual(source_quote, raw_text[span.start_char : span.end_char])

    def test_find_source_span_missing_quote_raises(self) -> None:
        with self.assertRaisesRegex(SourceSpanError, "not found"):
            find_source_span("Patient denies chest pain.", "Patient reports chest pain.")

    def test_find_source_span_empty_raw_text_raises(self) -> None:
        with self.assertRaisesRegex(SourceSpanError, "Document text is empty"):
            find_source_span("", "Hypertension")

        with self.assertRaisesRegex(SourceSpanError, "Document text is empty"):
            find_source_span("\n  \t", "Hypertension")

    def test_find_source_span_empty_quote_raises(self) -> None:
        with self.assertRaisesRegex(SourceSpanError, "Source quote is empty"):
            find_source_span("Hypertension.", "")

        with self.assertRaisesRegex(SourceSpanError, "Source quote is empty"):
            find_source_span("Hypertension.", "\n  \t")

    def test_validate_source_span_accepts_exact_span(self) -> None:
        raw_text = "Patient denies chest pain."
        source_quote = "denies chest pain"
        start_char = raw_text.index(source_quote)
        end_char = start_char + len(source_quote)

        span = validate_source_span(raw_text, source_quote, start_char, end_char)

        self.assertEqual(SourceSpan(source_quote=source_quote, start_char=start_char, end_char=end_char), span)

    def test_validate_source_span_rejects_mismatch(self) -> None:
        raw_text = "Patient denies chest pain."

        with self.assertRaisesRegex(SourceSpanError, "does not match"):
            validate_source_span(raw_text, "reports chest pain", 8, 25)

    def test_validate_source_span_rejects_negative_offsets(self) -> None:
        with self.assertRaisesRegex(SourceSpanError, "start_char cannot be negative"):
            validate_source_span("Hypertension.", "Hypertension", -1, 12)

        with self.assertRaisesRegex(SourceSpanError, "end_char cannot be negative"):
            validate_source_span("Hypertension.", "Hypertension", 0, -1)

    def test_validate_source_span_rejects_end_before_start(self) -> None:
        with self.assertRaisesRegex(SourceSpanError, "before start_char"):
            validate_source_span("Hypertension.", "Hypertension", 8, 3)

    def test_validate_source_span_rejects_out_of_bounds_span(self) -> None:
        with self.assertRaisesRegex(SourceSpanError, "outside document text bounds"):
            validate_source_span("Hypertension.", "Hypertension", 0, 999)

    def test_repeated_quote_returns_first_occurrence(self) -> None:
        raw_text = "Assessment:\nStable.\n\nAssessment:\nStable.\n"
        source_quote = "Stable."

        span = find_source_span(raw_text, source_quote)

        self.assertEqual(raw_text.index(source_quote), span.start_char)
        self.assertEqual(12, span.start_char)
        self.assertEqual(source_quote, raw_text[span.start_char : span.end_char])

    def test_golden_expected_source_quotes_resolve_in_matching_notes(self) -> None:
        expected_paths = sorted((GOLDEN_SET / "expected").glob("note_*.expected.json"))
        self.assertEqual(10, len(expected_paths))

        for expected_path in expected_paths:
            expected = json.loads(expected_path.read_text(encoding="utf-8"))
            document_id = expected["document_id"]
            raw_text = (GOLDEN_SET / "notes" / f"{document_id}.txt").read_text(encoding="utf-8")

            for index, item in enumerate(expected["items"], start=1):
                with self.subTest(expected=expected_path.name, item=index, quote=item["source_quote"]):
                    span = find_source_span(raw_text, item["source_quote"])
                    validated = validate_source_span(
                        raw_text,
                        item["source_quote"],
                        span.start_char,
                        span.end_char,
                    )
                    self.assertEqual(span, validated)


if __name__ == "__main__":
    unittest.main()
