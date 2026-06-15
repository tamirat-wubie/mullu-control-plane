<!--
Purpose: Define the repeatable public route monitoring procedure for Govern Cloud.
Governance scope: api.mullusi.com public read-route health, blocked-route guard,
  operator response, and rollback evidence.
Dependencies: scripts/collect_govern_cloud_public_route_monitor.py,
  scripts/validate_govern_evaluate_route_rollback.py,
  schemas/govern_cloud_public_route_monitor_receipt.schema.json, public HTTPS
  access to api.mullusi.com.
Invariants: no secret values are required; the monitor does not mutate DNS,
  Render, GitHub, Cloudflare, or gateway configuration; public write routes stay
  closed unless a separate governed approval changes the boundary.
-->

# Govern Cloud Public Route Monitor Runbook

## Scope

This runbook monitors the public Govern Cloud read proxy on `api.mullusi.com`.
It covers only:

| Route | Expected state |
|---|---|
| `GET /v1/health` | HTTP 200 with `status=ok` and `service=mullusi-govern-cloud-staging` |
| `GET /v1/version` | HTTP 200 with `api=2026.05.v1` and `evaluator=govern-evaluator.v1` |
| `POST /v1/govern/evaluate` | HTTP 404 because non-allowlisted `/v1/*` routes are not public |

## Collection

Run from the repository root:

```powershell
python scripts/collect_govern_cloud_public_route_monitor.py --json --output .change_assurance/govern_cloud_public_route_monitor_receipt.json
```

The collector emits a receipt with:

| Field | Purpose |
|---|---|
| `solver_outcome` | `SolvedVerified` only when all route contracts pass |
| `route_observations` | HTTP status, bounded public JSON fields, and response digest |
| `summary.monitor_closed` | terminal monitor decision for the sampled time |
| `remediation.decision` | `observe` or `rollback_public_proxy` |

The receipt does not contain raw response bodies or secret values.

## Rollback Witness

Run the local rollback witness after any gateway change that touches public
Govern Cloud proxy routes:

```powershell
python scripts/validate_govern_evaluate_route_rollback.py
```

The validator is read-only. It passes only when:

| Check | Required state |
|---|---|
| Preserved public read routes | `/v1/health` and `/v1/version` remain allowlisted |
| Product write route | `/v1/govern/evaluate` is absent from the public proxy allowlist |
| Rollback probe | `POST /v1/govern/evaluate` returns HTTP 404 |
| Outbound transport | blocked route does not call the private Govern Cloud service |

Use JSON mode when a machine-readable receipt is needed:

```powershell
python scripts/validate_govern_evaluate_route_rollback.py --json
```

## Failure Handling

If `solver_outcome` is not `SolvedVerified`:

1. Treat the public read-route monitor as `AwaitingEvidence`.
2. Check whether the failing route is a read-route outage or a blocked-route
   guard failure.
3. If `POST /v1/govern/evaluate` returns HTTP 200, immediately disable the
   public proxy with `MULLU_GOVERN_CLOUD_PUBLIC_PROXY_ENABLED=false` on the
   gateway and redeploy.
4. Preserve the private Govern Cloud Render service for evidence review.
5. Rerun the monitor and rollback witness after remediation and keep the new
   receipts.

## Cadence

For manual operation, run the monitor after every gateway deploy, every Govern
Cloud image deploy, and after any Cloudflare or Render routing change.

For scheduled operation, run it at least hourly and retain the latest passing
receipt plus the latest failing receipt, if any.

## Boundary

This monitor is not a public write-route approval. It is evidence that the
already approved read proxy remains bounded.
