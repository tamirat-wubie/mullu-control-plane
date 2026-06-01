"""Purpose: verify Universal Action Orchestration contract validation.

Governance scope:
  OCE: action, stage, guard, decision, receipt, reconciliation, memory, closure,
  and lineage fields are explicit.
  RAG: stages, traces, receipts, and closure are linked.
  CDCV: execution is allowed only after admission passes.
  UWMA: examples remain repeatable governed proof artifacts.

Dependencies:
  Python standard library only.

Invariants:
  The validator is read-only, blocks execution bypass, and rejects raw private
  reasoning exposure.
"""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = WORKSPACE_ROOT / "scripts" / "validate_universal_action_orchestration.py"
SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "universal_action_orchestration.schema.json"
DOCUMENT_PATH = WORKSPACE_ROOT / "docs" / "UNIVERSAL_ACTION_ORCHESTRATION.md"
ALLOWED_EXAMPLE_PATH = WORKSPACE_ROOT / "examples" / "universal_action_orchestration.allowed_status_publish.json"
BLOCKED_EXAMPLE_PATH = WORKSPACE_ROOT / "examples" / "universal_action_orchestration.blocked_invoice_payment.json"
BLOCKED_MISSING_APPROVAL_PATH = WORKSPACE_ROOT / "examples" / "uao" / "blocked_missing_approval.json"
DEFERRED_STALE_EVIDENCE_PATH = WORKSPACE_ROOT / "examples" / "uao" / "deferred_stale_evidence.json"
SIMULATED_LOW_RISK_READONLY_PATH = WORKSPACE_ROOT / "examples" / "uao" / "simulated_low_risk_readonly.json"


