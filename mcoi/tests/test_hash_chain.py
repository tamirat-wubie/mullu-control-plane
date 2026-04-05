"""Purpose: tests for SHA-256 hash-chain audit trail.
Governance scope: persistence integrity verification tests.
Dependencies: integrity contracts, hash_chain store, trace_store, replay_store.
Invariants: tamper detection must be reliable; genesis is deterministic.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mcoi_runtime.contracts.integrity import HashChainEntry, HashChainValidationResult
from mcoi_runtime.persistence.hash_chain import (
    GENESIS_PREVIOUS_HASH,
    HashChainStore,
    compute_chain_hash,
    compute_content_hash,
)
from mcoi_runtime.persistence.errors import CorruptedDataError, PathTraversalError
from mcoi_runtime.persistence.trace_store import TraceStore
from mcoi_runtime.persistence.replay_store import ReplayStore
from mcoi_runtime.contracts.trace import TraceEntry
from mcoi_runtime.core.replay_engine import (
    EffectControl,
    ReplayArtifact,
    ReplayEffect,
    ReplayMode,
    ReplayRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_trace_entry(trace_id: str = "t-001") -> TraceEntry:
    return TraceEntry(
        trace_id=trace_id,
        parent_trace_id=None,
        event_type="test_event",
        subject_id="subj-1",
        goal_id="goal-1",
        state_hash="abc123",
        registry_hash="def456",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def _make_replay_record(replay_id: str = "r-001") -> ReplayRecord:
    return ReplayRecord(
        replay_id=replay_id,
        trace_id="t-001",
        source_hash="src-hash-1",
        approved_effects=(
            ReplayEffect(
                effect_id="eff-1",
                control=EffectControl.CONTROLLED,
            ),
        ),
        blocked_effects=(),
        mode=ReplayMode.OBSERVATION_ONLY,
        recorded_at=datetime.now(timezone.utc).isoformat(),
        artifacts=(
            ReplayArtifact(artifact_id="art-1", payload_digest="digest-1"),
        ),
        state_hash="state-hash-1",
        environment_digest="env-digest-1",
    )


# ---------------------------------------------------------------------------
# Hash chain core tests
# ---------------------------------------------------------------------------

class TestGenesisEntry:
    def test_genesis_entry(self, tmp_path: Path) -> None:
        store = HashChainStore(tmp_path / "chain", chain_id="test-chain")
        entry = store.append("first-content-hash")

        assert isinstance(entry, HashChainEntry)
        assert entry.sequence_number == 0
        assert entry.previous_hash == GENESIS_PREVIOUS_HASH
        assert entry.content_hash == "first-content-hash"

        expected_chain = compute_chain_hash(0, "first-content-hash", GENESIS_PREVIOUS_HASH)
        assert entry.chain_hash == expected_chain

    def test_genesis_latest(self, tmp_path: Path) -> None:
        store = HashChainStore(tmp_path / "chain")
        assert store.latest() is None

        entry = store.append("hash-a")
        latest = store.latest()
        assert latest is not None
        assert latest.entry_id == entry.entry_id


class TestChainValidates:
    def test_chain_validates(self, tmp_path: Path) -> None:
        store = HashChainStore(tmp_path / "chain", chain_id="valid-chain")
        store.append("hash-1")
        store.append("hash-2")
        store.append("hash-3")

        result = store.validate()
        assert isinstance(result, HashChainValidationResult)
        assert result.valid is True
        assert result.entries_checked == 3
        assert result.first_broken_sequence is None
        assert result.chain_id == "valid-chain"
        assert result.detail == "chain valid"

    def test_chain_linkage(self, tmp_path: Path) -> None:
        store = HashChainStore(tmp_path / "chain")
        e0 = store.append("h0")
        e1 = store.append("h1")
        e2 = store.append("h2")

        assert e1.previous_hash == e0.chain_hash
        assert e2.previous_hash == e1.chain_hash
        assert e0.sequence_number == 0
        assert e1.sequence_number == 1
        assert e2.sequence_number == 2


class TestTamperedDetected:
    def test_tampered_content_hash(self, tmp_path: Path) -> None:
        chain_dir = tmp_path / "chain"
        store = HashChainStore(chain_dir, chain_id="tamper-test")
        store.append("h0")
        store.append("h1")
        store.append("h2")

        # Tamper with entry at sequence 1: change its content_hash
        entry_file = chain_dir / "000000000001.json"
        raw = json.loads(entry_file.read_text(encoding="utf-8"))
        raw["content_hash"] = "tampered-hash"
        entry_file.write_text(
            json.dumps(raw, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
            encoding="utf-8",
        )

        result = store.validate()
        assert result.valid is False
        assert result.first_broken_sequence == 1
        assert result.detail == "chain hash mismatch"

    def test_tampered_chain_hash(self, tmp_path: Path) -> None:
        chain_dir = tmp_path / "chain"
        store = HashChainStore(chain_dir, chain_id="tamper-test")
        store.append("h0")
        store.append("h1")

        # Tamper with entry at sequence 0: change its chain_hash
        entry_file = chain_dir / "000000000000.json"
        raw = json.loads(entry_file.read_text(encoding="utf-8"))
        raw["chain_hash"] = "a" * 64
        entry_file.write_text(
            json.dumps(raw, sort_keys=True, ensure_ascii=True, separators=(",", ":")),
            encoding="utf-8",
        )

        result = store.validate()
        assert result.valid is False
        assert result.first_broken_sequence == 0
        assert result.detail == "chain hash mismatch"


class TestDeletedDetected:
    def test_deleted_detected(self, tmp_path: Path) -> None:
        chain_dir = tmp_path / "chain"
        store = HashChainStore(chain_dir, chain_id="delete-test")
        store.append("h0")
        store.append("h1")
        store.append("h2")

        # Delete the middle entry
        middle = chain_dir / "000000000001.json"
        middle.unlink()

        result = store.validate()
        assert result.valid is False
        # After deleting seq 1, file for seq 2 remains. Validation sees
        # seq 0 then seq 2, which breaks expected sequential numbering.
        assert result.first_broken_sequence is not None
        assert result.detail == "sequence continuity failure"


class TestEmptyValidates:
    def test_empty_validates(self, tmp_path: Path) -> None:
        store = HashChainStore(tmp_path / "chain", chain_id="empty")
        result = store.validate()
        assert result.valid is True
        assert result.entries_checked == 0
        assert result.first_broken_sequence is None
        assert result.detail == "empty chain"


class TestPathTraversalBounded:
    @pytest.mark.parametrize(
        ("bad_id", "expected"),
        (
            ("../escape", "identifier contains forbidden characters"),
            ("a\0b", "identifier contains null byte"),
        ),
    )
    def test_safe_path_bounds_identifier_message(
        self, tmp_path: Path, bad_id: str, expected: str
    ) -> None:
        store = HashChainStore(tmp_path / "chain")
        with pytest.raises(PathTraversalError, match=rf"^{expected}$") as excinfo:
            store._safe_path(bad_id, suffix=".json")
        assert bad_id not in str(excinfo.value)


class TestLoadAll:
    def test_load_all(self, tmp_path: Path) -> None:
        store = HashChainStore(tmp_path / "chain")
        store.append("a")
        store.append("b")
        store.append("c")

        entries = store.load_all()
        assert len(entries) == 3
        assert all(isinstance(e, HashChainEntry) for e in entries)
        assert [e.sequence_number for e in entries] == [0, 1, 2]

    def test_load_all_empty(self, tmp_path: Path) -> None:
        store = HashChainStore(tmp_path / "chain")
        assert store.load_all() == ()

    def test_load_all_bounds_malformed_entry_errors(self, tmp_path: Path) -> None:
        chain_dir = tmp_path / "chain"
        chain_dir.mkdir(parents=True)
        (chain_dir / "000000000000.json").write_text("not json", encoding="utf-8")

        store = HashChainStore(chain_dir)
        with pytest.raises(CorruptedDataError, match=r"^invalid hash chain entry \(CorruptedDataError\)$"):
            store.load_all()


# ---------------------------------------------------------------------------
# Integration with TraceStore
# ---------------------------------------------------------------------------

class TestTraceStoreIntegration:
    def test_trace_store_integration(self, tmp_path: Path) -> None:
        chain_dir = tmp_path / "trace_chain"
        trace_dir = tmp_path / "traces"
        chain = HashChainStore(chain_dir, chain_id="trace-chain")
        store = TraceStore(trace_dir, hash_chain=chain)

        store.append(_make_trace_entry("t-001"))
        store.append(_make_trace_entry("t-002"))
        store.append(_make_trace_entry("t-003"))

        # Chain should have 3 entries
        entries = chain.load_all()
        assert len(entries) == 3

        # Chain should validate
        result = chain.validate()
        assert result.valid is True
        assert result.entries_checked == 3

    def test_trace_store_without_chain(self, tmp_path: Path) -> None:
        """TraceStore works normally without a hash chain."""
        store = TraceStore(tmp_path / "traces")
        store.append(_make_trace_entry("t-001"))
        loaded = store.load_trace("t-001")
        assert loaded.trace_id == "t-001"


# ---------------------------------------------------------------------------
# Integration with ReplayStore
# ---------------------------------------------------------------------------

class TestReplayStoreIntegration:
    def test_replay_store_integration(self, tmp_path: Path) -> None:
        chain_dir = tmp_path / "replay_chain"
        replay_dir = tmp_path / "replays"
        chain = HashChainStore(chain_dir, chain_id="replay-chain")
        store = ReplayStore(replay_dir, hash_chain=chain)

        store.save(_make_replay_record("r-001"))
        store.save(_make_replay_record("r-002"))

        entries = chain.load_all()
        assert len(entries) == 2

        result = chain.validate()
        assert result.valid is True
        assert result.entries_checked == 2

    def test_replay_store_without_chain(self, tmp_path: Path) -> None:
        """ReplayStore works normally without a hash chain."""
        store = ReplayStore(tmp_path / "replays")
        store.save(_make_replay_record("r-001"))
        loaded = store.load("r-001")
        assert loaded.replay_id == "r-001"
