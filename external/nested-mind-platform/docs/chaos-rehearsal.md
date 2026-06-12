# Chaos Rehearsal

Chaos rehearsal describes failure injections as data before they are executed. The platform now ships a production rehearsal plan covering append-before-apply, signature enforcement, event hash-chain fracture, stale consensus terms, duplicate leases, provider receipt mismatch, projection leaks, and unsafe lawbook migration.

```text
experiment declaration
  → invariant under test
  → injection point
  → expected containment
  → evidence required
  → rollback guard
```

The rehearsal plan is hash-bound. If an experiment is modified after approval, the plan hash changes.

## Safety boundary

Run rehearsals only against staging, local mirrors, deterministic dry-run stores, or isolated test clusters. Rehearsals should never corrupt a live canonical event chain.

## CLI

```bash
cargo run -p mind-cli -- chaos-rehearsal-plan <mind-id>
```

## API

```http
POST /system/creative-engineering/chaos-rehearsal-plans
GET  /system/creative-engineering/chaos-rehearsal-plans
```
