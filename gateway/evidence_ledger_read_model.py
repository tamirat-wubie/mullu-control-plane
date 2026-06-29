"""Gateway evidence-ledger read-model projection.

Purpose: build a Foundation Mode proof projection for the causal evidence
    continuity ledger without registering a live evidence write path.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.evidence_ledger.
Invariants:
  - Projection is read-only and local-fixture backed.
  - Projection is not live operator evidence, terminal closure, or authority.
  - Raw artifact payloads are not exposed through proof-only summaries.
  - Chain verification must pass before the route reports SolvedVerified.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from gateway.evidence_ledger import (
    EvidenceKind,
    EvidenceLedgerKernel,
    ExpectedEvidenceProfile,
    ExposureViewType,
    RelationType,
    SourceAuthority,
)


DEFAULT_LEDGER_ID = "foundation-evidence-ledger-read-model"
DEFAULT_OBSERVED_AT = "2026-06-29T12:00:00+00:00"


def build_foundation_evidence_ledger_read_model(
    *,
    generated_at: str = DEFAULT_OBSERVED_AT,
    clock: Callable[[], str] | None = None,
) -> dict[str, object]:
    """Return a deterministic proof-bound evidence-ledger read model.

    Input contract: optional timestamp and clock for deterministic tests.
    Output contract: JSON-serializable Foundation Mode projection. Error
    contract: raises if the kernel cannot produce a verified chain, making the
    route fail closed rather than emitting unsupported certainty.
    """

    ledger = EvidenceLedgerKernel(
        ledger_id=DEFAULT_LEDGER_ID,
        clock=clock or (lambda: generated_at),
    )
    _register_sources(ledger)
    claim = ledger.create_claim(
        claim_id="claim-foundation-invoice-123-paid",
        claim_type="payment_completed",
        proposition="Invoice 123 payment is supported by local proof evidence.",
        subject="invoice-123",
        scope={"tenant_id": "foundation-tenant", "foundation_fixture": True},
        temporal_scope={"valid_at": generated_at, "strongly_supported_at_time": generated_at},
        expected_evidence_profile=ExpectedEvidenceProfile(
            required_evidence_kinds=(
                EvidenceKind.TRANSACTION,
                EvidenceKind.EMAIL,
                EvidenceKind.API_RESPONSE,
            ),
            minimum_independent_sources=2,
        ),
        actor_id="foundation-read-model",
        expiration_policy={"requires_recheck_after": "PT24H", "claim_expires_without_recheck": True},
    )
    evidence_results = (
        _ingest_evidence(
            ledger,
            kind=EvidenceKind.TRANSACTION,
            source_id="foundation-bank-feed",
            authority_domain="payment_settlement",
            raw_payload={"transaction_id": "txn-123", "invoice_id": "123", "state": "posted"},
        ),
        _ingest_evidence(
            ledger,
            kind=EvidenceKind.EMAIL,
            source_id="foundation-gmail",
            authority_domain="email_receipt",
            raw_payload={"message_id": "msg-123", "invoice_id": "123", "state": "receipt_observed"},
        ),
        _ingest_evidence(
            ledger,
            kind=EvidenceKind.API_RESPONSE,
            source_id="foundation-invoice-system",
            authority_domain="invoice_status",
            raw_payload={"invoice_id": "123", "state": "paid"},
        ),
    )
    link_results = tuple(
        ledger.link_evidence(
            evidence_id=result.evidence.evidence_id,
            claim_id=claim.claim_id,
            relation_type=RelationType.SUPPORTS,
            rule_id="foundation-payment-support-rule-v1",
            weight=0.95,
            confidence=0.95,
            explanation="Local fixture evidence supports the demonstration payment claim.",
            actor_id="foundation-read-model",
        )
        for result in evidence_results
    )
    judgment = ledger.judge_claim(claim_id=claim.claim_id, verifier="foundation-read-model")
    proof_view = ledger.expose_claim(
        claim_id=claim.claim_id,
        actor_id="foundation-read-model",
        purpose="foundation_read_model",
        view_type=ExposureViewType.PROOF_ONLY,
    )
    audit = ledger.audit_claim(claim_id=claim.claim_id, actor_id="foundation-read-model")
    chain = ledger.verify_event_chain()
    outcome = "SolvedVerified" if chain.verified and judgment.new_judgment.value == "strongly_supported" else "SolvedUnverified"
    return {
        "route_id": "causal_evidence_continuity_ledger_read_model",
        "route_version": 1,
        "schema_version": 2,
        "status": outcome,
        "outcome": outcome,
        "read_only": True,
        "foundation_mode": True,
        "foundation_fixture_is_not_live_evidence": True,
        "route_is_not_write_path": True,
        "route_is_not_terminal_closure": True,
        "external_effects_allowed": False,
        "raw_payloads_exposed": False,
        "generated_at": generated_at,
        "ledger": {
            "ledger_id": ledger.ledger_id,
            "rule_version": ledger.rule_version,
            "ontology_version": ledger.ontology_version,
            "source_registry_version": ledger.source_registry_version,
            "head_hash": chain.head_hash,
            "event_count": chain.event_count,
            "chain_verified": chain.verified,
            "chain_reason": chain.reason,
        },
        "claim": {
            "claim_id": claim.claim_id,
            "claim_type": claim.claim_type,
            "subject": claim.subject,
            "judgment": judgment.new_judgment.value,
            "receipt_id": judgment.receipt_id,
            "missing_evidence": list(judgment.missing_evidence),
            "conflicts": list(judgment.conflicts),
            "confidence_limits": list(judgment.confidence_limits),
        },
        "evidence": {
            "accepted_count": sum(1 for result in evidence_results if result.accepted),
            "rejected_count": sum(1 for result in evidence_results if not result.accepted),
            "linked_count": sum(1 for result in link_results if result.accepted),
            "proof_summaries": list(proof_view.to_json_dict()["evidence_summaries"]),
        },
        "judgment_receipt": judgment.to_json_dict(),
        "proof_view": proof_view.to_json_dict(),
        "audit_receipt": asdict(audit),
        "validators": [
            "test_evidence_ledger_kernel",
            "test_evidence_ledger_read_model_route",
            "validate_sdlc_artifact",
            "validate_agents_governance",
        ],
        "invariants": {
            "evidence_is_not_truth": True,
            "claim_is_not_evidence": True,
            "judgment_receipt_required": True,
            "conflicts_checked": True,
            "missing_evidence_checked": True,
            "proof_view_redacts_raw_payload": True,
            "append_only_hash_chain_verified": chain.verified,
        },
        "next_action": "Replace the local fixture with an admitted repository-local evidence source before any live write path.",
    }


def _register_sources(ledger: EvidenceLedgerKernel) -> None:
    ledger.register_source_authority(
        SourceAuthority(
            source_id="foundation-bank-feed",
            source_type="local_bank_fixture",
            authority_domains=("payment_settlement", "bank_transaction"),
            reliability_score=0.95,
            verification_method="foundation_fixture",
            last_verified_at=DEFAULT_OBSERVED_AT,
        ),
        actor_id="foundation-read-model",
    )
    ledger.register_source_authority(
        SourceAuthority(
            source_id="foundation-gmail",
            source_type="local_email_fixture",
            authority_domains=("email_receipt",),
            reliability_score=0.7,
            verification_method="foundation_fixture",
            last_verified_at=DEFAULT_OBSERVED_AT,
        ),
        actor_id="foundation-read-model",
    )
    ledger.register_source_authority(
        SourceAuthority(
            source_id="foundation-invoice-system",
            source_type="local_invoice_fixture",
            authority_domains=("invoice_status",),
            reliability_score=0.8,
            verification_method="foundation_fixture",
            last_verified_at=DEFAULT_OBSERVED_AT,
        ),
        actor_id="foundation-read-model",
    )


def _ingest_evidence(
    ledger: EvidenceLedgerKernel,
    *,
    kind: EvidenceKind,
    source_id: str,
    authority_domain: str,
    raw_payload: dict[str, str],
):
    return ledger.ingest_evidence(
        evidence_kind=kind,
        source_id=source_id,
        observer_id="foundation-observer",
        capture_method="local_fixture_projection",
        observed_at=DEFAULT_OBSERVED_AT,
        raw_payload=raw_payload,
        canonical_payload={
            "evidence_kind": kind.value,
            "source_id": source_id,
            "invoice_id": "123",
            "authority_domain": authority_domain,
        },
        ontology_type="payment_evidence",
        authority_domain=authority_domain,
        actor_id="foundation-read-model",
        sensitivity_level="restricted",
        raw_reference=f"foundation://raw/{kind.value}/{source_id}",
        canonical_reference=f"foundation://canonical/{kind.value}/{source_id}",
    )
