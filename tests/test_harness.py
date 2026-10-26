import json
from pathlib import Path
import sys
import subprocess
import tempfile
import tomllib
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from harness import read_json, validate_receipt, validate_task


def task_fixture():
    return {
        "schema_version": "1.0",
        "task_id": "task-fixture",
        "objective": "Inspect a synthetic fixture.",
        "target": {"kind": "fixture", "id": "fixture-root", "allowed_paths": ["fixtures/"]},
        "control": {"primary_role": "primary", "executor_role": "executor", "single_writer": "executor"},
        "interfaces": [{"kind": "fixture", "name": "fake-reader", "verified_for_task": True}],
        "allowed_actions": ["read fixture metadata"],
        "prohibited_actions": ["network", "write"],
        "acceptance_criteria": [{"id": "metadata", "description": "Expected metadata appears."}],
        "stop_conditions": ["Fixture missing"],
        "max_attempts": 1,
    }


def receipt_fixture():
    return {
        "schema_version": "1.0",
        "task_id": "task-fixture",
        "executor": {"id": "executor", "route": "fixture-only"},
        "reported_status": "completed",
        "actions_reported": ["Read fixture metadata."],
        "changes": [],
        "evidence": [{"kind": "text", "reference": "synthetic-receipt", "establishes": "Executor reported the metadata."}],
        "limitations": ["Synthetic test data."],
        "independent_acceptance": {
            "status": "pending",
            "accepted_by": None,
            "checks": [{"id": "metadata", "result": "not_run", "evidence": []}],
        },
    }


class HarnessValidationTests(unittest.TestCase):
    def test_valid_task_packet(self):
        self.assertEqual(validate_task(task_fixture()), [])

    def test_reported_completed_remains_pending_until_primary_accepts(self):
        result = validate_receipt(receipt_fixture(), task_fixture())
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["outcome"], "reported_completed_pending_acceptance")
        self.assertFalse(result["accepted"])

    def test_independent_primary_acceptance_requires_pass_and_evidence(self):
        receipt = receipt_fixture()
        receipt["independent_acceptance"] = {
            "status": "accepted",
            "accepted_by": {"role": "primary", "id": "primary"},
            "checks": [{"id": "metadata", "result": "pass", "evidence": [{"kind": "readback", "reference": "fixture-check", "establishes": "Metadata matches."}]}],
        }
        result = validate_receipt(receipt, task_fixture())
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["outcome"], "accepted")
        self.assertTrue(result["accepted"])

    def test_cannot_accept_executor_self_report_or_missing_evidence(self):
        receipt = receipt_fixture()
        receipt["independent_acceptance"] = {
            "status": "accepted",
            "accepted_by": {"role": "primary", "id": "executor"},
            "checks": [{"id": "metadata", "result": "pass", "evidence": []}],
        }
        result = validate_receipt(receipt, task_fixture())
        self.assertEqual(result["outcome"], "invalid")
        self.assertFalse(result["accepted"])
        self.assertTrue(any("independent" in error for error in result["errors"]))
        self.assertTrue(any("cite evidence" in error for error in result["errors"]))

    def test_acceptance_must_cover_task_checks_and_match_task_id(self):
        receipt = receipt_fixture()
        receipt["task_id"] = "different-task"
        receipt["independent_acceptance"] = {
            "status": "accepted",
            "accepted_by": {"role": "primary", "id": "primary"},
            "checks": [{"id": "other", "result": "pass", "evidence": [{"kind": "readback", "reference": "r", "establishes": "Synthetic."}]}],
        }
        result = validate_receipt(receipt, task_fixture())
        self.assertEqual(result["outcome"], "invalid")
        self.assertTrue(any("does not match" in error for error in result["errors"]))
        self.assertTrue(any("missing one or more" in error for error in result["errors"]))

    def test_cli_returns_invalid_for_unhashable_task_criterion_id(self):
        task = task_fixture()
        task["acceptance_criteria"][0]["id"] = ["not-a-string"]
        receipt = receipt_fixture()
        receipt["independent_acceptance"] = {
            "status": "accepted",
            "accepted_by": {"role": "primary", "id": "primary"},
            "checks": [{"id": "metadata", "result": "pass", "evidence": [{"kind": "readback", "reference": "synthetic", "establishes": "Example."}]}],
        }
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="harness-invalid-task-") as folder:
            task_path = Path(folder) / "task.json"
            receipt_path = Path(folder) / "receipt.json"
            task_path.write_text(json.dumps(task))
            receipt_path.write_text(json.dumps(receipt))
            completed = subprocess.run(
                [sys.executable, str(root / "harness.py"), "validate-receipt", str(receipt_path), "--task", str(task_path)],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(completed.returncode, 2)
        result = json.loads(completed.stdout)
        self.assertFalse(result["valid"])
        self.assertEqual(result["outcome"], "invalid")
        self.assertTrue(any("acceptance criterion" in error for error in result["errors"]))

    def test_malformed_types_return_validation_errors_not_tracebacks(self):
        receipt = receipt_fixture()
        receipt["reported_status"] = []
        receipt["independent_acceptance"]["status"] = []
        result = validate_receipt(receipt)
        self.assertEqual(result["outcome"], "invalid")
        self.assertFalse(result["accepted"])

    def test_interface_examples_are_placeholders_and_mcp_is_disabled(self):
        root = Path(__file__).resolve().parents[1]
        config = tomllib.loads((root / "examples/mcp-config.example.toml").read_text())
        self.assertFalse(config["mcp_servers"]["example_read_only"]["enabled"])
        self.assertIn("replace_with_your_mcp_package", config["mcp_servers"]["example_read_only"]["args"])
        skill = (root / "examples/skills/portable-example/SKILL.md").read_text()
        self.assertIn("allow_implicit_invocation: false", skill)
        self.assertIn("Placeholder", skill)

    def test_json_input_size_is_bounded(self):
        with tempfile.TemporaryDirectory(prefix="harness-fixture-") as folder:
            path = Path(folder) / "oversized.json"
            path.write_bytes(b" " * (1_000_001))
            data, error = read_json(path)
        self.assertIsNone(data)
        self.assertEqual(error, "document exceeds 1 MB limit")


if __name__ == "__main__":
    unittest.main()
