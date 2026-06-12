# Transactional Event and Snapshot Store

`mind-store-sqlite` adds a transactional single-node store for event records and snapshot records.

Event append flow:

```text
validate signature requirement
begin transaction
load previous sequence/hash for mind
construct EventRecord
insert record JSON + sequence/hash metadata
commit transaction
```

Snapshot save flow:

```text
verify snapshot hash
verify state hash
verify lawbook hash
begin transaction
insert snapshot JSON + checkpoint metadata
commit transaction
```

Runtime configuration:

```text
MIND_EVENT_DB=./data/mind-events.sqlite
MIND_REQUIRE_SIGNATURES=true
```

Snapshot persistence can share the event database or use its own database:

```text
MIND_EVENT_DB=./data/mind-events.sqlite
MIND_SNAPSHOT_DB=./data/mind-snapshots.sqlite
```

SQLite is suitable for local production prototypes, single-node deployments, and deterministic tests. Multi-node deployment should add compare-and-append semantics, schema migrations, backups, and replay audits.

## v6 SQLite tables

```text
observability_events   trace/audit JSON records
backup_manifests       backup id, optional mind id, backup hash, manifest JSON
```

The event chain remains append-only. Backup manifests are operational metadata and do not mutate symbolic state.

## v7 SQLite tables

Version 7 adds metadata tables for identity assertions, external signing requests, object-backup pointers, and distributed node plans. Event append semantics remain unchanged: commit validation and signature requirements still happen before insertion into `mind_events`.

## v8 SQLite tables

```text
oidc_jwks_verifier_configs
managed_signing_requests
cloud_object_backup_plans
replication_batches
replication_acks
```

These ledgers preserve the operational records around direct identity, managed signing, cloud backup planning, and replication validation without granting them mutation authority over symbolic state.

## v9 SQLite tables

```text
oidc_jwks_cache
signing_execution_receipts
cloud_transfer_receipts
replication_inbox
consensus_memberships
```

`append_replicated_records` inserts exact leader-produced event records inside one transaction after tail verification.
