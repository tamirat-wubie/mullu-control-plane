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
  reasoning exposure. Validation receipts stay canonical and under the workspace root.
"""

from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = (
    WORKSPACE_ROOT / "scripts" / "validate_universal_action_orchestration.py"
)
SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "universal_action_orchestration.schema.json"
DOCUMENT_PATH = WORKSPACE_ROOT / "docs" / "UNIVERSAL_ACTION_ORCHESTRATION.md"
ALLOWED_EXAMPLE_PATH = (
    WORKSPACE_ROOT
    / "examples"
    / "universal_action_orchestration.allowed_status_publish.json"
)
BLOCKED_EXAMPLE_PATH = (
    WORKSPACE_ROOT
    / "examples"
    / "universal_action_orchestration.blocked_invoice_payment.json"
)
BLOCKED_MISSING_APPROVAL_PATH = (
    WORKSPACE_ROOT / "examples" / "uao" / "blocked_missing_approval.json"
)
DEFERRED_STALE_EVIDENCE_PATH = (
    WORKSPACE_ROOT / "examples" / "uao" / "deferred_stale_evidence.json"
)
SIMULATED_LOW_RISK_READONLY_PATH = (
    WORKSPACE_ROOT / "examples" / "uao" / "simulated_low_risk_readonly.json"
)


def _load_validator_module():
    spec = importlib.util.spec_from_file_location(
        "validate_universal_action_orchestration", VALIDATOR_PATH
    )
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
        self.assertIn("claim_ledger", schema["$defs"])
        self.assertIn("claim", schema["$defs"])
        self.assertIn("fracture_report", schema["$defs"])
        self.assertIn("fracture_check", schema["$defs"])
        self.assertIn("life_meaning_judgment", schema["$defs"])
        self.assertIn("life_meaning_affected_symbol", schema["$defs"])
        self.assertIn("life_meaning_impact", schema["$defs"])
        self.assertIn("life_meaning_delta", schema["$defs"])
        self.assertIn("life_meaning_boundary_state", schema["$defs"])
        self.assertIn("life_continuity_judgment", schema["$defs"])
        self.assertIn("life_continuity_impact", schema["$defs"])
        self.assertIn("life_continuity_delta", schema["$defs"])
        self.assertIn("memory_constitution", schema["$defs"])
        self.assertIn("pipeline_stage", schema["$defs"])
        self.assertIn("action_envelope", schema["required"])
        self.assertIn("claim_ledger", schema["required"])
        self.assertIn("fracture_report", schema["required"])
        self.assertIn("life_meaning_judgment", schema["properties"])
        self.assertIn("life_meaning_judgment", schema["required"])
        self.assertIn("life_continuity_judgment", schema["properties"])
        self.assertIn("life_continuity_judgment", schema["required"])
        self.assertIn("admission_guards", schema["required"])
        self.assertIn("closure_state", schema["required"])
        self.assertIn("raw_reasoning_included", schema["required"])
        self.assertIn("reconciliation_ref", schema["$defs"]["closure"]["required"])
        self.assertIn("memory_ref", schema["$defs"]["closure"]["required"])
        self.assertIn("constitution", schema["$defs"]["memory_update"]["required"])
        self.assertEqual(
            "^sha256:.+$",
            schema["$defs"]["whqr_replay_binding"]["properties"]["semantics_hash"][
                "pattern"
            ],
        )

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
            self.assertIn("reconciliation_ref", record["closure"])
            self.assertIn("memory_ref", record["closure"])

        self.assertEqual({"block", "defer", "simulate"}, observed_decisions)

    def test_doctrine_declares_preflight_gate_contract(self) -> None:
        document_text = VALIDATOR.load_document_text(DOCUMENT_PATH)
        errors = VALIDATOR.validate_document_contract(document_text)

        self.assertEqual([], errors)
        self.assertIn("passive doc -> schema contract", document_text)
        self.assertIn("not UAO_valid(action) -> preflight_fail", document_text)
        self.assertIn("does not execute actions", document_text)
        self.assertIn("raw private reasoning", document_text)
        self.assertIn(
            "Canonical validation receipts require the default schema", document_text
        )
        self.assertIn("Every command replay record must fail closed", document_text)
        self.assertIn("Every command replay record must bind", document_text)
        self.assertIn("receipt kind, tier, and root receipt reference", document_text)
        self.assertIn("event-local universal action proof detail", document_text)
        self.assertIn(
            "event hash recomputes from the persisted event payload", document_text
        )
        self.assertIn(
            "source channel, idempotency key, policy version, and trace id",
            document_text,
        )
        self.assertIn(
            "canonical ordered UAO pipeline stage sequence",
            document_text,
        )
        self.assertIn("independent recomputation", document_text)
        self.assertIn("closure receipt must bind closure state", document_text)
        self.assertIn("Runtime bypass detection scans", document_text)
        self.assertIn("verified claims require evidence refs", document_text)
        self.assertIn("Every memory update must expose a `constitution`", document_text)
        self.assertIn("memory_update.learning_allowed = true", document_text)
        self.assertIn("Every UAO record must expose a `fracture_report`", document_text)
        self.assertIn("decision.execution_allowed -> fracture_report.status = passed", document_text)
        self.assertIn("Every canonical UAO record must expose a `life_meaning_judgment`", document_text)
        self.assertIn("docs/LIFE_MEANING_GOVERNANCE_KERNEL.md", document_text)
        self.assertIn("Every canonical UAO record must expose a `life_continuity_judgment`", document_text)
        self.assertIn("docs/LIFE_CONTINUITY_CONFLICT_DOCTRINE.md", document_text)

    def test_allowed_action_requires_life_meaning_pass(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["life_meaning_judgment"]["decision"] = "pause"
        invalid_record["life_meaning_judgment"]["approval_required"] = True

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertIn(
            "allow decision requires life_meaning_judgment.decision pass",
            errors,
        )

    def test_life_meaning_pass_rejects_domination_risk(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["life_meaning_judgment"]["domination_risk"] = True

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertIn(
            "life_meaning_judgment.decision pass requires domination_risk false",
            errors,
        )

    def test_life_meaning_unknown_meaning_impact_pauses_effect_bearing_action(
        self,
    ) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["life_meaning_judgment"]["meaning_impact"] = "unknown"

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertIn(
            "effect-bearing pass requires known life_meaning_judgment.meaning_impact",
            errors,
        )

    def test_allowed_action_requires_life_continuity_pass(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["life_continuity_judgment"]["decision"] = "pause"
        invalid_record["life_continuity_judgment"]["review_required"] = True

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertIn(
            "allow decision requires life_continuity_judgment.decision pass",
            errors,
        )

    def test_life_continuity_pass_rejects_domination_risk(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["life_continuity_judgment"]["domination_risk"] = True

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertIn(
            "life_continuity_judgment.decision pass requires domination_risk false",
            errors,
        )

    def test_life_continuity_unknown_meaning_impact_pauses_effect_bearing_action(
        self,
    ) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["life_continuity_judgment"]["meaning_impact"] = "unknown"
        invalid_record["life_continuity_judgment"]["lived_meaning_risk"] = "unknown"

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 2)
        self.assertIn(
            "effect-bearing pass requires known life_continuity_judgment.meaning_impact",
            errors,
        )
        self.assertIn(
            "unknown meaning-impact on effect-bearing action cannot pass life-continuity judgment",
            errors,
        )

    def test_claim_ledger_rejects_verified_claim_without_evidence(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["claim_ledger"]["claims"][0]["evidence_refs"] = []

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertIn(
            "claim_ledger.claims[0]: verified claim requires evidence_refs",
            errors,
        )

    def test_evidence_free_unverified_claim_requires_index_entry(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["claim_ledger"]["claims"][0]["evidence_refs"] = []
        invalid_record["claim_ledger"]["claims"][0]["verified"] = False

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertIn(
            "claim_ledger.claims[0]: evidence-free claim must appear in unverified_claim_ids",
            errors,
        )

    def test_recorded_memory_requires_constitution_evidence_refs(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["memory_update"]["constitution"]["evidence_refs"] = []

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertIn(
            "memory_update.constitution.evidence_refs must contain at least 1 item(s)",
            errors,
        )

    def test_whqr_replay_binding_rejects_mismatched_replay_ref(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["closure"]["whqr_replay_binding"] = {
            "replay_ref": "whqr://replay/wrong-canonical-hash",
            "canonical_hash": "expected-canonical-hash",
            "semantics_hash": "sha256:expected-semantics",
            "version": "0.1.0",
        }

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 2)
        self.assertIn(
            "closure.whqr_replay_binding.replay_ref must bind canonical_hash",
            errors,
        )
        self.assertIn(
            "closure receipt confirms must bind closure state, reconciliation_ref, memory_ref, and whqr_replay_binding",
            errors,
        )
        self.assertEqual(
            "whqr://replay/wrong-canonical-hash",
            invalid_record["closure"]["whqr_replay_binding"]["replay_ref"],
        )

    def test_whqr_replay_binding_rejects_unsupported_fields(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["closure"]["whqr_replay_binding"] = {
            "replay_ref": "whqr://replay/expected-canonical-hash",
            "canonical_hash": "expected-canonical-hash",
            "semantics_hash": "sha256:expected-semantics",
            "version": "0.1.0",
            "authority_override": "not-permitted",
        }

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 2)
        self.assertIn(
            "closure.whqr_replay_binding contains unsupported field(s): authority_override",
            errors,
        )
        self.assertIn(
            "closure receipt confirms must bind closure state, reconciliation_ref, memory_ref, and whqr_replay_binding",
            errors,
        )
        self.assertEqual(
            "not-permitted",
            invalid_record["closure"]["whqr_replay_binding"]["authority_override"],
        )

    def test_whqr_replay_binding_rejects_unhashed_semantics_ref(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["closure"]["whqr_replay_binding"] = {
            "replay_ref": "whqr://replay/expected-canonical-hash",
            "canonical_hash": "expected-canonical-hash",
            "semantics_hash": "expected-semantics",
            "version": "0.1.0",
        }

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 2)
        self.assertIn(
            "closure.whqr_replay_binding.semantics_hash must start with sha256:",
            errors,
        )
        self.assertIn(
            "closure receipt confirms must bind closure state, reconciliation_ref, memory_ref, and whqr_replay_binding",
            errors,
        )
        self.assertEqual(
            "expected-semantics",
            invalid_record["closure"]["whqr_replay_binding"]["semantics_hash"],
        )

    def test_whqr_replay_binding_rejects_non_object_binding(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["closure"]["whqr_replay_binding"] = (
            "whqr://replay/not-a-binding-object"
        )

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertIn(
            "closure.whqr_replay_binding must be null or an object",
            errors,
        )
        self.assertNotIn(
            "closure receipt confirms must bind closure state, reconciliation_ref, memory_ref, and whqr_replay_binding",
            errors,
        )
        self.assertEqual(
            "whqr://replay/not-a-binding-object",
            invalid_record["closure"]["whqr_replay_binding"],
        )

    def test_memory_constitution_rejects_allowed_forbidden_use_overlap(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["memory_update"]["constitution"]["forbidden_uses"].append(
            "learning"
        )

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertIn(
            "memory_update.constitution allowed_uses and forbidden_uses overlap: learning",
            errors,
        )

    def test_execution_rejects_failed_fracture_report(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        check = invalid_record["fracture_report"]["checks"][0]
        check["status"] = "failed"
        check["proof_state"] = "Fail"
        check["reason_code"] = "policy_conflict"
        check["blocking"] = True
        invalid_record["fracture_report"]["status"] = "failed"
        invalid_record["fracture_report"]["blocking_check_ids"] = [check["check_id"]]
        next(
            stage
            for stage in invalid_record["pipeline_stages"]
            if stage["stage_kind"] == "fracture"
        )["status"] = "blocked"

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertIn("execution requires fracture_report.status passed", errors)

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
        self.assertTrue(
            any("effect-bearing action requires" in error for error in errors)
        )

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
        self.assertIn(
            "high-risk allow requires action_envelope.capability_refs", errors
        )

    def test_raw_chain_of_thought_field_is_rejected(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["chain_of_thought"] = "private reasoning must not be serialized"

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertTrue(
            any("chain_of_thought is prohibited" in error for error in errors)
        )

    def test_allow_decision_rejects_blocked_guard(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["admission_guards"][0]["verdict"] = "blocked"
        invalid_record["admission_guards"][0]["proof_state"] = "Fail"

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertTrue(
            any(
                "allow requires every admission guard to pass" in error
                for error in errors
            )
        )
        self.assertEqual("blocked", invalid_record["admission_guards"][0]["verdict"])

    def test_blocked_decision_cannot_execute(self) -> None:
        record = VALIDATOR.load_json_object(BLOCKED_EXAMPLE_PATH, "blocked UAO")
        invalid_record = copy.deepcopy(record)
        execution_stage = next(
            stage
            for stage in invalid_record["pipeline_stages"]
            if stage["stage_kind"] == "execution"
        )
        execution_stage["status"] = "completed"
        execution_stage["failure_reason"] = None
        invalid_record["decision"]["execution_allowed"] = True

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 2)
        self.assertTrue(
            any(
                "non-allow status requires execution_allowed false" in error
                for error in errors
            )
        )
        self.assertTrue(
            any(
                "non-allow status cannot complete execution stage" in error
                for error in errors
            )
        )

    def test_missing_required_guard_is_rejected(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["admission_guards"] = [
            guard
            for guard in invalid_record["admission_guards"]
            if guard["guard"] != "receipt_emittable"
        ]

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 1)
        self.assertIn("missing required admission guard: receipt_emittable", errors)
        self.assertEqual(10, len(invalid_record["admission_guards"]))

    def test_raw_reasoning_exposure_is_rejected(self) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["raw_reasoning_included"] = True
        invalid_record["exposure_boundary"]["blocked_payload_classes"].remove(
            "raw_private_reasoning"
        )

        errors = VALIDATOR.validate_orchestration(invalid_record)

        self.assertGreaterEqual(len(errors), 2)
        self.assertTrue(
            any("raw_reasoning_included must be false" in error for error in errors)
        )
        self.assertTrue(
            any(
                "blocked_payload_classes must include raw_private_reasoning" in error
                for error in errors
            )
        )

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
                    "--json",
                ]
            )

        report = json.loads(stdout_buffer.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual(
            "universal_action_orchestration_validation_receipt", report["receipt_id"]
        )
        self.assertTrue(report["terminal_closure_required"])
        self.assertTrue(report["receipt_is_not_terminal_closure"])
        self.assertTrue(report["valid"])
        self.assertEqual("passed", report["status"])
        self.assertEqual(
            "schemas/universal_action_orchestration.schema.json", report["schema_path"]
        )
        self.assertEqual(
            "docs/UNIVERSAL_ACTION_ORCHESTRATION.md", report["document_path"]
        )
        self.assertEqual(
            [
                "examples/universal_action_orchestration.allowed_status_publish.json",
                "examples/universal_action_orchestration.blocked_invoice_payment.json",
                "examples/uao/blocked_missing_approval.json",
                "examples/uao/deferred_stale_evidence.json",
                "examples/uao/simulated_low_risk_readonly.json",
            ],
            report["example_paths"],
        )
        self.assertEqual(5, report["example_count"])
        self.assertEqual(6, report["check_count"])
        self.assertEqual(0, report["error_count"])
        self.assertEqual([], report["errors"])
        self.assertTrue(all(check["passed"] for check in report["checks"]))
        self.assertIn(
            "universal_action_orchestration_runtime_bypass_detector",
            {check["name"] for check in report["checks"]},
        )

    def test_build_validation_report_sanitizes_load_error_paths_without_receipt_claim(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            missing_schema_path = temporary_path / "secret" / "missing.schema.json"

            report = VALIDATOR.build_validation_report(
                missing_schema_path,
                (ALLOWED_EXAMPLE_PATH,),
                DOCUMENT_PATH,
            )

            serialized_report = json.dumps(report, sort_keys=True)
            self.assertFalse(report["valid"])
            self.assertEqual("missing.schema.json", report["schema_path"])
            self.assertEqual(1, report["error_count"])
            self.assertTrue(
                any("missing.schema.json" in error for error in report["errors"])
            )
            self.assertNotIn(str(temporary_path), serialized_report)
            self.assertNotIn(str(missing_schema_path), serialized_report)

    def test_cli_json_receipt_rejects_noncanonical_example_scope_without_writing(
        self,
    ) -> None:
        record = VALIDATOR.load_json_object(ALLOWED_EXAMPLE_PATH, "allowed UAO")
        invalid_record = copy.deepcopy(record)
        invalid_record["chain_of_thought"] = "private reasoning must not be serialized"

        with tempfile.TemporaryDirectory() as temporary_directory:
            invalid_path = Path(temporary_directory) / "invalid_uao.json"
            receipt_path = (
                WORKSPACE_ROOT / ".tmp" / "uao-validation-failed-receipt.json"
            )
            receipt_path.unlink(missing_ok=True)
            invalid_path.write_text(json.dumps(invalid_record), encoding="utf-8")
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()

            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
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

            self.assertEqual(1, exit_code)
            self.assertEqual("", stdout_buffer.getvalue())
            self.assertIn("receipt-scope", stderr_buffer.getvalue())
            self.assertIn(
                "canonical UAO fixture set and order", stderr_buffer.getvalue()
            )
            self.assertFalse(receipt_path.exists())
            self.assertTrue(invalid_path.exists())

    def test_receipt_path_rejects_workspace_escape_and_non_json_suffix(self) -> None:
        report = VALIDATOR.build_validation_report()

        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory) / "workspace"
            workspace_root.mkdir()
            receipt_path = VALIDATOR.write_validation_report(
                report, Path(".tmp/uao-receipt.json"), workspace_root
            )

            self.assertEqual("uao-receipt.json", receipt_path.name)
            self.assertTrue(receipt_path.exists())
            self.assertEqual(
                workspace_root.resolve(), receipt_path.parents[1].resolve()
            )
            with self.assertRaises(ValueError):
                VALIDATOR.resolve_validation_receipt_path(
                    Path("../uao-receipt.json"), workspace_root
                )
            with self.assertRaises(ValueError):
                VALIDATOR.resolve_validation_receipt_path(
                    Path(".tmp/uao-receipt.txt"), workspace_root
                )

    def test_write_validation_report_rejects_noncanonical_report_scope(self) -> None:
        report = VALIDATOR.build_validation_report(
            SCHEMA_PATH, (ALLOWED_EXAMPLE_PATH,), DOCUMENT_PATH
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace_root = Path(temporary_directory) / "workspace"
            workspace_root.mkdir()

            with self.assertRaises(ValueError) as raised:
                VALIDATOR.write_validation_report(
                    report, Path(".tmp/uao-receipt.json"), workspace_root
                )

            self.assertIn("canonical UAO fixture set and order", str(raised.exception))
            self.assertFalse((workspace_root / ".tmp" / "uao-receipt.json").exists())

    def test_cli_rejects_receipt_path_escape_without_writing(self) -> None:
        escaped_receipt_path = (
            WORKSPACE_ROOT.parent / "uao-validation-escaped-receipt.json"
        )
        escaped_receipt_path.unlink(missing_ok=True)

        exit_code = VALIDATOR.main(
            [
                "--schema",
                str(SCHEMA_PATH),
                "--document",
                str(DOCUMENT_PATH),
                "--json",
                "--receipt-path",
                str(escaped_receipt_path),
            ]
        )

        self.assertEqual(1, exit_code)
        self.assertFalse(escaped_receipt_path.exists())

    def test_cli_json_receipt_rejects_noncanonical_schema_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            missing_schema_path = temporary_path / "secret" / "missing.schema.json"
            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()

            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
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

            self.assertEqual(1, exit_code)
            self.assertEqual("", stdout_buffer.getvalue())
            self.assertIn("receipt-scope", stderr_buffer.getvalue())
            self.assertIn("canonical UAO schema", stderr_buffer.getvalue())
            self.assertNotIn(str(temporary_path), stderr_buffer.getvalue())

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
