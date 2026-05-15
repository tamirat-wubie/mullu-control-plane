"""Purpose: verify external audit entries can be rejoined to admission proofs.
Governance scope: audit/proof cross-verifier for governed session actions.
Dependencies: AuditTrail, ProofBridge serialization, GovernedSession audit shape.
Invariants:
  - Governed audit actions carry request_envelope_proof.
  - Verifier fails closed on missing proof refs or missing receipt payloads.
  - Verifier rejects receipts whose guard verdicts are absent or failed.
  - Non-governed audit actions are skipped, not treated as admitted.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from mcoi_runtime.core.proof_bridge import ProofBridge
from mcoi_runtime.governance.audit.admission_verifier import verify_audit_admission
from mcoi_runtime.governance.audit.trail import AuditTrail


def _clock() -> str:
    return "2026-05-15T00:00:00Z"


def _admission_proof(endpoint: str = "session/query") -> dict[str, Any]:
    bridge = ProofBridge(clock=_clock)
    proof = bridge.certify_governance_decision(
        tenant_id="tenant-1",
        endpoint=endpoint,
        actor_id="actor-1",
        decision="allowed",
        guard_results=[
            {"guard_name": "policy", "allowed": True, "reason": "passed"},
            {"guard_name": "rbac", "allowed": True, "reason": "passed"},
            {"guard_name": "rate_limit", "allowed": True, "reason": "passed"},
        ],
    )
    return bridge.serialize_proof(proof)


def _audit_entry(proof_payload: dict[str, Any], *, action: str = "session.query"):
    receipt = proof_payload["receipt"]
    trail = AuditTrail(clock=_clock)
    return trail.record(
        action=action,
        actor_id="actor-1",
        tenant_id="tenant-1",
        target="documents",
        outcome="success",
        detail={
            "request_envelope_proof": {
                "endpoint": proof_payload["endpoint"],
                "decision": proof_payload["decision"],
                "proof_receipt_id": receipt["receipt_id"],
                "proof_hash": receipt["receipt_hash"],
            }
        },
    )


def test_verify_audit_admission_accepts_matching_receipt() -> None:
    proof_payload = _admission_proof()
    audit_entry = _audit_entry(proof_payload)

    report = verify_audit_admission([audit_entry], [proof_payload])

    assert report.passed is True
    assert report.checked_entries == 1
    assert report.admitted_entries == 1
    assert report.skipped_entries == 0
    assert report.findings == ()


def test_verify_audit_admission_rejects_missing_request_proof() -> None:
    trail = AuditTrail(clock=_clock)
    audit_entry = trail.record(
        action="session.query",
        actor_id="actor-1",
        tenant_id="tenant-1",
        target="documents",
        outcome="success",
        detail={"filters": {}},
    )

    report = verify_audit_admission([audit_entry], [])

    assert report.passed is False
    assert report.checked_entries == 1
    assert report.admitted_entries == 0
    assert report.findings[0].reason == "missing_request_envelope_proof"
    assert report.findings[0].detail["expected_endpoint"] == "session/query"


def test_verify_audit_admission_rejects_missing_receipt_payload() -> None:
    proof_payload = _admission_proof()
    audit_entry = _audit_entry(proof_payload)

    report = verify_audit_admission([audit_entry], [])

    assert report.passed is False
    assert report.checked_entries == 1
    assert report.admitted_entries == 0
    assert report.findings[0].reason == "proof_receipt_not_found"
    assert report.findings[0].detail["proof_receipt_id"] == proof_payload["receipt"]["receipt_id"]


def test_verify_audit_admission_rejects_failed_guard_verdict() -> None:
    proof_payload = _admission_proof()
    audit_entry = _audit_entry(proof_payload)
    failed_guard_payload = deepcopy(proof_payload)
    failed_guard_payload["receipt"]["guard_verdicts"][1]["passed"] = False

    report = verify_audit_admission([audit_entry], [failed_guard_payload])

    assert report.passed is False
    assert report.checked_entries == 1
    assert report.admitted_entries == 0
    assert report.findings[0].reason == "guard_verdicts_not_all_passed"
    assert report.findings[0].detail["failed_guards"] == ["rbac"]


def test_verify_audit_admission_skips_unmapped_audit_actions() -> None:
    proof_payload = _admission_proof()
    audit_entry = _audit_entry(proof_payload, action="session.close")

    report = verify_audit_admission([audit_entry], [proof_payload])

    assert report.passed is True
    assert report.checked_entries == 0
    assert report.skipped_entries == 1
    assert report.admitted_entries == 0
    assert report.to_dict()["findings"] == []
