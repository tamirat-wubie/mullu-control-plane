"""Phase 4C — Proof Bridge tests.

Tests: Governance decision certification, receipt verification, causal
    lineage tracking, serialization round-trip, state machine integration.
"""

import json
from unittest.mock import patch

import pytest
import mcoi_runtime.core.proof_bridge as proof_bridge_module
from mcoi_runtime.core.proof_bridge import (
    GOVERNANCE_MACHINE,
    GovernanceProof,
    ProofBridge,
)
from mcoi_runtime.contracts.proof import (
    CausalLineage,
    GuardVerdict,
    ProofCapsule,
    TransitionReceipt,
)
from mcoi_runtime.contracts.state_machine import TransitionVerdict


def _clock() -> str:
    return "2026-01-01T00:00:00Z"


# ═══ Governance State Machine ═══


class TestGovernanceMachine:
    def test_machine_has_required_states(self):
        assert "pending" in GOVERNANCE_MACHINE.states
        assert "evaluating" in GOVERNANCE_MACHINE.states
        assert "allowed" in GOVERNANCE_MACHINE.states
        assert "denied" in GOVERNANCE_MACHINE.states
        assert "error" in GOVERNANCE_MACHINE.states

    def test_terminal_states(self):
        assert "allowed" in GOVERNANCE_MACHINE.terminal_states
        assert "denied" in GOVERNANCE_MACHINE.terminal_states
        assert "error" in GOVERNANCE_MACHINE.terminal_states

    def test_legal_transitions(self):
        assert GOVERNANCE_MACHINE.is_legal("pending", "evaluating", "start_evaluation") == TransitionVerdict.ALLOWED
        assert GOVERNANCE_MACHINE.is_legal("evaluating", "allowed", "all_guards_passed") == TransitionVerdict.ALLOWED
        assert GOVERNANCE_MACHINE.is_legal("evaluating", "denied", "guard_rejected") == TransitionVerdict.ALLOWED

    def test_illegal_transitions(self):
        assert GOVERNANCE_MACHINE.is_legal("pending", "allowed", "skip") == TransitionVerdict.DENIED_ILLEGAL_EDGE
        assert GOVERNANCE_MACHINE.is_legal("allowed", "pending", "revert") == TransitionVerdict.DENIED_TERMINAL_STATE


# ═══ ProofBridge — Allowed Decision ═══


class TestAllowedDecision:
    def test_certify_allowed_decision(self):
        bridge = ProofBridge(clock=_clock)
        proof = bridge.certify_governance_decision(
            tenant_id="t1",
            endpoint="/api/v1/test",
            guard_results=[
                {"guard_name": "tenant", "allowed": True, "reason": ""},
                {"guard_name": "rate_limit", "allowed": True, "reason": ""},
                {"guard_name": "budget", "allowed": True, "reason": ""},
            ],
            decision="allowed",
            actor_id="user1",
        )
        assert proof.decision == "allowed"
        assert proof.tenant_id == "t1"
        assert proof.endpoint == "/api/v1/test"
        assert isinstance(proof.capsule, ProofCapsule)

    def test_receipt_has_correct_transition(self):
        bridge = ProofBridge(clock=_clock)
        with patch(
            "mcoi_runtime.core.proof_bridge.certify_transition",
            wraps=proof_bridge_module.certify_transition,
        ) as wrapped:
            proof = bridge.certify_governance_decision(
                tenant_id="t1", endpoint="/api/test",
                guard_results=[{"guard_name": "guard1", "allowed": True, "reason": ""}],
                decision="allowed",
            )
        receipt = proof.capsule.receipt
        assert receipt.from_state == "evaluating"
        assert receipt.to_state == "allowed"
        assert receipt.action == "all_guards_passed"
        assert wrapped.call_args_list[0].kwargs["reason"] == "evaluating governed request"
        assert "/api/test" not in wrapped.call_args_list[0].kwargs["reason"]
        assert receipt.verdict == TransitionVerdict.ALLOWED

    def test_guard_verdicts_mapped(self):
        bridge = ProofBridge(clock=_clock)
        proof = bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[
                {"guard_name": "auth", "allowed": True, "reason": "valid key"},
                {"guard_name": "budget", "allowed": True, "reason": ""},
            ],
            decision="allowed",
        )
        assert len(proof.guard_verdicts) == 2
        assert proof.guard_verdicts[0].guard_id == "auth"
        assert proof.guard_verdicts[0].passed is True


