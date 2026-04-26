"""Phase 202D — Audit trail tests."""

import pytest
from mcoi_runtime.core.audit_trail import AuditTrail, AuditEntry

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class TestAuditEntry:
    def test_record(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        entry = trail.record(
            action="llm.complete", actor_id="actor-1", tenant_id="t1",
            target="model/claude", outcome="success",
        )
        assert entry.action == "llm.complete"
        assert entry.sequence == 1
        assert entry.entry_hash
        assert entry.previous_hash

    def test_sequential_ids(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        e1 = trail.record(action="a", actor_id="x", tenant_id="t", target="y", outcome="ok")
        e2 = trail.record(action="b", actor_id="x", tenant_id="t", target="z", outcome="ok")
        assert e1.sequence == 1
        assert e2.sequence == 2

    def test_hash_chain(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        e1 = trail.record(action="a", actor_id="x", tenant_id="t", target="y", outcome="ok")
        e2 = trail.record(action="b", actor_id="x", tenant_id="t", target="z", outcome="ok")
        assert e2.previous_hash == e1.entry_hash

    def test_with_detail(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        entry = trail.record(
            action="llm.complete", actor_id="a1", tenant_id="t1",
            target="model", outcome="success", detail={"cost": 0.5, "tokens": 100},
        )
        assert entry.detail["cost"] == 0.5


class TestAuditQueries:
    def _setup(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="llm.complete", actor_id="a1", tenant_id="t1", target="m1", outcome="success")
        trail.record(action="execute", actor_id="a1", tenant_id="t1", target="g1", outcome="success")
        trail.record(action="llm.complete", actor_id="a2", tenant_id="t2", target="m1", outcome="denied")
        trail.record(action="session.create", actor_id="a1", tenant_id="t1", target="s1", outcome="success")
        return trail

    def test_query_all(self):
        trail = self._setup()
        entries = trail.query()
        assert len(entries) == 4

    def test_query_by_tenant(self):
        trail = self._setup()
        entries = trail.query(tenant_id="t1")
        assert len(entries) == 3
        assert all(e.tenant_id == "t1" for e in entries)

    def test_query_by_action(self):
        trail = self._setup()
        entries = trail.query(action="llm.complete")
        assert len(entries) == 2

    def test_query_by_outcome(self):
        trail = self._setup()
        entries = trail.query(outcome="denied")
        assert len(entries) == 1

    def test_query_with_limit(self):
        trail = self._setup()
        entries = trail.query(limit=2)
        assert len(entries) == 2

    def test_query_by_actor(self):
        trail = self._setup()
        entries = trail.query(actor_id="a2")
        assert len(entries) == 1

    def test_combined_filters(self):
        trail = self._setup()
        entries = trail.query(tenant_id="t1", action="llm.complete")
        assert len(entries) == 1


class TestChainVerification:
    def test_verify_empty(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        valid, checked = trail.verify_chain()
        assert valid is True
        assert checked == 0

    def test_verify_valid_chain(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        for i in range(10):
            trail.record(action=f"action-{i}", actor_id="a", tenant_id="t", target="x", outcome="ok")
        valid, checked = trail.verify_chain()
        assert valid is True
        assert checked == 10

    def test_entry_count(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        assert trail.entry_count == 0
        trail.record(action="a", actor_id="x", tenant_id="t", target="y", outcome="ok")
        assert trail.entry_count == 1


class TestAuditSummary:
    def test_summary(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="llm.complete", actor_id="a", tenant_id="t", target="m", outcome="success")
        trail.record(action="llm.complete", actor_id="a", tenant_id="t", target="m", outcome="denied")
        trail.record(action="execute", actor_id="a", tenant_id="t", target="g", outcome="success")
        summary = trail.summary()
        assert summary["entry_count"] == 3
        assert summary["chain_valid"] is True
        assert summary["actions"]["llm.complete"] == 2
        assert summary["outcomes"]["success"] == 2
        assert summary["outcomes"]["denied"] == 1


# ═══════════════════════════════════════════
# G3 — External Verifier (tamper detection)
# ═══════════════════════════════════════════

from dataclasses import asdict
from mcoi_runtime.core.audit_trail import (
    GENESIS_HASH,
    ExternalVerifyResult,
    verify_chain_from_entries,
)


def _trail_to_entries(trail: AuditTrail) -> list[dict]:
    """Convert recorded entries to dicts (as if exported to JSONL)."""
    return [asdict(e) for e in trail.query(limit=10000)]


class TestExternalVerifier:
    def test_empty_chain_is_valid(self):
        result = verify_chain_from_entries([])
        assert result.valid is True
        assert result.entries_checked == 0

    def test_intact_chain_passes(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        for i in range(5):
            trail.record(
                action=f"a{i}", actor_id="x", tenant_id="t",
                target="y", outcome="ok",
            )
        entries = _trail_to_entries(trail)
        result = verify_chain_from_entries(entries)
        assert result.valid is True
        assert result.entries_checked == 5

    def test_tampered_detail_detected(self):
        """Mutating an entry's detail should fail entry_hash check."""
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="a", actor_id="x", tenant_id="t",
                     target="y", outcome="ok", detail={"k": "original"})
        trail.record(action="b", actor_id="x", tenant_id="t",
                     target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        # Tamper with first entry's detail
        entries[0]["detail"] = {"k": "tampered"}
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "entry_hash"
        assert result.failure_sequence == 1

    def test_tampered_action_detected(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="benign", actor_id="x", tenant_id="t",
                     target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        entries[0]["action"] = "malicious"
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "entry_hash"

    def test_broken_chain_link_detected(self):
        """Mutating previous_hash should fail chain linkage check."""
        trail = AuditTrail(clock=FIXED_CLOCK)
        for _ in range(3):
            trail.record(action="a", actor_id="x", tenant_id="t",
                         target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        # Tamper with second entry's previous_hash
        entries[1]["previous_hash"] = "0" * 64
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "previous_hash"
        assert result.failure_sequence == 2

    def test_genesis_violation_detected(self):
        """First entry's previous_hash must equal GENESIS_HASH."""
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="a", actor_id="x", tenant_id="t",
                     target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        entries[0]["previous_hash"] = "f" * 64
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "previous_hash"

    def test_deleted_entry_detected(self):
        """Removing an entry from the middle should break the chain.

        With sequence monotonicity (G3.2), the gap is detected before
        chain linkage — a stronger signal because it pinpoints the
        deletion location precisely.
        """
        trail = AuditTrail(clock=FIXED_CLOCK)
        for _ in range(5):
            trail.record(action="a", actor_id="x", tenant_id="t",
                         target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        # Delete entry at index 2 (sequence 3)
        del entries[2]
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        # Sequence monotonicity catches it first (was previous_hash before G3.2)
        assert result.failure_field == "sequence"

    def test_missing_required_field_detected(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="a", actor_id="x", tenant_id="t",
                     target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        del entries[0]["entry_hash"]
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "schema"
        assert "entry_hash" in result.failure_reason

    def test_in_memory_verify_matches_external(self):
        """AuditTrail.verify_chain() and verify_chain_from_entries() must agree."""
        trail = AuditTrail(clock=FIXED_CLOCK)
        for _ in range(10):
            trail.record(action="a", actor_id="x", tenant_id="t",
                         target="y", outcome="ok")
        in_memory_valid, in_memory_count = trail.verify_chain()
        external = verify_chain_from_entries(_trail_to_entries(trail))
        assert in_memory_valid == external.valid
        assert in_memory_count == external.entries_checked

    def test_genesis_hash_constant(self):
        """GENESIS_HASH must be sha256(b'genesis') for spec stability."""
        from hashlib import sha256
        assert GENESIS_HASH == sha256(b"genesis").hexdigest()


# ═══════════════════════════════════════════
# G3.2 — Sequence-monotonicity (deletion-with-rewrite attack)
# ═══════════════════════════════════════════

from mcoi_runtime.core.audit_trail import (
    LEDGER_SCHEMA_VERSION_MAX,
    _recompute_entry_hash,
)


class TestSequenceMonotonicity:
    """G3.2: Sequence gap must be detected even when chain linkage is consistent.

    Attack: delete entry seq=3 from a 5-entry chain, then re-link entries
    seq=4,5 directly to entry seq=2. With only chain-linkage + entry-hash
    checks, this passes — the resulting chain has sequences (1,2,4,5) but
    each previous_hash correctly points to the prior entry. Sequence
    monotonicity catches this.
    """

    def test_sequence_gap_detected(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        for _ in range(5):
            trail.record(action="a", actor_id="x", tenant_id="t",
                         target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        # Delete the middle entry, then re-link downstream so chain
        # linkage stays valid (this is the actual exploitable attack).
        del entries[2]  # remove sequence=3
        # Re-link entries[2] (now sequence=4) to entries[1].entry_hash
        entries[2] = dict(entries[2])
        entries[2]["previous_hash"] = entries[1]["entry_hash"]
        entries[2]["entry_hash"] = _recompute_entry_hash(entries[2])
        # Re-link entries[3] (sequence=5) to the new entries[2].entry_hash
        entries[3] = dict(entries[3])
        entries[3]["previous_hash"] = entries[2]["entry_hash"]
        entries[3]["entry_hash"] = _recompute_entry_hash(entries[3])

        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "sequence"
        # Gap is at index 2: expected sequence=3, got sequence=4
        assert result.failure_sequence == 4

    def test_sequence_must_start_at_one(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        for _ in range(3):
            trail.record(action="a", actor_id="x", tenant_id="t",
                         target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        # Drop the first entry — slice that doesn't start at 1
        result = verify_chain_from_entries(entries[1:])
        # Without anchor_hash, chain link from GENESIS fails first
        assert result.valid is False

    def test_full_chain_must_be_contiguous(self):
        """Mutating sequence numbers without rehashing fails entry_hash first;
        rehashing makes the gap the sole detector."""
        trail = AuditTrail(clock=FIXED_CLOCK)
        for _ in range(3):
            trail.record(action="a", actor_id="x", tenant_id="t",
                         target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        # Renumber third entry: sequence 3 → 5, rehash to make chain consistent
        entries[2] = dict(entries[2])
        entries[2]["sequence"] = 5
        entries[2]["entry_hash"] = _recompute_entry_hash(entries[2])
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "sequence"


# ═══════════════════════════════════════════
# G3.3 — Schema version awareness
# ═══════════════════════════════════════════

class TestSchemaVersion:
    def test_missing_schema_version_treated_as_v1(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="a", actor_id="x", tenant_id="t",
                     target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        assert "schema_version" not in entries[0]
        result = verify_chain_from_entries(entries)
        assert result.valid is True

    def test_explicit_v1_accepted(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="a", actor_id="x", tenant_id="t",
                     target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        # Adding schema_version doesn't change entry_hash (it's not in content)
        entries[0]["schema_version"] = 1
        result = verify_chain_from_entries(entries)
        assert result.valid is True

    def test_unknown_future_version_rejected(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="a", actor_id="x", tenant_id="t",
                     target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        entries[0]["schema_version"] = LEDGER_SCHEMA_VERSION_MAX + 1
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "schema"
        assert "unknown schema_version" in result.failure_reason

    def test_invalid_schema_version_type_rejected(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="a", actor_id="x", tenant_id="t",
                     target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        entries[0]["schema_version"] = "v1"  # string, not int
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "schema"

    def test_negative_schema_version_rejected(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        trail.record(action="a", actor_id="x", tenant_id="t",
                     target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        entries[0]["schema_version"] = 0
        result = verify_chain_from_entries(entries)
        assert result.valid is False
        assert result.failure_field == "schema"


# ═══════════════════════════════════════════
# G3.4 — Slice verification with anchor_hash
# ═══════════════════════════════════════════

class TestAnchoredSliceVerification:
    def test_slice_with_correct_anchor_passes(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        for _ in range(5):
            trail.record(action="a", actor_id="x", tenant_id="t",
                         target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        # Verify entries [3,4,5] using entry 2's hash as anchor
        anchor = entries[1]["entry_hash"]
        result = verify_chain_from_entries(
            entries[2:], anchor_hash=anchor, anchor_sequence=3,
        )
        assert result.valid is True
        assert result.entries_checked == 3

    def test_slice_with_wrong_anchor_fails(self):
        trail = AuditTrail(clock=FIXED_CLOCK)
        for _ in range(5):
            trail.record(action="a", actor_id="x", tenant_id="t",
                         target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        result = verify_chain_from_entries(
            entries[2:], anchor_hash="0" * 64, anchor_sequence=3,
        )
        assert result.valid is False
        assert result.failure_field == "previous_hash"

    def test_slice_with_wrong_anchor_sequence_fails(self):
        """Anchor sequence must match the slice's first entry."""
        trail = AuditTrail(clock=FIXED_CLOCK)
        for _ in range(5):
            trail.record(action="a", actor_id="x", tenant_id="t",
                         target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        anchor = entries[1]["entry_hash"]
        # Claim slice starts at 99 but first entry has sequence=3
        result = verify_chain_from_entries(
            entries[2:], anchor_hash=anchor, anchor_sequence=99,
        )
        assert result.valid is False
        assert result.failure_field == "sequence"

    def test_bare_slice_fails(self):
        """Bare slice (no anchor) must NOT pass.

        Slice [2,3,4,5] without anchor: first entry has sequence=2 but
        expected_sequence=1 (no anchor_sequence supplied). Either the
        sequence check or the previous_hash check will fire first depending
        on order — both are correct rejections per LEDGER_SPEC.md.
        """
        trail = AuditTrail(clock=FIXED_CLOCK)
        for _ in range(5):
            trail.record(action="a", actor_id="x", tenant_id="t",
                         target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        result = verify_chain_from_entries(entries[1:])
        assert result.valid is False
        assert result.failure_field in ("sequence", "previous_hash")


# ═══════════════════════════════════════════
# G3.1 — Document the limitation (no test, just an assertion that the
# spec exists and the verifier name reflects what it actually proves)
# ═══════════════════════════════════════════

class TestSpecDocExists:
    def test_ledger_spec_doc_present(self):
        """LEDGER_SPEC.md is the canonical contract; absence is a regression."""
        from pathlib import Path
        # Walk up from this test file to find the repo root
        candidate = Path(__file__).resolve()
        for _ in range(6):
            candidate = candidate.parent
            spec = candidate / "docs" / "LEDGER_SPEC.md"
            if spec.exists():
                content = spec.read_text(encoding="utf-8")
                assert "Schema version" in content
                assert "GENESIS_HASH" in content
                assert "What the verifier does NOT prove" in content
                return
        pytest.fail("docs/LEDGER_SPEC.md not found from any parent of test file")
