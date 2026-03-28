"""Tests for proof substrate contracts — Python mirrors of MAF proof types."""
from __future__ import annotations

import json
import pytest

from mcoi_runtime.contracts.state_machine import (
    StateMachineSpec, TransitionRule, TransitionVerdict,
)
from mcoi_runtime.contracts.proof import (
    GuardVerdict, TransitionReceipt, CausalLineage, ProofCapsule,
    certify_transition,
)


def _machine() -> StateMachineSpec:
    return StateMachineSpec(
        machine_id="test", name="Test", version="1.0",
        states=("idle", "running", "done"),
        initial_state="idle",
        terminal_states=("done",),
        transitions=(
            TransitionRule(from_state="idle", to_state="running", action="start"),
            TransitionRule(from_state="running", to_state="done", action="finish"),
            TransitionRule(from_state="running", to_state="idle", action="reset"),
        ),
    )


class TestGuardVerdict:
    def test_create(self):
        g = GuardVerdict(guard_id="budget", passed=True, reason="ok")
        assert g.passed
        assert g.guard_id == "budget"

    def test_empty_guard_id_raises(self):
        with pytest.raises(ValueError):
            GuardVerdict(guard_id="", passed=True, reason="ok")


class TestCertifyTransition:
    def test_legal_transition_produces_capsule(self):
        m = _machine()
        capsule = certify_transition(
            m, entity_id="e1", from_state="idle", to_state="running",
            action="start", before_state_hash="h1", after_state_hash="h2",
            actor_id="actor", reason="starting", timestamp="2026-03-27T12:00:00Z",
        )
        assert isinstance(capsule, ProofCapsule)
        assert capsule.receipt.from_state == "idle"
        assert capsule.receipt.to_state == "running"
        assert capsule.receipt.verdict == TransitionVerdict.ALLOWED
        assert capsule.receipt.receipt_hash
        assert capsule.receipt.replay_token.startswith("replay-")
        assert capsule.audit_record.actor_id == "actor"

    def test_illegal_transition_raises(self):
        m = _machine()
        with pytest.raises(ValueError, match="denied_illegal_edge"):
            certify_transition(
                m, entity_id="e1", from_state="idle", to_state="done",
                action="skip", before_state_hash="h1", after_state_hash="h2",
                actor_id="actor", reason="skip", timestamp="2026-03-27T12:00:00Z",
            )

    def test_terminal_state_raises(self):
        m = _machine()
        with pytest.raises(ValueError, match="denied_terminal_state"):
            certify_transition(
                m, entity_id="e1", from_state="done", to_state="idle",
                action="reset", before_state_hash="h1", after_state_hash="h2",
                actor_id="actor", reason="reset", timestamp="2026-03-27T12:00:00Z",
            )

    def test_failed_guard_raises(self):
        m = _machine()
        guards = (
            GuardVerdict(guard_id="budget", passed=True, reason="ok"),
            GuardVerdict(guard_id="auth", passed=False, reason="unauthorized"),
        )
        with pytest.raises(ValueError, match="auth"):
            certify_transition(
                m, entity_id="e1", from_state="idle", to_state="running",
                action="start", before_state_hash="h1", after_state_hash="h2",
                guards=guards, actor_id="actor", reason="start",
                timestamp="2026-03-27T12:00:00Z",
            )

    def test_receipt_hash_deterministic(self):
        m = _machine()
        c1 = certify_transition(
            m, entity_id="e1", from_state="idle", to_state="running",
            action="start", before_state_hash="h1", after_state_hash="h2",
            actor_id="a", reason="r", timestamp="2026-01-01T00:00:00Z",
        )
        c2 = certify_transition(
            m, entity_id="e1", from_state="idle", to_state="running",
            action="start", before_state_hash="h1", after_state_hash="h2",
            actor_id="a", reason="r", timestamp="2026-01-01T00:00:00Z",
        )
        assert c1.receipt.receipt_hash == c2.receipt.receipt_hash

    def test_with_guards_passed(self):
        m = _machine()
        guards = (
            GuardVerdict(guard_id="budget", passed=True, reason="within budget"),
            GuardVerdict(guard_id="rate", passed=True, reason="under limit"),
        )
        capsule = certify_transition(
            m, entity_id="e1", from_state="idle", to_state="running",
            action="start", before_state_hash="h1", after_state_hash="h2",
            guards=guards, actor_id="actor", reason="start",
            timestamp="2026-03-27T12:00:00Z",
        )
        assert len(capsule.receipt.guard_verdicts) == 2
        assert all(g.passed for g in capsule.receipt.guard_verdicts)


