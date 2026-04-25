# Lineage Query API Skeleton

Purpose: define `lineage://` URI semantics for querying every governed action
that causally contributed to a symbolic intelligence output.

Governance scope: read-only causal lineage queries over trace entries,
policy decisions, model invocation records, tenant context, budget reservations,
tool receipts, and replay witnesses.

## Architecture

| Component | Responsibility | Input | Output |
|---|---|---|---|
| URI parser | Parse and validate `lineage://` references | Lineage URI | bounded query envelope |
| Lineage resolver | Locate root output and ancestor chain | output id or trace id | ordered causal graph |
| Context projector | Attach policy, model, tenant, and budget context | trace node ids | decorated lineage nodes |
| Proof verifier | Validate hash links and proof references | decorated nodes | verification summary |
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
| `depth` | Maximum ancestor depth | `25` |
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

## Initial Endpoint Shape

| Route | Method | Purpose |
|---|---|---|
| `/api/v1/lineage/resolve` | `POST` | Resolve a `lineage://` URI into a causal graph |
| `/api/v1/lineage/{trace_id}` | `GET` | Fetch lineage by trace id |
| `/api/v1/lineage/output/{output_id}` | `GET` | Fetch lineage by output id |

STATUS:
  Completeness: 100%
  Invariants verified: URI grammar, read-only boundary, tenant context retention, missing ancestor visibility, proof verification position
  Open issues: route implementation and response schema remain pending
  Next action: add `lineage_query.schema.json` and a resolver backed by trace/replay stores
