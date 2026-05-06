"""Tests for proof substrate contracts — Python mirrors of MAF proof types."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from mcoi_runtime.contracts.state_machine import (
    StateMachineSpec, TransitionRule, TransitionVerdict,
)
from mcoi_runtime.contracts.proof import (
    GuardVerdict, TransitionReceipt, CausalLineage, ProofCapsule,
    certify_transition,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_DENIED_GUARD_FIXTURE = (
    REPO_ROOT / "tests" / "fixtures" / "python_proof_capsule_denied_guard.json"
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
        with pytest.raises(ValueError) as exc_info:
            certify_transition(
                m, entity_id="e1", from_state="idle", to_state="done",
                action="skip", before_state_hash="h1", after_state_hash="h2",
                actor_id="actor", reason="skip", timestamp="2026-03-27T12:00:00Z",
            )
        message = str(exc_info.value)
        assert message == "transition denied"
        assert "denied_illegal_edge" not in message

    def test_terminal_state_raises(self):
        m = _machine()
        with pytest.raises(ValueError) as exc_info:
            certify_transition(
                m, entity_id="e1", from_state="done", to_state="idle",
                action="reset", before_state_hash="h1", after_state_hash="h2",
                actor_id="actor", reason="reset", timestamp="2026-03-27T12:00:00Z",
            )
        message = str(exc_info.value)
        assert message == "transition denied"
        assert "denied_terminal_state" not in message

    def test_failed_guard_emits_denied_receipt(self):
        """A failed guard does NOT raise. Instead, certify_transition
        emits a receipt with verdict=DENIED_GUARD_FAILED that contains
        the full guard list (passing AND failing). The receipt IS the
        proof of the denial — stripping failed verdicts would erase the
        audit-trail reason for the rejection."""
        m = _machine()
        guards = (
            GuardVerdict(guard_id="budget", passed=True, reason="ok"),
            GuardVerdict(guard_id="auth", passed=False, reason="unauthorized"),
        )
        capsule = certify_transition(
            m, entity_id="e1", from_state="idle", to_state="running",
            action="start", before_state_hash="h1", after_state_hash="h2",
            guards=guards, actor_id="actor", reason="start",
            timestamp="2026-03-27T12:00:00Z",
        )
        # Receipt is emitted, not raised.
        assert capsule.receipt.verdict == TransitionVerdict.DENIED_GUARD_FAILED
        # Audit record carries the same verdict.
        assert capsule.audit_record.verdict == TransitionVerdict.DENIED_GUARD_FAILED
        # Full guard list is preserved on the receipt — both passing AND
        # failing entries, in original order.
        assert len(capsule.receipt.guard_verdicts) == 2
        assert capsule.receipt.guard_verdicts[0].guard_id == "budget"
        assert capsule.receipt.guard_verdicts[0].passed is True
        assert capsule.receipt.guard_verdicts[1].guard_id == "auth"
        assert capsule.receipt.guard_verdicts[1].passed is False
        assert capsule.receipt.guard_verdicts[1].reason == "unauthorized"

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

    def test_python_denied_guard_fixture_matches_certified_capsule(self):
        """F1 direct witness: Python emits the fixture Rust deserializes."""
        guards = (
            GuardVerdict(guard_id="budget", passed=True, reason="ok"),
            GuardVerdict(guard_id="auth", passed=False, reason="unauthorized"),
        )
        capsule = certify_transition(
            _machine(),
            entity_id="e1",
            from_state="idle",
            to_state="running",
            action="start",
            before_state_hash="h1",
            after_state_hash="h2",
            guards=guards,
            actor_id="actor",
            reason="start",
            timestamp="2026-03-27T12:00:00Z",
        )
        expected = json.loads(PYTHON_DENIED_GUARD_FIXTURE.read_text(encoding="utf-8"))

        assert capsule.to_json_dict() == expected
        assert capsule.receipt.verdict == TransitionVerdict.DENIED_GUARD_FAILED
        assert [guard.passed for guard in capsule.receipt.guard_verdicts] == [True, False]
        assert capsule.receipt.guard_verdicts[1].reason == "unauthorized"


# ═══════════════════════════════════════════
# CORE_STRUCTURE.md — Type-asymmetry boundary checks
# ═══════════════════════════════════════════

class TestLineageDepthBoundary:
    """`ProofCapsule.lineage_depth` is `u32` in Rust (`maf-kernel/src/lib.rs:387`)
    and `int` in Python (`mcoi/contracts/proof.py:122`). The Python-side
    validation in `__post_init__` enforces non-negative values, making the
    Python type effectively `u32` at the boundary. These tests ensure that
    boundary check stays load-bearing.

    See docs/CORE_STRUCTURE.md §"Known gaps" entry for `lineage_depth`.
    A future PR should align both sides to a bounded type; until then
    this test guards against the validation being silently removed.
    """

    def test_negative_lineage_depth_rejected(self):
        """Boundary: validation must reject negative values."""
        m = _machine()
        capsule = certify_transition(
            m, entity_id="e1", from_state="idle", to_state="running",
            action="start", before_state_hash="h1", after_state_hash="h2",
            actor_id="actor", reason="start", timestamp="2026-03-27T12:00:00Z",
        )
        with pytest.raises(ValueError, match="lineage_depth"):
            ProofCapsule(
                receipt=capsule.receipt,
                audit_record=capsule.audit_record,
                lineage_depth=-1,
            )

    def test_zero_lineage_depth_accepted(self):
        """Boundary: zero is the genesis depth and must be accepted."""
        m = _machine()
        capsule = certify_transition(
            m, entity_id="e1", from_state="idle", to_state="running",
            action="start", before_state_hash="h1", after_state_hash="h2",
            actor_id="actor", reason="start", timestamp="2026-03-27T12:00:00Z",
        )
        # Reconstructing with depth=0 must not raise
        rebuilt = ProofCapsule(
            receipt=capsule.receipt,
            audit_record=capsule.audit_record,
            lineage_depth=0,
        )
        assert rebuilt.lineage_depth == 0

    def test_large_lineage_depth_accepted(self):
        """Boundary: any non-negative int is accepted Python-side. Rust
        u32 max is 4_294_967_295. Python accepts larger; if a future
        refactor tightens to match Rust, this test will need updating."""
        m = _machine()
        capsule = certify_transition(
            m, entity_id="e1", from_state="idle", to_state="running",
            action="start", before_state_hash="h1", after_state_hash="h2",
            actor_id="actor", reason="start", timestamp="2026-03-27T12:00:00Z",
        )
        # u32 max value
        rebuilt = ProofCapsule(
            receipt=capsule.receipt,
            audit_record=capsule.audit_record,
            lineage_depth=4_294_967_295,
        )
        assert rebuilt.lineage_depth == 4_294_967_295
