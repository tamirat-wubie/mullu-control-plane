"""Phase 4C — Proof Bridge tests.

Tests: Governance decision certification, receipt verification, causal
    lineage tracking, serialization round-trip, state machine integration.
"""

import json
from unittest.mock import patch

import mcoi_runtime.core.proof_bridge as proof_bridge_module
from mcoi_runtime.contracts.temporal_runtime import TemporalActionRequest
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.proof_bridge import (
    GOVERNANCE_MACHINE,
    ProofBridge,
    TEMPORAL_SCHEDULER_MACHINE,
    TemporalSchedulerProof,
)
from mcoi_runtime.core.temporal_runtime import TemporalRuntimeEngine
from mcoi_runtime.core.temporal_scheduler import TemporalSchedulerEngine
from mcoi_runtime.contracts.proof import (
    ProofCapsule,
)
from mcoi_runtime.contracts.state_machine import TransitionVerdict


def _clock() -> str:
    return "2026-01-01T00:00:00Z"


class MutableClock:
    def __init__(self, now: str) -> None:
        self.now = now

    def __call__(self) -> str:
        return self.now

    def set(self, now: str) -> None:
        self.now = now


def _temporal_scheduler(clock: MutableClock) -> TemporalSchedulerEngine:
    temporal = TemporalRuntimeEngine(EventSpineEngine(), clock=clock)
    return TemporalSchedulerEngine(temporal, clock=clock)


def _temporal_action(
    *,
    action_id: str = "act-1",
    execute_at: str = "2026-05-04T14:00:00+00:00",
    approval_expires_at: str = "",
) -> TemporalActionRequest:
    return TemporalActionRequest(
        action_id=action_id,
        tenant_id="tenant-a",
        actor_id="user-a",
        action_type="reminder",
        requested_at="2026-05-04T13:00:00+00:00",
        execute_at=execute_at,
        approval_expires_at=approval_expires_at,
    )


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


class TestTemporalSchedulerMachine:
    def test_machine_has_required_states(self):
        assert "pending" in TEMPORAL_SCHEDULER_MACHINE.states
        assert "running" in TEMPORAL_SCHEDULER_MACHINE.states
        assert "completed" in TEMPORAL_SCHEDULER_MACHINE.states
        assert "blocked" in TEMPORAL_SCHEDULER_MACHINE.states

    def test_legal_temporal_transitions(self):
        assert (
            TEMPORAL_SCHEDULER_MACHINE.is_legal("pending", "running", "temporal_action_due")
            == TransitionVerdict.ALLOWED
        )
        assert (
            TEMPORAL_SCHEDULER_MACHINE.is_legal("pending", "blocked", "temporal_action_blocked")
            == TransitionVerdict.ALLOWED
        )
        assert (
            TEMPORAL_SCHEDULER_MACHINE.is_legal("running", "completed", "temporal_action_completed")
            == TransitionVerdict.ALLOWED
        )

    def test_terminal_temporal_states_do_not_reopen(self):
        assert (
            TEMPORAL_SCHEDULER_MACHINE.is_legal("completed", "running", "temporal_action_due")
            == TransitionVerdict.DENIED_TERMINAL_STATE
        )
        assert (
            TEMPORAL_SCHEDULER_MACHINE.is_legal("blocked", "pending", "temporal_action_deferred")
            == TransitionVerdict.DENIED_TERMINAL_STATE
        )
        assert (
            TEMPORAL_SCHEDULER_MACHINE.is_legal("pending", "completed", "skip_execution")
            == TransitionVerdict.DENIED_ILLEGAL_EDGE
        )


