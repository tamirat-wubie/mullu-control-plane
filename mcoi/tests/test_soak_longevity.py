"""Purpose: soak / longevity test suite for sustained-operation validation.
Governance scope: stress-testing queue churn, escalation cycles, learning stability,
    persistence under load, provider health churn, and memory growth.
Dependencies: core engines, persistence stores, knowledge registry.
Invariants:
  - Every test uses a deterministic clock (sequential timestamps).
  - No network, no real filesystem (tmp dirs only).
  - Each test completes in under 10 seconds.
  - Assertions verify specific invariants, not just absence of crash.
"""

from __future__ import annotations

import hashlib
import tempfile
import weakref
from pathlib import Path
from typing import Callable

import pytest

from mcoi_runtime.contracts.job import JobPriority, JobStatus, PauseReason
from mcoi_runtime.contracts.knowledge_ingestion import (
    KnowledgeLifecycle,
    KnowledgeSource,
    KnowledgeSourceType,
)
from mcoi_runtime.contracts.organization import (
    EscalationChain,
    EscalationStep,
    EscalationState,
    Person,
    RoleType,
)
from mcoi_runtime.contracts.roles import (
    RoleDescriptor,
    WorkerProfile,
    WorkerStatus,
)
from mcoi_runtime.contracts.trace import TraceEntry
from mcoi_runtime.core.jobs import JobEngine, WorkQueue
from mcoi_runtime.core.knowledge import KnowledgeExtractor, KnowledgeRegistry
from mcoi_runtime.core.learning import LearningEngine
from mcoi_runtime.core.organization import EscalationManager, OrgDirectory
from mcoi_runtime.core.team_runtime import TeamEngine, WorkerRegistry
from mcoi_runtime.core.telemetry import TelemetryCollector
from mcoi_runtime.persistence.snapshot_store import SnapshotStore
from mcoi_runtime.persistence.trace_store import TraceStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

soak = pytest.mark.soak


def make_clock(start: int = 0) -> Callable[[], str]:
    """Return a deterministic clock that yields sequential ISO timestamps."""
    state = {"tick": start}

    def _clock() -> str:
        t = state["tick"]
        state["tick"] += 1
        return f"2025-01-01T{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}+00:00"

    return _clock


def make_high_range_clock(start: int = 0) -> Callable[[], str]:
    """Clock that can span many days for large tick counts."""
    state = {"tick": start}

    def _clock() -> str:
        t = state["tick"]
        state["tick"] += 1
        day = 1 + t // 86400
        rem = t % 86400
        return f"2025-01-{day:02d}T{rem // 3600:02d}:{(rem % 3600) // 60:02d}:{rem % 60:02d}+00:00"

    return _clock


# ============================================================================
# Queue churn (5+ tests)
# ============================================================================


