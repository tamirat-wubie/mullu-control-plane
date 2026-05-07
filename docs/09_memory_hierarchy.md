# Memory Hierarchy

Scope: all Mullu Platform modules that store, retrieve, or reason over retained data.

Memory is organized into tiers. Each tier has distinct mutability, retention, trust level, and promotion rules. No tier may be bypassed by writing directly to a higher tier.

## Tiers

### Tier 1: Working Memory

Purpose: hold data needed for the current session's active reasoning.

Retention: session-scoped. Discarded when the session ends unless explicitly promoted.
Mutability: fully mutable within the session.
Trust level: untrusted until verified. Working memory contains raw observations, intermediate computations, and draft plans.

Contents:
- Current world state snapshot.
- Active goal and plan context.
- In-flight execution state.
- Unverified observations.

Rules:
- Working memory MUST NOT be used as a source for cross-session reasoning.
- Working memory size MUST be bounded. Overflow MUST trigger eviction or promotion, not silent truncation.

### Tier 2: Episodic Memory

Purpose: retain verified records of what happened during specific sessions.

Retention: configurable per workspace. Default: retained until archive policy triggers.
Mutability: append-only after verification closure. Existing entries MUST NOT be modified.
Trust level: trusted. Only verified execution outcomes and closed traces enter this tier.

Contents:
- Completed `ExecutionResult` records with verification closure.
- Closed trace segments.
- Session summaries.

Promotion from Working Memory:
- An entry promotes from Working Memory to Episodic Memory when its verification closure exists and its `VerificationResult.status` is `pass` or `inconclusive` with accepted risk.
- Failed verifications promote as failure records, not as trusted knowledge.

Rules:
- Episodic Memory MUST be queryable by identity chain (goal, plan, action, execution, verification).
- Episodic Memory MUST preserve temporal ordering.

### Tier 3: Semantic Memory

Purpose: hold generalized knowledge extracted from episodic records.

Retention: indefinite until explicitly revoked or superseded.
Mutability: versioned. Updates create new versions; old versions are retained.
Trust level: trusted, but MUST pass the learning admission gate before entry (Invariant 3).

Contents:
- Admitted patterns, rules, and heuristics derived from episodic data.
- Capability performance profiles.
- Environment models.

Promotion from Episodic Memory:
- An entry promotes from Episodic Memory to Semantic Memory only through the learning admission gate.
- The admission decision (`admit`, `reject`, `defer`) MUST be recorded.
- Rejected entries MUST NOT enter Semantic Memory.

Rules:
- Semantic Memory MUST NOT contain unadmitted knowledge.
- Semantic Memory MUST NOT mutate kernel invariants (Invariant 8).
- Every Semantic Memory entry MUST reference the episodic source(s) it was derived from.
- Semantic Memory write paths MUST require a recorded `LearningAdmissionDecision`
  with `status=admit`.
- Semantic Memory updates MUST append a new version and preserve the old version.
- Semantic Memory revocation MUST record the revocation reason, actor, and evidence,
  preserve every historical version, and remove the revoked knowledge from current
  planning projection.

### Tier 4: Procedural Memory

Purpose: store reusable action sequences, strategies, and operational templates.

Retention: indefinite until explicitly revoked or superseded.
Mutability: versioned. Same rules as Semantic Memory.
Trust level: trusted. MUST pass learning admission before entry.

Contents:
- Validated action sequences that can be reused across goals.
- Strategy templates with precondition guards.
- Adapter-specific operational patterns.

Promotion from Semantic Memory:
- An entry promotes from Semantic Memory to Procedural Memory when it is formalized into a reusable template with explicit preconditions and postconditions.
- The formalization MUST be verified against at least one episodic record of successful use.

Rules:
- Procedural Memory entries MUST declare their preconditions and postconditions.
- A procedural entry MUST NOT be applied if its preconditions are not met in the current world state.
- Procedural entries MUST be re-validated when the capability registry changes.
- Procedural Memory write paths MUST require a recorded `LearningAdmissionDecision`
  with `status=admit`; replay success alone is not sufficient admission.
- Procedural Memory revocation MUST record the revocation reason, actor, and
  evidence, preserve the admitted runbook history, and remove the revoked
  runbook from active selection.
- MIL-derived procedural runbooks MUST be admitted from hash-anchored MIL audit
  records through persisted replay validation and explicit learning admission.
  The operator procedure is documented in `docs/64_mil_audit_runbook_workflow.md`.

### Tier 5: Archive Memory

Purpose: long-term cold storage for data that has left active use.

Retention: governed by tenant-level retention policy. May be indefinite or time-bounded.
Mutability: immutable. Archived data MUST NOT be modified.
Trust level: as-was at archival time. Trust level is recorded but not re-evaluated on retrieval.

Contents:
- Expired episodic records.
- Superseded semantic and procedural entries.
- Historical trace data beyond active retention windows.

Demotion to Archive:
- Any tier may demote entries to Archive when retention policy triggers.
- Demotion MUST preserve the full identity chain and original trust level.

Rules:
- Archive retrieval MUST NOT inject data directly into Working Memory or Planning without re-admission through the appropriate tier's entry gate.
- Archive data MUST be integrity-verified on retrieval.

## Cross-tier rules

1. Promotion MUST follow the tier order: Working -> Episodic -> Semantic -> Procedural. No tier may be skipped.
2. Demotion to Archive may occur from any tier.
3. Every tier transition MUST be recorded in the trace with source tier, destination tier, entry identity, and reason.
4. Cross-tier queries MUST declare which tiers are being searched. Implicit all-tier searches are prohibited.
5. Untrusted content (Working Memory) MUST NOT be mixed with trusted content (Episodic, Semantic, Procedural) without explicit tier transition and trust upgrade.

## Trusted vs untrusted content

- Untrusted: Working Memory contents. Raw observations, draft plans, unverified computations.
- Trusted: Episodic, Semantic, Procedural, Archive contents. These have passed verification or admission gates.
- Trust is not transitive. Retrieving trusted content into Working Memory does not make the Working Memory context trusted as a whole.
- A consumer MUST check the trust level of each data item individually, not the trust level of the tier it was retrieved from in the current context.
