from pathlib import Path
import unittest

from processor.src.domain.sectioning import (
    PARSER_VERSION,
    SectionParseError,
    normalize_heading,
    parse_sections,
)


ROOT = Path(__file__).resolve().parents[2]
GOLDEN_NOTES = ROOT / "golden_set" / "notes"


class SectioningTests(unittest.TestCase):
    def test_parser_version_is_stable_and_non_empty(self) -> None:
        self.assertEqual("section-parser-v1", PARSER_VERSION)

    def test_known_headings_normalize_to_canonical_names(self) -> None:
        cases = {
            "history of present illness": "History of Present Illness",
            "Past Medical History": "Past Medical History",
            "assessment and plan": "Assessment and Plan",
            "MEDICATIONS ON DISCHARGE": "Medications on Discharge",
            "  Allergies and Adverse Reactions  ": "Allergies and Adverse Reactions",
        }

        for heading, expected in cases.items():
            with self.subTest(heading=heading):
                self.assertEqual(expected, normalize_heading(heading))

    def test_unknown_headings_preserve_compact_original_text(self) -> None:
        self.assertEqual("Unknown: Custom Trial Context", normalize_heading(" Custom  Trial Context "))

    def test_empty_string_raises_clear_parse_error(self) -> None:
        with self.assertRaisesRegex(SectionParseError, "empty or whitespace-only"):
            parse_sections("")

    def test_whitespace_only_input_raises_clear_parse_error(self) -> None:
        with self.assertRaisesRegex(SectionParseError, "empty or whitespace-only"):
            parse_sections("\n\t  \n")

    def test_missing_headings_returns_one_unsectioned_section_covering_full_text(self) -> None:
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
        self.assertEqual(raw_text[section.start_char : section.end_char], section.text)
        self.assertEqual(1, section.ordinal)
        self.assertIsNone(section.page_number)

    def test_repeated_assessment_headings_create_distinct_ordered_sections(self) -> None:
        raw_text = "Assessment:\nFirst issue.\n\nAssessment:\nSecond issue.\n"

        sections = parse_sections(raw_text, document_id="repeat_note")

        self.assertEqual(2, len(sections))
        self.assertEqual(["repeat_note:section:001", "repeat_note:section:002"], [s.section_id for s in sections])
        self.assertEqual(2, len({s.section_id for s in sections}))
        self.assertEqual([1, 2], [s.ordinal for s in sections])
        self.assertEqual(["Assessment", "Assessment"], [s.name for s in sections])
        self.assertEqual("\nFirst issue.\n\n", sections[0].text)
        self.assertEqual("\nSecond issue.\n", sections[1].text)
        self.assertEqual(raw_text[sections[0].start_char : sections[0].end_char], sections[0].text)
        self.assertEqual(raw_text[sections[1].start_char : sections[1].end_char], sections[1].text)
        self.assertLessEqual(sections[0].end_char, sections[1].start_char)
        self.assert_body_text_is_preserved(raw_text, sections)

    def test_repeated_medications_headings_do_not_drop_text_between_sections(self) -> None:
        raw_text = (
            "Medications:\n"
            "Aspirin 81 mg daily.\n\n"
            "Medications:\n"
            "Metformin 500 mg twice daily.\n"
        )

        sections = parse_sections(raw_text, document_id="repeat_meds")

        self.assertEqual(2, len(sections))
        self.assertEqual(["Medications", "Medications"], [s.name for s in sections])
        self.assertEqual("\nAspirin 81 mg daily.\n\n", sections[0].text)
        self.assertEqual("\nMetformin 500 mg twice daily.\n", sections[1].text)
        self.assert_body_text_is_preserved(raw_text, sections)

    def test_unknown_heading_like_lines_are_retained_with_exact_offsets(self) -> None:
        raw_text = "Custom Trial Context:\nSynthetic enrollment note.\n\nAssessment:\nStable.\n"

        sections = parse_sections(raw_text, document_id="unknown_note")

        self.assertEqual(2, len(sections))
        unknown = sections[0]
        self.assertEqual("Unknown: Custom Trial Context", unknown.name)
        self.assertEqual("Custom Trial Context", unknown.heading)
        self.assertTrue(unknown.name.startswith("Unknown:"))
        self.assertEqual("\nSynthetic enrollment note.\n\n", unknown.text)
        self.assertEqual(raw_text[unknown.start_char : unknown.end_char], unknown.text)
        self.assertLessEqual(unknown.end_char, sections[1].start_char)
        self.assert_body_text_is_preserved(raw_text, sections)

    def test_golden_notes_parse_to_non_empty_ordered_unique_sections(self) -> None:
        note_paths = sorted(GOLDEN_NOTES.glob("note_*.txt"))
        self.assertEqual(10, len(note_paths))

        for note_path in note_paths:
            with self.subTest(note=note_path.name):
                raw_text = note_path.read_text(encoding="utf-8")
                sections = parse_sections(raw_text, document_id=note_path.stem)

                self.assertGreater(len(sections), 0)
                self.assertEqual(len(sections), len({section.section_id for section in sections}))
                self.assertEqual(list(range(1, len(sections) + 1)), [section.ordinal for section in sections])
                self.assertTrue(all(section.section_id.startswith(f"{note_path.stem}:section:") for section in sections))

    def test_golden_note_section_spans_reconstruct_exact_source_text(self) -> None:
        note_paths = sorted(GOLDEN_NOTES.glob("note_*.txt"))
        self.assertEqual(10, len(note_paths))

        for note_path in note_paths:
            with self.subTest(note=note_path.name):
                raw_text = note_path.read_text(encoding="utf-8")
                sections = parse_sections(raw_text, document_id=note_path.stem)
                previous_end = -1

                for section in sections:
                    self.assertGreaterEqual(section.start_char, 0)
                    self.assertGreaterEqual(section.end_char, section.start_char)
                    self.assertGreaterEqual(section.start_char, previous_end)
                    self.assertEqual(raw_text[section.start_char : section.end_char], section.text)
                    self.assertIsNone(section.page_number)
                    previous_end = section.end_char

    def assert_body_text_is_preserved(self, raw_text, sections) -> None:
        reconstructed_body = "".join(section.text for section in sections)
        raw_without_heading_labels = raw_text

        for section in reversed(sections):
            heading_label = f"{section.heading}:"
            heading_start = raw_without_heading_labels.rfind(heading_label, 0, section.start_char)
            self.assertNotEqual(-1, heading_start)
            raw_without_heading_labels = (
                raw_without_heading_labels[:heading_start]
                + raw_without_heading_labels[section.start_char :]
            )

        self.assertEqual(raw_without_heading_labels, reconstructed_body)


if __name__ == "__main__":
    unittest.main()
