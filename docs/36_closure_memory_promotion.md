# 36 - Closure Memory Promotion

## Purpose

Closure memory promotion turns verified closure outcomes into append-only
episodic records. It closes the gap between "the action was verified" and "the
system may remember what happened across sessions."

The layer answers: which execution closed, what verification status was reached,
whether accepted risk was explicitly attached, whether compensation succeeded,
what evidence backs the memory, and what trust class the episodic record carries.

## Owned Runtime

| Runtime | Role |
|---|---|
| `ClosureMemoryPromoter` | Admits closure outcomes into `EpisodicMemory` |
| `MemoryEntry` | Existing append-only episodic record |
| `EpisodicMemory` | Existing trusted event memory tier |

## Admission Rules

Execution closure:

| Verification status | Accepted risk | Episodic category | Trust class |
|---|---|---|---|
| `pass` | not required | `execution_success` | `trusted` |
| `fail` | not allowed as success | `execution_failure` | `failure_record` |
| `inconclusive` | active accepted risk required | `execution_accepted_risk` | `accepted_risk` |

Compensation closure:

| Compensation outcome | Episodic category | Trust class |
|---|---|---|
| `succeeded` | `compensation_success` | `trusted_compensation` |
| `requires_review` / `failed` | rejected from trusted episodic memory | none |

## Hard Invariants

1. No successful execution memory without passing verification.
2. No inconclusive execution memory without active accepted risk.
3. Failed verification promotes only as failure memory, never trusted success.
4. No trusted compensation memory without successful compensation outcome.
5. Closure memory writes only episodic memory; it does not write semantic or
   procedural memory.
6. Every episodic closure entry carries source identifiers and evidence refs.

## Boundary

Closure memory promotion does not generalize knowledge. Semantic or procedural
memory still requires learning admission. This bridge only records what happened
in a specific execution or compensation closure.
