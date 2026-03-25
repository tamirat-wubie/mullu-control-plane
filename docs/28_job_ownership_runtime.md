# 28 Job Ownership Runtime

## Purpose

The job ownership runtime provides persistent job ownership, work queues,
assignment, follow-up, escalation, and SLA tracking for the Mullu Platform.
Jobs are the unit of accountable work: every task that an agent, team, or
operator must complete is modelled as a job with an explicit lifecycle,
priority, deadline, and audit trail.

Jobs bridge the goal reasoning layer (doc 22) with the organisational
awareness layer (doc 24) and the threaded communication layer (doc 25).
A goal may spawn one or more jobs; each job tracks its own assignment,
progress, and outcome independently.

## Job Lifecycle

A job passes through a strict ordered lifecycle:

```
created --> queued --> assigned --> in_progress --> waiting --> paused
                                       |              |          |
                                       v              v          v
                                  completed       completed   completed
                                    failed          failed      failed
                                  cancelled       cancelled   cancelled
                                       |              |          |
                                       v              v          v
                                                 archived
```

| Status        | Meaning                                                   |
|---------------|-----------------------------------------------------------|
| `created`     | Job descriptor exists but is not yet in any queue.        |
| `queued`      | Job is in a priority-ordered work queue awaiting pickup.   |
| `assigned`    | Job has been bound to an agent, team, role, or operator.  |
| `in_progress` | Active execution is underway.                             |
| `waiting`     | Execution paused pending an external event or response.   |
| `paused`      | Execution explicitly paused (approval, review, hold, ...) |
| `completed`   | Job finished successfully.                                |
| `failed`      | Job finished with an unrecoverable error.                 |
| `cancelled`   | Job was explicitly cancelled before completion.           |
| `archived`    | Terminal: job record preserved for audit; immutable.       |

## Queue Model

Work queues are **priority-ordered** and **deadline-aware**.

- Each queue entry carries a `priority` (critical / high / normal / low /
  background) and, when present, a `deadline`.
- Queues are sorted by priority rank first, then by deadline proximity, then
  by enqueue time (FIFO within equal rank and deadline).
- A job MUST have a queue entry before it can be assigned. Direct assignment
  without a queue entry is prohibited.

## Assignment

Jobs bind to an **agent, team, role, or operator** via the organisational
awareness layer (doc 24).

- An `AssignmentRecord` captures who was assigned, by whom, when, and why.
- Re-assignment creates a new `AssignmentRecord`; the previous one is
  retained for audit.
- Assignment always references the queue entry that produced the job.

## Follow-Up

When a job is in `waiting` or `paused` status for longer than a
configurable threshold, the runtime creates a `FollowUpRecord`.

- Follow-ups are scheduled at creation time and executed when the scheduled
  time arrives.
- A follow-up that finds the job still stalled triggers an escalation.
- Resolved follow-ups are marked but never deleted.

## Escalation

Escalation is tied to the organisational escalation chains defined in doc 24.

- When a follow-up fires and the job remains stalled, the runtime walks the
  org escalation chain for the assigned entity.
- Each escalation step produces an audit record and may reassign the job.
- Escalation does not bypass priority ordering; it raises priority and
  reassigns within the queue model.

## SLA Tracking

Every job may carry a target completion time expressed as
`sla_target_minutes`.

| SLA Status       | Meaning                                              |
|------------------|------------------------------------------------------|
| `on_track`       | Elapsed time is within the SLA window.               |
| `at_risk`        | Elapsed time exceeds a warning threshold.            |
| `breached`       | Elapsed time exceeds the SLA target.                 |
| `not_applicable` | No SLA target was set for this job.                  |

SLA status is evaluated explicitly via `DeadlineRecord` snapshots.

## Communication Integration

Jobs create and bind conversation threads (doc 25).

- When a job enters `in_progress`, a thread may be created or an existing
  thread bound via `thread_id` on the `JobState`.
- All status changes, follow-ups, and escalations post messages to the
  bound thread.

## Learning Integration

Job outcomes feed the learning loop (doc 05, doc 26).

- On `completed` or `failed`, the runtime emits a `JobExecutionRecord`
  containing `outcome_summary` and `errors`.
- These records are eligible for knowledge ingestion (doc 26) and learning
  admission (doc 05).

## Prohibitions

1. **No job mutation after archive.** Once a job reaches `archived`, its
   records are immutable. Any attempt to modify an archived job MUST be
   rejected.
2. **No assignment without queue entry.** A job cannot be assigned unless
   it has a corresponding `WorkQueueEntry`.
3. **No silent deadline skip.** When a deadline or SLA target passes, a
   `DeadlineRecord` MUST be created. The runtime MUST NOT silently ignore
   missed deadlines.
