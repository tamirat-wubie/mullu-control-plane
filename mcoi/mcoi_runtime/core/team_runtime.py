"""Purpose: team runtime core engine — worker registry, assignment, handoff, and workload management.
Governance scope: worker lifecycle, role-based assignment, capacity tracking, workload rebalancing.
Dependencies: roles contracts, invariant helpers.
Invariants:
  - Worker/role/policy registration rejects duplicate IDs.
  - Lookups return None for missing records; never raise.
  - Assignment uses policy strategy (least_loaded default).
  - If all workers for a role are at capacity, assignment returns None (escalation needed).
  - Handoff creates a provenance record with timestamps and thread context.
  - Clock function is injected for determinism.
  - No network logic; all operations are in-memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from mcoi_runtime.contracts.roles import (
    AssignmentDecision,
    AssignmentPolicy,
    AssignmentStrategy,
    HandoffReason,
    HandoffRecord,
    RoleDescriptor,
    TeamQueueState,
    WorkerCapacity,
    WorkerProfile,
    WorkerStatus,
    WorkloadSnapshot,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


# --- Internal capacity tracking (not exported as contract) ---

@dataclass
class _InternalCapacity:
    """Mutable capacity tracker used inside the registry."""
    worker_id: str
    max_concurrent: int
    current_load: int

    @property
    def available_slots(self) -> int:
        return max(0, self.max_concurrent - self.current_load)

    @property
    def clamped_load(self) -> int:
        """Load clamped to max for contract-valid capacity records."""
        return min(self.current_load, self.max_concurrent)


class WorkerRegistry:
    """In-memory registry for workers, roles, and assignment policies.

    Rules:
    - Duplicate IDs on registration are rejected.
    - Lookups return None for missing records.
    - get_workers_for_role returns workers whose roles include the given role.
    - update_capacity recalculates available_slots from max_concurrent - current_load.
    """

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._workers: dict[str, WorkerProfile] = {}
        self._roles: dict[str, RoleDescriptor] = {}
        self._policies: dict[str, AssignmentPolicy] = {}
        self._capacities: dict[str, _InternalCapacity] = {}

    # --- Worker ---

    def register_worker(self, profile: WorkerProfile) -> WorkerProfile:
        """Register a worker profile. Rejects duplicate worker_id."""
        if profile.worker_id in self._workers:
            raise RuntimeCoreInvariantError(
                f"worker already registered: {profile.worker_id}"
            )
        self._workers[profile.worker_id] = profile
        # Initialize capacity tracking
        self._capacities[profile.worker_id] = _InternalCapacity(
            worker_id=profile.worker_id,
            max_concurrent=profile.max_concurrent_jobs,
            current_load=0,
        )
        return profile

    def get_worker(self, worker_id: str) -> WorkerProfile | None:
        """Return worker profile or None if not found."""
        return self._workers.get(worker_id)

    # --- Role ---

    def register_role(self, descriptor: RoleDescriptor) -> RoleDescriptor:
        """Register a role descriptor. Rejects duplicate role_id."""
        if descriptor.role_id in self._roles:
            raise RuntimeCoreInvariantError(
                f"role already registered: {descriptor.role_id}"
            )
        self._roles[descriptor.role_id] = descriptor
        return descriptor

    def get_role(self, role_id: str) -> RoleDescriptor | None:
        """Return role descriptor or None if not found."""
        return self._roles.get(role_id)

    def list_role_ids(self) -> tuple[str, ...]:
        """Return all registered role IDs."""
        return tuple(self._roles)

    def get_workers_for_role(self, role_id: str) -> tuple[WorkerProfile, ...]:
        """Return all workers whose roles include the given role."""
        return tuple(
            w for w in self._workers.values()
            if role_id in w.roles
        )

    # --- Policy ---

    def register_policy(self, policy: AssignmentPolicy) -> AssignmentPolicy:
        """Register an assignment policy. Rejects duplicate policy_id."""
        if policy.policy_id in self._policies:
            raise RuntimeCoreInvariantError(
                f"policy already registered: {policy.policy_id}"
            )
        self._policies[policy.policy_id] = policy
        return policy

    def get_policy(self, policy_id: str) -> AssignmentPolicy | None:
        """Return assignment policy or None if not found."""
        return self._policies.get(policy_id)

    # --- Capacity ---

    def update_capacity(self, worker_id: str, current_load: int) -> WorkerCapacity:
        """Update worker load and return a contract-valid WorkerCapacity snapshot."""
        if worker_id not in self._workers:
            raise RuntimeCoreInvariantError(f"worker not found: {worker_id}")
        profile = self._workers[worker_id]
        internal = _InternalCapacity(
            worker_id=worker_id,
            max_concurrent=profile.max_concurrent_jobs,
            current_load=current_load,
        )
        self._capacities[worker_id] = internal
        now = self._clock()
        # Contract requires available_slots == max - load, and load >= 0.
        # Clamp load to max for the contract record.
        clamped_load = internal.clamped_load
        return WorkerCapacity(
            worker_id=worker_id,
            max_concurrent=profile.max_concurrent_jobs,
            current_load=clamped_load,
            available_slots=profile.max_concurrent_jobs - clamped_load,
            updated_at=now,
        )

    def get_internal_capacity(self, worker_id: str) -> _InternalCapacity | None:
        """Return internal capacity tracker for a worker."""
        return self._capacities.get(worker_id)

    def list_all_capacities(self) -> dict[str, _InternalCapacity]:
        """Return all internal capacity trackers (worker_id -> capacity)."""
        return dict(self._capacities)


class TeamEngine:
    """Manages job assignment, handoff, workload snapshots, and rebalancing.

    All timestamps are produced by the injected clock function for determinism.
    """

    def __init__(self, *, registry: WorkerRegistry, clock: Callable[[], str]) -> None:
        self._registry = registry
        self._clock = clock

    @property
    def registry(self) -> WorkerRegistry:
        """Public accessor for the worker registry."""
        return self._registry

    # --- Assignment ---

    def assign_job(self, job_id: str, role_id: str) -> AssignmentDecision | None:
        """Assign a job to the best available worker for a role.

        Strategy: least_loaded — pick the active worker with the most available_slots.
        Returns None if no workers are available (escalation needed).
        """
        ensure_non_empty_text("job_id", job_id)
        ensure_non_empty_text("role_id", role_id)
        now = self._clock()

        workers = self._registry.get_workers_for_role(role_id)
        if not workers:
            return None

        # Find the active worker with the most available_slots
        best_worker: WorkerProfile | None = None
        best_slots = -1

        for w in workers:
            if w.status != WorkerStatus.AVAILABLE:
                continue
            cap = self._registry.get_internal_capacity(w.worker_id)
            if cap is None:
                continue
            if cap.available_slots > best_slots:
                best_slots = cap.available_slots
                best_worker = w

        if best_worker is None or best_slots <= 0:
            return None

        decision_id = stable_identifier("assign-decision", {
            "job_id": job_id,
            "worker_id": best_worker.worker_id,
            "decided_at": now,
        })
        return AssignmentDecision(
            decision_id=decision_id,
            job_id=job_id,
            worker_id=best_worker.worker_id,
            role_id=role_id,
            reason=f"least loaded worker with {best_slots} available slots",
            decided_at=now,
        )

    # --- Handoff ---

    def handoff_job(
        self,
        job_id: str,
        from_worker_id: str,
        to_worker_id: str,
        reason: HandoffReason,
        *,
        thread_id: str | None = None,
    ) -> HandoffRecord:
        """Transfer a job from one worker to another, creating a provenance record."""
        ensure_non_empty_text("job_id", job_id)
        ensure_non_empty_text("from_worker_id", from_worker_id)
        ensure_non_empty_text("to_worker_id", to_worker_id)
        now = self._clock()
        handoff_id = stable_identifier("handoff", {
            "job_id": job_id,
            "from": from_worker_id,
            "to": to_worker_id,
            "at": now,
        })
        return HandoffRecord(
            handoff_id=handoff_id,
            job_id=job_id,
            from_worker_id=from_worker_id,
            to_worker_id=to_worker_id,
            reason=reason,
            thread_id=thread_id,
            handoff_at=now,
        )

    # --- Workload observation ---

    def capture_workload(self, team_id: str) -> WorkloadSnapshot | None:
        """Capture a point-in-time workload snapshot for all registered workers.

        Returns None if no workers are registered (contract requires non-empty capacities).
        """
        ensure_non_empty_text("team_id", team_id)
        now = self._clock()

        capacities: list[WorkerCapacity] = []
        for wid, internal in self._registry.list_all_capacities().items():
            clamped = internal.clamped_load
            capacities.append(WorkerCapacity(
                worker_id=wid,
                max_concurrent=internal.max_concurrent,
                current_load=clamped,
                available_slots=internal.max_concurrent - clamped,
                updated_at=now,
            ))

        if not capacities:
            return None

        snapshot_id = stable_identifier("workload-snap", {
            "team_id": team_id,
            "captured_at": now,
        })
        return WorkloadSnapshot(
            snapshot_id=snapshot_id,
            team_id=team_id,
            worker_capacities=tuple(capacities),
            captured_at=now,
        )

    def capture_queue_state(
        self,
        team_id: str,
        queued: int,
        assigned: int,
        waiting: int,
    ) -> TeamQueueState:
        """Capture a point-in-time queue state snapshot."""
        ensure_non_empty_text("team_id", team_id)
        now = self._clock()
        overloaded_count = len(self.find_overloaded_workers())
        return TeamQueueState(
            team_id=team_id,
            queued_jobs=queued,
            assigned_jobs=assigned,
            waiting_jobs=waiting,
            overloaded_workers=overloaded_count,
            captured_at=now,
        )

    # --- Overload and availability detection ---

    def find_overloaded_workers(self) -> list[str]:
        """Return worker_ids where current_load >= max_concurrent."""
        overloaded: list[str] = []
        for wid, cap in self._registry.list_all_capacities().items():
            if cap.current_load >= cap.max_concurrent:
                overloaded.append(wid)
        return overloaded

    def find_available_workers(self, role_id: str) -> list[WorkerProfile]:
        """Return workers for a role that have available slots and are active."""
        workers = self._registry.get_workers_for_role(role_id)
        available: list[WorkerProfile] = []
        for w in workers:
            if w.status != WorkerStatus.AVAILABLE:
                continue
            cap = self._registry.get_internal_capacity(w.worker_id)
            if cap is not None and cap.available_slots > 0:
                available.append(w)
        return available

    # --- Rebalancing ---

    def rebalance_suggestion(
        self, role_id: str,
    ) -> list[tuple[str, str, int]]:
        """Suggest moving jobs from overloaded to underloaded workers for a role.

        Returns a list of (from_worker_id, to_worker_id, job_count) tuples.
        Jobs are moved one at a time from the most loaded to the least loaded
        until no worker is overloaded or no underloaded workers remain.
        """
        workers = self._registry.get_workers_for_role(role_id)
        if not workers:
            return []

        # Build load map for active workers only
        load_map: dict[str, int] = {}
        max_map: dict[str, int] = {}
        for w in workers:
            if w.status != WorkerStatus.AVAILABLE:
                continue
            cap = self._registry.get_internal_capacity(w.worker_id)
            if cap is not None:
                load_map[w.worker_id] = cap.current_load
                max_map[w.worker_id] = cap.max_concurrent

        suggestions: list[tuple[str, str, int]] = []

        # Iteratively move one job at a time from most-loaded to least-loaded
        max_iterations = sum(load_map.values()) + 1  # safety bound
        for _ in range(max_iterations):
            # Find overloaded workers (load >= max)
            overloaded = [
                wid for wid, load in load_map.items()
                if load >= max_map[wid] and load > 0
            ]
            if not overloaded:
                break

            # Find underloaded workers (load < max)
            underloaded = [
                wid for wid, load in load_map.items()
                if load < max_map[wid]
            ]
            if not underloaded:
                break

            # Pick the most loaded and least loaded
            from_wid = max(overloaded, key=lambda wid: load_map[wid])
            to_wid = min(underloaded, key=lambda wid: load_map[wid])

            load_map[from_wid] -= 1
            load_map[to_wid] += 1

            # Merge into existing suggestion if same pair
            merged = False
            for i, (fw, tw, cnt) in enumerate(suggestions):
                if fw == from_wid and tw == to_wid:
                    suggestions[i] = (fw, tw, cnt + 1)
                    merged = True
                    break
            if not merged:
                suggestions.append((from_wid, to_wid, 1))

        return suggestions
