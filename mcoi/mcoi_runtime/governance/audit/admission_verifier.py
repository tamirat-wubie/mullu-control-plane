"""Purpose: verify audited governed operations have prior admission receipts.
Governance scope: external audit/proof join verification for guarded actions.
Dependencies: AuditEntry shape and serialized ProofBridge payloads.
Invariants:
  - Required governed audit actions must carry a request proof reference.
  - Referenced receipts must exist in the supplied proof bundle.
  - Receipt endpoint, tenant, decision, state transition, and guard verdicts
    must agree with the audit entry.
  - Unknown or malformed proof state is reported as a bounded finding.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from mcoi_runtime.governance.audit.trail import AuditEntry


DEFAULT_GOVERNED_ACTION_ENDPOINTS: dict[str, str] = {
    "session.llm": "session/llm",
    "session.execute": "session/execute",
    "session.query": "session/query",
}


@dataclass(frozen=True, slots=True)
class AdmissionVerificationFinding:
    """One bounded admission verification finding."""

    entry_id: str
    sequence: int
    action: str
    reason: str
    detail: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AdmissionVerificationReport:
    """External verifier report for audit entries and receipt proofs."""

    status: str
    checked_entries: int
    skipped_entries: int
    admitted_entries: int
    findings: tuple[AdmissionVerificationFinding, ...]

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    def to_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-compatible report."""
        return {
            "status": self.status,
            "checked_entries": self.checked_entries,
            "skipped_entries": self.skipped_entries,
            "admitted_entries": self.admitted_entries,
            "findings": [
                {
                    "entry_id": finding.entry_id,
                    "sequence": finding.sequence,
                    "action": finding.action,
                    "reason": finding.reason,
                    "detail": dict(finding.detail),
                }
                for finding in self.findings
            ],
        }


def verify_audit_admission(
    audit_entries: Iterable[AuditEntry | Mapping[str, Any]],
    proof_payloads: Iterable[Mapping[str, Any]],
    *,
    governed_action_endpoints: Mapping[str, str] | None = None,
) -> AdmissionVerificationReport:
    """Verify governed audit entries join to allowed request receipts."""
    action_endpoints = dict(governed_action_endpoints or DEFAULT_GOVERNED_ACTION_ENDPOINTS)
    proof_index = _index_proofs_by_receipt_id(proof_payloads)
    findings: list[AdmissionVerificationFinding] = []
    checked_entries = 0
    skipped_entries = 0
    admitted_entries = 0

    for entry_source in audit_entries:
        entry = _audit_entry_view(entry_source)
        expected_endpoint = action_endpoints.get(entry["action"])
        if expected_endpoint is None:
            skipped_entries += 1
            continue

        checked_entries += 1
        entry_findings = _verify_entry(entry, expected_endpoint, proof_index)
        findings.extend(entry_findings)
        if not entry_findings:
            admitted_entries += 1

    return AdmissionVerificationReport(
        status="passed" if not findings else "failed",
        checked_entries=checked_entries,
        skipped_entries=skipped_entries,
        admitted_entries=admitted_entries,
        findings=tuple(findings),
    )


