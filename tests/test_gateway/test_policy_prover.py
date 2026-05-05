"""Gateway policy prover tests.

Purpose: verify bounded policy proof reports and counterexample witnesses.
Governance scope: policy invariant proof, counterexample reporting, schema
    contract, and proof non-mutation metadata.
Dependencies: gateway.policy_prover and schemas/policy_proof_report.schema.json.
Invariants:
  - Passing cases produce proved reports with no counterexamples.
  - Violations produce concrete counterexamples.
  - Empty proof inputs are rejected.
  - Schema contract marks reports as bounded and policy weakening as forbidden.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from gateway.policy_prover import PolicyProofCase, PolicyProofInvariant, PolicyProver


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "policy_proof_report.schema.json"


def test_policy_prover_emits_proved_report_for_passing_cases() -> None:
    report = PolicyProver().prove(
        policy_id="tenant-write-policy",
        invariants=(_tenant_write_invariant(),),
        cases=(
            PolicyProofCase(
                case_id="case-allowed-write",
                subject_id="tenant-a/user-1",
                attributes={
                    "tenant_bound": True,
                    "approval_required": True,
                    "write_scope": "tenant",
                },
                evidence_refs=("proof://case-allowed-write",),
            ),
        ),
        evidence_refs=("proof://policy-source",),
    )

    assert report.status == "proved"
    assert report.counterexample_count == 0
    assert report.counterexamples == ()
    assert report.proven_invariants == ("tenant_write_requires_approval",)
    assert report.metadata["policy_weakening_allowed"] is False
    assert report.report_hash


def test_policy_prover_reports_counterexamples_for_missing_or_mismatched_fields() -> None:
    report = PolicyProver().prove(
        policy_id="tenant-write-policy",
        invariants=(_tenant_write_invariant(),),
        cases=(
            PolicyProofCase(
                case_id="case-unbound-write",
                subject_id="tenant-a/user-2",
                attributes={"tenant_bound": False, "write_scope": "global"},
                evidence_refs=("proof://case-unbound-write",),
            ),
        ),
    )
    reasons = {counterexample.reason for counterexample in report.counterexamples}

    assert report.status == "counterexample_found"
    assert report.counterexample_count == 3
    assert "missing_required_field:approval_required" in reasons
    assert "expected_value_mismatch:tenant_bound" in reasons
    assert "expected_value_mismatch:write_scope" in reasons
    assert report.proven_invariants == ()


def test_policy_prover_rejects_empty_inputs() -> None:
    prover = PolicyProver()

    with pytest.raises(ValueError, match="policy_invariants_required"):
        prover.prove(policy_id="policy", invariants=(), cases=(_valid_case(),))

    with pytest.raises(ValueError, match="policy_cases_required"):
        prover.prove(policy_id="policy", invariants=(_tenant_write_invariant(),), cases=())

    with pytest.raises(ValueError, match="policy_id_required"):
        prover.prove(policy_id="", invariants=(_tenant_write_invariant(),), cases=(_valid_case(),))


def test_policy_proof_report_schema_contract_is_bounded_and_non_weakening() -> None:
    report = PolicyProver().prove(
        policy_id="tenant-write-policy",
        invariants=(_tenant_write_invariant(),),
        cases=(_valid_case(),),
    )
    payload = asdict(report)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert set(schema["required"]).issubset(payload)
    assert schema["$id"] == "urn:mullusi:schema:policy-proof-report:1"
    assert schema["properties"]["metadata"]["properties"]["proof_is_bounded"]["const"] is True
    assert schema["properties"]["metadata"]["properties"]["policy_weakening_allowed"]["const"] is False
    assert payload["metadata"]["proof_is_bounded"] is True


def _tenant_write_invariant() -> PolicyProofInvariant:
    return PolicyProofInvariant(
        invariant_id="tenant_write_requires_approval",
        description="Tenant writes require tenant binding, approval, and tenant scope.",
        required_fields=("tenant_bound", "approval_required", "write_scope"),
        expected_values={
            "tenant_bound": True,
            "approval_required": True,
            "write_scope": "tenant",
        },
    )


def _valid_case() -> PolicyProofCase:
    return PolicyProofCase(
        case_id="case-valid",
        subject_id="tenant-a/user-1",
        attributes={"tenant_bound": True, "approval_required": True, "write_scope": "tenant"},
    )
