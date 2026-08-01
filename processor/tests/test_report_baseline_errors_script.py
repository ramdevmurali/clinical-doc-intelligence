import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import report_baseline_errors


ROOT = Path(__file__).resolve().parents[2]
BASELINE_PREDICTIONS = ROOT / "predictions_baseline"


class ReportBaselineErrorsScriptTests(unittest.TestCase):
    def test_report_runs_against_temp_fixture_and_exits_zero(self) -> None:
        stdout, stderr, exit_code = self.run_temp_fixture(
            documents=[
                self.document_fixture(
                    document_id="note_a",
                    raw_text="Hypertension.",
                    expected_items=[
                        self.expected_item(
                            item_type="condition",
                            name="hypertension",
                            source_quote="Hypertension.",
                        )
                    ],
                    predicted_items=[
                        self.prediction_item(
                            item_type="condition",
                            name="hypertension",
                            source_quote="Hypertension.",
                            source_start_char=0,
                            source_end_char=len("Hypertension."),
                        )
                    ],
                )
            ]
        )

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        self.assertIn("Baseline Error Report", stdout)
        self.assertIn("notes_evaluated: 1", stdout)

    def test_aggregate_counts_are_printed(self) -> None:
        stdout, _, exit_code = self.run_temp_fixture(
            documents=[
                self.document_fixture(
                    document_id="note_a",
                    raw_text="Hypertension. Metformin.",
                    expected_items=[
                        self.expected_item(
                            item_type="condition",
                            name="hypertension",
                            source_quote="Hypertension.",
                        ),
                        self.expected_item(
                            item_type="medication",
                            name="metformin",
                            status="active",
                            source_quote="Metformin.",
                        ),
                    ],
                    predicted_items=[
                        self.prediction_item(
                            item_type="condition",
                            name="hypertension",
                            source_quote="Hypertension.",
                            source_start_char=0,
                            source_end_char=len("Hypertension."),
                        )
                    ],
                )
            ]
        )

        self.assertEqual(0, exit_code)
        self.assertIn("expected_item_count: 2", stdout)
        self.assertIn("predicted_item_count: 1", stdout)
        self.assertIn("matched_item_count: 1", stdout)
        self.assertIn("missing_item_count: 1", stdout)
        self.assertIn("extra_item_count: 0", stdout)

    def test_missing_by_type_is_counted_and_sorted(self) -> None:
        stdout, _, exit_code = self.run_temp_fixture(
            documents=[
                self.document_fixture(
                    document_id="note_a",
                    raw_text="Hypertension. Metformin. Warfarin.",
                    expected_items=[
                        self.expected_item(item_type="medication", name="metformin"),
                        self.expected_item(item_type="condition", name="hypertension"),
                        self.expected_item(item_type="medication", name="warfarin"),
                    ],
                    predicted_items=[],
                )
            ]
        )

        self.assertEqual(0, exit_code)
        self.assertIn("Missing By Type:", stdout)
        self.assertLess(stdout.index("  medication: 2"), stdout.index("  condition: 1"))

    def test_extra_by_type_is_counted_and_sorted(self) -> None:
        stdout, _, exit_code = self.run_temp_fixture(
            documents=[
                self.document_fixture(
                    document_id="note_a",
                    raw_text="Hypertension. Warfarin. Appendectomy.",
                    expected_items=[],
                    predicted_items=[
                        self.prediction_item(item_type="procedure", name="appendectomy"),
                        self.prediction_item(item_type="condition", name="hypertension"),
                        self.prediction_item(item_type="procedure", name="colonoscopy"),
                    ],
                )
            ]
        )

        self.assertEqual(0, exit_code)
        self.assertIn("Extra By Type:", stdout)
        self.assertLess(stdout.index("  procedure: 2"), stdout.index("  condition: 1"))

    def test_worst_documents_are_sorted_by_total_failures_desc(self) -> None:
        stdout, _, exit_code = self.run_temp_fixture(
            documents=[
                self.document_fixture(
                    document_id="note_b",
                    raw_text="Hypertension.",
                    expected_items=[self.expected_item(item_type="condition", name="hypertension")],
                    predicted_items=[],
                ),
                self.document_fixture(
                    document_id="note_a",
                    raw_text="Hypertension. Metformin. Warfarin.",
                    expected_items=[
                        self.expected_item(item_type="condition", name="hypertension"),
                        self.expected_item(item_type="medication", name="metformin"),
                    ],
                    predicted_items=[
                        self.prediction_item(item_type="procedure", name="appendectomy")
                    ],
                ),
            ]
        )

        self.assertEqual(0, exit_code)
        self.assertIn("Worst Documents:", stdout)
        self.assertLess(
            stdout.index("  note_a: missing=2, extra=1"),
            stdout.index("  note_b: missing=1, extra=0"),
        )

    def test_source_grounding_total_is_printed(self) -> None:
        stdout, _, exit_code = self.run_temp_fixture(
            documents=[
                self.document_fixture(
                    document_id="note_a",
                    raw_text="Assessment: Hypertension.",
                    expected_items=[],
                    predicted_items=[
                        self.prediction_item(
                            source_quote="Hypertension.",
                            source_start_char=0,
                            source_end_char=len("Hypertension."),
                        )
                    ],
                )
            ]
        )

        self.assertEqual(0, exit_code)
        self.assertIn("Source Grounding:", stdout)
        self.assertIn("  failures: 1", stdout)

    def test_invalid_trap_total_is_printed(self) -> None:
        stdout, _, exit_code = self.run_temp_fixture(
            documents=[
                self.document_fixture(
                    document_id="note_a",
                    raw_text="Patient denies chest pain.",
                    expected_items=[],
                    invalid_extractions=[
                        {
                            "type": "condition",
                            "name": "chest pain",
                            "forbidden_status": "active",
                            "reason": "Denied symptom.",
                        }
                    ],
                    predicted_items=[
                        self.prediction_item(
                            item_type="condition",
                            name="chest pain",
                            status="active",
                            source_quote="Patient denies chest pain.",
                            source_start_char=0,
                            source_end_char=len("Patient denies chest pain."),
                        )
                    ],
                )
            ]
        )

        self.assertEqual(0, exit_code)
        self.assertIn("Invalid Trap Hits:", stdout)
        self.assertIn("  hits: 1", stdout)

    def test_document_id_limits_report_to_one_document(self) -> None:
        stdout, _, exit_code = self.run_temp_fixture(
            document_id="note_b",
            documents=[
                self.document_fixture(document_id="note_a", raw_text="Hypertension."),
                self.document_fixture(document_id="note_b", raw_text="Metformin."),
            ],
        )

        self.assertEqual(0, exit_code)
        self.assertIn("notes_evaluated: 1", stdout)
        self.assertNotIn("note_a:", stdout)

    def test_missing_prediction_returns_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes_dir = root / "notes"
            expected_dir = root / "expected"
            predictions_dir = root / "predictions_baseline"
            notes_dir.mkdir()
            expected_dir.mkdir()
            predictions_dir.mkdir()

            stdout, stderr, exit_code = self.run_main(
                [
                    "--document-id",
                    "missing_note",
                    "--notes-dir",
                    str(notes_dir),
                    "--expected-dir",
                    str(expected_dir),
                    "--predictions-dir",
                    str(predictions_dir),
                ]
            )

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout)
        self.assertIn("missing prediction file", stderr)

    def test_missing_note_returns_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes_dir = root / "notes"
            expected_dir = root / "expected"
            predictions_dir = root / "predictions_baseline"
            notes_dir.mkdir()
            expected_dir.mkdir()
            predictions_dir.mkdir()
            self.write_expected(expected_dir, "note_a", [])
            self.write_prediction(predictions_dir, "note_a", [])

            stdout, stderr, exit_code = self.run_main(
                [
                    "--document-id",
                    "note_a",
                    "--notes-dir",
                    str(notes_dir),
                    "--expected-dir",
                    str(expected_dir),
                    "--predictions-dir",
                    str(predictions_dir),
                ]
            )

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout)
        self.assertIn("missing note file", stderr)

    def test_missing_expected_returns_exit_one(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes_dir = root / "notes"
            expected_dir = root / "expected"
            predictions_dir = root / "predictions_baseline"
            notes_dir.mkdir()
            expected_dir.mkdir()
            predictions_dir.mkdir()
            (notes_dir / "note_a.txt").write_text("Hypertension.", encoding="utf-8")
            self.write_prediction(predictions_dir, "note_a", [])

            stdout, stderr, exit_code = self.run_main(
                [
                    "--document-id",
                    "note_a",
                    "--notes-dir",
                    str(notes_dir),
                    "--expected-dir",
                    str(expected_dir),
                    "--predictions-dir",
                    str(predictions_dir),
                ]
            )

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout)
        self.assertIn("missing expected file", stderr)

    def test_real_baseline_predictions_report_if_present(self) -> None:
        if not BASELINE_PREDICTIONS.exists():
            self.skipTest("predictions_baseline directory is not present")

        stdout, stderr, exit_code = self.run_main(["--document-id", "note_001"])

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        self.assertIn("Baseline Error Report", stdout)
        self.assertIn("notes_evaluated: 1", stdout)

    def run_temp_fixture(
        self,
        *,
        documents: list[dict],
        document_id: str | None = None,
    ) -> tuple[str, str, int]:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes_dir = root / "notes"
            expected_dir = root / "expected"
            predictions_dir = root / "predictions_baseline"
            notes_dir.mkdir()
            expected_dir.mkdir()
            predictions_dir.mkdir()

            for document in documents:
                (notes_dir / f"{document['document_id']}.txt").write_text(
                    document["raw_text"],
                    encoding="utf-8",
                )
                self.write_expected(
                    expected_dir,
                    document["document_id"],
                    document["expected_items"],
                    document["invalid_extractions"],
                )
                self.write_prediction(
                    predictions_dir,
                    document["document_id"],
                    document["predicted_items"],
                )

            argv = [
                "--notes-dir",
                str(notes_dir),
                "--expected-dir",
                str(expected_dir),
                "--predictions-dir",
                str(predictions_dir),
            ]
            if document_id:
                argv.extend(["--document-id", document_id])
            return self.run_main(argv)

    def run_main(self, argv: list[str]) -> tuple[str, str, int]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = report_baseline_errors.main(argv)
        return stdout.getvalue(), stderr.getvalue(), exit_code

    def document_fixture(
        self,
        *,
        document_id: str,
        raw_text: str,
        expected_items: list[dict] | None = None,
        predicted_items: list[dict] | None = None,
        invalid_extractions: list[dict] | None = None,
    ) -> dict:
        return {
            "document_id": document_id,
            "raw_text": raw_text,
            "expected_items": expected_items or [],
            "predicted_items": predicted_items or [],
            "invalid_extractions": invalid_extractions or [],
        }

    def expected_item(
        self,
        *,
        item_type: str,
        name: str,
        status: str | None = "active",
        source_quote: str | None = None,
    ) -> dict:
        item = {
            "type": item_type,
            "name": name,
        }
        if status is not None:
            item["status"] = status
        if source_quote is not None:
            item["source_quote"] = source_quote
        return item

    def prediction_item(
        self,
        *,
        item_type: str = "condition",
        name: str = "hypertension",
        status: str | None = "active",
        source_quote: str = "Hypertension.",
        source_start_char: int = 0,
        source_end_char: int | None = None,
    ) -> dict:
        if source_end_char is None:
            source_end_char = source_start_char + len(source_quote)
        item = {
            "type": item_type,
            "name": name,
            "confidence": 0.75,
            "source_quote": source_quote,
            "source_start_char": source_start_char,
            "source_end_char": source_end_char,
            "section_id": "note_test:section:001",
            "section_name": "Assessment",
        }
        if status is not None:
            item["status"] = status
        return item

    def write_expected(
        self,
        expected_dir: Path,
        document_id: str,
        items: list[dict],
        invalid_extractions: list[dict] | None = None,
    ) -> None:
        (expected_dir / f"{document_id}.expected.json").write_text(
            json.dumps({"items": items, "invalid_extractions": invalid_extractions or []}),
            encoding="utf-8",
        )

    def write_prediction(
        self,
        predictions_dir: Path,
        document_id: str,
        items: list[dict],
    ) -> None:
        (predictions_dir / f"{document_id}.predicted.json").write_text(
            json.dumps(
                {
                    "schema_version": "prediction-format-v1",
                    "document_id": document_id,
                    "extractor": {
                        "name": "deterministic-baseline",
                        "version": "baseline-extractor-v1",
                    },
                    "items": items,
                }
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
