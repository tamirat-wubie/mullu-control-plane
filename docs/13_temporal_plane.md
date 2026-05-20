# Temporal Plane

> **In one box:** How the system handles things that span time — delays,
> schedules, timeouts, "do this later" — so time-based actions stay governed
> and replayable. New here? → [Plain-English Overview](explain/PLAIN_ENGLISH.md);
> unknown word? → [Glossary](GLOSSARY.md). *(Doc type: Reference.)*

Scope: all Mullu Platform modules that operate across time boundaries.

Without temporal awareness, the platform is limited to single-turn request-response. The temporal plane gives the system time — delayed actions, waiting states, recurring tasks, resumable work, and deadline awareness.

## Purpose

Manage time-dependent scheduling, deadlines, temporal ordering, and long-horizon operation.

## Owned artifacts

- `TemporalTask` — a unit of work with an explicit time boundary.
- `TemporalTrigger` — the condition or time that activates a task.
- `TemporalState` — the current lifecycle position of a temporal task.
- `Reminder` — a time-bound notification tied to a goal or action.
- `RecurringSchedule` — a repeating trigger pattern.
- `ResumeCheckpoint` — a persisted point from which interrupted work can resume.

## Task lifecycle states

- `pending` — created but not yet due.
- `waiting` — due condition not yet met (awaiting external event or approval).
- `due` — trigger condition met, ready for execution.
- `running` — currently executing.
- `completed` — finished successfully with verification closure.
- `expired` — deadline passed without execution.
- `cancelled` — explicitly cancelled before completion.

Rules:
- State transitions MUST be explicit and recorded.
- A task MUST NOT transition from `completed`, `expired`, or `cancelled` to any active state.
- Expired tasks MUST NOT be silently retried. Re-scheduling requires a new task.
- State transitions MUST carry timestamps and the identity of the triggering event.

## Trigger types

- `at_time` — fire at a specific absolute timestamp.
- `after_delay` — fire after a duration from creation or from a reference event.
- `on_event` — fire when a named event occurs (e.g., execution completion, approval received).
- `recurring` — fire on a repeating schedule (cron-like pattern or interval).

Rules:
- Triggers MUST be explicit and persisted. No in-memory-only timers for durable tasks.
- A trigger that cannot be evaluated (missing event source, unparseable schedule) MUST fail the task to `expired`, not silently wait forever.

## Resume and checkpoint rules

1. A `ResumeCheckpoint` MUST capture enough state to restart work without re-executing completed steps.
2. Checkpoints MUST be persisted before the work they protect proceeds.
3. Resuming from a checkpoint MUST NOT re-execute verified steps.
4. A checkpoint MUST reference the temporal task and the last completed step by identity.

## Deadline rules

1. Every temporal task MAY carry a deadline. Tasks without deadlines have no automatic expiry.
2. Deadline evaluation MUST be deterministic — given the same clock input, the same decision results.
3. A breached deadline MUST transition the task to `expired` with an explicit reason.
4. Deadline breach MUST be recorded in the trace.

## Policy hooks

- Scheduling policy: which tasks may be scheduled, by whom, with what resource limits.
- Execution timing policy: minimum/maximum delay, blackout windows.
- Recurrence limits: maximum recurrence count, maximum total duration.

## Failure modes

- `trigger_unparseable` — trigger definition is malformed.
- `deadline_breached` — task expired before execution.
- `checkpoint_corrupted` — resume checkpoint is unreadable.
- `schedule_conflict` — recurring schedule conflicts with policy or resource limits.
- `resume_failed` — checkpoint references missing or incompatible state.

## Prohibited behaviors

- MUST NOT execute actions (that is the Execution Plane's role).
- MUST NOT fabricate timestamps.
- MUST NOT silently drop expired deadlines.
- MUST NOT use in-memory-only timers for durable temporal tasks.
- MUST NOT resume past a checkpoint that references unverified steps.

## Dependencies

- Governance Plane: scheduling policy, execution timing policy.
- Execution Plane: for deadline-bound actions.
- Memory Plane: for persisting checkpoints and temporal state.
- Persistence: temporal tasks and checkpoints MUST survive process restarts.