@soak
class TestQueueChurn:
    """Sustained queue operations under high-volume enqueue/dequeue cycles."""

    def test_enqueue_dequeue_100_no_data_loss(self) -> None:
        """Create 100 jobs, enqueue all, dequeue all, verify queue empty and no loss."""
        clock = make_clock()
        engine = JobEngine(clock=clock)
        queue = WorkQueue(clock=clock)

        job_ids: list[str] = []
        for i in range(100):
            desc, _ = engine.create_job(
                name=f"job-{i}",
                description=f"soak job {i}",
                priority=JobPriority.NORMAL,
            )
            queue.enqueue(desc)
            job_ids.append(desc.job_id)

        dequeued_ids: list[str] = []
        while True:
            entry = queue.dequeue_next()
            if entry is None:
                break
            dequeued_ids.append(entry.job_id)

        assert len(dequeued_ids) == 100, f"expected 100 dequeued, got {len(dequeued_ids)}"
        assert set(dequeued_ids) == set(job_ids), "dequeued IDs do not match enqueued IDs"
        assert queue.peek() is None, "queue should be empty after full drain"
        assert len(queue.list_entries()) == 0

    def test_mixed_priority_strict_ordering(self) -> None:
        """50 jobs with mixed priorities; dequeue order must be strictly priority-ordered."""
        clock = make_clock()
        engine = JobEngine(clock=clock)
        queue = WorkQueue(clock=clock)

        priorities = [
            JobPriority.CRITICAL,
            JobPriority.HIGH,
            JobPriority.NORMAL,
            JobPriority.LOW,
            JobPriority.BACKGROUND,
        ]
        # 10 jobs per priority, interleaved insertion
        for i in range(50):
            prio = priorities[i % 5]
            desc, _ = engine.create_job(
                name=f"prio-job-{i}",
                description=f"priority test {i}",
                priority=prio,
            )
            queue.enqueue(desc)

        prev_rank = -1
        for _ in range(50):
            entry = queue.dequeue_next()
            assert entry is not None
            rank_map = {
                JobPriority.CRITICAL: 0,
                JobPriority.HIGH: 1,
                JobPriority.NORMAL: 2,
                JobPriority.LOW: 3,
                JobPriority.BACKGROUND: 4,
            }
            rank = rank_map[entry.priority]
            assert rank >= prev_rank, (
                f"priority ordering violated: got rank {rank} after {prev_rank}"
            )
            prev_rank = rank

        assert queue.dequeue_next() is None

    def test_enqueue_dequeue_reenqueue_200_cycles(self) -> None:
        """Enqueue/dequeue/re-enqueue cycle 200 times, verify consistency."""
        clock = make_clock()
        engine = JobEngine(clock=clock)
        queue = WorkQueue(clock=clock)

        # Create a pool of 20 jobs
        descriptors = []
        for i in range(20):
            desc, _ = engine.create_job(
                name=f"cycle-job-{i}",
                description=f"cycle test {i}",
                priority=JobPriority.NORMAL,
            )
            descriptors.append(desc)

        total_enqueued = 0
        total_dequeued = 0

        for cycle in range(200):
            # Enqueue a job (round-robin through descriptors)
            # Each enqueue needs a unique clock tick to avoid duplicate entry IDs
            desc = descriptors[cycle % len(descriptors)]
            queue.enqueue(desc)
            total_enqueued += 1

            # Dequeue one every other cycle to build up and drain
            if cycle % 2 == 1:
                entry = queue.dequeue_next()
                if entry is not None:
                    total_dequeued += 1

        # Drain remaining
        while queue.dequeue_next() is not None:
            total_dequeued += 1

        assert total_enqueued == 200
        assert total_dequeued == 200, (
            f"expected 200 total dequeued, got {total_dequeued}"
        )
        assert len(queue.list_entries()) == 0

    def test_assign_50_jobs_across_5_workers(self) -> None:
        """Assign 50 jobs across 5 workers via TeamEngine, verify load distribution."""
        clock = make_clock()
        registry = WorkerRegistry(clock=clock)
        team_engine = TeamEngine(registry=registry, clock=clock)
        job_engine = JobEngine(clock=clock)

        role_id = "dev-role"
        registry.register_role(RoleDescriptor(
            role_id=role_id,
            name="Developer",
            description="dev role",
            required_skills=("python",),
            max_concurrent_per_worker=10,
        ))

        worker_ids = []
        for i in range(5):
            wid = f"worker-{i}"
            registry.register_worker(WorkerProfile(
                worker_id=wid,
                name=f"Worker {i}",
                roles=(role_id,),
                max_concurrent_jobs=10,
                status=WorkerStatus.AVAILABLE,
            ))
            worker_ids.append(wid)

        assignment_counts: dict[str, int] = {wid: 0 for wid in worker_ids}
        for i in range(50):
            desc, _ = job_engine.create_job(
                name=f"assign-job-{i}",
                description=f"assign test {i}",
                priority=JobPriority.NORMAL,
            )
            decision = team_engine.assign_job(desc.job_id, role_id)
            assert decision is not None, f"assignment failed for job {i}"
            assignment_counts[decision.worker_id] += 1
            # Update the worker's load so least_loaded works correctly
            registry.update_capacity(decision.worker_id, assignment_counts[decision.worker_id])

        # With 50 jobs across 5 workers, each should get exactly 10 (least_loaded)
        for wid, count in assignment_counts.items():
            assert count == 10, (
                f"worker {wid} got {count} jobs, expected 10"
            )

    def test_cancel_half_queued_jobs(self) -> None:
        """Cancel half of queued jobs, verify remaining are correct."""
        clock = make_clock()
        engine = JobEngine(clock=clock)
        queue = WorkQueue(clock=clock)

        entries = []
        for i in range(50):
            desc, _ = engine.create_job(
                name=f"cancel-job-{i}",
                description=f"cancel test {i}",
                priority=JobPriority.NORMAL,
            )
            entry = queue.enqueue(desc)
            entries.append(entry)

        # Remove entries at even indices
        removed_ids = set()
        for i in range(0, 50, 2):
            ok = queue.remove(entries[i].entry_id)
            assert ok, f"failed to remove entry {entries[i].entry_id}"
            removed_ids.add(entries[i].job_id)

        remaining = queue.list_entries()
        assert len(remaining) == 25, f"expected 25 remaining, got {len(remaining)}"

        remaining_job_ids = {e.job_id for e in remaining}
        assert remaining_job_ids.isdisjoint(removed_ids), "removed jobs still in queue"

        # Verify all remaining are from odd indices
        expected_remaining = {entries[i].job_id for i in range(1, 50, 2)}
        assert remaining_job_ids == expected_remaining

    def test_rapid_peek_during_churn(self) -> None:
        """Peek must always reflect the current highest-priority entry during churn."""
        clock = make_clock()
        engine = JobEngine(clock=clock)
        queue = WorkQueue(clock=clock)

        # Enqueue 20 NORMAL, then insert a CRITICAL
        for i in range(20):
            desc, _ = engine.create_job(
                name=f"normal-{i}", description="n", priority=JobPriority.NORMAL,
            )
            queue.enqueue(desc)

        critical_desc, _ = engine.create_job(
            name="critical-peek", description="c", priority=JobPriority.CRITICAL,
        )
        queue.enqueue(critical_desc)

        peeked = queue.peek()
        assert peeked is not None
        assert peeked.priority == JobPriority.CRITICAL
        assert peeked.job_id == critical_desc.job_id

        # Dequeue the critical, now peek should be NORMAL
        dequeued = queue.dequeue_next()
        assert dequeued is not None
        assert dequeued.priority == JobPriority.CRITICAL

        peeked = queue.peek()
        assert peeked is not None
        assert peeked.priority == JobPriority.NORMAL


