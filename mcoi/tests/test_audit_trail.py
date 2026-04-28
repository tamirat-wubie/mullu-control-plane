"""Phase 202D — Audit trail tests."""

import pytest
from mcoi_runtime.governance.audit.trail import AuditTrail, AuditEntry

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
from mcoi_runtime.governance.audit.trail import (
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

from mcoi_runtime.governance.audit.trail import LEDGER_SCHEMA_VERSION_MAX
# Private helpers stay on the canonical core path (the shim only
# re-exports public API). Phase 4 of the F7 reorg moves the
# implementation here, at which point this can collapse to one import.
from mcoi_runtime.governance.audit.trail import _recompute_entry_hash


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


# ═══════════════════════════════════════════
# G3.6 — Writer ↔ Spec drift (no asymmetry)
# ═══════════════════════════════════════════

from mcoi_runtime.governance.audit.trail import LEDGER_V1_CONTENT_FIELDS
# Private helpers stay on the canonical core path; see note above.
from mcoi_runtime.governance.audit.trail import (
    _canonical_hash_v1,
    _canonical_content_v1,
)


class TestWriterSpecAlignment:
    """G3.6: The writer must obey LEDGER_SPEC.md §"Canonical entry-hash
    content layout (v1)" exactly. Otherwise fresh ledgers fail external
    verification and the failure mode is indistinguishable from tamper.

    This is enforced *by construction* (writer and verifier share
    _canonical_hash_v1) AND *by test* (these property tests catch any
    future regression that re-introduces divergence).
    """

    def test_v1_field_set_exactly_matches_spec(self):
        """LEDGER_SPEC.md §'Canonical entry-hash content layout (v1)' lists
        exactly these nine fields. If anyone reorders, adds, or removes,
        this test catches it before LEDGER_SPEC.md drifts from reality."""
        expected = (
            "sequence", "action", "actor_id", "tenant_id", "target",
            "outcome", "detail", "previous_hash", "recorded_at",
        )
        assert LEDGER_V1_CONTENT_FIELDS == expected
        # The spec also fixes a count of 9 fields exactly
        assert len(LEDGER_V1_CONTENT_FIELDS) == 9

    def test_writer_hash_matches_canonical_hash(self):
        """Round-trip: a recorded entry's stored entry_hash must equal
        what _canonical_hash_v1 produces from the same fields. If the
        writer ever computes the hash differently from the spec, this
        breaks immediately."""
        trail = AuditTrail(clock=FIXED_CLOCK)
        entry = trail.record(
            action="llm.complete", actor_id="actor-1", tenant_id="t1",
            target="model/claude", outcome="success",
            detail={"tokens": 42, "cost": 0.01},
        )
        # Reconstruct the source mapping the writer would have used
        source = {
            "sequence": entry.sequence,
            "action": entry.action,
            "actor_id": entry.actor_id,
            "tenant_id": entry.tenant_id,
            "target": entry.target,
            "outcome": entry.outcome,
            "detail": entry.detail,
            "previous_hash": entry.previous_hash,
            "recorded_at": entry.recorded_at,
        }
        assert _canonical_hash_v1(source) == entry.entry_hash

    def test_canonical_content_only_contains_spec_fields(self):
        """The hash content must include EXACTLY the spec fields and
        nothing else — no entry_id, no entry_hash itself, no
        schema_version. Future fields added to AuditEntry must not leak
        into the hash unless the spec is bumped to v2."""
        sample = {
            "sequence": 1,
            "action": "a", "actor_id": "x", "tenant_id": "t",
            "target": "y", "outcome": "ok", "detail": {},
            "previous_hash": GENESIS_HASH, "recorded_at": "2026-01-01T00:00:00Z",
            # Distractor fields that MUST be ignored by the canonical hash:
            "entry_id": "audit-1",
            "entry_hash": "deadbeef" * 8,
            "schema_version": 1,
            "extra_future_field": "should not affect hash",
        }
        content = _canonical_content_v1(sample)
        assert set(content.keys()) == set(LEDGER_V1_CONTENT_FIELDS)
        assert "entry_id" not in content
        assert "entry_hash" not in content
        assert "schema_version" not in content
        assert "extra_future_field" not in content

    def test_distractor_fields_do_not_change_hash(self):
        """Adding fields outside LEDGER_V1_CONTENT_FIELDS must not change
        the hash. This is what makes schema_version safely additive (it
        doesn't enter the hash, so v1 entries hash the same with or
        without the field present)."""
        base = {
            "sequence": 1, "action": "a", "actor_id": "x", "tenant_id": "t",
            "target": "y", "outcome": "ok", "detail": {},
            "previous_hash": GENESIS_HASH, "recorded_at": "2026-01-01T00:00:00Z",
        }
        h1 = _canonical_hash_v1(base)
        with_extras = {
            **base,
            "entry_id": "audit-1",
            "schema_version": 1,
            "future_field": ["a", "b", "c"],
        }
        h2 = _canonical_hash_v1(with_extras)
        assert h1 == h2

    def test_concurrent_writes_produce_verifiable_chain(self):
        """Stress: multiple threads writing concurrently must produce a
        chain that the external verifier accepts. Catches any drift
        introduced by future thread-safety refactors."""
        import threading
        trail = AuditTrail(clock=FIXED_CLOCK)

        def writer(action: str):
            for i in range(20):
                trail.record(
                    action=action, actor_id="x", tenant_id="t",
                    target=f"y{i}", outcome="ok", detail={"i": i},
                )

        threads = [threading.Thread(target=writer, args=(f"a{i}",)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        entries = _trail_to_entries(trail)
        assert len(entries) == 100
        result = verify_chain_from_entries(entries)
        assert result.valid is True, (
            f"concurrent-write chain failed verification: {result.failure_reason}"
        )


# ═══════════════════════════════════════════
# G3.6c — Public API contract (signature pinning)
# ═══════════════════════════════════════════

class TestVerifierPublicAPI:
    """`verify_chain_from_entries` is a public contract. Adding kwargs
    with defaults is backward-compatible; reordering, renaming, or
    removing parameters is breaking. These tests pin the signature so
    breaking changes are caught at PR review."""

    def test_signature_pinned(self):
        import inspect
        sig = inspect.signature(verify_chain_from_entries)
        params = sig.parameters
        # Required positional
        assert "entries" in params
        assert params["entries"].kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.POSITIONAL_ONLY,
        )
        # Keyword-only with defaults (additive over time, never removed)
        assert "anchor_hash" in params
        assert params["anchor_hash"].kind == inspect.Parameter.KEYWORD_ONLY
        assert params["anchor_hash"].default is None
        assert "anchor_sequence" in params
        assert params["anchor_sequence"].kind == inspect.Parameter.KEYWORD_ONLY
        assert params["anchor_sequence"].default is None

    def test_result_dataclass_fields_pinned(self):
        """ExternalVerifyResult is part of the public contract. Adding
        fields with defaults is backward-compatible; removing or renaming
        fields breaks downstream consumers."""
        from dataclasses import fields
        names = {f.name for f in fields(ExternalVerifyResult)}
        # Pinned fields (must remain)
        assert "valid" in names
        assert "entries_checked" in names
        assert "failure_reason" in names
        assert "failure_sequence" in names
        assert "failure_field" in names

    def test_failure_field_values_documented_in_spec(self):
        """failure_field is part of the operational contract — exit code
        mapping in the CLI and external alerting depend on it. Pin the
        valid values so additions can't silently break operators."""
        # Documented in LEDGER_SPEC.md and in ExternalVerifyResult docstring
        documented_values = {"schema", "sequence", "previous_hash", "entry_hash", ""}

        # Exhaust each by triggering it
        produced: set[str] = set()

        # Empty chain → "" (success)
        produced.add(verify_chain_from_entries([]).failure_field)

        # Schema
        bad_schema = [{"sequence": 1}]  # missing many fields
        produced.add(verify_chain_from_entries(bad_schema).failure_field)

        # Sequence: build a chain with sequence gap
        trail = AuditTrail(clock=FIXED_CLOCK)
        for _ in range(3):
            trail.record(action="a", actor_id="x", tenant_id="t",
                         target="y", outcome="ok")
        entries = _trail_to_entries(trail)
        del entries[1]
        produced.add(verify_chain_from_entries(entries).failure_field)

        # previous_hash: tamper a previous_hash
        trail2 = AuditTrail(clock=FIXED_CLOCK)
        trail2.record(action="a", actor_id="x", tenant_id="t",
                      target="y", outcome="ok")
        trail2.record(action="b", actor_id="x", tenant_id="t",
                      target="y", outcome="ok")
        e2 = _trail_to_entries(trail2)
        e2[1]["previous_hash"] = "0" * 64
        produced.add(verify_chain_from_entries(e2).failure_field)

        # entry_hash: tamper detail
        trail3 = AuditTrail(clock=FIXED_CLOCK)
        trail3.record(action="a", actor_id="x", tenant_id="t",
                      target="y", outcome="ok")
        e3 = _trail_to_entries(trail3)
        e3[0]["detail"] = {"tampered": True}
        produced.add(verify_chain_from_entries(e3).failure_field)

        # All produced values must be in the documented set
        assert produced.issubset(documented_values), (
            f"undocumented failure_field values: {produced - documented_values}"
        )
