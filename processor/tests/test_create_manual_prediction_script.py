import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import create_manual_prediction


class CreateManualPredictionScriptTests(unittest.TestCase):
    def test_generates_valid_prediction_json_for_temp_fixture(self) -> None:
        stdout, stderr, exit_code, root = self.run_temp_fixture()

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        self.assertIn("document_id: note_test", stdout)
        self.assertIn("item_count: 1", stdout)
        self.assertIn("all spans ok", stdout)

        prediction = self.read_prediction(root)
        self.assertEqual("prediction-format-v1", prediction["schema_version"])
        self.assertEqual("note_test", prediction["document_id"])
        self.assertEqual("manual-baseline", prediction["extractor"]["name"])
        self.assertEqual("0.1.0", prediction["extractor"]["version"])
        self.assertEqual(1, len(prediction["items"]))

    def test_output_item_has_exact_offsets_and_parser_section(self) -> None:
        _, _, exit_code, root = self.run_temp_fixture()

        self.assertEqual(0, exit_code)
        prediction = self.read_prediction(root)
        item = prediction["items"][0]

        self.assertEqual("condition", item["type"])
        self.assertEqual("hypertension", item["name"])
        self.assertEqual("active", item["status"])
        self.assertEqual(1.0, item["confidence"])
        self.assertEqual("Hypertension.", item["source_quote"])
        self.assertEqual(12, item["source_start_char"])
        self.assertEqual(25, item["source_end_char"])
        self.assertEqual("note_test:section:001", item["section_id"])
        self.assertEqual("Assessment", item["section_name"])

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
        self.assertIn("all spans ok", stdout)
        prediction = self.read_prediction(root)
        self.assertEqual(1, len(prediction["items"]))

    def test_missing_source_quote_returns_error(self) -> None:
        stdout, stderr, exit_code, _ = self.run_temp_fixture(
            expected_json=self.expected_json(source_quote="Missing quote."),
        )

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout)
        self.assertIn("source_quote not found", stderr)

    def test_ambiguous_repeated_source_quote_returns_error(self) -> None:
        stdout, stderr, exit_code, _ = self.run_temp_fixture(
            raw_text="Assessment:\nHypertension. Hypertension.",
        )

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout)
        self.assertIn("source_quote is ambiguous", stderr)

    def test_invalid_extractions_are_not_generated_as_predictions(self) -> None:
        _, _, exit_code, root = self.run_temp_fixture(
            expected_json=self.expected_json(
                invalid_extractions=[
                    {
                        "type": "condition",
                        "name": "chest pain",
                        "reason": "Negated symptom.",
                    }
                ]
            )
        )

        self.assertEqual(0, exit_code)
        prediction = self.read_prediction(root)
        self.assertEqual(1, len(prediction["items"]))
        self.assertEqual("hypertension", prediction["items"][0]["name"])

    def run_temp_fixture(
        self,
        *,
        raw_text: str = "Assessment:\nHypertension.",
        expected_json: dict | None = None,
        existing_output: bool = False,
        overwrite: bool = False,
    ) -> tuple[str, str, int, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        notes_dir = root / "notes"
        expected_dir = root / "expected"
        predictions_dir = root / "predictions"
        notes_dir.mkdir()
        expected_dir.mkdir()
        predictions_dir.mkdir()

        (notes_dir / "note_test.txt").write_text(raw_text, encoding="utf-8")
        (expected_dir / "note_test.expected.json").write_text(
            json.dumps(expected_json or self.expected_json()),
            encoding="utf-8",
        )
        output_path = predictions_dir / "note_test.predicted.json"
        if existing_output:
            output_path.write_text("{}", encoding="utf-8")

        argv = [
            "--document-id",
            "note_test",
            "--notes-dir",
            str(notes_dir),
            "--expected-dir",
            str(expected_dir),
            "--predictions-dir",
            str(predictions_dir),
        ]
        if overwrite:
            argv.append("--overwrite")

        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = create_manual_prediction.main(argv)

        return stdout.getvalue(), stderr.getvalue(), exit_code, root

    def expected_json(
        self,
        *,
        source_quote: str = "Hypertension.",
        invalid_extractions: list | None = None,
    ) -> dict:
        return {
            "document_id": "note_test",
            "items": [
                {
                    "type": "condition",
                    "name": "hypertension",
                    "status": "active",
                    "source_quote": source_quote,
                }
            ],
            "invalid_extractions": invalid_extractions or [],
        }

    def read_prediction(self, root: Path) -> dict:
        prediction_path = root / "predictions" / "note_test.predicted.json"
        return json.loads(prediction_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