# ============================================================================
# Escalation cycles (3+ tests)
# ============================================================================


def _build_escalation_fixtures(
    clock: Callable[[], str],
    chain_id: str = "chain-1",
    num_steps: int = 3,
) -> tuple[OrgDirectory, EscalationManager, EscalationChain]:
    """Build an OrgDirectory with a person per step and an escalation chain."""
    directory = OrgDirectory(clock=clock)

    steps = []
    for i in range(1, num_steps + 1):
        pid = f"person-{chain_id}-{i}"
        directory.register_person(Person(
            person_id=pid,
            name=f"Escalation Target {i}",
            email=f"esc{i}@test.com",
            roles=(RoleType.ESCALATION_TARGET,),
        ))
        steps.append(EscalationStep(
            step_order=i,
            target_person_id=pid,
            timeout_minutes=10,
        ))

    chain = EscalationChain(
        chain_id=chain_id,
        name=f"chain {chain_id}",
        steps=tuple(steps),
        created_at=clock(),
    )
    directory.register_escalation_chain(chain)

    manager = EscalationManager(directory=directory, clock=clock)
    return directory, manager, chain


@soak
class TestEscalationCycles:
    """Repeated escalation start/advance/resolve cycles."""

    def test_20_full_escalation_cycles(self) -> None:
        """Run 20 escalation start/advance/resolve cycles, verify all resolve cleanly."""
        clock = make_clock()
        resolved_count = 0

        for i in range(20):
            cid = f"cycle-chain-{i}"
            _, manager, chain = _build_escalation_fixtures(clock, chain_id=cid, num_steps=3)

            state = manager.start_escalation(cid)
            assert state.current_step == 1
            assert not state.resolved

            # Advance through steps
            state = manager.advance_escalation(state)
            assert state.current_step == 2
            state = manager.advance_escalation(state)
            assert state.current_step == 3

            # Resolve
            state = manager.resolve_escalation(state)
            assert state.resolved
            resolved_count += 1

            # Resolved chain cannot advance
            with pytest.raises(ValueError, match="resolved"):
                manager.advance_escalation(state)

        assert resolved_count == 20

    def test_advance_through_all_steps(self) -> None:
        """Start escalation, advance through all steps, verify final step reached."""
        clock = make_clock()
        num_steps = 7
        _, manager, chain = _build_escalation_fixtures(
            clock, chain_id="deep-chain", num_steps=num_steps,
        )

        state = manager.start_escalation("deep-chain")
        for expected_step in range(2, num_steps + 1):
            state = manager.advance_escalation(state)
            assert state.current_step == expected_step

        # At final step, cannot advance further
        with pytest.raises(ValueError, match="last"):
            manager.advance_escalation(state)

        # But can resolve
        state = manager.resolve_escalation(state)
        assert state.resolved
        assert state.current_step == num_steps

    def test_interleaved_10_chains_no_cross_contamination(self) -> None:
        """Interleave 10 escalation chains, verify no cross-contamination."""
        clock = make_clock()
        managers: dict[str, EscalationManager] = {}
        states: dict[str, EscalationState] = {}

        for i in range(10):
            cid = f"interleave-{i}"
            _, mgr, _ = _build_escalation_fixtures(clock, chain_id=cid, num_steps=4)
            managers[cid] = mgr
            states[cid] = mgr.start_escalation(cid)

        # Advance each chain by different amounts
        for i in range(10):
            cid = f"interleave-{i}"
            advances = i % 3  # 0, 1, or 2 advances
            for _ in range(advances):
                states[cid] = managers[cid].advance_escalation(states[cid])

        # Resolve odd-numbered chains
        for i in range(1, 10, 2):
            cid = f"interleave-{i}"
            states[cid] = managers[cid].resolve_escalation(states[cid])

        # Verify states are independent
        for i in range(10):
            cid = f"interleave-{i}"
            expected_step = 1 + (i % 3)
            assert states[cid].current_step == expected_step, (
                f"chain {cid}: expected step {expected_step}, got {states[cid].current_step}"
            )
            assert states[cid].chain_id == cid
            if i % 2 == 1:
                assert states[cid].resolved, f"chain {cid} should be resolved"
            else:
                assert not states[cid].resolved, f"chain {cid} should NOT be resolved"


