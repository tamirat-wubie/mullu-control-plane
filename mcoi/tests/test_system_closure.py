"""Tests for Phases 181-185 — System Closure Program."""
from __future__ import annotations
import pytest
from hashlib import sha256

from mcoi_runtime.core.system_closure import (
    IngestionValidator,
    ExecutionVerificationLoop,
    TemporalScheduler,
    FailureRecoveryEngine,
    SimRealityBoundary,
)

# ═══ Phase 181 — Ingestion Validation ═══

class TestIngestionValidator:
    def test_ingest_valid(self):
        v = IngestionValidator()
        r = v.ingest("r1", "sensor-a", "hello world", confidence=0.9)
        assert r.validation_status == "valid"
        assert r.confidence == 0.9
        assert r.canonical_form == "hello world"
        assert v.count == 1

    def test_ingest_suspicious(self):
        v = IngestionValidator()
        r = v.ingest("r1", "sensor-b", "maybe", confidence=0.5)
        assert r.validation_status == "suspicious"

    def test_ingest_rejected(self):
        v = IngestionValidator()
        r = v.ingest("r1", "sensor-c", "garbage", confidence=0.1)
        assert r.validation_status == "rejected"

    def test_duplicate_blocked(self):
        v = IngestionValidator()
        v.ingest("r1", "s", "data")
        with pytest.raises(ValueError, match="Duplicate"):
            v.ingest("r1", "s", "data2")

    def test_rejected_count(self):
        v = IngestionValidator()
        v.ingest("r1", "s", "ok", confidence=0.8)
        v.ingest("r2", "s", "bad", confidence=0.1)
        v.ingest("r3", "s", "worse", confidence=0.05)
        assert v.rejected_count() == 2
        assert v.count == 3

    def test_content_hash_deterministic(self):
        v = IngestionValidator()
        r = v.ingest("r1", "s", "fixed content", confidence=0.9)
        expected = sha256(b"fixed content").hexdigest()
        assert r.content_hash == expected

# ═══ Phase 182 — Execution Verification ═══

class TestExecutionVerificationLoop:
    def test_verify_match(self):
        loop = ExecutionVerificationLoop()
        v = loop.verify_execution("v1", "a1", "effect-X", "effect-X")
        assert v.verified is True
        assert loop.count == 1

    def test_verify_mismatch(self):
        loop = ExecutionVerificationLoop()
        v = loop.verify_execution("v1", "a1", "effect-X", "effect-Y")
        assert v.verified is False

    def test_ledger_hash_deterministic(self):
        loop = ExecutionVerificationLoop()
        v = loop.verify_execution("v1", "a1", "X", "X")
        expected = sha256(b"a1:X:X:True").hexdigest()
        assert v.ledger_hash == expected

    def test_failed_count(self):
        loop = ExecutionVerificationLoop()
        loop.verify_execution("v1", "a1", "X", "X")
        loop.verify_execution("v2", "a2", "X", "Y")
        loop.verify_execution("v3", "a3", "A", "B")
        assert loop.failed_count() == 2

    def test_verification_rate(self):
        loop = ExecutionVerificationLoop()
        loop.verify_execution("v1", "a1", "X", "X")
        loop.verify_execution("v2", "a2", "X", "Y")
        assert loop.verification_rate() == 0.5

    def test_verification_rate_empty(self):
        loop = ExecutionVerificationLoop()
        assert loop.verification_rate() == 1.0

# ═══ Phase 183 — Temporal Scheduler ═══

