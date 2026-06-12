# Production Hardening Plan

This repository is now a production-oriented foundation, not a finished production service.

## Current hard guarantees

```text
identity-target matching
immutable key protection
required key protection
lawbook validation after simulated patch
commit before/after state hashes
append-before-apply API mutation path
per-mind event-record hash chain
replay verification
replayable child topology attachment
projection policy scopes
CI for fmt, clippy, and tests
```

## Required before external deployment

```text
1. Authentication and authorization
2. Durable transactional event store
3. Signed commits and service identity key management
4. Key management and secret scanning
5. Rate limits and request size limits
6. API schema versioning
7. Lawbook migration mechanism
8. Snapshotting after replay checkpoints
9. Structured tracing and audit log export
10. Threat model review
```

## Fracture checks

Every future feature must answer:

```text
Does it mutate Σ without Λ validation?
Does it expose Σ through Γ without policy?
Does it break replay from Ι + H?
Does it create hidden state outside the event stream?
Does it attach, remove, or reorder children outside causal history?
Does it allow child minds to mutate parent invariants?
Does it weaken auditability, reversibility, or causal trace?
```

A feature that answers yes to any question is not production-valid until redesigned.


## v6 additions

```text
+ request body limits
+ in-memory rate limits
+ telemetry export endpoint
+ SQLite observability sink
+ verified backup object
+ file-level restore workflow
+ deployment manifests
```

Remaining hardening: distributed rate limiting, OIDC/mTLS, HSM-backed signing, object-storage backups, and multi-node event-store semantics.

## v7 hardening additions

```text
+ trusted identity headers are disabled by default
+ identity binding policy checks issuer, audience, and optional mTLS certificate digest
+ required signatures still require inline signing before append
+ external HSM/KMS signing is represented as a request-completion boundary
+ object backup pointers are verified against backup content hashes
+ follower/archive nodes reject local mutation before event append
```

## v8 hardening priorities

```text
1. Add JWKS refresh, issuer discovery, and key cache invalidation.
2. Wire managed signing provider commands to vendor SDK clients behind explicit feature flags.
3. Add S3/GCS/Azure upload implementations with object-lock/retention policy checks.
4. Add follower durable append and leader replication transport.
5. Add distributed rate limiting and request identity correlation across nodes.
```

## v9 hardening priorities

```text
1. Replace file-backed OIDC discovery refresh with HTTPS fetch, cache rotation, and pinning controls.
2. Add vendor SDK execution adapters for KMS/HSM signing.
3. Add S3/GCS/Azure SDK upload/download implementations behind the cloud transfer boundary.
4. Add outbound replication transport with retries, idempotency keys, and backoff.
5. Replace static consensus membership with a governed membership-change event path.
```


## v11 hardening additions

```text
+ move request-local retry into durable scheduler jobs
+ record provider SDK/gateway execution receipts with expected/observed hashes
+ require consensus commit certificates before distributed commit acceptance
```

Remaining hardening work: implement an always-on scheduler worker, distributed scheduler leases, provider-specific SDK clients, and a complete consensus protocol.

## v12 hardening targets

```text
- Replace manual worker-run endpoint with an always-on worker process.
- Back scheduler claims with distributed leases or database compare-and-swap updates.
- Implement real SDK crates behind ProviderSdkInvocation while preserving ProviderSdkReceipt.
- Add idempotent consensus apply protection for duplicate certificates.
- Add durable retry scheduling for failed provider SDK and replication operations.
```


## v14 hardening notes

Job execution, distributed leases, native provider calls, and physical compaction must all be receipt-driven. Operators should reject any workflow where a worker changes job status without a matching `JobExecutionReceipt`, or where consensus certificates are deleted without a verified `ConsensusCompactionBackupGuard`.

Native provider feature flags expose capability state; they do not by themselves prove a provider call was safe. Production provider adapters must verify payload hash, provider request id, provider response signature or attestation when available, and idempotency key.

## v15 hardening targets

```text
1. Replace placeholder provider execution with vendor SDK receipts for each enabled provider feature.
2. Implement Postgres/Redis/etcd/Consul lease adapters behind `DistributedLeaseAdapterReport`.
3. Add job-kind executors that produce real evidence for OIDC refresh, replication delivery, backup upload, and consensus commit jobs.
4. Require backup verification before any retention policy with `delete_apply_reports = true` is allowed in production.
5. Add retention dry-run review gates before physical deletion in multi-node clusters.
```

## v16 hardening notes

Before enabling v16 execution paths in production:

```text
- configure retention approval quorum for each consensus cluster
- require backup verification before retention approval votes are accepted
- implement concrete Postgres/etcd lease clients from the command plans
- require provider SDK execution reports for native cloud/HSM calls
- verify all live job handlers produce declared evidence keys
```

## v17 release-gate hardening

Before production promotion, generate and review:

```text
CreativeEngineeringReport
ChaosRehearsalPlan
InvariantFuzzRunReport
ProductionReadinessGateReport
```

A blocked readiness gate should stop production promotion until blockers are resolved or explicitly waived by governance.

## v18 hardening gates

Before staging promotion, generate and persist:

```text
ChaosExecutionRun
InvariantFuzzExecutionReport
ProductionReadinessGateReport
```

If a gate is blocked, use readiness waivers only for staging movement and only with risk-owner approval. Waivers should expire and should create remediation jobs from the creative-engineering report.

## v19 promotion controls

v19 adds promotion controls that should be wired into branch protection and staging rollout:

```text
+ mandatory CI readiness report must pass
+ invariant fuzz execution must have zero failures unless explicitly configured
+ staging chaos report must pass when required by policy
+ readiness waivers should use multi-operator certificates
+ implementation jobs should close only with PR, test, readiness, and rollback evidence bundles
```

## v20 hardening additions

```text
GitHub evidence connector
  → verify PR/check-run readiness before attaching implementation evidence

Branch protection policy generator
  → keep release branch requirements as auditable artifacts

Live staging chaos adapter
  → require adapter receipts before destructive staging execution

Waiver review flow
  → require role-specific review comments before waiver certification
```

## v21 hardening notes

GitHub writes must use a GitHub App installation token with `checks:write`. Branch-protection reconciliation should run first in dry-run mode and then in apply-approved mode only after protected-branch drift is reviewed. Kubernetes chaos should use server-side dry-run before live staging submission. Waiver assignment should have team/role separation and escalation targets configured before production use.

## v22 hardening notes

```text
+ GitHub App token exchange stores fingerprints, not tokens
+ GitHub writes are action plans + receipts, not blind connector side effects
+ branch-protection reconcile can run as worker-level evidence
+ Kubernetes chaos execution remains server-dry-run receipt-bound
+ waiver notification delivery is channel-labeled and receipt-bound
```


## v23 hardening controls

```text
+ never persist raw private keys or JWTs
+ require secret fingerprints for approved secret reads
+ require external receipt hash for approved connector execution
+ require Kubernetes audit uid and rehearsal annotation before live chaos promotion
+ require provider message/response evidence for waiver notifications
```

## v24 hardening notes

```text
+ require secret-manager material fingerprint on resolved secret reads
+ require GitHub installation-token fingerprint before check-run or branch-protection execution
+ require Kubernetes audit UID/watermark before live staging chaos promotion
+ require provider message id for sent waiver notifications
```

## v25 hardening delta

v25 closes the v24 runtime-surface gap by wiring the live connector evidence types into API/CLI/store paths. It also adds an action-promotion gate so a connector worker cannot proceed from planned side effects to approved live action without the required evidence set.