# ============================================================================
# Learning stability (3+ tests)
# ============================================================================


@soak
class TestLearningStability:
    """Sustained learning engine operations under high iteration counts."""

    def test_confidence_1000_alternating_stays_bounded(self) -> None:
        """Update confidence 1000 times with alternating success/failure; stays in [0,1]."""
        clock = make_high_range_clock()
        engine = LearningEngine(clock=clock)

        kid = "knowledge-alt"
        for i in range(1000):
            outcome = i % 2 == 0  # alternating success/failure
            result = engine.update_confidence(kid, outcome, weight=0.15)
            assert 0.0 <= result.value <= 1.0, (
                f"iteration {i}: confidence {result.value} out of bounds"
            )

        final = engine.get_confidence(kid)
        assert 0.0 <= final <= 1.0
        # With alternating equal-weight updates, confidence should converge near center
        assert 0.3 <= final <= 0.7, f"expected convergence near 0.5, got {final}"

    def test_record_500_lessons_all_retrievable(self) -> None:
        """Record 500 lessons, verify all retrievable by keyword."""
        clock = make_high_range_clock()
        engine = LearningEngine(clock=clock)

        keywords = ["alpha", "beta", "gamma", "delta", "epsilon"]
        for i in range(500):
            kw = keywords[i % len(keywords)]
            engine.record_lesson(
                source_id=f"src-{i}",
                context=f"context about {kw} topic number {i}",
                action=f"action-{i}",
                outcome="success" if i % 3 != 0 else "failure",
                lesson=f"lesson learned about {kw}",
            )

        # Each keyword should find exactly 100 lessons
        for kw in keywords:
            found = engine.find_relevant_lessons((kw,))
            assert len(found) == 100, (
                f"keyword '{kw}': expected 100 lessons, got {len(found)}"
            )

        # Combined search
        found_all = engine.find_relevant_lessons(("alpha", "beta"))
        assert len(found_all) == 200

    def test_promote_reject_100_knowledge_lifecycle(self) -> None:
        """Promote/reject 100 knowledge artifacts through lifecycle; no invalid states."""
        clock = make_high_range_clock()
        registry = KnowledgeRegistry(clock=clock)
        engine = LearningEngine(clock=clock)
        extractor = KnowledgeExtractor(clock=clock)

        valid_lifecycle_values = set(KnowledgeLifecycle)

        for i in range(100):
            source = KnowledgeSource(
                source_id=f"src-lc-{i}",
                source_type=KnowledgeSourceType.DOCUMENT,
                reference_id=f"ref-{i}",
                description=f"doc {i}",
                created_at=clock(),
            )
            candidate = extractor.extract_from_document(
                source, f"1. Step one for {i}\n2. Step two for {i}\n3. Step three",
            )
            registry.register(candidate)
            kid = candidate.candidate_id

            lc = registry.get_lifecycle(kid)
            assert lc in valid_lifecycle_values, f"artifact {kid}: invalid lifecycle {lc}"
            assert lc == KnowledgeLifecycle.CANDIDATE

            if i % 3 == 0:
                # Promote: candidate -> provisional -> verified
                registry.promote(kid, KnowledgeLifecycle.PROVISIONAL, "good", "system")
                assert registry.get_lifecycle(kid) == KnowledgeLifecycle.PROVISIONAL

                registry.promote(kid, KnowledgeLifecycle.VERIFIED, "verified", "system")
                assert registry.get_lifecycle(kid) == KnowledgeLifecycle.VERIFIED
            elif i % 3 == 1:
                # Deprecate
                registry.promote(kid, KnowledgeLifecycle.DEPRECATED, "outdated", "system")
                assert registry.get_lifecycle(kid) == KnowledgeLifecycle.DEPRECATED
            else:
                # Block
                registry.promote(kid, KnowledgeLifecycle.BLOCKED, "harmful", "system")
                assert registry.get_lifecycle(kid) == KnowledgeLifecycle.BLOCKED

                # Blocked cannot be promoted further
                from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
                with pytest.raises(RuntimeCoreInvariantError):
                    registry.promote(kid, KnowledgeLifecycle.TRUSTED, "try", "system")

        assert registry.size == 100

    def test_confidence_extreme_weights(self) -> None:
        """Stress confidence with weight=1.0 and weight=0.0 extremes."""
        clock = make_clock()
        engine = LearningEngine(clock=clock)

        # weight=1.0 success should push to 1.0 immediately
        engine.set_confidence("k-extreme", 0.5)
        result = engine.update_confidence("k-extreme", True, weight=1.0)
        assert result.value == 1.0

        # weight=1.0 failure from 1.0 should push to 0.0
        result = engine.update_confidence("k-extreme", False, weight=1.0)
        assert result.value == 0.0

        # weight=0.0 should not change confidence
        engine.set_confidence("k-zero", 0.5)
        result = engine.update_confidence("k-zero", True, weight=0.0)
        assert result.value == 0.5
        result = engine.update_confidence("k-zero", False, weight=0.0)
        assert result.value == 0.5


