# Nested-mind integration seam — Phase 1 read-only bridge

<!-- TYPE: Design -->
<!-- AUDIENCE: developer integrating nested symbolic memory with the control plane -->

## Decision

Treat `nested-mind-platform` as a separate governed-memory service, not as code to
transplant into MAF.

The control plane remains the outer agentic/governance brain. Nested-mind owns
the recursive symbolic-state substrate:

- `Σ`: nested symbolic state.
- `Λ`: lawbook/admissibility rules for state evolution.
- `H`: signed causal history.
- `Γ`: read/proposal boundary exposed over HTTP.

Phase 1 mounts only the read side of `Γ`. It does not expose proposal,
child-mind creation, lawbook mutation, or commit-writing routes.

## Why not merge the Rust crates now?

The prior analysis found two compatible but differently-shaped kernels:
Mullu's current Rust/MAF surface mainly preserves symbolic-governance contract
shapes, while nested-mind is a deployable Rust service with a concrete kernel,
SQLite persistence, signing, OIDC-oriented identity, worker support, and backup
mechanics. Pulling nested-mind internals into MAF would force an immediate
vocabulary reconciliation between `StateMachineSpec`/`TransitionReceipt` and
`Lawbook`/`Commit`/`SymbolState`.

A service seam avoids that collision:

```text
Mullu Φ_gov
  gates intent and operational authority
      ↓
Nested-mind Γ
  exposes projection/history without leaking mutation authority
      ↓
Nested-mind Λ/H
  validates and signs state evolution inside the nested-brain service
```

## Phase 1 surface

Phase 1 adds a default-off read-only connector with these operations:

| Operation | Nested-mind route | Effect class | Mutation allowed |
| --- | --- | --- | --- |
| `read_projection(mind_id="root")` | `GET /minds/{mind_id}` | `EXTERNAL_READ` | No |
| `verify_history(mind_id="root")` | `GET /minds/{mind_id}/audit` | `EXTERNAL_READ` | No |
| `replay_history(mind_id="root")` | `GET /minds/{mind_id}/replay` | `EXTERNAL_READ` | No |

The connector delegates transport to the existing governed `HttpConnector`.
That means request execution keeps the existing HTTP invariants: method
allowlist, HTTPS provider policy, response-size cap, content-type check,
no redirect following, DNS/private-address protection, and connector receipts.

## Environment contract

```text
MULLU_NESTED_MIND_ENABLED=true
MULLU_NESTED_MIND_OBSERVATION_BRIDGE_ENABLED=false
MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED=false
MULLU_NESTED_MIND_BASE_URL=https://nested-mind.example
MULLU_NESTED_MIND_BEARER_TOKEN=<optional>
```

Startup posture:

- flag unset/false/blank → connector is not mounted; zero runtime behavior
  changes.
- flag enabled but base URL missing → fail closed at bootstrap.
- base URL must be HTTPS, must include a host, and must not include query or
  fragment.
- bearer token is optional; when present, only the `Authorization` header name
  is included in request hashing/receipts, not the token value.

## Phase P2.3 live record_observation submission

Phase P2.3 adds the first live mutation path, but only for
`record_observation` proposals generated as `NestedMindObservationProposalPlan`.
It remains default-off and operator-flagged.

Required gates for a live network write:

```text
MULLU_NESTED_MIND_ENABLED=true
MULLU_NESTED_MIND_OBSERVATION_BRIDGE_ENABLED=true
MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED=true
MULLU_NESTED_MIND_BASE_URL=https://nested-mind.example
MULLU_NESTED_MIND_BEARER_TOKEN=<optional>
```

Submission path:

```text
NestedMindProposalEvidence
  -> NestedMindObservationProposalPlan
  -> NestedMindObservationSubmitter
  -> NestedMindCommitResponseEnvelope
  -> VERIFIED NestedMindCommitWitness
  -> verified bridge report
  -> read-after-write reconciliation
  -> internal append-only evidence store
```

The live submitter does not enable:

- child-mind creation;
- lawbook migration;
- arbitrary patch operations;
- semantic memory admission;
- procedural memory admission;
- system-of-record switching;
- raw response persistence;
- raw token persistence.

Operator CLI:

