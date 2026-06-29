"""Gateway causal evidence ledger tests.

Purpose: verify source authority, evidence admission, claim readiness,
    conflict preservation, proof-safe exposure, challenge records, and
    append-only event-chain continuity.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.evidence_ledger.
Invariants:
  - Claims are judged only through evidence, authority, conflict, and missing
    evidence checks.
  - Rejected evidence and rejected links are append-only events.
  - Proof-only exposure never leaks raw artifact payloads.
  - Audit receipts replay a verified event chain.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from gateway.evidence_ledger import (
    AdmissibilityState,
    ClaimStatus,
    EvidenceKind,
    EvidenceLedgerKernel,
    ExpectedEvidenceProfile,
    ExposureViewType,
    RelationType,
    SourceAuthority,
)
from gateway.evidence_ledger_read_model import (
    EvidenceLedgerReadModelSourceError,
    build_foundation_evidence_ledger_read_model,
    load_repository_evidence_source,
)
from gateway.server import create_gateway_app


NOW = "2026-06-29T12:00:00+00:00"


def test_evidence_ledger_judges_claim_strongly_when_required_evidence_is_present() -> None:
    ledger = _ledger()
    _register_standard_sources(ledger)
    claim = _payment_claim(ledger)
    transaction = _ingest(ledger, kind=EvidenceKind.TRANSACTION, source_id="bank-feed", domain="payment_settlement")
    receipt = _ingest(ledger, kind=EvidenceKind.EMAIL, source_id="gmail", domain="email_receipt")
    invoice_state = _ingest(ledger, kind=EvidenceKind.API_RESPONSE, source_id="invoice-system", domain="invoice_status")

    transaction_link = _link(ledger, transaction.evidence.evidence_id, claim.claim_id, RelationType.SUPPORTS)
    receipt_link = _link(ledger, receipt.evidence.evidence_id, claim.claim_id, RelationType.SUPPORTS, weight=0.9)
    invoice_link = _link(ledger, invoice_state.evidence.evidence_id, claim.claim_id, RelationType.SUPPORTS, weight=0.95)
    judgment = ledger.judge_claim(claim_id=claim.claim_id, verifier="kernel-test")
    chain = ledger.verify_event_chain()

    assert transaction.accepted is True
    assert receipt.accepted is True
    assert invoice_state.evidence.admissibility_state == AdmissibilityState.ADMITTED
    assert transaction_link.accepted is True
    assert receipt_link.edge is not None
    assert invoice_link.edge is not None
    assert judgment.new_judgment == ClaimStatus.STRONGLY_SUPPORTED
    assert judgment.missing_evidence == ()
    assert judgment.source_registry_version == "source-authority-registry-v1"
    assert chain.verified is True
    assert len(ledger.history()) >= 8


def test_evidence_ledger_blocks_premature_judgment_when_required_evidence_is_missing() -> None:
    ledger = _ledger()
    _register_standard_sources(ledger)
    claim = ledger.create_claim(
        claim_id="claim-payment-missing",
        claim_type="payment_completed",
        proposition="Invoice 123 was paid.",
        subject="invoice-123",
        scope={"tenant_id": "tenant-1"},
        temporal_scope={"valid_at": NOW},
        expected_evidence_profile=ExpectedEvidenceProfile(
            required_evidence_kinds=(EvidenceKind.TRANSACTION, EvidenceKind.API_RESPONSE),
            minimum_independent_sources=2,
        ),
        actor_id="kernel-test",
    )
    transaction = _ingest(ledger, kind=EvidenceKind.TRANSACTION, source_id="bank-feed", domain="payment_settlement")

    link = _link(ledger, transaction.evidence.evidence_id, claim.claim_id, RelationType.SUPPORTS)
    judgment = ledger.judge_claim(claim_id=claim.claim_id, verifier="kernel-test")
    stored_claim = ledger.get_claim(claim.claim_id)

    assert link.accepted is True
    assert judgment.new_judgment == ClaimStatus.NOT_READY_TO_JUDGE
    assert judgment.missing_evidence == (EvidenceKind.API_RESPONSE.value,)
    assert "missing_required_evidence:api_response" in judgment.confidence_limits
    assert stored_claim is not None
    assert stored_claim.current_judgment == ClaimStatus.NOT_READY_TO_JUDGE
    assert ledger.verify_event_chain().verified is True


def test_evidence_ledger_preserves_conflict_and_refutes_with_decisive_authority() -> None:
    ledger = _ledger()
    _register_standard_sources(ledger)
    claim = ledger.create_claim(
        claim_id="claim-payment-conflict",
        claim_type="payment_completed",
        proposition="Invoice 123 was paid.",
        subject="invoice-123",
        scope={"tenant_id": "tenant-1"},
        temporal_scope={"valid_at": NOW},
        expected_evidence_profile=ExpectedEvidenceProfile(
            required_evidence_kinds=(EvidenceKind.TRANSACTION,),
            minimum_independent_sources=1,
        ),
        actor_id="kernel-test",
    )
    payment = _ingest(ledger, kind=EvidenceKind.TRANSACTION, source_id="bank-feed", domain="payment_settlement")
    reversal = _ingest(
        ledger,
        kind=EvidenceKind.TRANSACTION,
        source_id="bank-feed",
        domain="payment_settlement",
        raw_payload={"transaction_id": "txn-1", "state": "reversed"},
    )

    support = _link(ledger, payment.evidence.evidence_id, claim.claim_id, RelationType.SUPPORTS)
    refute = _link(ledger, reversal.evidence.evidence_id, claim.claim_id, RelationType.REFUTES, weight=0.95)
    conflicts = ledger.detect_conflicts(claim_id=claim.claim_id, actor_id="kernel-test")
    judgment = ledger.judge_claim(claim_id=claim.claim_id, verifier="kernel-test")

    assert support.accepted is True
    assert refute.accepted is True
    assert len(conflicts) == 1
    assert conflicts[0].status == "open"
    assert conflicts[0].severity == "high"
    assert judgment.new_judgment == ClaimStatus.REFUTED
    assert judgment.conflicts == (conflicts[0].conflict_id,)
    assert ledger.verify_event_chain().verified is True


def test_evidence_ledger_records_rejections_without_allowing_bad_evidence_to_support_claim() -> None:
    ledger = _ledger()
    ledger.register_source_authority(
        SourceAuthority(
            source_id="gmail",
            source_type="email_inbox",
            authority_domains=("email_receipt",),
            forbidden_domains=("payment_settlement",),
            reliability_score=0.7,
            verification_method="oauth_metadata",
            last_verified_at=NOW,
        ),
        actor_id="kernel-test",
    )
    claim = _payment_claim(ledger)

    rejected = _ingest(ledger, kind=EvidenceKind.EMAIL, source_id="gmail", domain="payment_settlement")
    link = _link(ledger, rejected.evidence.evidence_id, claim.claim_id, RelationType.SUPPORTS)
    judgment = ledger.judge_claim(claim_id=claim.claim_id, verifier="kernel-test")
    event_types = tuple(event.event_type for event in ledger.history())

    assert rejected.accepted is False
    assert rejected.evidence.admissibility_state == AdmissibilityState.INADMISSIBLE_FOR_JUDGMENT
    assert rejected.event.event_type == "evidence_rejected"
    assert link.accepted is False
    assert link.edge is None
    assert link.event.event_type == "claim_link_rejected"
    assert judgment.new_judgment == ClaimStatus.NOT_READY_TO_JUDGE
    assert "evidence_rejected" in event_types
    assert "claim_link_rejected" in event_types
    assert ledger.verify_event_chain().verified is True


def test_evidence_ledger_exposes_proof_only_view_without_raw_payload() -> None:
    ledger = _ledger()
    _register_standard_sources(ledger)
    claim = ledger.create_claim(
        claim_id="claim-proof-view",
        claim_type="payment_completed",
        proposition="Invoice 123 was paid.",
        subject="invoice-123",
        scope={"tenant_id": "tenant-1"},
        temporal_scope={"valid_at": NOW},
        expected_evidence_profile=ExpectedEvidenceProfile(
            required_evidence_kinds=(EvidenceKind.TRANSACTION,),
            minimum_independent_sources=1,
        ),
        actor_id="kernel-test",
    )
    transaction = _ingest(ledger, kind=EvidenceKind.TRANSACTION, source_id="bank-feed", domain="payment_settlement")
    _link(ledger, transaction.evidence.evidence_id, claim.claim_id, RelationType.SUPPORTS)
    judgment = ledger.judge_claim(claim_id=claim.claim_id, verifier="kernel-test")

    view = ledger.expose_claim(
        claim_id=claim.claim_id,
        actor_id="viewer-1",
        purpose="external_summary",
        view_type=ExposureViewType.PROOF_ONLY,
    )
    summary = view.evidence_summaries[0]

    assert judgment.new_judgment == ClaimStatus.STRONGLY_SUPPORTED
    assert view.view_type == ExposureViewType.PROOF_ONLY
    assert view.receipt_id == judgment.receipt_id
    assert summary["raw_hash"].startswith("sha256:")
    assert summary["canonical_hash"].startswith("sha256:")
    assert summary["redaction"] == "raw_payload_not_exposed"
    assert "raw_payload" not in summary
    assert "raw_reference" not in summary
    assert ledger.verify_event_chain().verified is True


def test_evidence_ledger_records_challenge_and_audit_receipt() -> None:
    ledger = _ledger()
    _register_standard_sources(ledger)
    claim = ledger.create_claim(
        claim_id="claim-challenge",
        claim_type="payment_completed",
        proposition="Invoice 123 was paid.",
        subject="invoice-123",
        scope={"tenant_id": "tenant-1"},
        temporal_scope={"valid_at": NOW},
        expected_evidence_profile=ExpectedEvidenceProfile(
            required_evidence_kinds=(EvidenceKind.TRANSACTION,),
            minimum_independent_sources=1,
        ),
        actor_id="kernel-test",
    )
    transaction = _ingest(ledger, kind=EvidenceKind.TRANSACTION, source_id="bank-feed", domain="payment_settlement")
    _link(ledger, transaction.evidence.evidence_id, claim.claim_id, RelationType.SUPPORTS)
    ledger.judge_claim(claim_id=claim.claim_id, verifier="kernel-test")

    challenge = ledger.challenge_judgment(
        claim_id=claim.claim_id,
        challenger_id="operator-review",
        reason="settlement reversal should be checked before closure",
    )
    audit = ledger.audit_claim(claim_id=claim.claim_id, actor_id="auditor-1")
    stored_claim = ledger.get_claim(claim.claim_id)

    assert challenge.status == "open"
    assert challenge.challenge_id in audit.challenge_ids
    assert transaction.evidence.evidence_id in audit.evidence_ids
    assert audit.chain_verified is True
    assert audit.head_hash == ledger.current_head_hash()
    assert stored_claim is not None
    assert stored_claim.challenge_state == "challenged"
    assert ledger.verify_event_chain().verified is True


def test_evidence_ledger_read_model_projection_is_foundation_bound() -> None:
    payload = build_foundation_evidence_ledger_read_model(generated_at=NOW)
    proof_summary = payload["evidence"]["proof_summaries"][0]
    invariants = payload["invariants"]

    assert payload["route_id"] == "causal_evidence_continuity_ledger_read_model"
    assert payload["status"] == "SolvedVerified"
    assert payload["read_only"] is True
    assert payload["repository_local_source"] is True
    assert payload["repository_source_ref"] == "examples/evidence_ledger/foundation_evidence_source.json"
    assert payload["repository_source_hash"].startswith("sha256:")
    assert payload["repository_source_loaded"] is True
    assert payload["foundation_fixture_is_not_live_evidence"] is True
    assert payload["route_is_not_write_path"] is True
    assert payload["external_effects_allowed"] is False
    assert payload["claim"]["judgment"] == ClaimStatus.STRONGLY_SUPPORTED.value
    assert payload["ledger"]["chain_verified"] is True
    assert proof_summary["raw_hash"].startswith("sha256:")
    assert "raw_payload" not in proof_summary
    assert "raw_reference" not in proof_summary
    assert invariants["proof_view_redacts_raw_payload"] is True
    assert invariants["repository_local_source_loaded"] is True
    assert invariants["repository_source_is_not_write_path"] is True


def test_evidence_ledger_gateway_route_is_read_only() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get("/api/v1/evidence-ledger/read-model")
    post_response = client.post("/api/v1/evidence-ledger/read-model", json={"action": "mutate"})
    payload = response.json()

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert payload["status"] == "SolvedVerified"
    assert payload["read_only"] is True
    assert payload["repository_local_source"] is True
    assert payload["repository_source_loaded"] is True
    assert payload["route_is_not_write_path"] is True
    assert payload["foundation_fixture_is_not_live_evidence"] is True
    assert payload["raw_payloads_exposed"] is False
    assert payload["ledger"]["chain_verified"] is True
    assert payload["evidence"]["accepted_count"] == 3
    assert payload["evidence"]["rejected_count"] == 0
    assert payload["evidence"]["linked_count"] == 3


def test_evidence_ledger_repository_source_rejects_missing_foundation_marker(tmp_path: Path) -> None:
    source_payload = load_repository_evidence_source()
    source_payload["source_is_not_write_path"] = False
    bad_source = tmp_path / "bad-evidence-source.json"
    bad_source.write_text(json.dumps(source_payload), encoding="utf-8")

    try:
        build_foundation_evidence_ledger_read_model(generated_at=NOW, source_path=bad_source)
    except EvidenceLedgerReadModelSourceError as exc:
        error = str(exc)
    else:
        error = ""

    assert error == "source_is_not_write_path_must_be_true"
    assert bad_source.exists()
    assert source_payload["repository_local_source"] is True
    assert source_payload["source_is_not_live_evidence"] is True


class StubPlatform:
    """Minimal governed platform fixture for gateway app construction."""

    def connect(self, *, identity_id: str, tenant_id: str):
        return StubSession()


class StubSession:
    """Minimal governed session fixture."""

    def llm(self, prompt: str, **kwargs):  # noqa: ANN001
        return type("Result", (), {"content": "ok", "succeeded": True, "error": "", "cost": 0.0})()

    def close(self) -> None:
        return None


def _ledger() -> EvidenceLedgerKernel:
    return EvidenceLedgerKernel(ledger_id="test-evidence-ledger", clock=lambda: NOW)


def _register_standard_sources(ledger: EvidenceLedgerKernel) -> None:
    ledger.register_source_authority(
        SourceAuthority(
            source_id="bank-feed",
            source_type="bank_feed",
            authority_domains=("payment_settlement", "bank_transaction"),
            reliability_score=0.95,
            verification_method="api_account_binding",
            last_verified_at=NOW,
        ),
        actor_id="kernel-test",
    )
    ledger.register_source_authority(
        SourceAuthority(
            source_id="gmail",
            source_type="email_inbox",
            authority_domains=("email_receipt",),
            reliability_score=0.7,
            verification_method="oauth_metadata",
            last_verified_at=NOW,
        ),
        actor_id="kernel-test",
    )
    ledger.register_source_authority(
        SourceAuthority(
            source_id="invoice-system",
            source_type="invoice_api",
            authority_domains=("invoice_status",),
            reliability_score=0.8,
            verification_method="service_account_read",
            last_verified_at=NOW,
        ),
        actor_id="kernel-test",
    )


def _payment_claim(ledger: EvidenceLedgerKernel):
    return ledger.create_claim(
        claim_id="claim-payment-123",
        claim_type="payment_completed",
        proposition="Invoice 123 was paid.",
        subject="invoice-123",
        scope={"tenant_id": "tenant-1"},
        temporal_scope={"valid_at": NOW},
        expected_evidence_profile=ExpectedEvidenceProfile(
            required_evidence_kinds=(EvidenceKind.TRANSACTION, EvidenceKind.EMAIL, EvidenceKind.API_RESPONSE),
            minimum_independent_sources=2,
        ),
        actor_id="kernel-test",
    )


def _ingest(
    ledger: EvidenceLedgerKernel,
    *,
    kind: EvidenceKind,
    source_id: str,
    domain: str,
    raw_payload: dict[str, str] | None = None,
):
    payload = raw_payload or {
        "artifact_id": f"{kind.value}-{source_id}",
        "invoice_id": "123",
        "state": "observed",
    }
    return ledger.ingest_evidence(
        evidence_kind=kind,
        source_id=source_id,
        observer_id="observer-1",
        capture_method="deterministic_fixture",
        observed_at=NOW,
        raw_payload=payload,
        canonical_payload={"kind": kind.value, "source_id": source_id, "invoice_id": "123"},
        ontology_type="payment_evidence",
        authority_domain=domain,
        actor_id="kernel-test",
        sensitivity_level="restricted",
        raw_reference=f"fixture://raw/{kind.value}/{source_id}",
        canonical_reference=f"fixture://canonical/{kind.value}/{source_id}",
    )


def _link(
    ledger: EvidenceLedgerKernel,
    evidence_id: str,
    claim_id: str,
    relation: RelationType,
    *,
    weight: float = 1.0,
):
    return ledger.link_evidence(
        evidence_id=evidence_id,
        claim_id=claim_id,
        relation_type=relation,
        rule_id="payment-evidence-rule-v1",
        weight=weight,
        confidence=weight,
        explanation=f"{relation.value} payment claim under fixture rule",
        actor_id="kernel-test",
    )
