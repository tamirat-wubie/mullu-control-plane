"""Tests for LedgerRuntimeIntegration bridge.

Covers anchor helpers (contract, assurance, regulatory), settlement proof
helpers (billing, partner, marketplace), memory mesh attachment, and
graph attachment.
"""

import pytest

from mcoi_runtime.contracts.ledger_runtime import (
    AnchorDisposition,
    SettlementProofStatus,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.ledger_runtime import LedgerRuntimeEngine
from mcoi_runtime.core.ledger_runtime_integration import LedgerRuntimeIntegration
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


# ======================================================================
# Fixtures
# ======================================================================

FIXED_TIME = "2026-01-01T00:00:00+00:00"


def _make_integration():
    es = EventSpineEngine()
    clk = FixedClock(FIXED_TIME)
    ledger = LedgerRuntimeEngine(es, clock=clk)
    mem = MemoryMeshEngine()
    integ = LedgerRuntimeIntegration(ledger, es, mem)
    return integ, ledger, es, mem


# ======================================================================
# Constructor validation
# ======================================================================


class TestConstructor:
    def test_valid_construction(self):
        integ, _, _, _ = _make_integration()
        assert integ is not None

    def test_invalid_ledger_engine_rejected(self):
        es = EventSpineEngine()
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="LedgerRuntimeEngine"):
            LedgerRuntimeIntegration("not-engine", es, mem)

    def test_invalid_event_spine_rejected(self):
        es = EventSpineEngine()
        clk = FixedClock(FIXED_TIME)
        ledger = LedgerRuntimeEngine(es, clock=clk)
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="EventSpineEngine"):
            LedgerRuntimeIntegration(ledger, "not-es", mem)

    def test_invalid_memory_engine_rejected(self):
        es = EventSpineEngine()
        clk = FixedClock(FIXED_TIME)
        ledger = LedgerRuntimeEngine(es, clock=clk)
        with pytest.raises(RuntimeCoreInvariantError, match="MemoryMeshEngine"):
            LedgerRuntimeIntegration(ledger, es, "not-mem")

    def test_none_ledger_rejected(self):
        es = EventSpineEngine()
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            LedgerRuntimeIntegration(None, es, mem)

    def test_none_event_spine_rejected(self):
        es = EventSpineEngine()
        clk = FixedClock(FIXED_TIME)
        ledger = LedgerRuntimeEngine(es, clock=clk)
        mem = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            LedgerRuntimeIntegration(ledger, None, mem)

    def test_none_memory_rejected(self):
        es = EventSpineEngine()
        clk = FixedClock(FIXED_TIME)
        ledger = LedgerRuntimeEngine(es, clock=clk)
        with pytest.raises(RuntimeCoreInvariantError):
            LedgerRuntimeIntegration(ledger, es, None)


# ======================================================================
# Anchor: contract attestation
# ======================================================================