# ═══ ProofBridge — Denied Decision ═══


class TestDeniedDecision:
    def test_certify_denied_decision(self):
        bridge = ProofBridge(clock=_clock)
        proof = bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[
                {"guard_name": "rate_limit", "allowed": False, "reason": "rate limited"},
            ],
            decision="denied",
            reason="rate limit exceeded",
        )
        assert proof.decision == "denied"
        receipt = proof.capsule.receipt
        assert receipt.to_state == "denied"
        assert receipt.action == "guard_rejected"

    def test_failed_guard_verdict(self):
        bridge = ProofBridge(clock=_clock)
        proof = bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "budget", "allowed": False, "reason": "exhausted"}],
            decision="denied",
        )
        # Note: guard verdicts are still included even though they failed
        # The bridge doesn't re-check guards, it records the decision
        assert proof.guard_verdicts[0].passed is False


# ═══ Receipt Verification ═══


class TestReceiptVerification:
    def test_verify_valid_receipt(self):
        bridge = ProofBridge(clock=_clock)
        proof = bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        assert bridge.verify_receipt(proof.capsule.receipt)

    def test_receipt_hash_deterministic(self):
        bridge1 = ProofBridge(clock=_clock)
        bridge2 = ProofBridge(clock=_clock)
        proof1 = bridge1.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        proof2 = bridge2.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        assert proof1.receipt_hash == proof2.receipt_hash


# ═══ Causal Lineage ═══


class TestCausalLineage:
    def test_lineage_created(self):
        bridge = ProofBridge(clock=_clock)
        proof = bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        entity_id = "request:t1:/api/test"
        lineage = bridge.get_lineage(entity_id)
        assert lineage is not None
        assert lineage.depth == 1
        assert len(lineage.receipt_chain) == 1

    def test_lineage_grows(self):
        bridge = ProofBridge(clock=_clock)
        for _ in range(3):
            bridge.certify_governance_decision(
                tenant_id="t1", endpoint="/api/test",
                guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
                decision="allowed",
            )
        entity_id = "request:t1:/api/test"
        lineage = bridge.get_lineage(entity_id)
        assert lineage.depth == 3
        assert len(lineage.receipt_chain) == 3

    def test_different_entities_separate_lineages(self):
        bridge = ProofBridge(clock=_clock)
        bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/a",
            guard_results=[], decision="allowed",
        )
        bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/b",
            guard_results=[], decision="allowed",
        )
        assert bridge.lineage_count == 2

    def test_lineage_unknown_entity(self):
        bridge = ProofBridge(clock=_clock)
        assert bridge.get_lineage("nonexistent") is None


# ═══ Serialization ═══


class TestSerialization:
    def test_serialize_proof_structure(self):
        bridge = ProofBridge(clock=_clock)
        proof = bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "guard1", "allowed": True, "reason": "ok"}],
            decision="allowed",
            actor_id="user1",
        )
        data = bridge.serialize_proof(proof)
        assert "receipt" in data
        assert "audit_record" in data
        assert "lineage_depth" in data
        assert "decision" in data
        assert "tenant_id" in data

    def test_serialize_receipt_fields(self):
        bridge = ProofBridge(clock=_clock)
        proof = bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        data = bridge.serialize_proof(proof)
        receipt = data["receipt"]
        assert "receipt_id" in receipt
        assert "machine_id" in receipt
        assert "from_state" in receipt
        assert "to_state" in receipt
        assert "guard_verdicts" in receipt
        assert "verdict" in receipt
        assert receipt["verdict"] == "allowed"

    def test_serialize_is_json_compatible(self):
        bridge = ProofBridge(clock=_clock)
        proof = bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        data = bridge.serialize_proof(proof)
        # Must be JSON-serializable (matches MAF Rust serde output)
        json_str = json.dumps(data, sort_keys=True)
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["decision"] == "allowed"


# ═══ Bridge State ═══


class TestBridgeState:
    def test_receipt_count(self):
        bridge = ProofBridge(clock=_clock)
        assert bridge.receipt_count == 0
        bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[], decision="allowed",
        )
        assert bridge.receipt_count == 1

    def test_summary(self):
        bridge = ProofBridge(clock=_clock)
        bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[], decision="allowed",
        )
        summary = bridge.summary()
        assert summary["receipt_count"] == 1
        assert summary["lineage_count"] == 1
        assert len(summary["last_receipt_hash"]) == 16