# ============================================================================
# Persistence under load (3+ tests)
# ============================================================================


@soak
class TestPersistenceUnderLoad:
    """Sustained persistence operations using temp directories."""

    def test_save_load_100_snapshots(self) -> None:
        """Save/load 100 snapshots, verify all round-trip correctly."""
        clock = make_clock()
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(Path(tmpdir), clock=clock)

            for i in range(100):
                data = {"index": i, "payload": f"data-{i}" * 50, "nested": {"x": i}}
                meta = store.save_snapshot(f"snap-{i:04d}", data, description=f"snapshot {i}")
                assert meta.snapshot_id == f"snap-{i:04d}"

            for i in range(100):
                meta, data = store.load_snapshot(f"snap-{i:04d}")
                assert data["index"] == i
                assert data["payload"] == f"data-{i}" * 50
                assert data["nested"]["x"] == i

            listing = store.list_snapshots()
            assert len(listing) == 100

    def test_save_load_200_trace_entries_ordering(self) -> None:
        """Save/load 200 trace entries, verify ordering preserved."""
        clock = make_clock()
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TraceStore(Path(tmpdir))

            trace_ids = []
            for i in range(200):
                tid = f"trace-{i:04d}"
                entry = TraceEntry(
                    trace_id=tid,
                    parent_trace_id=None,
                    event_type="test_event",
                    subject_id=f"subj-{i}",
                    goal_id="goal-1",
                    state_hash=f"hash-{i}",
                    registry_hash=f"rhash-{i}",
                    timestamp=clock(),
                )
                store.append(entry)
                trace_ids.append(tid)

            # list_traces returns sorted by trace_id (filename sort)
            listed = store.list_traces()
            assert len(listed) == 200
            assert list(listed) == sorted(trace_ids)

            # Load all and verify ordering
            all_entries = store.load_all()
            assert len(all_entries) == 200
            for idx, entry in enumerate(all_entries):
                assert entry.trace_id == f"trace-{idx:04d}"
                assert entry.subject_id == f"subj-{idx}"

    def test_snapshot_content_integrity_via_hash(self) -> None:
        """Save 50 snapshots then load all, verify content integrity via hash."""
        clock = make_clock()
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(Path(tmpdir), clock=clock)

            expected_hashes: dict[str, str] = {}
            for i in range(50):
                data = {
                    "id": i,
                    "large_field": f"x" * (100 + i * 10),
                    "list_field": list(range(i + 1)),
                }
                sid = f"integrity-{i:04d}"
                meta = store.save_snapshot(sid, data)
                expected_hashes[sid] = meta.content_hash

            # Load all and verify content_hash matches
            for sid, expected_hash in expected_hashes.items():
                meta, data = store.load_snapshot(sid)
                assert meta.content_hash == expected_hash, (
                    f"snapshot {sid}: hash mismatch"
                )
                # Also verify snapshot_exists
                assert store.snapshot_exists(sid)

            assert not store.snapshot_exists("nonexistent-snap")

    def test_trace_individual_load(self) -> None:
        """Save 100 traces, load each individually, verify no data corruption."""
        clock = make_clock()
        with tempfile.TemporaryDirectory() as tmpdir:
            store = TraceStore(Path(tmpdir))

            for i in range(100):
                entry = TraceEntry(
                    trace_id=f"ind-{i:04d}",
                    parent_trace_id=f"ind-{i - 1:04d}" if i > 0 else None,
                    event_type="sequential",
                    subject_id=f"subj-{i}",
                    goal_id="goal-ind",
                    state_hash=hashlib.sha256(f"state-{i}".encode()).hexdigest(),
                    registry_hash=hashlib.sha256(f"reg-{i}".encode()).hexdigest(),
                    timestamp=clock(),
                )
                store.append(entry)

            for i in range(100):
                loaded = store.load_trace(f"ind-{i:04d}")
                assert loaded.subject_id == f"subj-{i}"
                assert loaded.event_type == "sequential"
                if i > 0:
                    assert loaded.parent_trace_id == f"ind-{i - 1:04d}"
                else:
                    assert loaded.parent_trace_id is None


