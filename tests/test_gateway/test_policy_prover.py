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

from gateway.policy_prover import PolicyCounterexample, PolicyProofCase, PolicyProofInvariant, PolicyProofReport, PolicyProver


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


def test_payment_requires_approval_counterexample() -> None:
    report = _counterexample_report(
        invariant_id="payment_requires_approval",
        required_fields=("approval_id",),
        expected_values={"approval_state": "approved"},
        case_attributes={"approval_state": "missing"},
    )
    reasons = {counterexample.reason for counterexample in report.counterexamples}

    assert report.status == "counterexample_found"
    assert "missing_required_field:approval_id" in reasons
    assert "expected_value_mismatch:approval_state" in reasons


def test_tenant_isolation_counterexample() -> None:
    report = _counterexample_report(
        invariant_id="tenant_isolation",
        required_fields=("tenant_bound", "tenant_id_matches"),
        expected_values={"tenant_bound": True, "tenant_id_matches": True},
        case_attributes={"tenant_bound": False, "tenant_id_matches": False},
    )
    reasons = {counterexample.reason for counterexample in report.counterexamples}

    assert report.counterexample_count == 2
    assert "expected_value_mismatch:tenant_bound" in reasons
    assert "expected_value_mismatch:tenant_id_matches" in reasons


def test_shell_requires_sandbox_counterexample() -> None:
    report = _counterexample_report(
        invariant_id="shell_requires_sandbox",
        required_fields=("sandbox_enabled", "argv_only"),
        expected_values={"sandbox_enabled": True, "argv_only": True},
        case_attributes={"sandbox_enabled": False, "argv_only": False},
    )
    reasons = {counterexample.reason for counterexample in report.counterexamples}

    assert report.status == "counterexample_found"
    assert "expected_value_mismatch:sandbox_enabled" in reasons
    assert "expected_value_mismatch:argv_only" in reasons


def test_provider_url_approved_counterexample() -> None:
    report = _counterexample_report(
        invariant_id="provider_url_approved",
        required_fields=("provider_url_approved", "provider_origin"),
        expected_values={"provider_url_approved": True},
        case_attributes={"provider_url_approved": False, "provider_origin": "external"},
    )
    reasons = {counterexample.reason for counterexample in report.counterexamples}

    assert report.counterexample_count == 1
    assert report.counterexamples[0].invariant_id == "provider_url_approved"
    assert "expected_value_mismatch:provider_url_approved" in reasons


def test_memory_requires_admission_counterexample() -> None:
    report = _counterexample_report(
        invariant_id="memory_requires_admission",
        required_fields=("memory_admission_id", "memory_use_approved"),
        expected_values={"memory_use_approved": True},
        case_attributes={"memory_use_approved": False},
    )
    reasons = {counterexample.reason for counterexample in report.counterexamples}

    assert report.counterexample_count == 2
    assert "missing_required_field:memory_admission_id" in reasons
    assert "expected_value_mismatch:memory_use_approved" in reasons


def test_unknown_property_fails_closed() -> None:
    report = _counterexample_report(
        invariant_id="unknown_property_fails_closed",
        required_fields=("unknown_hard_safety_property",),
        expected_values={},
        case_attributes={"declared_property": "soft_utility"},
    )
    counterexample = report.counterexamples[0]

    assert report.status == "counterexample_found"
    assert counterexample.reason == "missing_required_field:unknown_hard_safety_property"
    assert report.proven_invariants == ()


def test_policy_prover_rejects_empty_inputs() -> None:
    prover = PolicyProver()

    with pytest.raises(ValueError, match="policy_invariants_required"):
        prover.prove(policy_id="policy", invariants=(), cases=(_valid_case(),))

    with pytest.raises(ValueError, match="policy_cases_required"):
        prover.prove(policy_id="policy", invariants=(_tenant_write_invariant(),), cases=())

    with pytest.raises(ValueError, match="policy_id_required"):
        prover.prove(policy_id="", invariants=(_tenant_write_invariant(),), cases=(_valid_case(),))


def test_policy_proof_evidence_refs_reject_non_string_values() -> None:
    with pytest.raises(ValueError, match="^evidence_refs_invalid$"):
        PolicyProofCase(
            case_id="case-invalid-evidence",
            subject_id="tenant-a/user-1",
            attributes={"tenant_bound": True},
            evidence_refs=({"ref": "proof://case"},),  # type: ignore[arg-type]
        )

    with pytest.raises(ValueError, match="^evidence_refs_invalid$"):
        PolicyCounterexample(
            invariant_id="tenant_write_requires_approval",
            case_id="case-invalid-evidence",
            subject_id="tenant-a/user-1",
            reason="missing_required_field:approval_required",
            evidence_refs=(1,),  # type: ignore[arg-type]
        )

    with pytest.raises(ValueError, match="^evidence_refs_invalid$"):
        PolicyProofReport(
            report_id="report-invalid-evidence",
            policy_id="tenant-write-policy",
            status="proved",
            invariant_count=1,
            case_count=1,
            counterexample_count=0,
            proven_invariants=("tenant_write_requires_approval",),
            counterexamples=(),
            evidence_refs=(object(),),  # type: ignore[arg-type]
        )


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


def test_policy_proof_report_schema_valid() -> None:
    report = PolicyProver().prove(
        policy_id="tenant-write-policy",
        invariants=(_tenant_write_invariant(),),
        cases=(_valid_case(),),
        evidence_refs=("proof://policy-source",),
    )
    payload = asdict(report)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["$id"] == "urn:mullusi:schema:policy-proof-report:1"
    assert set(schema["required"]).issubset(payload)
    assert payload["report_id"].startswith("policy-proof-")


def _counterexample_report(
    *,
    invariant_id: str,
    required_fields: tuple[str, ...],
    expected_values: dict[str, object],
    case_attributes: dict[str, object],
):
    return PolicyProver().prove(
        policy_id=f"{invariant_id}-policy",
        invariants=(
            PolicyProofInvariant(
                invariant_id=invariant_id,
                description=f"Prove {invariant_id}.",
                required_fields=required_fields,
                expected_values=expected_values,
            ),
        ),
        cases=(
            PolicyProofCase(
                case_id=f"{invariant_id}-case",
                subject_id="tenant-a/agent-1",
                attributes=case_attributes,
                evidence_refs=(f"proof://{invariant_id}",),
            ),
        ),
    )


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
