# 22 Goal Reasoning Layer

## Purpose

The goal reasoning layer decomposes ambiguous, high-level goals into concrete
actionable plans, manages priorities across competing goals, and supports
replanning when execution encounters failures or changing conditions.

It sits above the skill system and workflow engine: goals produce plans, plans
reference skills and workflows, and the goal reasoning engine tracks execution
progress end to end.

## Owned Artifacts

| Artifact | Role |
|---|---|
| `GoalDescriptor` | Identity and metadata for a single goal |
| `GoalDependency` | Typed edge between two goals |
| `SubGoal` | One actionable unit within a goal plan |
| `GoalPlan` | Versioned collection of sub-goals for a goal |
| `GoalExecutionState` | Mutable progress tracker for a goal |
| `GoalReplanRecord` | Audit record when a plan is replaced |

Supporting enums: `GoalStatus`, `GoalPriority`, `SubGoalStatus`.

## Goal Lifecycle

```
proposed -> accepted -> planning -> executing -> completed
                                             \-> failed
                                             \-> replanning -> planning
                                                            \-> archived
```

| State | Meaning |
|---|---|
| `proposed` | Goal submitted but not yet evaluated |
| `accepted` | Goal evaluated and accepted for planning |
| `planning` | Decomposition into sub-goals in progress |
| `executing` | Plan is being executed |
| `completed` | All sub-goals succeeded |
| `failed` | Sub-goal failure with no replan path |
| `replanning` | Previous plan failed; new plan being constructed |
| `archived` | Terminal state after completion or abandonment |

Transition rules:
- `proposed` may move to `accepted` or `archived`.
- `accepted` moves to `planning`.
- `planning` moves to `executing`.
- `executing` moves to `completed`, `failed`, or `replanning`.
- `replanning` moves to `planning` or `archived`.
- `completed` and `failed` may move to `archived`.
- No other transitions are valid.

## Priority Model

| Priority | Rank | Semantics |
|---|---|---|
| `critical` | 0 (highest) | Must execute before all others; deadline-sensitive |
| `high` | 1 | Important but may yield to critical |
| `normal` | 2 | Default priority |
| `low` | 3 | Execute when resources are available |
| `background` | 4 (lowest) | Best-effort; may be preempted indefinitely |

When priorities are equal, goals with earlier deadlines sort first.
Goals without deadlines sort after goals with deadlines at the same priority.

## Decomposition

Goals decompose into sub-goals. Each sub-goal references either:
- A skill (`skill_id`) to execute directly, or
- A workflow (`workflow_id`) to orchestrate.

Sub-goals may declare predecessors (other sub-goal IDs that must complete
before they can start). The engine validates that predecessor references
form a DAG before accepting a plan.

## Replanning

When a sub-goal fails during execution, the goal reasoning engine:

1. Moves the goal to `replanning` status.
2. Accepts a new set of sub-goals (which may reuse completed work).
3. Produces a new `GoalPlan` with an incremented version number.
4. Records a `GoalReplanRecord` linking old plan to new plan with a reason.
5. Transitions the goal back to `planning` then `executing`.

Replanning is always explicit and auditable. No silent plan mutation is
permitted.

## Deadline Awareness

Goals carry an optional ISO 8601 deadline. The engine provides a
`check_deadline` method that compares the current time against the goal
deadline. Expired deadlines are surfaced to callers; the engine does not
autonomously cancel goals.

## Prohibitions

1. **No policy bypass.** Goal execution is subject to the same autonomy and
   policy constraints as direct skill execution.
2. **No silent goal mutation.** A goal's descriptor is frozen once accepted.
   Changes require explicit replanning with an audit record.
3. **No untracked replanning.** Every replan produces a `GoalReplanRecord`.
   Plans without records are invariant violations.
4. **No execution without a plan.** Sub-goals may only execute when the
   parent goal has an accepted, versioned plan.
5. **No circular sub-goal dependencies.** The engine rejects plans whose
   predecessor graph contains cycles.
