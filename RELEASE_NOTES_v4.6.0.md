# Mullu Platform v4.6.0 — MUSIA Runtime (Third Domain + Migration Tool)

**Release date:** TBD
**Codename:** Reach
**Migration required:** No (additive)

---

## What this release is

Two completion-shaped pieces in one release:

1. **`scientific_research` domain adapter** — third concrete domain proving the framework's universality claim. Distinct in shape from `software_dev` and `business_process` (statistical thresholds, peer review authority, replication requirements).

2. **Bulk proof migration runner** — fulfills the v4.0.0 promise of `mcoi migrate-proofs`. The migration spec was published in v4.0.0; v4.6.0 ships the runner that executes it.

Neither adds new conceptual ground. Both close specific outstanding promises from earlier releases.

---

## What is new in v4.6.0

### `scientific_research` domain adapter

[domain_adapters/scientific_research.py](mullu-control-plane/mcoi/mcoi_runtime/domain_adapters/scientific_research.py).

Eight `ResearchActionKind` values: hypothesis_formation, experiment_design,
data_collection, analysis, peer_review, publication, replication, retraction.

What makes this adapter structurally distinct from the prior two:

- **Authority comes from peer review, not tenant role.** `peer_reviewers` populates `authority_required` as `peer_reviewer:<name>`. Without peer reviewers, the principal investigator is sole authority — flagged as a risk for publication/retraction.
- **Statistical constraints distinct from acceptance criteria.** Each request emits up to four constraints: `research_correctness` (block), `statistical_significance` (escalate), `replication` (escalate), `statistical_power` (warn). Conservation, Constraint, and Validation tier-4 constructs each carry a different violation_response.
- **Reversibility is content-dependent.** `RETRACTION` produces an `irreversible` Transformation. Replication is reversible (results can be re-replicated). All others reversible.
- **Risk flags surface the methodological structure.** Low confidence threshold, underpowered study, no replications required, no peer reviewers on publication, discipline blast radius — each maps to a research-community-recognized risk.

The pattern matches `software_dev` and `business_process`:
- `translate_to_universal(ResearchRequest) → UniversalRequest`
- `translate_from_universal(UniversalResult, ResearchRequest) → ResearchResult`
- `run_with_ucja(ResearchRequest) → ResearchResult`

### Bulk proof migration runner

[migration/runner.py](mullu-control-plane/mcoi/mcoi_runtime/migration/runner.py).

Implements the spec in [PROOF_V1_TO_V2.md](mullu-control-plane/mcoi/mcoi_runtime/migration/PROOF_V1_TO_V2.md) §3.2. Key properties:

- **Idempotent.** Running twice produces no new records on the second run; the manifest tracks `migrated[v1_proof_id] = v2_proof_id`.
- **Hash-chain integrity.** Verifies the v1 chain is self-consistent (each `prev_hash` matches the prior `proof_hash`) before migration. Halts the tenant's batch on first chain break; other tenants continue.
- **Cross-link integrity.** Every v2 record's `lineage.parent_ids[0]` resolves to the v1 record it migrated from.
- **Atomic writes.** v2 records and per-tenant manifests use temp + `os.replace` so a crash mid-write never leaves a half-readable file.
- **Tenant isolation.** Per-tenant chains are independent; one tenant's chain break does not affect others.
- **Genesis chain link.** First v2 record's `prev_hash = SHA256(last_v1_proof_hash || "v2_genesis")` per spec §3.3.
- **Pass/fail mapping.** v1 `pass` → v2 `Pass`; v1 `fail` with reason → v2 `Fail(reason)`; v1 `fail` without reason → v2 `Fail("v1_migration_no_reason")`.
- **Synthesized v2 fields.** `construct_id = uuid5(NAMESPACE_URL, "v1:" + proof_id)` (deterministic), `tier` from the action prefix mapping, `phi_level=3`, `mfidel_sig=[]`, `cascade_chain=[]`, `tension_snap=null`.

### CLI entry point

```toml
[project.scripts]
mcoi = "mcoi_runtime.app.cli:main"
mcoi-migrate-proofs = "mcoi_runtime.migration.runner:main"
```

```bash
$ mcoi-migrate-proofs --v1-dir /var/lib/mullu/proofs/v1 \
                       --v2-dir /var/lib/mullu/proofs/v2 \
                       --manifest-dir /var/lib/mullu/proofs/manifest \
                       --dry-run
```