class TestTemporalScheduler:
    def test_schedule_and_start(self):
        s = TemporalScheduler()
        t = s.schedule("t1", "runtime-a", "op", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
        assert t.status == "pending"
        s.start("t1")
        assert t.status == "running"

    def test_complete(self):
        s = TemporalScheduler()
        s.schedule("t1", "r", "op", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
        s.start("t1")
        s.complete("t1")
        t = s._tasks["t1"]
        assert t.status == "completed"

    def test_fail_with_retry_and_backoff(self):
        s = TemporalScheduler()
        s.schedule("t1", "r", "op", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", max_retries=2)
        s.start("t1")
        t = s.fail("t1")
        assert t.status == "retrying"
        assert t.retry_count == 1
        assert t.backoff_ms == 2000

    def test_fail_exhausts_retries(self):
        s = TemporalScheduler()
        s.schedule("t1", "r", "op", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", max_retries=1)
        s.start("t1")
        s.fail("t1")  # retrying
        s.start("t1")  # restart
        t = s.fail("t1")  # now exhausted
        assert t.status == "failed"

    def test_timeout(self):
        s = TemporalScheduler()
        s.schedule("t1", "r", "op", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
        s.timeout("t1")
        assert s._tasks["t1"].status == "timeout"

    def test_overdue_count(self):
        s = TemporalScheduler()
        s.schedule("t1", "r", "op", "2026-01-01T00:00:00Z", "2026-01-01T12:00:00Z")
        s.schedule("t2", "r", "op", "2026-01-01T00:00:00Z", "2026-12-31T00:00:00Z")
        assert s.overdue_count("2026-06-01T00:00:00Z") == 1

    def test_duplicate_task_blocked(self):
        s = TemporalScheduler()
        s.schedule("t1", "r", "op", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
        with pytest.raises(ValueError, match="Duplicate"):
            s.schedule("t1", "r", "op2", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")

# ═══ Phase 184 — Failure Recovery ═══

class TestFailureRecoveryEngine:
    def test_register_and_execute(self):
        e = FailureRecoveryEngine()
        c = e.register_compensation("c1", "failed-a1", "rollback")
        assert c.status == "pending"
        e.execute_compensation("c1")
        assert c.status == "executed"

    def test_fail_compensation(self):
        e = FailureRecoveryEngine()
        e.register_compensation("c1", "f1", "retry")
        e.fail_compensation("c1")
        assert e._compensations["c1"].status == "failed"

    def test_invalid_type_blocked(self):
        e = FailureRecoveryEngine()
        with pytest.raises(ValueError, match="Invalid type"):
            e.register_compensation("c1", "f1", "nuke")

    def test_duplicate_blocked(self):
        e = FailureRecoveryEngine()
        e.register_compensation("c1", "f1", "accept")
        with pytest.raises(ValueError, match="Duplicate"):
            e.register_compensation("c1", "f2", "accept")

    def test_pending_count(self):
        e = FailureRecoveryEngine()
        e.register_compensation("c1", "f1", "rollback")
        e.register_compensation("c2", "f2", "escalate")
        e.execute_compensation("c1")
        assert e.pending_count() == 1
        assert e.count == 2

# ═══ Phase 185 — Simulation/Reality Boundary ═══

class TestSimRealityBoundary:
    def test_safe_default(self):
        b = SimRealityBoundary()
        assert b.current_mode == "simulation"
        assert b.is_real() is False

    def test_declare_mode(self):
        b = SimRealityBoundary()
        d = b.declare_mode("d1", "sandbox", "test-scope")
        assert d.mode == "sandbox"
        assert b.current_mode == "sandbox"

    def test_promote_sim_to_reality(self):
        b = SimRealityBoundary()
        b.promote_to_reality("d1", "prod")
        assert b.current_mode == "reality"
        assert b.is_real() is True

    def test_cannot_promote_from_reality(self):
        b = SimRealityBoundary()
        b.declare_mode("d1", "reality", "prod")
        with pytest.raises(ValueError, match="Cannot promote"):
            b.promote_to_reality("d2", "prod")

    def test_demote_to_simulation(self):
        b = SimRealityBoundary()
        b.declare_mode("d1", "reality", "prod")
        b.demote_to_simulation("d2", "prod")
        assert b.current_mode == "simulation"
        assert b.is_real() is False

    def test_invalid_mode_rejected(self):
        b = SimRealityBoundary()
        with pytest.raises(ValueError, match="Invalid mode"):
            b.declare_mode("d1", "production", "scope")

# ═══ Golden: Full Lifecycle ═══

class TestSystemClosureGolden:
    def test_ingestion_to_verification_lifecycle(self):
        """Ingest data, verify execution against it, check ledger integrity."""
        iv = IngestionValidator()
        rec = iv.ingest("data-1", "api", "expected_output", confidence=0.95)
        assert rec.validation_status == "valid"

        evl = ExecutionVerificationLoop()
        v = evl.verify_execution("v1", "action-run-1", "expected_output", "expected_output")
        assert v.verified is True
        assert evl.verification_rate() == 1.0

    def test_failure_compensation_mode_boundary_lifecycle(self):
        """Schedule task, fail it, compensate, then cross mode boundary."""
        # Schedule and fail
        sched = TemporalScheduler()
        sched.schedule("t1", "runtime", "deploy", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", max_retries=0)
        sched.start("t1")
        t = sched.fail("t1")
        assert t.status == "failed"

        # Compensate
        fre = FailureRecoveryEngine()
        fre.register_compensation("comp-1", "t1", "rollback", detail="undo deploy")
        fre.execute_compensation("comp-1")
        assert fre.pending_count() == 0

        # Mode boundary: ensure we were in simulation, promote safely
        boundary = SimRealityBoundary()
        assert boundary.current_mode == "simulation"
        boundary.promote_to_reality("go-live", "deploy-scope")
        assert boundary.is_real() is True
        assert boundary.declaration_count == 1