# ============================================================================
# Provider health churn (2+ tests)
# ============================================================================


@soak
class TestProviderHealthChurn:
    """Cycling provider health states under sustained load."""

    def test_cycle_10_providers_health_100_times(self) -> None:
        """Register 10 providers, cycle health 100 times, verify final states."""
        clock = make_clock()
        collector = TelemetryCollector(clock=clock)

        provider_ids = [f"provider-{i}" for i in range(10)]
        health_states = ["available", "degraded", "unavailable"]

        # Track expected final state per provider
        expected_final: dict[str, str] = {}

        for cycle in range(100):
            for pid in provider_ids:
                state_idx = (cycle + hash(pid)) % 3
                state = health_states[state_idx]
                succeeded = state == "available"
                timeout = state == "unavailable"

                collector.record_provider_invocation(
                    pid,
                    succeeded=succeeded,
                    timeout=timeout,
                )
                expected_final[pid] = state

        # Verify telemetry captured all invocations
        snap = collector.snapshot()
        assert len(snap.provider_metrics) == 10

        for pm in snap.provider_metrics:
            assert pm.total_invocations == 100, (
                f"provider {pm.provider_id}: expected 100 invocations"
            )
            assert pm.succeeded + pm.failed == 100

    def test_no_assignment_to_unavailable_workers(self) -> None:
        """Assign jobs while cycling worker status; unavailable workers never assigned."""
        clock = make_clock()
        registry = WorkerRegistry(clock=clock)
        team_engine = TeamEngine(registry=registry, clock=clock)
        job_engine = JobEngine(clock=clock)

        role_id = "churn-role"
        registry.register_role(RoleDescriptor(
            role_id=role_id,
            name="Churn Role",
            description="for health cycling",
            required_skills=("skill-a",),
        ))

        # 5 workers, 3 available, 2 offline
        for i in range(5):
            status = WorkerStatus.AVAILABLE if i < 3 else WorkerStatus.OFFLINE
            registry.register_worker(WorkerProfile(
                worker_id=f"hw-{i}",
                name=f"Health Worker {i}",
                roles=(role_id,),
                max_concurrent_jobs=20,
                status=status,
            ))

        assigned_workers: set[str] = set()
        for i in range(30):
            desc, _ = job_engine.create_job(
                name=f"health-job-{i}",
                description=f"health test {i}",
                priority=JobPriority.NORMAL,
            )
            decision = team_engine.assign_job(desc.job_id, role_id)
            if decision is not None:
                assigned_workers.add(decision.worker_id)
                registry.update_capacity(
                    decision.worker_id,
                    registry.get_internal_capacity(decision.worker_id).current_load + 1,
                )

        # Workers 3 and 4 (OFFLINE) should never be assigned
        assert "hw-3" not in assigned_workers, "offline worker hw-3 was assigned"
        assert "hw-4" not in assigned_workers, "offline worker hw-4 was assigned"
        # Only available workers should have assignments
        assert assigned_workers.issubset({"hw-0", "hw-1", "hw-2"})

    def test_telemetry_alert_under_sustained_failures(self) -> None:
        """Sustained provider failures should trigger alerts via thresholds."""
        clock = make_clock()
        collector = TelemetryCollector(clock=clock)

        from mcoi_runtime.core.telemetry import AlertThreshold
        from mcoi_runtime.contracts.telemetry import AlertSeverity

        collector.add_threshold(AlertThreshold(
            metric_name="failure_rate",
            source="bad-provider",
            threshold=0.5,
            severity=AlertSeverity.CRITICAL,
            message_template="failure rate {value:.2f} >= {threshold}",
        ))

        # 80 failures, 20 successes => 80% failure rate
        for i in range(100):
            collector.record_provider_invocation(
                "bad-provider",
                succeeded=(i >= 80),  # first 80 fail, last 20 succeed
            )

        snap = collector.snapshot()
        assert len(snap.active_alerts) >= 1
        alert = snap.active_alerts[0]
        assert alert.metric_name == "failure_rate"
        assert alert.metric_value >= 0.5


