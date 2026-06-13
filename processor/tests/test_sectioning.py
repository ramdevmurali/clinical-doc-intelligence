from pathlib import Path
import unittest

from processor.src.domain.sectioning import SectionParseError, parse_sections


ROOT = Path(__file__).resolve().parents[2]
GOLDEN_NOTES = ROOT / "golden_set" / "notes"


class SectioningTests(unittest.TestCase):
    def test_golden_notes_parse_to_non_empty_sections_with_exact_spans(self) -> None:
        note_paths = sorted(GOLDEN_NOTES.glob("note_*.txt"))
        self.assertEqual(10, len(note_paths))

        for note_path in note_paths:
            with self.subTest(note=note_path.name):
                raw_text = note_path.read_text(encoding="utf-8")
                sections = parse_sections(raw_text, document_id=note_path.stem)

                self.assertGreater(len(sections), 0)
                previous_end = -1
                for expected_ordinal, section in enumerate(sections, start=1):
                    self.assertEqual(expected_ordinal, section.ordinal)
                    self.assertGreaterEqual(section.start_char, 0)
                    self.assertGreaterEqual(section.end_char, section.start_char)
                    self.assertGreaterEqual(section.start_char, previous_end)
                    self.assertEqual(raw_text[section.start_char : section.end_char], section.text)
                    self.assertIsNone(section.page_number)
                    previous_end = section.end_char

    def test_empty_input_raises(self) -> None:
        with self.assertRaises(SectionParseError):
            parse_sections("")

        with self.assertRaises(SectionParseError):
            parse_sections("\n\t  \n")

    def test_missing_headings_returns_one_unsectioned_section(self) -> None:
        raw_text = "Patient reports mild cough. No fever. Follow up as needed."

        sections = parse_sections(raw_text, document_id="plain_note")

        self.assertEqual(1, len(sections))
        section = sections[0]
        self.assertEqual("plain_note:section:001", section.section_id)
        self.assertEqual("Unsectioned", section.name)
        self.assertEqual("Unsectioned", section.heading)
        self.assertEqual(raw_text, section.text)
        self.assertEqual(0, section.start_char)
        self.assertEqual(len(raw_text), section.end_char)
        self.assertEqual(1, section.ordinal)

    def test_repeated_headings_create_distinct_sections(self) -> None:
        raw_text = "Assessment:\nFirst issue.\n\nAssessment:\nSecond issue.\n"

        sections = parse_sections(raw_text, document_id="repeat_note")

        self.assertEqual(2, len(sections))
        self.assertEqual(["repeat_note:section:001", "repeat_note:section:002"], [s.section_id for s in sections])
        self.assertEqual([1, 2], [s.ordinal for s in sections])
        self.assertEqual("\nFirst issue.\n\n", sections[0].text)
        self.assertEqual("\nSecond issue.\n", sections[1].text)

    def test_unknown_heading_like_lines_are_retained(self) -> None:
        raw_text = "Custom Trial Context:\nSynthetic enrollment note.\n\nAssessment:\nStable.\n"

        sections = parse_sections(raw_text, document_id="unknown_note")

        self.assertEqual(2, len(sections))
        self.assertEqual("Unknown: Custom Trial Context", sections[0].name)
        self.assertEqual("Custom Trial Context", sections[0].heading)
        self.assertEqual("\nSynthetic enrollment note.\n\n", sections[0].text)
        self.assertEqual(raw_text[sections[0].start_char : sections[0].end_char], sections[0].text)


if __name__ == "__main__":
    unittest.main()
