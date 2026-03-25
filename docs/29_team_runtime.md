# 29 Team Runtime

## Purpose

The team runtime subsystem governs role-based job assignment, worker capacity
tracking, queue balancing, explicit handoffs, and workload-aware escalation.

Jobs route through roles to workers. Each worker declares a capacity ceiling.
The runtime enforces that ceiling, balances load across eligible workers, and
produces typed audit records for every assignment, handoff, and escalation.

## Owned Artifacts

| Contract               | Responsibility                                      |
|------------------------|-----------------------------------------------------|
| `RoleDescriptor`       | Defines a role with required skills and constraints  |
| `WorkerProfile`        | Identity, role memberships, capacity, and status     |
| `WorkerCapacity`       | Point-in-time load snapshot for a single worker      |
| `AssignmentPolicy`     | Strategy binding for how jobs reach workers           |
| `AssignmentDecision`   | Audit record for a single assignment decision         |
| `HandoffRecord`        | Explicit job transfer between workers                 |
| `WorkloadSnapshot`     | Team-wide capacity snapshot at a point in time        |
| `TeamQueueState`       | Aggregate queue health for a team                     |

Supporting enums: `WorkerStatus`, `AssignmentStrategy`, `HandoffReason`.

## Assignment Model

1. A job enters the system with a target **role** (via `AssignmentPolicy`).
2. The runtime resolves eligible **workers** whose `WorkerProfile.roles`
   includes the target role and whose status is `available` or `busy` (not
   `overloaded`, `offline`, or `on_hold`).
3. The `AssignmentPolicy.strategy` selects the worker:
   - `least_loaded` -- worker with the most `available_slots`.
   - `round_robin` -- next worker in rotation order.
   - `explicit` -- a specific worker named in the job request.
   - `escalate` -- no direct assignment; the job enters the escalation chain.
4. An `AssignmentDecision` record is produced for every assignment.

## Capacity

- Every `WorkerProfile` declares `max_concurrent_jobs`.
- `WorkerCapacity` tracks `current_load` and `available_slots` at a point in
  time (`available_slots = max_concurrent - current_load`).
- `WorkerStatus` transitions:
  - `available` when `current_load < max_concurrent_jobs`.
  - `busy` when `current_load == max_concurrent_jobs - 1` (one slot left).
  - `overloaded` when `current_load >= max_concurrent_jobs`.
  - `offline` and `on_hold` are set externally.

## Handoff

- A handoff transfers a job from one worker to another.
- Every handoff produces a `HandoffRecord` with:
  - Source and destination worker IDs.
  - A typed `HandoffReason`.
  - Optional `thread_id` preserving conversation context.
- Thread context is preserved across handoffs; the receiving worker inherits
  the communication thread.

## Queue Balancing

- When multiple workers match a role, `least_loaded` selects the worker with
  the highest `available_slots`.
- Ties are broken by worker ID lexicographic order (deterministic).
- `TeamQueueState` provides aggregate visibility: queued, assigned, waiting
  job counts and the number of overloaded workers.

## Escalation

- When all eligible workers for a role are `overloaded`, the runtime triggers
  escalation rather than silent overload.
- The `AssignmentPolicy.escalation_chain_id` links to the organizational
  `EscalationChain` (from `docs/24_organizational_awareness.md`).
- If no escalation chain is configured, the job routes to
  `AssignmentPolicy.fallback_team_id`.

## Prohibitions

1. **No assignment beyond capacity without escalation.** A worker at
   `max_concurrent_jobs` must not receive new jobs unless the escalation path
   is exhausted and an operator override is recorded.
2. **No handoff without provenance.** Every handoff must include a
   `HandoffReason` and produce a `HandoffRecord`.
3. **No silent reassignment.** Reassigning a job from one worker to another
   always produces both a `HandoffRecord` and a new `AssignmentDecision`.
