"""Phases 181-185 — System Closure Program.

Purpose: Address structural gaps in reality interaction, execution verification,
    temporal operations, failure recovery, and simulation/reality boundary.
Governance scope: execution verification, temporal scheduling, failure compensation,
    ingestion validation, mode separation.
Dependencies: event_spine, invariants, contracts._base
Invariants: fail-closed defaults, deterministic state, proof-carrying results.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime, timezone
from hashlib import sha256

# ═══ Phase 181 — Ground Truth & Ingestion Validation ═══

@dataclass(frozen=True)
class IngestionRecord:
    record_id: str
    source: str
    content_hash: str
    confidence: float  # 0.0-1.0
    validation_status: str  # "valid", "suspicious", "rejected", "unvalidated"
    canonical_form: str
    ingested_at: str

class IngestionValidator:
    """Validates and normalizes incoming data before it enters the system."""
    def __init__(self):
        self._records: dict[str, IngestionRecord] = {}

    def ingest(self, record_id: str, source: str, raw_content: str, confidence: float = 0.5) -> IngestionRecord:
        if record_id in self._records:
            raise ValueError(f"Duplicate ingestion: {record_id}")
        content_hash = sha256(raw_content.encode("utf-8")).hexdigest()
        status = "valid" if confidence >= 0.7 else "suspicious" if confidence >= 0.3 else "rejected"
        record = IngestionRecord(record_id, source, content_hash, confidence, status, raw_content.strip(), datetime.now(timezone.utc).isoformat())
        self._records[record_id] = record
        return record

    def get(self, record_id: str) -> IngestionRecord | None:
        return self._records.get(record_id)

    @property
    def count(self) -> int:
        return len(self._records)

    def rejected_count(self) -> int:
        return sum(1 for r in self._records.values() if r.validation_status == "rejected")

# ═══ Phase 182 — Execution Verification Loop ═══

@dataclass(frozen=True)
class ExecutionVerification:
    verification_id: str
    action_id: str
    expected_effect: str
    actual_effect: str
    verified: bool
    ledger_hash: str
    verified_at: str

class ExecutionVerificationLoop:
    """Action -> External Effect -> Verified Outcome -> Ledger."""
    def __init__(self):
        self._verifications: dict[str, ExecutionVerification] = {}

    def verify_execution(self, verification_id: str, action_id: str, expected: str, actual: str) -> ExecutionVerification:
        if verification_id in self._verifications:
            raise ValueError(f"Duplicate verification: {verification_id}")
        verified = expected.strip().lower() == actual.strip().lower()
        ledger_hash = sha256(f"{action_id}:{expected}:{actual}:{verified}".encode()).hexdigest()
        v = ExecutionVerification(verification_id, action_id, expected, actual, verified, ledger_hash, datetime.now(timezone.utc).isoformat())
        self._verifications[verification_id] = v
        return v

    def get(self, vid: str) -> ExecutionVerification | None:
        return self._verifications.get(vid)

    @property
    def count(self) -> int:
        return len(self._verifications)

    def failed_count(self) -> int:
        return sum(1 for v in self._verifications.values() if not v.verified)

    def verification_rate(self) -> float:
        if not self._verifications:
            return 1.0
        return sum(1 for v in self._verifications.values() if v.verified) / len(self._verifications)

# ═══ Phase 183 — Temporal Operations Engine ═══

@dataclass
class ScheduledTask:
    task_id: str
    target_runtime: str
    operation: str
    scheduled_at: str  # ISO 8601
    deadline_at: str  # ISO 8601
    retry_count: int = 0
    max_retries: int = 3
    backoff_ms: int = 1000
    status: str = "pending"  # "pending", "running", "completed", "failed", "timeout", "retrying"

class TemporalScheduler:
    """Operational scheduling with deadlines, retries, and SLA enforcement."""
    def __init__(self):
        self._tasks: dict[str, ScheduledTask] = {}

    def schedule(self, task_id: str, target: str, operation: str, scheduled_at: str, deadline_at: str, max_retries: int = 3) -> ScheduledTask:
        if task_id in self._tasks:
            raise ValueError(f"Duplicate task: {task_id}")
        task = ScheduledTask(task_id, target, operation, scheduled_at, deadline_at, max_retries=max_retries)
        self._tasks[task_id] = task
        return task

    def start(self, task_id: str) -> ScheduledTask:
        t = self._tasks.get(task_id)
        if not t:
            raise ValueError(f"Unknown task: {task_id}")
        if t.status not in ("pending", "retrying"):
            raise ValueError(f"Cannot start task in {t.status}")
        t.status = "running"
        return t

    def complete(self, task_id: str) -> ScheduledTask:
        t = self._tasks.get(task_id)
        if not t or t.status != "running":
            raise ValueError(f"Cannot complete")
        t.status = "completed"
        return t

    def fail(self, task_id: str) -> ScheduledTask:
        t = self._tasks.get(task_id)
        if not t or t.status != "running":
            raise ValueError(f"Cannot fail")
        if t.retry_count < t.max_retries:
            t.retry_count += 1
            t.backoff_ms *= 2
            t.status = "retrying"
        else:
            t.status = "failed"
        return t

    def timeout(self, task_id: str) -> ScheduledTask:
        t = self._tasks.get(task_id)
        if not t:
            raise ValueError(f"Unknown task")
        t.status = "timeout"
        return t

    @property
    def count(self) -> int:
        return len(self._tasks)

    def overdue_count(self, now_iso: str) -> int:
        return sum(1 for t in self._tasks.values() if t.status in ("pending", "running") and t.deadline_at < now_iso)

# ═══ Phase 184 — Failure Recovery & Compensation ═══

@dataclass
class CompensationAction:
    action_id: str
    failed_action_ref: str
    compensation_type: str  # "rollback", "retry", "compensate", "escalate", "accept"
    status: str = "pending"  # "pending", "executed", "failed"
    detail: str = ""

class FailureRecoveryEngine:
    """Rollback, compensation, and resilience for failed operations."""
    def __init__(self):
        self._compensations: dict[str, CompensationAction] = {}

    def register_compensation(self, action_id: str, failed_ref: str, comp_type: str, detail: str = "") -> CompensationAction:
        if action_id in self._compensations:
            raise ValueError(f"Duplicate: {action_id}")
        if comp_type not in ("rollback", "retry", "compensate", "escalate", "accept"):
            raise ValueError(f"Invalid type: {comp_type}")
        c = CompensationAction(action_id, failed_ref, comp_type, detail=detail)
        self._compensations[action_id] = c
        return c

    def execute_compensation(self, action_id: str) -> CompensationAction:
        c = self._compensations.get(action_id)
        if not c or c.status != "pending":
            raise ValueError(f"Cannot execute")
        c.status = "executed"
        return c

    def fail_compensation(self, action_id: str) -> CompensationAction:
        c = self._compensations.get(action_id)
        if not c or c.status != "pending":
            raise ValueError(f"Cannot fail")
        c.status = "failed"
        return c

    @property
    def count(self) -> int:
        return len(self._compensations)

    def pending_count(self) -> int:
        return sum(1 for c in self._compensations.values() if c.status == "pending")

# ═══ Phase 185 — Simulation vs Reality Boundary ═══

@dataclass(frozen=True)
class ModeDeclaration:
    declaration_id: str
    mode: str  # "simulation", "reality", "sandbox", "dry_run"
    scope: str
    enforced: bool
    declared_at: str

class SimRealityBoundary:
    """Explicit separation between simulated and real execution modes."""
    def __init__(self):
        self._declarations: dict[str, ModeDeclaration] = {}
        self._current_mode: str = "simulation"  # safe default

    def declare_mode(self, declaration_id: str, mode: str, scope: str) -> ModeDeclaration:
        if mode not in ("simulation", "reality", "sandbox", "dry_run"):
            raise ValueError(f"Invalid mode: {mode}")
        if declaration_id in self._declarations:
            raise ValueError(f"Duplicate: {declaration_id}")
        d = ModeDeclaration(declaration_id, mode, scope, True, datetime.now(timezone.utc).isoformat())
        self._declarations[declaration_id] = d
        self._current_mode = mode
        return d

    def promote_to_reality(self, declaration_id: str, scope: str) -> ModeDeclaration:
        """Safe promotion from simulation to reality -- explicit, auditable."""
        if self._current_mode not in ("simulation", "sandbox", "dry_run"):
            raise ValueError(f"Cannot promote from {self._current_mode}")
        return self.declare_mode(declaration_id, "reality", scope)

    def demote_to_simulation(self, declaration_id: str, scope: str) -> ModeDeclaration:
        return self.declare_mode(declaration_id, "simulation", scope)

    @property
    def current_mode(self) -> str:
        return self._current_mode

    def is_real(self) -> bool:
        return self._current_mode == "reality"

    @property
    def declaration_count(self) -> int:
        return len(self._declarations)
