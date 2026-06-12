# ADR 0024: v24 Runtime Wiring and v25 Connector Orchestration

## Decision

v25 wires the v24 action-evidence kernel objects into API, CLI, runtime store, and SQLite surfaces, then adds a connector orchestration and action-promotion gate layer.

## Reason

The platform had enough deterministic evidence objects to describe live side effects, but a production surface also needs:

```text
route handler
CLI rehearsal
store persistence
orchestration report
promotion gate
```

Without these, evidence objects remain isolated and hard to use operationally.

## Consequence

Provider effects remain outside the symbolic kernel. The kernel accepts only deterministic plans, receipts, reports, and gate results. Live provider workers can be implemented behind these contracts without changing the invariant model.
