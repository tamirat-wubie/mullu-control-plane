# One-Command Pilot Bring-Up

Purpose: define `mcoi pilot init` as the local scaffold command for a governed
pilot bundle.

Governance scope: tenant, policy, budget, dashboard, audit query, and lineage
example artifacts. The command writes local files only and does not mutate live
infrastructure.

## Command

```powershell
mcoi pilot init --tenant-id acme-pilot --name "Acme Pilot" --output pilots/acme
```

Optional controls:

| Flag | Meaning | Default |
|---|---|---|
| `--policy-pack` | Policy pack id | `default-safe` |
| `--policy-version` | Policy version | `v0.1` |
| `--max-cost` | Pilot budget cost limit | `100.0` |
| `--max-calls` | Pilot budget call limit | `1000` |
| `--force` | Overwrite scaffold files | disabled |

## Generated Artifacts

| File | Purpose |
|---|---|
| `pilot.manifest.json` | Pilot id, entrypoints, and governance bindings |
| `tenant.json` | Tenant identity and pilot status |
| `policy.json` | Enforced policy pack and shadow policy settings |
| `budget.json` | Tenant budget and streaming enforcement posture |
| `dashboard.json` | Dashboard and sandbox view hints |
| `audit_queries.json` | Ready-to-run audit query examples |
| `lineage_examples.json` | `lineage://` query templates |
| `README.md` | Operator bring-up checklist |

## Rules

1. The command MUST NOT call live APIs.
2. The command MUST fail closed when scaffold files already exist unless `--force` is provided.
3. Generated JSON MUST use stable key ordering.
4. Pilot id MUST be deterministic for identical tenant, name, policy pack, and policy version.
5. Every scaffold MUST include audit and lineage examples before demo use.

## Hosted Provisioning Endpoint

```powershell
POST /api/v1/pilots/provision
GET /api/v1/pilots/provisions
GET /api/v1/pilots/provisions/{pilot_id}
```

The hosted endpoint returns the same deterministic artifact bundle without
writing server-local files. Authentication is enforced by the existing API guard
in pilot and production profiles, and each accepted request records
`pilot.provision.scaffold` audit evidence. Accepted provisions are retained in a
bounded operator history read model for list and detail queries.

STATUS:
  Completeness: 100%
  Invariants verified: local-only scaffold, deterministic pilot id, stable JSON output, no silent overwrite, tenant/policy/budget/dashboard/audit/lineage artifacts, hosted endpoint has no filesystem mutation, hosted endpoint records audit evidence, accepted provisions persist to bounded history
  Open issues: none
  Next action: back hosted pilot provisioning history with the persistent governance store bundle
