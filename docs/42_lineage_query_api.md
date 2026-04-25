# Lineage Query API

Purpose: define `lineage://` URI semantics for querying every governed action
that causally contributed to a symbolic intelligence output.

Governance scope: read-only causal lineage queries over trace entries,
policy decisions, model invocation records, tenant context, budget reservations,
tool receipts, and replay witnesses.

## Architecture

| Component | Responsibility | Input | Output |
|---|---|---|---|
| URI parser | Parse and validate `lineage://` references | Lineage URI | bounded query envelope |
| Lineage resolver | Locate root trace, output, or command and ancestor chain | trace, output, or command id | ordered causal graph |
| Context projector | Attach policy, model, tenant, and budget context | trace node ids | decorated lineage nodes |
| Proof verifier | Validate graph edges, hash links, and proof references | decorated nodes and edges | verification summary |
| Policy-version projector | Build a bounded policy-version index from lineage nodes | decorated nodes | policy-version read model |
| Read API | Return bounded graph slices | query envelope | JSON lineage document |

## URI Form

```text
lineage://output/{output_id}
lineage://trace/{trace_id}
lineage://command/{command_id}
```

Optional query parameters:

| Parameter | Meaning | Default |
|---|---|---|
| `depth` | Maximum ancestor depth, bounded to `1..100` | `25` |
| `include` | Comma-separated context families | `policy,model,tenant,budget,tool,replay` |
| `verify` | Recompute proof and hash-chain validity | `true` |
| `at` | Point-in-time version boundary | latest visible state |

## Lineage Node Contract

Each node must include:

1. `node_id`
2. `node_type`
3. `parent_node_ids`
4. `trace_id`
5. `policy_version`
6. `model_version`
7. `tenant_id`
8. `budget_ref`
9. `proof_id`
10. `state_hash`
11. `timestamp`

## Lineage Document Contract

Each resolved document must include:

| Field | Meaning |
|---|---|
| `lineage_uri` | Caller-supplied query URI |
| `document_id` | Stable short identifier derived from the document hash |
| `document_hash` | `sha256:` hash over the canonical document body |
| `permalink` | Canonical `lineage://{type}/{id}` reference for the root |
| `root_ref` | Root reference type and id |
| `verification.checked_nodes` | Number of nodes included in graph verification |
| `verification.checked_edges` | Number of edges included in graph verification |
| `verification.reason_codes` | Bounded causes for unresolved or unverifiable graph state |
| `policy_versions` | Top-level index of policy versions, node ids, tenant ids, and counts |

## Query Examples

```text
lineage://output/out-42?depth=50&include=policy,model,tenant,budget,replay
lineage://trace/trc-9?verify=true
lineage://command/cmd-7?include=policy,tool
```

## Execution Rules

1. Queries are read-only and cannot mutate trace, budget, or policy state.
2. Missing ancestors are explicit `unresolved_node` entries, not silent gaps.
3. Verification failures return `verified=false` with bounded reason codes.
4. Tenant context is always included, even when omitted from `include`.
5. Redaction happens after proof verification so hashes remain auditable.
6. Parent declarations and edge endpoints must match exactly.
7. The document hash is computed after verification and before response return.

## Initial Endpoint Shape

| Route | Method | Purpose |
|---|---|---|
| `/api/v1/lineage/resolve` | `POST` | Resolve a `lineage://` URI into a causal graph |
| `/api/v1/lineage/{trace_id}` | `GET` | Fetch lineage by trace id |
| `/api/v1/lineage/output/{output_id}` | `GET` | Fetch lineage by output id |
| `/api/v1/lineage/command/{command_id}` | `GET` | Fetch lineage by command id |

## Index Resolution

Trace references resolve directly through `ReplayRecorder.get_trace`.

Output and command references resolve through a bounded replay index scan over
completed traces. The resolver inspects frame input and output contracts for:

1. `output_id`
2. `command_id`

The scan is capped at `MAX_TRACE_INDEX_SCAN` traces and returns the newest
matching trace first. Missing references remain explicit unresolved nodes.

## Policy-Version Read Model

Every lineage document includes a top-level `policy_versions` projection. Each
entry records:

1. `policy_version`
2. `node_count`
3. `node_ids`
4. `tenant_ids`

This lets operators query which policy versions governed the returned lineage
without walking every node manually.

STATUS:
  Completeness: 100%
  Invariants verified: URI grammar, read-only boundary, tenant context retention, missing ancestor visibility, proof verification position, bounded output index scan, bounded command index scan, edge endpoint verification, parent edge consistency, deterministic document hash, policy-version projection
  Open issues: none
  Next action: connect external policy registry metadata when a durable registry is introduced