`--tenant <id>` filters to a single tenant. `--from`/`--to` are accepted for documentation symmetry but reject anything other than `v1`/`v2` in this build.

The naming `mcoi-migrate-proofs` (separate binary) rather than `mcoi migrate-proofs` (subcommand) is a deliberate scope choice — keeping the existing `mcoi` CLI structure untouched. A future release may consolidate.

---

## Test counts

| Suite                                    | v4.5.0  | v4.6.0  |
| ---------------------------------------- | ------- | ------- |
| MUSIA-specific suites                    | 435     | 482     |
| Scientific research adapter (new)        | n/a     | 26      |
| Migration runner (new)                   | n/a     | 21      |

The 26 scientific-research tests cover translation across all 8 action kinds, statistical/replication/power constraint emission, validation rejection of invalid thresholds, blast-radius mapping, all 9 risk-flag conditions (replication absent, low confidence, underpowered, discipline radius, retraction, no peer reviewers, etc.), protocol generation, and 4 end-to-end UCJA→SCCCE round trips.

The 21 migration tests cover unit-level transformation, action-to-construct mapping for 7 cases, hash chain verification (clean + tampered), runner integration including idempotency, dry-run no-op, tenant isolation under chain break, genesis-link continuity, internal v2 chain linkage, manifest persistence, and CLI argument parsing + return codes (0 / 1 / 2).

Doc/code consistency check passes.

---

## Compatibility

- All v4.5.0 endpoints unchanged
- Library API additions (new module + new CLI entry point); no removals or renames
- Migration runner does not modify v1 records — v2 records are written to a separate directory
- Proof v2 schema version is `"2"`; recorded in every v2 record so future readers can dispatch correctly

---

## What v4.6.0 still does NOT include

- **Scientific-research adapter HTTP wrapper.** Same as `software_dev` and `business_process` — Python-only `run_with_ucja()`. Wrapping any of the three under `POST /domains/<name>/process` is a separate workstream.
- **Migration runner integration with the existing audit log.** The runner reads JSON files; production deployments need an adapter from the live audit-log shape to the runner's V1Proof shape. The runner is shaped for that integration but doesn't ship one.
- **Multi-process backend** for persistence — still file-based.
- **`mcoi migrate-proofs` as a subcommand** — separate binary instead.
- **Tenant onboarding/quotas/rate limits.**
- **Φ_gov ↔ existing `governance_guard.py`** integration.
- **Two more domain adapters** (`manufacturing`, `healthcare`, `education`).
- **Rust port.**
- **JWKS-based JWT key rotation.**

---

## Cumulative MUSIA progress

```
v4.0.0   substrate (Mfidel + Tier 1)
v4.1.0   full 25 constructs + cascade + Φ_gov + cognition + UCJA
v4.2.0   HTTP surface + governed writes + business_process adapter
v4.3.0   multi-tenant registry isolation
v4.3.1   auth-derived tenant resolution
v4.4.0   persistent tenant state
v4.5.0   auto-snapshot + JWT + scope enforcement
v4.6.0   scientific_research adapter + bulk migration runner
```

Three concrete domains. Full HTTP surface. Multi-tenant + multi-auth + persistent + scope-enforced. Migration tooling for the v1→v2 transition the framework promised at v4.0.0.

---

## Honest assessment

v4.6.0 is "close out the promises" rather than "open new ground." The
scientific_research adapter strengthens the universality claim with a
data point that's structurally distinct from the prior two — peer review
as authority, statistical thresholds as constraints, retraction as the
only structurally-irreversible action. The migration runner fulfills a
specific commitment from v4.0.0 docs.

What it is not: a tested-at-scale migration tool. The 21 tests cover
correctness and idempotency on synthetic chains up to a few records.
A real production migration with millions of v1 proofs needs benchmarking
the runner's throughput first; the spec's 30-min-per-1M-records target
in PROOF_V1_TO_V2.md §5 has not been validated.

**We recommend:**
- Upgrade in place. v4.6.0 is additive.
- For scientific_research adopters: use `business_process.py` as the
  closest reference for adapter style; `scientific_research.py` adds
  per-domain risk flags that are worth copying patterns from.
- For migration: dry-run first (`--dry-run`), inspect a sample of v2
  records, then run for real on one tenant (`--tenant <id>`) before
  full corpus.

---

## Contributors

Same single architect, same Mullusi project. v4.6.0 closes two specific
gaps without scope creep.
