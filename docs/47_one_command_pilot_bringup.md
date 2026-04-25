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

STATUS:
  Completeness: 100%
  Invariants verified: local-only scaffold, deterministic pilot id, stable JSON output, no silent overwrite, tenant/policy/budget/dashboard/audit/lineage artifacts
  Open issues: none
  Next action: connect scaffold application to an authenticated hosted pilot provisioning endpoint