class TestAnchorContractAttestation:
    def test_returns_dict(self):
        integ, _, _, _ = _make_integration()
        result = integ.anchor_contract_attestation("t-1", "contract-001", "hash-abc")
        assert isinstance(result, dict)

    def test_result_fields(self):
        integ, _, _, _ = _make_integration()
        r = integ.anchor_contract_attestation("t-1", "contract-001", "hash-abc")
        assert r["tenant_id"] == "t-1"
        assert r["source_ref"] == "contract-001"
        assert r["content_hash"] == "hash-abc"
        assert r["disposition"] == "pending"
        assert r["source_type"] == "contract_attestation"
        assert "anchor_id" in r
        assert "created_at" in r

    def test_custom_anchor_ref(self):
        integ, _, _, _ = _make_integration()
        r = integ.anchor_contract_attestation("t-1", "c1", "h1", anchor_ref="custom-ref")
        assert r["anchor_ref"] == "custom-ref"

    def test_default_anchor_ref(self):
        integ, _, _, _ = _make_integration()
        r = integ.anchor_contract_attestation("t-1", "c1", "h1")
        assert r["anchor_ref"] == "pending"

    def test_emits_event(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.anchor_contract_attestation("t-1", "c1", "h1")
        assert es.event_count > before

    def test_creates_anchor_in_ledger(self):
        integ, ledger, _, _ = _make_integration()
        integ.anchor_contract_attestation("t-1", "c1", "h1")
        assert ledger.anchor_count == 1

    def test_duplicate_contract_ref_rejected(self):
        integ, _, _, _ = _make_integration()
        integ.anchor_contract_attestation("t-1", "c1", "h1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate anchor_id"):
            integ.anchor_contract_attestation("t-1", "c1", "h2")


# ======================================================================
# Anchor: assurance attestation
# ======================================================================


class TestAnchorAssuranceAttestation:
    def test_returns_dict(self):
        integ, _, _, _ = _make_integration()
        result = integ.anchor_assurance_attestation("t-1", "assurance-001", "hash-xyz")
        assert isinstance(result, dict)

    def test_result_fields(self):
        integ, _, _, _ = _make_integration()
        r = integ.anchor_assurance_attestation("t-1", "assurance-001", "hash-xyz")
        assert r["tenant_id"] == "t-1"
        assert r["source_ref"] == "assurance-001"
        assert r["content_hash"] == "hash-xyz"
        assert r["disposition"] == "pending"
        assert r["source_type"] == "assurance_attestation"

    def test_custom_anchor_ref(self):
        integ, _, _, _ = _make_integration()
        r = integ.anchor_assurance_attestation("t-1", "a1", "h1", anchor_ref="my-ref")
        assert r["anchor_ref"] == "my-ref"

    def test_emits_event(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.anchor_assurance_attestation("t-1", "a1", "h1")
        assert es.event_count > before

    def test_creates_anchor_in_ledger(self):
        integ, ledger, _, _ = _make_integration()
        integ.anchor_assurance_attestation("t-1", "a1", "h1")
        assert ledger.anchor_count == 1


# ======================================================================
# Anchor: regulatory submission
# ======================================================================


class TestAnchorRegulatorySubmission:
    def test_returns_dict(self):
        integ, _, _, _ = _make_integration()
        result = integ.anchor_regulatory_submission("t-1", "reg-001", "hash-reg")
        assert isinstance(result, dict)

    def test_result_fields(self):
        integ, _, _, _ = _make_integration()
        r = integ.anchor_regulatory_submission("t-1", "reg-001", "hash-reg")
        assert r["tenant_id"] == "t-1"
        assert r["source_ref"] == "reg-001"
        assert r["content_hash"] == "hash-reg"
        assert r["disposition"] == "pending"
        assert r["source_type"] == "regulatory_submission"

    def test_custom_anchor_ref(self):
        integ, _, _, _ = _make_integration()
        r = integ.anchor_regulatory_submission("t-1", "r1", "h1", anchor_ref="chain-ref")
        assert r["anchor_ref"] == "chain-ref"

    def test_emits_event(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.anchor_regulatory_submission("t-1", "r1", "h1")
        assert es.event_count > before

    def test_creates_anchor_in_ledger(self):
        integ, ledger, _, _ = _make_integration()
        integ.anchor_regulatory_submission("t-1", "r1", "h1")
        assert ledger.anchor_count == 1


# ======================================================================
# Settlement proof: billing
# ======================================================================


class TestSettlementProofFromBilling:
    def test_returns_dict(self):
        integ, _, _, _ = _make_integration()
        result = integ.settlement_proof_from_billing("t-1", "bill-001", "tx-ref", "hash-bill")
        assert isinstance(result, dict)

    def test_result_fields(self):
        integ, _, _, _ = _make_integration()
        r = integ.settlement_proof_from_billing("t-1", "bill-001", "tx-ref", "hash-bill")
        assert r["tenant_id"] == "t-1"
        assert r["transaction_ref"] == "tx-ref"
        assert r["status"] == "pending"
        assert r["proof_hash"] == "hash-bill"
        assert r["source_type"] == "billing_settlement"
        assert r["billing_ref"] == "bill-001"
        assert "proof_id" in r
        assert "created_at" in r

    def test_emits_event(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.settlement_proof_from_billing("t-1", "b1", "tx", "h1")
        assert es.event_count > before

    def test_creates_proof_in_ledger(self):
        integ, ledger, _, _ = _make_integration()
        integ.settlement_proof_from_billing("t-1", "b1", "tx", "h1")
        assert ledger.proof_count == 1

    def test_duplicate_billing_ref_rejected(self):
        integ, _, _, _ = _make_integration()
        integ.settlement_proof_from_billing("t-1", "b1", "tx", "h1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate proof_id"):
            integ.settlement_proof_from_billing("t-1", "b1", "tx", "h2")


# ======================================================================
# Settlement proof: partner revenue share
# ======================================================================


class TestSettlementProofFromPartnerRevenueShare:
    def test_returns_dict(self):
        integ, _, _, _ = _make_integration()
        result = integ.settlement_proof_from_partner_revenue_share(
            "t-1", "partner-001", "tx-ref", "hash-partner"
        )
        assert isinstance(result, dict)

    def test_result_fields(self):
        integ, _, _, _ = _make_integration()
        r = integ.settlement_proof_from_partner_revenue_share(
            "t-1", "partner-001", "tx-ref", "hash-partner"
        )
        assert r["tenant_id"] == "t-1"
        assert r["transaction_ref"] == "tx-ref"
        assert r["status"] == "pending"
        assert r["proof_hash"] == "hash-partner"
        assert r["source_type"] == "partner_revenue_share"
        assert r["partner_ref"] == "partner-001"

    def test_emits_event(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.settlement_proof_from_partner_revenue_share("t-1", "p1", "tx", "h1")
        assert es.event_count > before

    def test_creates_proof_in_ledger(self):
        integ, ledger, _, _ = _make_integration()
        integ.settlement_proof_from_partner_revenue_share("t-1", "p1", "tx", "h1")
        assert ledger.proof_count == 1


# ======================================================================
# Settlement proof: marketplace transaction
# ======================================================================


class TestSettlementProofFromMarketplaceTransaction:
    def test_returns_dict(self):
        integ, _, _, _ = _make_integration()
        result = integ.settlement_proof_from_marketplace_transaction(
            "t-1", "mkt-001", "tx-ref", "hash-mkt"
        )
        assert isinstance(result, dict)

    def test_result_fields(self):
        integ, _, _, _ = _make_integration()
        r = integ.settlement_proof_from_marketplace_transaction(
            "t-1", "mkt-001", "tx-ref", "hash-mkt"
        )
        assert r["tenant_id"] == "t-1"
        assert r["transaction_ref"] == "tx-ref"
        assert r["status"] == "pending"
        assert r["proof_hash"] == "hash-mkt"
        assert r["source_type"] == "marketplace_transaction"
        assert r["marketplace_ref"] == "mkt-001"

    def test_emits_event(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.settlement_proof_from_marketplace_transaction("t-1", "m1", "tx", "h1")
        assert es.event_count > before

    def test_creates_proof_in_ledger(self):
        integ, ledger, _, _ = _make_integration()
        integ.settlement_proof_from_marketplace_transaction("t-1", "m1", "tx", "h1")
        assert ledger.proof_count == 1


# ======================================================================
# Memory mesh attachment
# ======================================================================


class TestAttachLedgerStateToMemoryMesh:
    def test_returns_memory_record(self):
        integ, _, _, _ = _make_integration()
        from mcoi_runtime.contracts.memory_mesh import MemoryRecord
        mem = integ.attach_ledger_state_to_memory_mesh("scope-001")
        assert isinstance(mem, MemoryRecord)

    def test_memory_record_fields(self):
        integ, _, _, _ = _make_integration()
        mem = integ.attach_ledger_state_to_memory_mesh("scope-001")
        assert mem.scope_ref_id == "scope-001"
        assert "Ledger state" in mem.title
        assert mem.confidence == 1.0

    def test_memory_content_reflects_ledger_state(self):
        integ, ledger, _, _ = _make_integration()
        ledger.register_account("a1", "t-1", "Account One")
        ledger.register_wallet("w1", "t-1", "id1", "pk1")
        mem = integ.attach_ledger_state_to_memory_mesh("scope-001")
        content = mem.content
        assert content["total_accounts"] == 1
        assert content["total_wallets"] == 1

    def test_adds_to_memory_engine(self):
        integ, _, _, mem_engine = _make_integration()
        integ.attach_ledger_state_to_memory_mesh("scope-001")
        # MemoryMeshEngine stores memories internally
        assert mem_engine.memory_count >= 1

    def test_emits_event(self):
        integ, _, es, _ = _make_integration()
        before = es.event_count
        integ.attach_ledger_state_to_memory_mesh("scope-001")
        assert es.event_count > before

    def test_sequential_calls_create_unique_memories(self):
        integ, _, _, mem_engine = _make_integration()
        m1 = integ.attach_ledger_state_to_memory_mesh("scope-001")
        m2 = integ.attach_ledger_state_to_memory_mesh("scope-001")
        assert m1.memory_id != m2.memory_id

    def test_tags_include_ledger(self):
        integ, _, _, _ = _make_integration()
        mem = integ.attach_ledger_state_to_memory_mesh("scope-001")
        # tags is a tuple
        assert "ledger" in mem.tags


# ======================================================================
# Graph attachment
# ======================================================================


class TestAttachLedgerStateToGraph:
    def test_returns_dict(self):
        integ, _, _, _ = _make_integration()
        result = integ.attach_ledger_state_to_graph("scope-001")
        assert isinstance(result, dict)

    def test_result_fields(self):
        integ, _, _, _ = _make_integration()
        r = integ.attach_ledger_state_to_graph("scope-001")
        assert r["scope_ref_id"] == "scope-001"
        assert "total_accounts" in r
        assert "total_transactions" in r
        assert "total_proofs" in r
        assert "total_anchors" in r
        assert "total_wallets" in r
        assert "total_violations" in r

    def test_reflects_ledger_state(self):
        integ, ledger, _, _ = _make_integration()
        ledger.register_account("a1", "t-1", "A1")
        ledger.register_account("a2", "t-2", "A2")
        r = integ.attach_ledger_state_to_graph("scope-001")
        assert r["total_accounts"] == 2

    def test_empty_engine_zeros(self):
        integ, _, _, _ = _make_integration()
        r = integ.attach_ledger_state_to_graph("scope-001")
        assert r["total_accounts"] == 0
        assert r["total_transactions"] == 0
        assert r["total_proofs"] == 0
        assert r["total_anchors"] == 0
        assert r["total_wallets"] == 0
        assert r["total_violations"] == 0


# ======================================================================
# Integration golden scenarios
# ======================================================================


class TestIntegrationGoldenBillingSettlement:
    """Billing settlement end-to-end via integration bridge."""

    def test_billing_settlement_full_flow(self):
        integ, ledger, es, mem_engine = _make_integration()
        # Create account for transaction
        ledger.register_account("billing-acct", "t-1", "Billing")
        # Create transaction
        ledger.create_transaction("tx-bill", "t-1", "billing-acct", "revenue-acct", 500.0, "inv-001")
        # Create proof via integration bridge
        r = integ.settlement_proof_from_billing("t-1", "billing-001", "tx-bill", "bill-hash")
        assert r["status"] == "pending"
        proof_id = r["proof_id"]
        # Confirm proof via ledger engine
        confirmed = ledger.confirm_proof(proof_id)
        assert confirmed.status is SettlementProofStatus.CONFIRMED
        # Attach to memory mesh
        mem = integ.attach_ledger_state_to_memory_mesh("billing-scope")
        assert mem.content["total_proofs"] == 1
        # Events emitted throughout
        assert es.event_count >= 5


class TestIntegrationGoldenPartnerRevenue:
    """Partner revenue share end-to-end."""

    def test_partner_revenue_full_flow(self):
        integ, ledger, es, _ = _make_integration()
        ledger.register_account("partner-acct", "t-1", "Partner")
        ledger.create_transaction("tx-partner", "t-1", "partner-acct", "share-acct", 200.0, "contract-001")
        r = integ.settlement_proof_from_partner_revenue_share("t-1", "partner-rev-001", "tx-partner", "partner-hash")
        assert r["status"] == "pending"
        proof_id = r["proof_id"]
        ledger.confirm_proof(proof_id)
        # Assessment
        a = ledger.ledger_assessment("assess-partner", "t-1")
        assert a.total_confirmed == 1
        assert a.integrity_score == 1.0


class TestIntegrationGoldenAssuranceAnchor:
    """Assurance artifact anchored via integration bridge."""

    def test_assurance_anchor_full_flow(self):
        integ, ledger, es, _ = _make_integration()
        r = integ.anchor_assurance_attestation("t-1", "assurance-001", "content-hash-abc")
        assert r["disposition"] == "pending"
        anchor_id = r["anchor_id"]
        confirmed = ledger.confirm_anchor(anchor_id)
        assert confirmed.disposition is AnchorDisposition.ANCHORED
        # Graph attachment
        graph = integ.attach_ledger_state_to_graph("assurance-scope")
        assert graph["total_anchors"] == 1


class TestIntegrationGoldenRegulatoryAnchor:
    """Regulatory package anchored and verified."""

    def test_regulatory_anchor_full_flow(self):
        integ, ledger, es, _ = _make_integration()
        r = integ.anchor_regulatory_submission("t-1", "reg-sub-001", "reg-hash")
        assert r["disposition"] == "pending"
        anchor_id = r["anchor_id"]
        ledger.confirm_anchor(anchor_id)
        # Also verify a proof
        p_r = integ.settlement_proof_from_billing("t-1", "reg-billing", "tx-reg", "proof-hash-reg")
        ledger.confirm_proof(p_r["proof_id"])
        assert ledger.verify_proof(p_r["proof_id"], "proof-hash-reg") is True
        snap = ledger.ledger_snapshot("snap-reg", "t-1")
        assert snap.total_anchors == 1
        assert snap.total_proofs == 1


class TestIntegrationGoldenFailedVerification:
    """Failed proof creates violation via integration bridge."""

    def test_failed_proof_violation(self):
        integ, ledger, es, _ = _make_integration()
        r = integ.settlement_proof_from_billing("t-1", "bad-billing", "tx-bad", "bad-hash")
        proof_id = r["proof_id"]
        ledger.fail_proof(proof_id)
        assert ledger.verify_proof(proof_id, "bad-hash") is False
        viols = ledger.detect_ledger_violations("t-1")
        assert len(viols) == 1
        assert viols[0].kind.value == "proof_failed"
