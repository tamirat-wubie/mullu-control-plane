# Architecture

## System shape

A mind is not a chat agent. A mind is a governed recursive state machine:

```text
Mind := ⟨Identity, Lawbook, State, Gateway, History, Children⟩
```

Each child mind is a full mind. The root mind coordinates, but it does not erase the autonomy boundary of children.

## Layers

### 1. Kernel: `mind-core`

Owns all invariant logic.

Responsibilities:

- identity creation
- invariant validation
- state patching
- lawbook validation
- commit creation
- causal history
- projection construction

No network, database, or UI logic belongs in the kernel.

### 2. Runtime/API: `mind-api`

Exposes controlled projection and proposal endpoints.

Responsibilities:

- receive proposals
- call the kernel evolution engine
- return commits/projections
- reject invalid edits without mutating state

### 3. CLI: `mind-cli`

Local deterministic execution for tests, debugging, and demos.

### 4. Storage adapters

Persistence sits behind `AppendOnlyEventStore` and `SnapshotStore`. State is recoverable by replaying commits from genesis or from a verified snapshot checkpoint plus tail events.

Current adapters:

```text
InMemoryEventStore
JsonlEventStore
SqliteEventStore
InMemorySnapshotStore
JsonlSnapshotStore
SqliteEventStore as SnapshotStore
```

## Evolution pipeline

```text
Input Proposal
  → target identity check
  → invariant validation
  → patch simulation
  → lawbook validation on next state
  → judgment construction
  → causal commit
  → state replacement
  → projection
```

## Parent/child rules

1. A child has exactly one parent.
2. Parent and child identities are immutable after creation.
3. A parent may observe a child through projection.
4. A child cannot directly mutate parent state.
5. Cross-mind edits must be expressed as proposals and validated by the target mind.

## LLM boundary

LLMs, users, APIs, or external tools are proposal sources only.

They may produce:

```text
Proposal(actor, reason, patch, evidence)
```

They may not produce:

```text
Commit
```

Only the kernel creates commits.

## Event-sourced runtime layer

The runtime now separates evaluation from mutation:

```text
EditProposal
  → EvolutionEngine::evaluate
  → EvolutionPlan { commit, next_state }
  → AppendOnlyEventStore::append(commit)
  → EvolutionEngine::apply_plan
```

This makes persistence a gate before mutation. The live `Mind` is treated as a cache of replayable truth, not the source of truth.

## Projection boundary

`MindProjection::with_policy` implements the initial `Γ` boundary. Public projection omits sensitive keys by default. Internal projection is available only as a trusted-operator view and must be protected before deployment.


## v4 checkpointed governance layer

```text
authenticate
  → authorize
  → evaluate patch/topology/lawbook migration
  → sign
  → append event
  → apply to live cache
  → optionally snapshot
  → audit by full replay or snapshot replay
```

The active lawbook is replayable because every migration is embedded in `Commit.lawbook_transition`.
Snapshots preserve the current lawbook, state, children, and history, and are independently hash-checked before use.


## v5 maintenance architecture

```text
SQLite open → schema_migrations ledger → pending migrations → runtime store
Snapshot list → compaction policy → delete older snapshots → audit event
Runtime action → observability sink → audit-event query/CLI export
```


## v6 runtime boundary

```text
HTTP request → safety gate → authorization → governed mutation/query → telemetry/backup projection
```

Request safety, telemetry export, and backup/restore live outside the deterministic symbolic kernel. The kernel still owns identity, lawbook validation, state transition, event commits, replay, and snapshot verification.

## v7 boundary architecture

```text
Gateway verified identity
  → IdentityBindingPolicy
  → Principal
  → AuthorizationPolicy
  → DistributedEventStorePlan::validate_append_authority
  → EvolutionEngine
  → managed signing boundary
  → AppendOnlyEventStore
  → projection / audit / backup
```

New kernel modules:

```text
identity.rs          external assertion and binding policy
key_management.rs    local/external commit signing service model
object_backup.rs     object pointer and file-backed object backup store
distributed.rs       event-store strategy and append-authority guard
```

The symbolic kernel still owns proposal validation, lawbook validation, state evolution, causal commit construction, hash verification, replay, and projection. v7 adds production boundaries around the kernel rather than weakening kernel invariants.

## v8 external-production seams

```text
Identity seam:
  Bearer JWT → OIDC/JWKS verifier → VerifiedIdentity → Principal

Signing seam:
  Commit → ManagedSigningRequest → provider command → ManagedSigningCompletion → verified CommitSignature

Backup seam:
  MindBackup → CloudObjectBackupPlan → external cloud upload → later verification

Replication seam:
  Leader records → ReplicationBatch → follower verification → ReplicationAck → quorum report
```

These seams keep external systems outside the mutation authority. Identity can authorize, signing can attest, backup can transfer, and replication can distribute records, but only validated commits and verified event records can affect `Σ`.

## v9 execution and replication seams

v9 separates five previously implicit seams:

```text
OIDC discovery refresh evidence
vendor signing execution evidence
cloud transfer execution evidence
leader append vs follower replicated append
consensus membership state
```

The most important architectural split is between `AppendOnlyEventStore::append` and `ReplicatedEventStore::append_replicated_records`. A leader creates new event records. A follower verifies and persists records already produced by the leader.


## v11 durable operation plane

```text
connector/worker intent
  -> ScheduledJob(idempotency_key, payload_hash)
  -> ProviderExecutionRequest/Receipt
  -> ConsensusLogEntry/Vote/Certificate
  -> SQLite operational ledger
```

The canonical mind event chain still owns symbolic state. v11 ledgers hold operational evidence around work scheduling, provider execution, and consensus quorum decisions.

## v12 worker and consensus-apply seam

```text
ScheduledJob
  -> SchedulerLeaseRecord
  -> WorkerRunReport
  -> ProviderSdkReceipt
  -> ConsensusCommitCertificate
  -> ConsensusApplyReport
```

The worker/scheduler path is operational metadata. It does not mutate symbolic state `Σ` directly. It either updates scheduled-job status or records receipt/report evidence.

The consensus apply path is the only v12 path that appends event records, and it only appends leader-produced `EventRecord` values after a commit certificate verifies quorum.