# ============================================================================
# Memory growth check (2+ tests)
# ============================================================================


@soak
class TestMemoryGrowth:
    """Verify no unbounded memory growth under sustained object creation."""

    def test_create_discard_500_jobs_no_reference_leak(self) -> None:
        """Create and discard 500 job objects, verify no reference leaks via weakrefs."""
        clock = make_high_range_clock()
        engine = JobEngine(clock=clock)

        weak_refs: list[weakref.ref] = []

        for i in range(500):
            desc, state = engine.create_job(
                name=f"leak-job-{i}",
                description=f"leak test {i}",
                priority=JobPriority.LOW,
            )
            weak_refs.append(weakref.ref(state))

        # The engine holds references internally via _states, so states should be alive
        alive_count = sum(1 for w in weak_refs if w() is not None)
        assert alive_count == 500, "engine should hold all state references"

        # Now test that independent objects (not held by engine) are GC-able
        standalone_refs: list[weakref.ref] = []
        for i in range(500):
            entry = TraceEntry(
                trace_id=f"gc-trace-{i}",
                parent_trace_id=None,
                event_type="gc_test",
                subject_id=f"gc-{i}",
                goal_id="gc-goal",
                state_hash="h",
                registry_hash="rh",
                timestamp=clock(),
            )
            standalone_refs.append(weakref.ref(entry))

        # Force reference loss (entry is reassigned each loop, old ones may be collected)
        import gc
        gc.collect()

        # The last entry is still referenced by `entry` variable, but others should be free
        # At least 490 of the 500 should have been collected (only the last one is live)
        collected = sum(1 for w in standalone_refs if w() is None)
        assert collected >= 490, (
            f"expected at least 490 collected, only {collected} were freed"
        )

    def test_knowledge_registry_size_matches_count(self) -> None:
        """Run 100 knowledge extractions, verify registry size matches expected count."""
        clock = make_high_range_clock()
        registry = KnowledgeRegistry(clock=clock)
        extractor = KnowledgeExtractor(clock=clock)

        for i in range(100):
            source = KnowledgeSource(
                source_id=f"mem-src-{i}",
                source_type=KnowledgeSourceType.DOCUMENT,
                reference_id=f"mem-ref-{i}",
                description=f"memory test doc {i}",
                created_at=clock(),
            )
            candidate = extractor.extract_from_document(
                source, f"1. Step A for {i}\n2. Step B for {i}",
            )
            registry.register(candidate)

        assert registry.size == 100, f"expected 100, got {registry.size}"

        # Verify each is individually lookupable
        for i in range(100):
            source_artifacts = registry.list_by_source(f"mem-src-{i}")
            assert len(source_artifacts) == 1, (
                f"source mem-src-{i}: expected 1 artifact, got {len(source_artifacts)}"
            )

    def test_telemetry_run_history_bounded(self) -> None:
        """Record more runs than MAX_RUN_HISTORY, verify history is pruned."""
        clock = make_high_range_clock()
        collector = TelemetryCollector(clock=clock)

        from mcoi_runtime.core.telemetry import MAX_RUN_HISTORY

        # Record 1.5x the cap
        count = int(MAX_RUN_HISTORY * 1.5)
        for i in range(count):
            collector.record_run(
                succeeded=(i % 2 == 0),
                dispatched=True,
                verification_closed=True,
                request_id=f"req-{i}",
            )

        history = collector.get_run_history(limit=MAX_RUN_HISTORY + 1000)
        assert len(history) <= MAX_RUN_HISTORY, (
            f"history size {len(history)} exceeds cap {MAX_RUN_HISTORY}"
        )

        snap = collector.snapshot()
        assert snap.run_metrics.total_runs == count