class TestTemporalSchedulerProof:
    def test_due_scheduler_receipt_certifies_running_transition(self):
        clock = MutableClock("2026-05-04T14:00:00+00:00")
        scheduler = _temporal_scheduler(clock)
        scheduled = scheduler.register("sched-1", _temporal_action())
        run_receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")
        bridge = ProofBridge(clock=clock)

        proof = bridge.certify_temporal_run_receipt(
            scheduled_action=scheduled,
            run_receipt=run_receipt,
            actor_id="worker-a",
        )

        assert isinstance(proof, TemporalSchedulerProof)
        assert proof.decision == "running"
        assert proof.capsule.receipt.machine_id == "temporal-scheduler"
        assert proof.capsule.receipt.from_state == "pending"
        assert proof.capsule.receipt.to_state == "running"
        assert proof.capsule.receipt.guard_verdicts[0].passed is True
        assert bridge.get_lineage("temporal_schedule:tenant-a:sched-1") is not None

    def test_blocked_scheduler_receipt_certifies_denied_guard_transition(self):
        clock = MutableClock("2026-05-04T15:01:00+00:00")
        scheduler = _temporal_scheduler(clock)
        scheduled = scheduler.register(
            "sched-1",
            _temporal_action(
                execute_at="2026-05-04T14:00:00+00:00",
                approval_expires_at="2026-05-04T15:00:00+00:00",
            ),
        )
        run_receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")
        bridge = ProofBridge(clock=clock)

        proof = bridge.certify_temporal_run_receipt(
            scheduled_action=scheduled,
            run_receipt=run_receipt,
            actor_id="worker-a",
        )

        assert proof.decision == "blocked"
        assert proof.capsule.receipt.to_state == "blocked"
        assert proof.capsule.receipt.verdict == TransitionVerdict.DENIED_GUARD_FAILED
        assert proof.capsule.receipt.guard_verdicts[0].passed is False
        assert proof.capsule.receipt.guard_verdicts[0].detail["temporal_verdict"] == "deny"

    def test_temporal_scheduler_proof_serializes_scheduler_detail(self):
        clock = MutableClock("2026-05-04T14:00:00+00:00")
        scheduler = _temporal_scheduler(clock)
        scheduled = scheduler.register("sched-1", _temporal_action(), handler_name="reminder_handler")
        run_receipt = scheduler.evaluate_due_action("sched-1", worker_id="worker-a")
        bridge = ProofBridge(clock=clock)
        proof = bridge.certify_temporal_run_receipt(scheduled_action=scheduled, run_receipt=run_receipt)

        data = bridge.serialize_temporal_scheduler_proof(proof)

        assert data["decision"] == "running"
        assert data["schedule_id"] == "sched-1"
        assert data["scheduler_receipt_id"] == run_receipt.receipt_id
        assert data["receipt"]["guard_verdicts"][0]["detail"]["handler_name"] == "reminder_handler"
        assert json.loads(json.dumps(data, sort_keys=True))["tenant_id"] == "tenant-a"

    def test_temporal_scheduler_proof_rejects_mismatched_receipt(self):
        clock = MutableClock("2026-05-04T14:00:00+00:00")
        scheduler = _temporal_scheduler(clock)
        scheduled = scheduler.register("sched-1", _temporal_action(action_id="act-1"))
        scheduler.register("sched-2", _temporal_action(action_id="act-2"))
        run_receipt = scheduler.evaluate_due_action("sched-2", worker_id="worker-a")
        bridge = ProofBridge(clock=clock)

        try:
            bridge.certify_temporal_run_receipt(scheduled_action=scheduled, run_receipt=run_receipt)
        except ValueError as exc:
            assert "schedule_id" in str(exc)
            assert bridge.receipt_count == 0
            assert bridge.lineage_count == 0
        else:
            raise AssertionError("mismatched scheduler receipt should fail closed")


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
        # Outer GovernanceProof wrapper preserves all verdicts.
        assert proof.guard_verdicts[0].passed is False
        # Receipt itself ALSO preserves the failed verdict (this is the
        # cryptographic record; stripping it would erase the denial reason).
        receipt = proof.capsule.receipt
        assert len(receipt.guard_verdicts) == 1
        assert receipt.guard_verdicts[0].guard_id == "budget"
        assert receipt.guard_verdicts[0].passed is False
        assert receipt.guard_verdicts[0].reason == "exhausted"
        # Verdict on the receipt reflects the guard failure, not just legality.
        from mcoi_runtime.contracts.state_machine import TransitionVerdict
        assert receipt.verdict == TransitionVerdict.DENIED_GUARD_FAILED

    def test_guard_detail_preserved_in_receipt(self):
        bridge = ProofBridge(clock=_clock)
        proof = bridge.certify_governance_decision(
            tenant_id="t1",
            endpoint="/api/v1/payment",
            guard_results=[
                {
                    "guard_name": "temporal",
                    "allowed": False,
                    "reason": "approval_expired",
                    "detail": {"decision_id": "dec-1", "verdict": "deny"},
                },
            ],
            decision="denied",
            reason="approval_expired",
        )
        receipt_verdict = proof.capsule.receipt.guard_verdicts[0]
        assert proof.guard_verdicts[0].detail["decision_id"] == "dec-1"
        assert receipt_verdict.detail["verdict"] == "deny"
        assert receipt_verdict.guard_id == "temporal"


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

    def test_verify_replay_token_returns_true_for_genuine_receipt(self):
        """A receipt produced by the bridge MUST verify against its own
        replay_token. Closes the "replay_token generated but never
        verified" finding."""
        bridge = ProofBridge(clock=_clock)
        proof = bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        assert ProofBridge.verify_replay_token(proof.capsule.receipt)

    def test_verify_replay_token_detects_tampered_token(self):
        """If a receipt's replay_token is replaced with a different
        valid-looking token, the verifier MUST reject it."""
        from dataclasses import replace
        bridge = ProofBridge(clock=_clock)
        proof = bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        original = proof.capsule.receipt
        tampered = replace(original, replay_token="replay-0000000000000000")
        assert ProofBridge.verify_replay_token(original) is True
        assert ProofBridge.verify_replay_token(tampered) is False

    def test_verify_replay_token_detects_tampered_timestamp(self):
        """The token is anchored to issued_at — substituting a different
        timestamp on the receipt MUST make the token fail to verify."""
        from dataclasses import replace
        bridge = ProofBridge(clock=_clock)
        proof = bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        original = proof.capsule.receipt
        # Substitute a different timestamp; the original replay_token was
        # computed against the original issued_at, so verification fails.
        tampered = replace(original, issued_at="2099-12-31T23:59:59Z")
        assert ProofBridge.verify_replay_token(tampered) is False

    def test_verify_replay_token_is_pure_static_method(self):
        """The verifier must be callable without instantiating a bridge —
        a downstream consumer who has only the receipt should be able
        to verify it without the platform's full state."""
        bridge = ProofBridge(clock=_clock)
        proof = bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        # Called via class, not instance.
        assert ProofBridge.verify_replay_token(proof.capsule.receipt) is True

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
        bridge.certify_governance_decision(
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

    def test_serialize_audit_record_includes_metadata_field(self):
        """The Rust `TransitionAuditRecord` struct has a `metadata`
        HashMap field with `#[serde(default)]`; the Python contract
        also has a `metadata` Mapping. Pre-fix, `serialize_proof`
        omitted it from the JSON output, causing silent cross-language
        drift: the in-memory contract carried metadata but the
        wire format dropped it. The field must always be present on
        the serialized audit_record (possibly as `{}`)."""
        bridge = ProofBridge(clock=_clock)
        proof = bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/test",
            guard_results=[{"guard_name": "g1", "allowed": True, "reason": ""}],
            decision="allowed",
        )
        data = bridge.serialize_proof(proof)
        audit = data["audit_record"]
        assert "metadata" in audit, (
            "audit_record.metadata is missing from serialize_proof output. "
            "This drops the field that Rust's TransitionAuditRecord "
            "expects (and serializes by default), breaking cross-language "
            "JSON parity."
        )
        # Fields the Rust serde struct serializes — all must be present
        # so a Rust deserializer can round-trip the Python output.
        for field_name in (
            "audit_id", "machine_id", "entity_id", "from_state",
            "to_state", "action", "verdict", "actor_id", "reason",
            "transitioned_at", "metadata",
        ):
            assert field_name in audit, (
                f"audit_record.{field_name} missing from serialize_proof "
                f"output — breaks parity with Rust TransitionAuditRecord."
            )


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