def _load_validator_module():
    spec = importlib.util.spec_from_file_location("validate_universal_action_orchestration", VALIDATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load validator module: {VALIDATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VALIDATOR = _load_validator_module()


class UniversalActionOrchestrationContractTests(unittest.TestCase):
    def test_current_universal_action_orchestration_contract_passes(self) -> None:
        example_paths = (
            ALLOWED_EXAMPLE_PATH,
            BLOCKED_EXAMPLE_PATH,
            BLOCKED_MISSING_APPROVAL_PATH,
            DEFERRED_STALE_EVIDENCE_PATH,
            SIMULATED_LOW_RISK_READONLY_PATH,
        )
        errors = VALIDATOR.validate_contract(SCHEMA_PATH, example_paths)

        self.assertEqual([], errors)
        self.assertTrue(SCHEMA_PATH.exists())
        self.assertTrue(DOCUMENT_PATH.exists())
        self.assertEqual(5, len(example_paths))
        for example_path in example_paths:
            self.assertTrue(example_path.exists())

    def test_schema_artifact_has_required_contract_surface(self) -> None:
        schema = VALIDATOR.load_json_object(SCHEMA_PATH, "schema")
        errors = VALIDATOR.validate_schema_artifact(schema)

        self.assertEqual([], errors)
        self.assertEqual("Universal Action Orchestration", schema["title"])
        self.assertIn("action_envelope", schema["$defs"])
        self.assertIn("pipeline_stage", schema["$defs"])
        self.assertIn("action_envelope", schema["required"])
        self.assertIn("admission_guards", schema["required"])
        self.assertIn("closure_state", schema["required"])
        self.assertIn("raw_reasoning_included", schema["required"])

    def test_recommended_v1_examples_are_non_executing_shapes(self) -> None:
        fixture_paths = (
            BLOCKED_MISSING_APPROVAL_PATH,
            DEFERRED_STALE_EVIDENCE_PATH,
            SIMULATED_LOW_RISK_READONLY_PATH,
        )
        observed_decisions: set[str] = set()

        for fixture_path in fixture_paths:
            record = VALIDATOR.load_json_object(fixture_path, fixture_path.name)
            errors = VALIDATOR.validate_orchestration(record)
            observed_decisions.add(record["decision"]["status"])

            self.assertEqual([], errors)
            self.assertFalse(record["decision"]["execution_allowed"])
            self.assertIsNone(record["execution_receipt_ref"])
            self.assertEqual(record["closure_state"], record["closure"]["status"])

        self.assertEqual({"block", "defer", "simulate"}, observed_decisions)

    def test_doctrine_declares_preflight_gate_contract(self) -> None:
        document_text = VALIDATOR.load_document_text(DOCUMENT_PATH)
        errors = VALIDATOR.validate_document_contract(document_text)

        self.assertEqual([], errors)
        self.assertIn("passive doc -> schema contract", document_text)
        self.assertIn("not UAO_valid(action) -> preflight_fail", document_text)
        self.assertIn("does not execute actions", document_text)
        self.assertIn("raw private reasoning", document_text)

    def test_effect_bearing_action_requires_causal_trace(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["trace_ref"] = ""
        invalid_record["causal_decision_trace_ref"] = ""
        invalid_record["pipeline_stages"][2]["output_refs"] = []

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 2)
        self.assertTrue(any("trace_ref" in error for error in errors))
        self.assertTrue(any("causal_decision_trace_ref" in error for error in errors))
        self.assertTrue(any("effect-bearing action requires" in error for error in errors))

    def test_action_envelope_identity_drift_is_rejected(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["action_envelope"]["actor"] = "operator:wrong_actor"
        invalid_record["action_envelope"]["tenant"] = "tenant_wrong"
        invalid_record["action_envelope"]["requested_at"] = "2026-05-31T09:30:00Z"

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 3)
        self.assertIn("action_envelope.actor must match actor_id", errors)
        self.assertIn("action_envelope.tenant must match tenant_id", errors)
        self.assertIn("action_envelope.requested_at must match created_at", errors)

    def test_high_risk_allow_requires_approval_evidence_and_capability(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["action_envelope"]["risk"] = "H3"
        invalid_record["action_envelope"]["approval_ref"] = None
        invalid_record["action_envelope"]["evidence_refs"] = []
        invalid_record["action_envelope"]["capability_refs"] = []

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 3)
        self.assertIn("high-risk allow requires action_envelope.approval_ref", errors)
        self.assertIn("high-risk allow requires action_envelope.evidence_refs", errors)
        self.assertIn("high-risk allow requires action_envelope.capability_refs", errors)

    def test_raw_chain_of_thought_field_is_rejected(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["chain_of_thought"] = "private reasoning must not be serialized"

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertTrue(any("chain_of_thought is prohibited" in error for error in errors))

    def test_allow_decision_rejects_blocked_guard(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["admission_guards"][0]["verdict"] = "blocked"
        invalid_record["admission_guards"][0]["proof_state"] = "Fail"

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertTrue(any("allow requires every admission guard to pass" in error for error in errors))
        self.assertEqual("blocked", invalid_record["admission_guards"][0]["verdict"])

    def test_blocked_decision_cannot_execute(self) -> None:
        record = VALIDATOR.load_json_object(BLOCKED_EXAMPLE_PATH, "blocked UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["pipeline_stages"][5]["status"] = "completed"
        invalid_record["pipeline_stages"][5]["failure_reason"] = None
        invalid_record["decision"]["execution_allowed"] = True

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 2)
        self.assertTrue(any("non-allow status requires execution_allowed false" in error for error in errors))
        self.assertTrue(any("non-allow status cannot complete execution stage" in error for error in errors))

    def test_missing_required_guard_is_rejected(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["admission_guards"] = [
            guard for guard in invalid_record["admission_guards"] if guard["guard"] != "receipt_emittable"
        ]

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertIn("missing required admission guard: receipt_emittable", errors)
        self.assertEqual(10, len(invalid_record["admission_guards"]))

    def test_raw_reasoning_exposure_is_rejected(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["raw_reasoning_included"] = True
        invalid_record["exposure_boundary"]["blocked_payload_classes"].remove("raw_private_reasoning")

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 2)
        self.assertTrue(any("raw_reasoning_included must be false" in error for error in errors))
        self.assertTrue(any("blocked_payload_classes must include raw_private_reasoning" in error for error in errors))

    def test_cli_reports_passed_for_current_contract(self) -> None:
        stdout_buffer = io.StringIO()

        with redirect_stdout(stdout_buffer):
            exit_code = VALIDATOR.main(
                [
                    "--schema",
                    str(SCHEMA_PATH),
                    "--document",
                    str(DOCUMENT_PATH),
                    "--example",
                    str(ALLOWED_EXAMPLE_PATH),
                    "--example",
                    str(BLOCKED_EXAMPLE_PATH),
                    "--example",
                    str(BLOCKED_MISSING_APPROVAL_PATH),
                    "--example",
                    str(DEFERRED_STALE_EVIDENCE_PATH),
                    "--example",
                    str(SIMULATED_LOW_RISK_READONLY_PATH),
                ]
            )

        output = stdout_buffer.getvalue()
        self.assertEqual(0, exit_code)
        self.assertIn("universal_action_orchestration_schema", output)
        self.assertIn("STATUS: passed", output)

    def test_cli_json_receipt_reports_passed_contract(self) -> None:
        stdout_buffer = io.StringIO()

        with redirect_stdout(stdout_buffer):
            exit_code = VALIDATOR.main(
                [
                    "--schema",
                    str(SCHEMA_PATH),
                    "--document",
                    str(DOCUMENT_PATH),
                    "--example",
                    str(ALLOWED_EXAMPLE_PATH),
                    "--json",
                ]
            )

        report = json.loads(stdout_buffer.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual("universal_action_orchestration_validation_receipt", report["receipt_id"])
        self.assertTrue(report["terminal_closure_required"])
        self.assertTrue(report["receipt_is_not_terminal_closure"])
        self.assertTrue(report["valid"])
        self.assertEqual("passed", report["status"])
        self.assertEqual("schemas/universal_action_orchestration.schema.json", report["schema_path"])
        self.assertEqual("docs/UNIVERSAL_ACTION_ORCHESTRATION.md", report["document_path"])
        self.assertEqual(["examples/universal_action_orchestration.allowed_status_publish.json"], report["example_paths"])
        self.assertEqual(1, report["example_count"])
        self.assertEqual(5, report["check_count"])
        self.assertEqual(0, report["error_count"])
        self.assertEqual([], report["errors"])
        self.assertTrue(all(check["passed"] for check in report["checks"]))

    def test_cli_json_receipt_persists_failed_contract_without_secret_path_leakage(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["chain_of_thought"] = "private reasoning must not be serialized"

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            invalid_path = temporary_path / "invalid_uao.json"
            receipt_path = temporary_path / "receipt.json"
            invalid_path.write_text(json.dumps(invalid_record), encoding="utf-8")
            stdout_buffer = io.StringIO()

            with redirect_stdout(stdout_buffer):
                exit_code = VALIDATOR.main(
                    [
                        "--schema",
                        str(SCHEMA_PATH),
                        "--document",
                        str(DOCUMENT_PATH),
                        "--example",
                        str(invalid_path),
                        "--json",
                        "--receipt-path",
                        str(receipt_path),
                    ]
                )

            report = json.loads(stdout_buffer.getvalue())
            persisted_report = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(1, exit_code)
            self.assertFalse(report["valid"])
            self.assertEqual("failed", report["status"])
            self.assertEqual(report, persisted_report)
            self.assertTrue(report["terminal_closure_required"])
            self.assertEqual(["invalid_uao.json"], report["example_paths"])
            self.assertGreaterEqual(report["error_count"], 1)
            self.assertTrue(any("chain_of_thought is prohibited" in error for error in report["errors"]))
            serialized_report = json.dumps(report, sort_keys=True)
            self.assertNotIn(str(temporary_path), serialized_report)
            self.assertNotIn(str(invalid_path), serialized_report)
            self.assertTrue(receipt_path.exists())

    def test_cli_json_receipt_sanitizes_load_error_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            missing_schema_path = temporary_path / "secret" / "missing.schema.json"
            stdout_buffer = io.StringIO()

            with redirect_stdout(stdout_buffer):
                exit_code = VALIDATOR.main(
                    [
                        "--schema",
                        str(missing_schema_path),
                        "--document",
                        str(DOCUMENT_PATH),
                        "--example",
                        str(ALLOWED_EXAMPLE_PATH),
                        "--json",
                    ]
                )

            report = json.loads(stdout_buffer.getvalue())
            serialized_report = json.dumps(report, sort_keys=True)
            self.assertEqual(1, exit_code)
            self.assertFalse(report["valid"])
            self.assertEqual("missing.schema.json", report["schema_path"])
            self.assertEqual(1, report["error_count"])
            self.assertTrue(any("missing.schema.json" in error for error in report["errors"]))
            self.assertNotIn(str(temporary_path), serialized_report)
            self.assertNotIn(str(missing_schema_path), serialized_report)

    def test_load_json_object_rejects_non_object_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            payload_path = Path(temporary_directory) / "payload.json"
            payload_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")

            with self.assertRaises(ValueError):
                VALIDATOR.load_json_object(payload_path, "payload")

            self.assertTrue(payload_path.exists())
            self.assertEqual("payload.json", payload_path.name)


if __name__ == "__main__":
    unittest.main()