class TestCausalLineage:
    def test_create(self):
        lineage = CausalLineage(
            lineage_id="lin-1", entity_id="e1",
            receipt_chain=("rcpt-a", "rcpt-b"),
            root_receipt_id="rcpt-a",
            current_state="running", depth=2,
        )
        assert lineage.depth == 2
        assert len(lineage.receipt_chain) == 2

    def test_empty_chain(self):
        lineage = CausalLineage(
            lineage_id="lin-1", entity_id="e1",
            receipt_chain=(), root_receipt_id="genesis",
            current_state="idle", depth=0,
        )
        assert lineage.depth == 0


class TestProofCapsule:
    def test_lineage_depth(self):
        m = _machine()
        capsule = certify_transition(
            m, entity_id="e1", from_state="idle", to_state="running",
            action="start", before_state_hash="h1", after_state_hash="h2",
            actor_id="actor", reason="start", timestamp="2026-03-27T12:00:00Z",
        )
        assert capsule.lineage_depth == 0


class TestCrossLanguageSerialization:
    """Verify Python proof types serialize to JSON matching MAF Rust serde format."""

    def test_guard_verdict_json_keys(self):
        g = GuardVerdict(guard_id="budget", passed=True, reason="ok")
        d = {"guard_id": g.guard_id, "passed": g.passed, "reason": g.reason}
        # Rust serde uses snake_case — verify Python field names match
        assert "guard_id" in d
        assert "passed" in d
        assert "reason" in d

    def test_transition_receipt_json_keys(self):
        m = _machine()
        capsule = certify_transition(
            m, entity_id="e1", from_state="idle", to_state="running",
            action="start", before_state_hash="h1", after_state_hash="h2",
            actor_id="actor", reason="start", timestamp="2026-03-27T12:00:00Z",
        )
        r = capsule.receipt
        # Verify all field names match Rust serde snake_case
        expected_keys = {
            "receipt_id", "machine_id", "entity_id", "from_state", "to_state",
            "action", "before_state_hash", "after_state_hash", "guard_verdicts",
            "verdict", "replay_token", "causal_parent", "issued_at", "receipt_hash",
        }
        actual_keys = {f.name for f in r.__dataclass_fields__.values()}
        assert expected_keys == actual_keys

    def test_verdict_enum_values_match_rust(self):
        """Verify Python enum values match Rust serde snake_case output."""
        assert TransitionVerdict.ALLOWED.value == "allowed"
        assert TransitionVerdict.DENIED_ILLEGAL_EDGE.value == "denied_illegal_edge"
        assert TransitionVerdict.DENIED_TERMINAL_STATE.value == "denied_terminal_state"
        assert TransitionVerdict.DENIED_GUARD_FAILED.value == "denied_guard_failed"

    def test_causal_lineage_json_keys(self):
        lineage = CausalLineage(
            lineage_id="lin-1", entity_id="e1",
            receipt_chain=("rcpt-a",), root_receipt_id="rcpt-a",
            current_state="idle", depth=0,
        )
        expected = {"lineage_id", "entity_id", "receipt_chain", "root_receipt_id", "current_state", "depth"}
        actual = {f.name for f in lineage.__dataclass_fields__.values()}
        assert expected == actual