```powershell
python scripts\nested_mind_build_observation_plan.py --mind-id root --observation-id obs-1 --observation path\to\observation.json --mullu-receipt-hash <hash> --authority-receipt-hash <hash> --plan-out path\to\plan.json --evidence-out path\to\evidence.json
python scripts\nested_mind_submit_observation.py --plan path\to\plan.json --evidence path\to\evidence.json --dry-run
python scripts\nested_mind_submit_observation.py --plan path\to\plan.json --evidence path\to\evidence.json --submit --store .tmp\nested-mind-evidence.jsonl
python scripts\nested_mind_reconcile_observation.py --store .tmp\nested-mind-evidence.jsonl --plan-id <plan_id> --witness-id <witness_id>
python scripts\report_nested_mind_evidence.py --store .tmp\nested-mind-evidence.jsonl --mind-id root
python scripts\validate_nested_mind_p3_readiness.py --store .tmp\nested-mind-evidence.jsonl
```

The default submit path is dry-run. `--submit` requires all environment gates
above and prints only a `NestedMindObservationSubmissionReport` JSON object.
The evidence store is append-only and rejects bearer-token or raw-response-body
fields. The report command is read-only and summarizes typed evidence counts,
verified record identifiers, readiness blockers, and the next operator action.
It exits with `0` only when the readiness validator reports `ready`; blocked
reports exit with `1` so automation cannot silently advance P3.
Malformed or corrupted evidence stores raise a typed persistence error and do
not emit a normal blocked readiness JSON object.

## What changes after this lands?

Constructive delta:

- Mullu gains a governed, testable read-only seam to nested-mind.
- Nested-mind can be observed as a nested-brain substrate without changing
  Mullu's Python runtime contracts.
- Projection/history reads are receipted through the same external connector
  plane used by the control plane.
- The seam is reversible: disable the env flag and no connector is constructed.

Fracture delta intentionally avoided:

- No Rust crate import.
- No MAF type replacement.
- No Python serialization-contract disruption.
- No nested-mind mutation route.
- No raw external response storage in Phase 1.

## Phase 2 typed projection import boundary

Phase 2 may import nested-mind projection content only through typed envelopes.
It is still a read-only boundary:

```text
Nested-mind Γ response
  → NestedMindProjectionEnvelope / NestedMindHistoryEnvelope
  → NestedMindProjectionImportReceipt
  → bounded Mullu read model
```

Phase 2 invariants:

- projection payloads must include `mind_id`, `scope`, `sequence`, `commit_hash`,
  `state_hash`, `lawbook_hash`, `history_hash`, `projected_at`, and `state`.
- `scope` must be `public`, `summary`, or `internal`.
- public and summary projections reject sensitive state-key names such as token,
  password, secret, credential, or private key.
- mutation-shaped payload keys such as `proposal`, `patch`, `ops`,
  `lawbook_migration`, `child_mind_create`, or `commit_write` are rejected.
- imports bind to a succeeded governed connector result through
  `NestedMindProjectionImportReceipt`.
- typed projection import does not admit content into semantic/procedural memory.

This is an information-flow boundary, not a write bridge.

## Current limitation

The existing governed HTTP connector returns a digest and receipt, not a raw
response body. Phase 1 therefore proves reachability, route construction,
policy posture, and auditability. It does not yet import nested-mind projection
content into Mullu memory.

A later Phase 2 can add a typed, schema-validated projection reader if the
control plane must consume nested-mind state content directly. That should be
a separate PR because it changes the information-flow boundary.

## Next phases

1. **Phase 1 — read-only witness bridge**: mount connector, test route
   construction and fail-closed env behavior.
2. **Phase 2 — typed projection import**: add schema-validated projection
   envelopes if Mullu needs to consume nested-mind state content.
3. **Phase 3 — governed proposal bridge**: add `POST /minds/root/proposals`
   only after Mullu-side approval/budget/effect receipts are mapped into
   nested-mind proposal metadata.
4. **Phase 4 — nested-brain topology**: map tenants/projects to child minds
   once the system-of-record decision is explicit.

## Open decisions before mutation routes

1. Is nested-mind the system of record for symbolic state, or only for one
   governed-memory lane?
2. Does each tenant get a child mind, or does each project/task get a child
   mind?
3. Which receipt from Mullu must be embedded into nested-mind proposal
   metadata?
4. Should internal/private nested-mind service URLs be allowed through a
   dedicated operator allowlist, or must production always route through HTTPS
   public ingress?

## Updated phase map

1. **Phase 1 read-only witness bridge**: mount connector, test route
   construction and fail-closed env behavior.
2. **Phase P2.3/P2.4 governed record_observation bridge**: submit only
   verified observation proposals, then reconcile through read-only projection
   and audit routes.
3. **Phase P2.5/P2.6 evidence store and operator CLI**: persist typed evidence
   internally and expose a dry-run-first operator script.
4. **Phase P3+ nested-brain topology**: map memory lattice, world graph,
   planning, capabilities, trust ledger, and closure learning only after
   record_observation is verified and reconciled.
