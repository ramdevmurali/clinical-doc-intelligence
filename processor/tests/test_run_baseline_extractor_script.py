import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import run_baseline_extractor


ROOT = Path(__file__).resolve().parents[2]
GOLDEN_NOTES = ROOT / "golden_set" / "notes"


class RunBaselineExtractorScriptTests(unittest.TestCase):
    def test_generates_prediction_json_for_one_temp_note(self) -> None:
        stdout, stderr, exit_code, root = self.run_temp_fixture()

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        self.assertIn("document_id: note_test", stdout)
        self.assertIn("item_count: 1", stdout)
        self.assertIn("documents_processed: 1", stdout)
        self.assertIn("total_items: 1", stdout)

        prediction = self.read_prediction(root, "note_test")
        self.assertEqual(1, len(prediction["items"]))

    def test_output_top_level_fields_match_prediction_format(self) -> None:
        _, _, exit_code, root = self.run_temp_fixture()

        self.assertEqual(0, exit_code)
        prediction = self.read_prediction(root, "note_test")
        self.assertEqual("prediction-format-v1", prediction["schema_version"])
        self.assertEqual("note_test", prediction["document_id"])
        self.assertEqual("deterministic-baseline", prediction["extractor"]["name"])
        self.assertEqual("baseline-extractor-v1", prediction["extractor"]["version"])

    def test_output_item_fields_match_extracted_item_data(self) -> None:
        _, _, exit_code, root = self.run_temp_fixture()

        self.assertEqual(0, exit_code)
        item = self.read_prediction(root, "note_test")["items"][0]
        self.assertEqual("condition", item["type"])
        self.assertEqual("hypertension", item["name"])
        self.assertEqual("active", item["status"])
        self.assertEqual(0.6, item["confidence"])
        self.assertEqual("Hypertension.", item["source_quote"])
        self.assertEqual(22, item["source_start_char"])
        self.assertEqual(35, item["source_end_char"])
        self.assertEqual("note_test:section:001", item["section_id"])
        self.assertEqual("Past Medical History", item["section_name"])

    def test_does_not_read_expected_json(self) -> None:
        stdout, stderr, exit_code, root = self.run_temp_fixture(create_expected_dir=False)

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        self.assertIn("documents_processed: 1", stdout)
        self.assertTrue((root / "predictions_baseline" / "note_test.predicted.json").exists())

    def test_processes_all_notes_in_sorted_order_when_document_id_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes_dir = root / "notes"
            output_dir = root / "predictions_baseline"
            notes_dir.mkdir()
            (notes_dir / "note_b.txt").write_text("Past Medical History:\nAsthma.\n", encoding="utf-8")
            (notes_dir / "note_a.txt").write_text("Past Medical History:\nHypertension.\n", encoding="utf-8")

            stdout, stderr, exit_code = self.run_main(
                [
                    "--notes-dir",
                    str(notes_dir),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(0, exit_code)
            self.assertEqual("", stderr)
            self.assertLess(stdout.index("document_id: note_a"), stdout.index("document_id: note_b"))
            self.assertIn("documents_processed: 2", stdout)
            self.assertTrue((output_dir / "note_a.predicted.json").exists())
            self.assertTrue((output_dir / "note_b.predicted.json").exists())

    def test_existing_output_without_overwrite_returns_error(self) -> None:
        stdout, stderr, exit_code, _ = self.run_temp_fixture(existing_output=True)

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout)
        self.assertIn("prediction file already exists", stderr)

    def test_existing_output_with_overwrite_succeeds(self) -> None:
        stdout, stderr, exit_code, root = self.run_temp_fixture(
            existing_output=True,
            overwrite=True,
        )

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        self.assertIn("documents_processed: 1", stdout)
        self.assertEqual(1, len(self.read_prediction(root, "note_test")["items"]))

    def test_missing_requested_note_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes_dir = root / "notes"
            output_dir = root / "predictions_baseline"
            notes_dir.mkdir()

            stdout, stderr, exit_code = self.run_main(
                [
                    "--document-id",
                    "missing_note",
                    "--notes-dir",
                    str(notes_dir),
                    "--output-dir",
                    str(output_dir),
                ]
            )

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout)
        self.assertIn("missing note file", stderr)

    def test_empty_notes_directory_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes_dir = root / "notes"
            output_dir = root / "predictions_baseline"
            notes_dir.mkdir()

            stdout, stderr, exit_code = self.run_main(
                [
                    "--notes-dir",
                    str(notes_dir),
                    "--output-dir",
                    str(output_dir),
                ]
            )

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout)
        self.assertIn("no note files found", stderr)

    def test_generated_source_spans_are_exact(self) -> None:
        raw_text = "Past Medical History:\nHypertension.\n\nMedications:\nMetformin 500 mg twice daily.\n"
        _, _, exit_code, root = self.run_temp_fixture(raw_text=raw_text)

        self.assertEqual(0, exit_code)
        prediction = self.read_prediction(root, "note_test")
        for item in prediction["items"]:
            with self.subTest(item=item):
                self.assertEqual(
                    item["source_quote"],
                    raw_text[item["source_start_char"] : item["source_end_char"]],
                )

    def test_real_note_001_into_temp_output_succeeds_with_non_empty_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "predictions_baseline"

            stdout, stderr, exit_code = self.run_main(
                [
                    "--document-id",
                    "note_001",
                    "--notes-dir",
                    str(GOLDEN_NOTES),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(0, exit_code)
            self.assertEqual("", stderr)
            self.assertIn("document_id: note_001", stdout)
            prediction = json.loads((output_dir / "note_001.predicted.json").read_text(encoding="utf-8"))
            self.assertGreater(len(prediction["items"]), 0)

    def run_temp_fixture(
        self,
        *,
        raw_text: str = "Past Medical History:\nHypertension.",
        existing_output: bool = False,
        overwrite: bool = False,
        create_expected_dir: bool = True,
    ) -> tuple[str, str, int, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        notes_dir = root / "notes"
        output_dir = root / "predictions_baseline"
        notes_dir.mkdir()
        output_dir.mkdir()
        if create_expected_dir:
            (root / "expected").mkdir()
            (root / "expected" / "note_test.expected.json").write_text("not json", encoding="utf-8")

        (notes_dir / "note_test.txt").write_text(raw_text, encoding="utf-8")
        output_path = output_dir / "note_test.predicted.json"
        if existing_output:
            output_path.write_text("{}", encoding="utf-8")

        argv = [
            "--document-id",
            "note_test",
            "--notes-dir",
            str(notes_dir),
            "--output-dir",
            str(output_dir),
        ]
        if overwrite:
            argv.append("--overwrite")

        stdout, stderr, exit_code = self.run_main(argv)
        return stdout, stderr, exit_code, root

    def run_main(self, argv: list[str]) -> tuple[str, str, int]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = run_baseline_extractor.main(argv)
        return stdout.getvalue(), stderr.getvalue(), exit_code

    def read_prediction(self, root: Path, document_id: str) -> dict:
        prediction_path = root / "predictions_baseline" / f"{document_id}.predicted.json"
        return json.loads(prediction_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
