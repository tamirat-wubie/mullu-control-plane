"""Tests for CoordinationStore: save, load, list, delete, and path traversal prevention."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.coordination import (
    ConflictRecord,
    ConflictStrategy,
    DelegationRequest,
    DelegationResult,
    DelegationStatus,
    HandoffRecord,
    MergeDecision,
    MergeOutcome,
)
from mcoi_runtime.persistence.coordination_store import CoordinationStore
from mcoi_runtime.persistence.errors import PathTraversalError, PersistenceError


def _make_delegation_request() -> DelegationRequest:
    return DelegationRequest(
        delegation_id="del-001",
        delegator_id="agent-a",
        delegate_id="agent-b",
        goal_id="goal-1",
        action_scope="review",
        deadline="2025-06-01T12:00:00Z",
        metadata={"priority": "high"},
    )


def _make_delegation_result() -> DelegationResult:
    return DelegationResult(
        delegation_id="del-001",
        status=DelegationStatus.ACCEPTED,
        reason="capacity available",
        resolved_at="2025-06-01T13:00:00Z",
    )


def _make_handoff_record() -> HandoffRecord:
    return HandoffRecord(
        handoff_id="ho-001",
        from_party="agent-a",
        to_party="agent-b",
        goal_id="goal-1",
        context_ids=("ctx-1", "ctx-2"),
        handed_off_at="2025-06-01T14:00:00Z",
        metadata={"notes": "smooth handoff"},
    )


def _make_merge_decision() -> MergeDecision:
    return MergeDecision(
        merge_id="merge-001",
        goal_id="goal-1",
        source_ids=("src-a", "src-b"),
        outcome=MergeOutcome.MERGED,
        reason="no conflicts detected",
        resolved_at="2025-06-01T15:00:00Z",
    )


def _make_conflict_record() -> ConflictRecord:
    return ConflictRecord(
        conflict_id="conf-001",
        goal_id="goal-1",
        conflicting_ids=("item-a", "item-b"),
        strategy=ConflictStrategy.ESCALATE,
        resolved=True,
        resolution_id="res-001",
        metadata={"severity": "medium"},
    )


class TestSaveAndLoadRoundTrips:
    """Round-trip serialization through save_state/load_state."""

    @pytest.mark.parametrize(
        "state_id,record,record_type",
        [
            ("del-req-001", _make_delegation_request(), DelegationRequest),
            ("del-res-001", _make_delegation_result(), DelegationResult),
            ("handoff-001", _make_handoff_record(), HandoffRecord),
            ("merge-001", _make_merge_decision(), MergeDecision),
            ("conflict-001", _make_conflict_record(), ConflictRecord),
        ],
        ids=["delegation_request", "delegation_result", "handoff", "merge", "conflict"],
    )
    def test_save_and_load_round_trips(self, tmp_path, state_id, record, record_type):
        store = CoordinationStore(tmp_path)
        store.save_state(state_id, record)
        loaded = store.load_state(state_id, record_type)
        assert loaded == record


class TestListStates:
    """list_states returns IDs of all persisted coordination records."""

    def test_list_states_returns_saved_ids(self, tmp_path):
        store = CoordinationStore(tmp_path)

        assert store.list_states() == ()

        store.save_state("alpha", _make_delegation_request())
        store.save_state("beta", _make_handoff_record())
        store.save_state("gamma", _make_merge_decision())

        ids = store.list_states()
        assert ids == ("alpha", "beta", "gamma")

    def test_list_states_empty_dir(self, tmp_path):
        store = CoordinationStore(tmp_path)
        assert store.list_states() == ()

    def test_list_states_nonexistent_dir(self, tmp_path):
        store = CoordinationStore(tmp_path / "does-not-exist")
        assert store.list_states() == ()


class TestDeleteState:
    """delete_state removes the file and the ID disappears from list_states."""

    def test_delete_state_removes_file(self, tmp_path):
        store = CoordinationStore(tmp_path)
        store.save_state("to-delete", _make_delegation_request())
        assert "to-delete" in store.list_states()

        store.delete_state("to-delete")
        assert "to-delete" not in store.list_states()

    def test_delete_missing_state_raises(self, tmp_path):
        store = CoordinationStore(tmp_path)
        with pytest.raises(PersistenceError, match="not found"):
            store.delete_state("nonexistent")


class TestLoadMissingStateRaises:
    """load_state raises PersistenceError for a non-existent state_id."""

    def test_load_missing_state_raises(self, tmp_path):
        store = CoordinationStore(tmp_path)
        with pytest.raises(PersistenceError, match="not found"):
            store.load_state("nonexistent", DelegationRequest)


class TestPathTraversalPrevented:
    """IDs with traversal characters are rejected."""

    @pytest.mark.parametrize(
        "bad_id",
        ["../escape", "foo/bar", "foo\\bar", "a\0b", ".."],
        ids=["dotdot_slash", "forward_slash", "backslash", "null_byte", "dotdot"],
    )
    def test_path_traversal_prevented_save(self, tmp_path, bad_id):
        store = CoordinationStore(tmp_path)
        with pytest.raises(PathTraversalError):
            store.save_state(bad_id, _make_delegation_request())

    @pytest.mark.parametrize(
        "bad_id",
        ["../escape", "foo/bar", "foo\\bar", "a\0b"],
    )
    def test_path_traversal_prevented_load(self, tmp_path, bad_id):
        store = CoordinationStore(tmp_path)
        with pytest.raises(PathTraversalError):
            store.load_state(bad_id, DelegationRequest)

    @pytest.mark.parametrize(
        "bad_id",
        ["../escape", "foo/bar", "foo\\bar", "a\0b"],
    )
    def test_path_traversal_prevented_delete(self, tmp_path, bad_id):
        store = CoordinationStore(tmp_path)
        with pytest.raises(PathTraversalError):
            store.delete_state(bad_id)
