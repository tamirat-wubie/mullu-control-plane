"""Runbook Learning — detect repeated patterns and promote to governed runbooks.

Purpose: observe successful execution patterns from the audit trail,
    detect repetition, and promote verified patterns into reusable
    governed runbooks. Requires explicit operator approval before promotion.
Governance scope: pattern detection and promotion pipeline only.
Dependencies: audit trail (read), clock injection.
Invariants:
  - Patterns are detected from real execution history, never fabricated.
  - Promotion requires explicit approval — no silent automation.
  - Promoted runbooks are versioned and bound to policy packs.
  - Learning history is bounded.
"""

from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from hashlib import sha256
from typing import Any, Callable


class RunbookStatus(StrEnum):
    """Lifecycle of a learned runbook."""

    CANDIDATE = "candidate"
    APPROVED = "approved"
    ACTIVE = "active"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class ExecutionPattern:
    """A detected repeated execution pattern."""

    pattern_id: str
    action_sequence: tuple[str, ...]
    occurrence_count: int
    first_seen: str
    last_seen: str
    success_rate: float
    tenant_ids: tuple[str, ...]
    sample_targets: tuple[str, ...]


@dataclass
class LearnedRunbook:
    """A runbook promoted from a detected pattern."""

    runbook_id: str
    name: str
    description: str
    pattern_id: str
    action_sequence: tuple[str, ...]
    status: RunbookStatus
    policy_pack_id: str
    version: int
    created_at: str
    approved_at: str = ""
    approved_by: str = ""
    occurrence_count: int = 0
    success_rate: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class RunbookLearningEngine:
    """Detects execution patterns and manages runbook promotion pipeline.

    Workflow:
    1. analyze() — scan audit trail for repeated successful patterns
    2. promote() — create a candidate runbook from a pattern
    3. approve() — operator approves a candidate for active use
    4. retire() — deactivate an approved runbook
    """

    _MAX_PATTERNS = 500
    _MAX_RUNBOOKS = 200
    _MIN_OCCURRENCES = 3
    _MIN_SUCCESS_RATE = 0.8

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._patterns: dict[str, ExecutionPattern] = {}
        self._runbooks: dict[str, LearnedRunbook] = {}
        self._lock = threading.Lock()

    def analyze(self, audit_entries: list[Any]) -> list[ExecutionPattern]:
        """Scan audit entries for repeated successful action sequences.

        Groups consecutive actions by actor_id, detects sequences that
        repeat with high success rates.
        """
        # Group actions by actor
        actor_sequences: dict[str, list[dict[str, str]]] = {}
        for entry in audit_entries:
            actor = getattr(entry, "actor_id", "")
            action = getattr(entry, "action", "")
            outcome = getattr(entry, "outcome", "")
            target = getattr(entry, "target", "")
            tenant = getattr(entry, "tenant_id", "")
            timestamp = getattr(entry, "recorded_at", "")
            if actor and action:
                actor_sequences.setdefault(actor, []).append({
                    "action": action,
                    "outcome": outcome,
                    "target": target,
                    "tenant_id": tenant,
                    "timestamp": timestamp,
                })

        # Detect repeated action sequences (sliding window, size 2-5)
        sequence_counts: Counter[tuple[str, ...]] = Counter()
        sequence_meta: dict[tuple[str, ...], dict[str, Any]] = {}

        for actor, actions in actor_sequences.items():
            for window_size in range(2, min(6, len(actions) + 1)):
                for i in range(len(actions) - window_size + 1):
                    window = actions[i:i + window_size]
                    seq = tuple(a["action"] for a in window)
                    successes = sum(1 for a in window if a["outcome"] == "success")
                    sequence_counts[seq] += 1
                    if seq not in sequence_meta:
                        sequence_meta[seq] = {
                            "first_seen": window[0]["timestamp"],
                            "last_seen": window[-1]["timestamp"],
                            "successes": 0,
                            "total": 0,
                            "tenants": set(),
                            "targets": set(),
                        }
                    meta = sequence_meta[seq]
                    meta["successes"] += successes
                    meta["total"] += len(window)
                    meta["last_seen"] = window[-1]["timestamp"]
                    for a in window:
                        if a["tenant_id"]:
                            meta["tenants"].add(a["tenant_id"])
                        if a["target"]:
                            meta["targets"].add(a["target"])

        # Filter to patterns meeting thresholds
        patterns: list[ExecutionPattern] = []
        for seq, count in sequence_counts.most_common(self._MAX_PATTERNS):
            if count < self._MIN_OCCURRENCES:
                continue
            meta = sequence_meta[seq]
            success_rate = meta["successes"] / max(meta["total"], 1)
            if success_rate < self._MIN_SUCCESS_RATE:
                continue

            pattern_id = f"pat-{sha256(':'.join(seq).encode()).hexdigest()[:12]}"
            pattern = ExecutionPattern(
                pattern_id=pattern_id,
                action_sequence=seq,
                occurrence_count=count,
                first_seen=meta["first_seen"],
                last_seen=meta["last_seen"],
                success_rate=round(success_rate, 3),
                tenant_ids=tuple(sorted(meta["tenants"]))[:10],
                sample_targets=tuple(sorted(meta["targets"]))[:10],
            )
            patterns.append(pattern)
            with self._lock:
                self._patterns[pattern_id] = pattern

        return patterns

    def promote(
        self,
        pattern_id: str,
        name: str,
        description: str = "",
        policy_pack_id: str = "default",
    ) -> LearnedRunbook:
        """Create a candidate runbook from a detected pattern."""
        with self._lock:
            pattern = self._patterns.get(pattern_id)
        if pattern is None:
            raise ValueError(f"pattern not found: {pattern_id}")

        now = self._clock()
        runbook_id = f"rb-{sha256(f'{pattern_id}:{now}'.encode()).hexdigest()[:12]}"
        runbook = LearnedRunbook(
            runbook_id=runbook_id,
            name=name,
            description=description or f"Learned from pattern {pattern_id}",
            pattern_id=pattern_id,
            action_sequence=pattern.action_sequence,
            status=RunbookStatus.CANDIDATE,
            policy_pack_id=policy_pack_id,
            version=1,
            created_at=now,
            occurrence_count=pattern.occurrence_count,
            success_rate=pattern.success_rate,
        )
        with self._lock:
            self._runbooks[runbook_id] = runbook
        return runbook

    def approve(self, runbook_id: str, approved_by: str) -> LearnedRunbook:
        """Operator approves a candidate runbook for active use."""
        with self._lock:
            runbook = self._runbooks.get(runbook_id)
            if runbook is None:
                raise ValueError(f"runbook not found: {runbook_id}")
            if runbook.status != RunbookStatus.CANDIDATE:
                raise ValueError(f"runbook {runbook_id} is not a candidate (status: {runbook.status.value})")
            runbook.status = RunbookStatus.APPROVED
            runbook.approved_at = self._clock()
            runbook.approved_by = approved_by
        return runbook

    def activate(self, runbook_id: str) -> LearnedRunbook:
        """Activate an approved runbook."""
        with self._lock:
            runbook = self._runbooks.get(runbook_id)
            if runbook is None:
                raise ValueError(f"runbook not found: {runbook_id}")
            if runbook.status != RunbookStatus.APPROVED:
                raise ValueError("runbook must be approved before activation")
            runbook.status = RunbookStatus.ACTIVE
        return runbook

    def retire(self, runbook_id: str) -> LearnedRunbook:
        """Retire an active runbook."""
        with self._lock:
            runbook = self._runbooks.get(runbook_id)
            if runbook is None:
                raise ValueError(f"runbook not found: {runbook_id}")
            runbook.status = RunbookStatus.RETIRED
        return runbook

    def list_patterns(self, limit: int = 50) -> list[ExecutionPattern]:
        with self._lock:
            return sorted(
                self._patterns.values(),
                key=lambda p: -p.occurrence_count,
            )[:limit]

    def list_runbooks(self, status: RunbookStatus | None = None) -> list[LearnedRunbook]:
        with self._lock:
            runbooks = list(self._runbooks.values())
            if status is not None:
                runbooks = [r for r in runbooks if r.status == status]
            return sorted(runbooks, key=lambda r: r.runbook_id)

    def get_runbook(self, runbook_id: str) -> LearnedRunbook | None:
        return self._runbooks.get(runbook_id)

    def summary(self) -> dict[str, Any]:
        with self._lock:
            statuses = Counter(r.status.value for r in self._runbooks.values())
            return {
                "patterns_detected": len(self._patterns),
                "total_runbooks": len(self._runbooks),
                "candidates": statuses.get("candidate", 0),
                "approved": statuses.get("approved", 0),
                "active": statuses.get("active", 0),
                "retired": statuses.get("retired", 0),
            }