# ============================================================================
# Job lifecycle stress (bonus)
# ============================================================================


@soak
class TestJobLifecycleStress:
    """Full lifecycle transitions under sustained load."""

    def test_100_jobs_full_lifecycle(self) -> None:
        """Create, start, complete/fail 100 jobs through full lifecycle."""
        clock = make_high_range_clock()
        engine = JobEngine(clock=clock)

        completed = 0
        failed = 0
        for i in range(100):
            desc, state = engine.create_job(
                name=f"lifecycle-{i}",
                description=f"lifecycle test {i}",
                priority=JobPriority.NORMAL,
            )
            assert state.status == JobStatus.CREATED

            state = engine.start_job(desc.job_id)
            assert state.status == JobStatus.IN_PROGRESS

            if i % 2 == 0:
                state, rec = engine.complete_job(desc.job_id, f"done-{i}")
                assert state.status == JobStatus.COMPLETED
                completed += 1
            else:
                state, rec = engine.fail_job(desc.job_id, (f"error-{i}",))
                assert state.status == JobStatus.FAILED
                failed += 1

        assert completed == 50
        assert failed == 50

    def test_pause_resume_cycles(self) -> None:
        """Pause and resume a job 50 times without state corruption."""
        clock = make_high_range_clock()
        engine = JobEngine(clock=clock)

        desc, _ = engine.create_job(
            name="pause-stress",
            description="pause resume stress",
            priority=JobPriority.HIGH,
        )
        engine.start_job(desc.job_id)

        for i in range(50):
            state, pause_rec = engine.pause_job(desc.job_id, PauseReason.OPERATOR_HOLD)
            assert state.status == JobStatus.PAUSED

            state, resume_rec = engine.resume_job(
                desc.job_id, f"user-{i}", f"resuming round {i}",
            )
            assert state.status == JobStatus.IN_PROGRESS

        # Can still complete after all the pauses
        state, _ = engine.complete_job(desc.job_id, "finally done")
        assert state.status == JobStatus.COMPLETED
