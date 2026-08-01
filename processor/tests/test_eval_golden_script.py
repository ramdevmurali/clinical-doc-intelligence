import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import eval_golden


class EvalGoldenScriptTests(unittest.TestCase):
    def test_document_id_note_001_evaluates_manual_baseline_prediction(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = eval_golden.main(["--document-id", "note_001"])

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr.getvalue())
        output = stdout.getvalue()
        self.assertIn("Document: note_001", output)
        self.assertIn("expected_item_count:", output)
        self.assertIn("predicted_item_count: 15", output)
        self.assertIn("matched_item_count: 15", output)
        self.assertIn("source_quote_failure_count: 0", output)
        self.assertNotIn("Missing Expected Items:", output)
        self.assertIn("Aggregate Summary", output)
        self.assertIn("notes_evaluated: 1", output)

    def test_extra_predicted_item_details_are_printed(self) -> None:
        stdout, stderr, exit_code = self.run_temp_fixture(
            raw_text="Hypertension.",
            expected_json={"items": [], "invalid_extractions": []},
            prediction_json={
                "items": [
                    self.prediction_item(
                        source_quote="Hypertension.",
                        source_start_char=0,
                        source_end_char=len("Hypertension."),
                    )
                ]
            },
        )

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        self.assertIn("extra_item_count: 1", stdout)
        self.assertIn("Extra Predicted Items:", stdout)
        self.assertIn("predicted_index: 0", stdout)
        self.assertIn("type: condition", stdout)
        self.assertIn("name: hypertension", stdout)
        self.assertIn("status: active", stdout)

    def test_invalid_trap_hit_details_are_printed(self) -> None:
        stdout, stderr, exit_code = self.run_temp_fixture(
            raw_text="Patient denies chest pain.",
            expected_json={
                "items": [],
                "invalid_extractions": [
                    {
                        "type": "condition",
                        "name": "chest pain",
                        "forbidden_status": "active",
                        "reason": "Denied symptom.",
                    }
                ],
            },
            prediction_json={
                "items": [
                    self.prediction_item(
                        name="chest pain",
                        source_quote="Patient denies chest pain.",
                        source_start_char=0,
                        source_end_char=len("Patient denies chest pain."),
                    )
                ]
            },
        )

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        self.assertIn("invalid_trap_hit_count: 1", stdout)
        self.assertIn("Invalid Trap Hits:", stdout)
        self.assertIn("trap_index: 0, predicted_index: 0", stdout)
        self.assertIn("message:", stdout)

    def test_source_quote_failure_details_are_printed(self) -> None:
        stdout, stderr, exit_code = self.run_temp_fixture(
            raw_text="Assessment: Hypertension.",
            expected_json={"items": [], "invalid_extractions": []},
            prediction_json={
                "items": [
                    self.prediction_item(
                        source_quote="Hypertension.",
                        source_start_char=0,
                        source_end_char=len("Hypertension."),
                    )
                ]
            },
        )

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        self.assertIn("source_quote_failure_count: 1", stdout)
        self.assertIn("Source Quote Failures:", stdout)
        self.assertIn("predicted_index: 0", stdout)
        self.assertIn("message:", stdout)

    def test_missing_prediction_file_returns_error(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = eval_golden.main(["--document-id", "missing_note"])

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("missing prediction file", stderr.getvalue())

    def test_missing_note_file_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes_dir = root / "notes"
            expected_dir = root / "expected"
            predictions_dir = root / "predictions"
            notes_dir.mkdir()
            expected_dir.mkdir()
            predictions_dir.mkdir()

            (expected_dir / "note_missing.expected.json").write_text(
                json.dumps({"items": [], "invalid_extractions": []}),
                encoding="utf-8",
            )
            (predictions_dir / "note_missing.predicted.json").write_text(
                json.dumps({"items": []}),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = eval_golden.main(
                    [
                        "--document-id",
                        "note_missing",
                        "--notes-dir",
                        str(notes_dir),
                        "--expected-dir",
                        str(expected_dir),
                        "--predictions-dir",
                        str(predictions_dir),
                    ]
                )

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("missing note file", stderr.getvalue())

    def run_temp_fixture(
        self,
        raw_text: str,
        expected_json: dict,
        prediction_json: dict,
    ) -> tuple[str, str, int]:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes_dir = root / "notes"
            expected_dir = root / "expected"
            predictions_dir = root / "predictions"
            notes_dir.mkdir()
            expected_dir.mkdir()
            predictions_dir.mkdir()

            (notes_dir / "note_test.txt").write_text(raw_text, encoding="utf-8")
            (expected_dir / "note_test.expected.json").write_text(
                json.dumps(expected_json),
                encoding="utf-8",
            )
            (predictions_dir / "note_test.predicted.json").write_text(
                json.dumps(prediction_json),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = eval_golden.main(
                    [
                        "--document-id",
                        "note_test",
                        "--notes-dir",
                        str(notes_dir),
                        "--expected-dir",
                        str(expected_dir),
                        "--predictions-dir",
                        str(predictions_dir),
                    ]
                )

        return stdout.getvalue(), stderr.getvalue(), exit_code

    def prediction_item(self, **overrides) -> dict:
        values = {
            "type": "condition",
            "name": "hypertension",
            "status": "active",
            "confidence": 0.95,
            "source_quote": "Hypertension.",
            "source_start_char": 0,
            "source_end_char": len("Hypertension."),
            "section_id": "note_test:section:001",
            "section_name": "Assessment",
        }
        values.update(overrides)
        return values


if __name__ == "__main__":
    unittest.main()