def _verify_entry(
    entry: Mapping[str, Any],
    expected_endpoint: str,
    proof_index: Mapping[str, Mapping[str, Any]],
) -> list[AdmissionVerificationFinding]:
    findings: list[AdmissionVerificationFinding] = []
    detail = _mapping(entry.get("detail"))
    proof_ref = _mapping(detail.get("request_envelope_proof"))
    if not proof_ref:
        return [_finding(entry, "missing_request_envelope_proof", {"expected_endpoint": expected_endpoint})]

    receipt_id = _text(proof_ref.get("proof_receipt_id"))
    proof_hash = _text(proof_ref.get("proof_hash"))
    if not receipt_id:
        findings.append(_finding(entry, "missing_proof_receipt_id", {"expected_endpoint": expected_endpoint}))
    if not proof_hash:
        findings.append(_finding(entry, "missing_proof_hash", {"expected_endpoint": expected_endpoint}))
    if _text(proof_ref.get("endpoint")) != expected_endpoint:
        findings.append(
            _finding(
                entry,
                "proof_endpoint_mismatch",
                {"expected_endpoint": expected_endpoint, "actual_endpoint": _text(proof_ref.get("endpoint"))},
            )
        )
    if _text(proof_ref.get("decision")) != "allowed":
        findings.append(_finding(entry, "proof_decision_not_allowed", {"decision": _text(proof_ref.get("decision"))}))
    if findings:
        return findings

    proof_payload = proof_index.get(receipt_id)
    if proof_payload is None:
        return [_finding(entry, "proof_receipt_not_found", {"proof_receipt_id": receipt_id})]

    receipt = _mapping(proof_payload.get("receipt"))
    proof_audit = _mapping(proof_payload.get("audit_record"))
    if _text(proof_payload.get("endpoint")) != expected_endpoint:
        findings.append(
            _finding(
                entry,
                "serialized_proof_endpoint_mismatch",
                {"expected_endpoint": expected_endpoint, "actual_endpoint": _text(proof_payload.get("endpoint"))},
            )
        )
    if _text(proof_payload.get("decision")) != "allowed":
        findings.append(_finding(entry, "serialized_proof_decision_not_allowed", {"decision": _text(proof_payload.get("decision"))}))
    if _text(proof_payload.get("tenant_id")) != _text(entry.get("tenant_id")):
        findings.append(
            _finding(
                entry,
                "tenant_mismatch",
                {"audit_tenant": _text(entry.get("tenant_id")), "proof_tenant": _text(proof_payload.get("tenant_id"))},
            )
        )
    if _text(proof_audit.get("actor_id")) and _text(proof_audit.get("actor_id")) != _text(entry.get("actor_id")):
        findings.append(
            _finding(
                entry,
                "actor_mismatch",
                {"audit_actor": _text(entry.get("actor_id")), "proof_actor": _text(proof_audit.get("actor_id"))},
            )
        )
    if _text(receipt.get("receipt_hash")) != proof_hash:
        findings.append(_finding(entry, "proof_hash_mismatch", {"proof_receipt_id": receipt_id}))
    if _text(receipt.get("to_state")) != "allowed":
        findings.append(_finding(entry, "receipt_state_not_allowed", {"to_state": _text(receipt.get("to_state"))}))
    if _text(receipt.get("action")) != "all_guards_passed":
        findings.append(_finding(entry, "receipt_action_not_admission", {"receipt_action": _text(receipt.get("action"))}))

    guard_verdicts = receipt.get("guard_verdicts")
    if not isinstance(guard_verdicts, list) or not guard_verdicts:
        findings.append(_finding(entry, "guard_verdicts_missing", {"proof_receipt_id": receipt_id}))
    else:
        failed_guards = [
            _text(_mapping(verdict).get("guard_id"))
            for verdict in guard_verdicts
            if _mapping(verdict).get("passed") is not True
        ]
        if failed_guards:
            findings.append(_finding(entry, "guard_verdicts_not_all_passed", {"failed_guards": failed_guards}))

    return findings


def _index_proofs_by_receipt_id(proof_payloads: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for payload in proof_payloads:
        receipt = _mapping(payload.get("receipt"))
        receipt_id = _text(receipt.get("receipt_id"))
        if receipt_id:
            indexed[receipt_id] = payload
    return indexed


def _audit_entry_view(entry: AuditEntry | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(entry, AuditEntry):
        return {
            "entry_id": entry.entry_id,
            "sequence": entry.sequence,
            "action": entry.action,
            "actor_id": entry.actor_id,
            "tenant_id": entry.tenant_id,
            "detail": dict(entry.detail),
        }
    return {
        "entry_id": _text(entry.get("entry_id")),
        "sequence": _int(entry.get("sequence")),
        "action": _text(entry.get("action")),
        "actor_id": _text(entry.get("actor_id")),
        "tenant_id": _text(entry.get("tenant_id")),
        "detail": _mapping(entry.get("detail")),
    }


def _finding(entry: Mapping[str, Any], reason: str, detail: dict[str, Any]) -> AdmissionVerificationFinding:
    return AdmissionVerificationFinding(
        entry_id=_text(entry.get("entry_id")),
        sequence=_int(entry.get("sequence")),
        action=_text(entry.get("action")),
        reason=reason,
        detail=detail,
    )


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
