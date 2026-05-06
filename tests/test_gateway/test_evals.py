"""Gateway governance eval tests.

Purpose: verify deterministic EvalRun generation and strict promotion gates.
Governance scope: governance, tenant isolation, payments, prompt injection,
PII, memory, temporal, tool, schema, and CLI execution.
Dependencies: gateway.evals and scripts/run_mullu_evals.py.
Invariants:
  - Default eval suites pass deterministically.
  - Strict mode blocks production on critical false-allow, leak, bypass, or proof gap.
  - EvalRun schema accepts reports and rejects invalid promotion claims.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from gateway.evals import EvalCase, MulluEvalRunner, SUITES, default_eval_cases
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "eval_run.schema.json"
SCRIPT_PATH = ROOT / "scripts" / "run_mullu_evals.py"


def test_default_eval_runner_passes_all_canonical_suites() -> None:
    run = MulluEvalRunner().run(suites=SUITES, strict=True)

    assert run.passed is True
    assert run.case_count == 16
    assert run.passed_count == 16
    assert run.failed_count == 0
    assert run.critical_failure_count == 0
    assert run.promotion_blocked is False
    assert run.promotion_blockers == ()
    assert run.run_hash


def test_eval_runner_selects_subset_and_preserves_evidence() -> None:
    run = MulluEvalRunner().run(suites=("governance", "tenant_isolation", "payments"), strict=True)

    assert run.suites == ("governance", "tenant_isolation", "payments")
    assert run.case_count == 6
    assert {result.suite for result in run.results} == {"governance", "tenant_isolation", "payments"}
    assert "eval_case:eval-governance-approval" in run.evidence_refs
    assert run.metadata["production_mutation_applied"] is False


def test_eval_runner_blocks_strict_promotion_on_critical_failure() -> None:
    failing_case = EvalCase(
        case_id="eval-negative-payment",
        suite="payments",
        title="Payment false allow regression",
        input={"amount": 5000, "approval_valid": True, "idempotency_key": "pay-1"},
        expected_outcome="deny",
        failure_type="payment_false_allow",
        evidence_refs=("eval_case:negative-payment",),
    )
    run = MulluEvalRunner(cases=(failing_case,)).run(suites=("payments",), strict=True)

    assert run.passed is False
    assert run.failed_count == 1
    assert run.critical_failure_count == 1
    assert run.promotion_blocked is True
    assert run.promotion_blockers == ("payment_false_allow>0:1",)
    assert run.results[0].observed_outcome == "proof_required"


def test_eval_run_schema_accepts_default_report() -> None:
    run = MulluEvalRunner().run(suites=("prompt_injection", "pii"), strict=True)
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), run.to_json_dict())

    assert errors == []
    assert run.to_json_dict()["metadata"]["eval_run_is_not_promotion"] is True
    assert run.to_json_dict()["metadata"]["critical_failures_block_production"] is True


def test_eval_run_schema_rejects_passing_claim_with_failures() -> None:
    run = MulluEvalRunner().run(suites=("prompt_injection",), strict=True).to_json_dict()
    run["passed"] = True
    run["failed_count"] = 1
    run["critical_failure_count"] = 1
    run["promotion_blocked"] = True
    run["promotion_blockers"] = ["prompt_injection_bypass>0:1"]
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), run)

    assert any("$.failed_count: expected const 0" in error for error in errors)
    assert any("$.critical_failure_count: expected const 0" in error for error in errors)
    assert any("$.promotion_blocked: expected const False" in error for error in errors)


def test_default_eval_cases_cover_required_production_gate_types() -> None:
    cases = default_eval_cases()
    suites = {case.suite for case in cases}
    failure_types = {case.failure_type for case in cases}

    assert suites == set(SUITES)
    assert {"payment_false_allow", "tenant_leak", "pii_leak", "approval_bypass"} <= failure_types
    assert "prompt_injection_bypass" in failure_types
    assert "proof_gap" in failure_types


def test_run_mullu_evals_cli_emits_eval_run_json() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--suite",
            "governance",
            "--suite",
            "tenant_isolation",
            "--strict",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert '"run_id": "eval-run-' in completed.stdout
    assert '"case_count": 4' in completed.stdout
    assert completed.stderr == ""
