<!--
Purpose: reconcile current api.mullusi.com public-route evidence with the
  upstream private readiness gate before any stronger production claim.
Governance scope: deployment witness, upstream readiness, DNS publication
  boundary, manual evidence blockers, and operator-safe next commands.
Dependencies: DEPLOYMENT_STATUS.md, scripts/collect_govern_cloud_public_route_monitor.py,
  scripts/emit_deployment_upstream_blocker_receipt.py, mullusi-site
  scripts/check-api-production-readiness.mjs, .change_assurance receipts.
Invariants: no secret values are recorded; public route health is not treated
  as proof of private persistence, secret storage, rollback, or runtime witness
  closure.
-->

# API Upstream Readiness Reconciliation

> **In one box:** `api.mullusi.com` is reachable and its public read routes are
> healthy. That does not yet prove every private setup item behind the service,
> so this page separates the facts we have from the facts still needing
> private evidence. *(Doc type: Reference.)*

---

## Current Judgment

| Claim | Current state | Evidence |
|---|---|---|
| Public API read routes | `SolvedVerified` | `.change_assurance/govern_cloud_public_route_monitor_receipt.json` recorded `/v1/health` and `/v1/version` returning `200` on 2026-06-13T21:12:20Z. |
| Public guarded route | `SolvedVerified` | The same monitor recorded `POST /v1/govern/evaluate` returning `404`, preserving the blocked evaluator boundary. |
| DNS target binding | `SolvedVerified` | `.change_assurance/gateway_dns_target_binding_receipt.json` records `api.mullusi.com -> mullu-gateway.onrender.com` through `cloudflare-render`. |
| DNS resolution | `SolvedVerified` | `.change_assurance/gateway_dns_resolution_receipt.json` records resolved IPv4 and IPv6 addresses. |
| Published deployment witness | `SolvedVerified` | `DEPLOYMENT_STATUS.md` and `.change_assurance/deployment_witness.json` record a published public-health witness for `https://api.mullusi.com/health`. |
| Upstream private readiness gate | `AwaitingEvidence` | `.change_assurance/deployment_upstream_blocker_receipt.json` records private/manual evidence blockers from the upstream checker. |
| Full DNS publication closure claim | `AwaitingEvidence` | The upstream checker allows API provisioning but does not allow DNS publication closure until private evidence is supplied. |

## Proven Public Surface

| Surface | Observed contract | Result |
|---|---|---|
| `GET https://api.mullusi.com/v1/health` | HTTP `200`, service `mullusi-govern-cloud-staging`, status `ok` | Pass |
| `GET https://api.mullusi.com/v1/version` | HTTP `200`, API `2026.05.v1`, evaluator `govern-evaluator.v1` | Pass |
| `POST https://api.mullusi.com/v1/govern/evaluate` | HTTP `404` guard | Pass |
| Raw secret handling | `raw_secret_values_included=false` | Pass |

## Remaining Private Evidence

These items are not safely inferred from public route health. They need private
runtime, hosting, database, or operator evidence before the upstream readiness
gate can close.

| Evidence key | Meaning | Current state |
|---|---|---|
| `production_image_published` | A versioned production image exists and is selected for deployment. | AwaitingEvidence |
| `runtime_host_ready` | The intended runtime host is provisioned and reachable through the expected private path. | AwaitingEvidence |
| `managed_postgres_ready` | The managed PostgreSQL database exists and is bound to the service. | AwaitingEvidence |
| `schema_applied` | Required database schema or migrations have been applied. | AwaitingEvidence |
| `production_secrets_stored` | Production secrets are stored in the hosting platform, not in the repository or docs. | AwaitingEvidence |
| `deploy_env_check_ready` | The deployed environment variables pass the expected environment check. | AwaitingEvidence |
| `release_preflight_ready` | The release preflight passed against the intended deployment target. | AwaitingEvidence |
| `persistence_check_ready` | Persistence behavior was checked against the managed database. | AwaitingEvidence |
| `host_firewall_configured` | Host/network access rules match the deployment boundary. | AwaitingEvidence |
| `tls_certificate_ready` | TLS is active for the intended host boundary. | AwaitingEvidence |
| `rollback_path_defined` | A rollback path is documented and executable for this deployment. | AwaitingEvidence |
| `private_runtime_witness_ready` | Private runtime witness evidence is available without exposing secrets. | AwaitingEvidence |
| `dns_authority_ready` | DNS authority evidence exists for the domain and target. | AwaitingEvidence |

## Operator-Safe Commands

Refresh the public route monitor:

```powershell
python scripts/collect_govern_cloud_public_route_monitor.py --json --output .change_assurance/govern_cloud_public_route_monitor_receipt.json
```

Refresh the upstream blocker receipt after collecting a new upstream report:

```powershell
python scripts/emit_deployment_upstream_blocker_receipt.py --target-gateway-url "https://api.mullusi.com" --upstream-readiness-report .change_assurance\upstream_api_readiness_report.json --output .change_assurance\deployment_upstream_blocker_receipt.json --json
```

Validate the blocker receipt:

```powershell
python scripts/validate_deployment_upstream_blocker_receipt.py --receipt .change_assurance\deployment_upstream_blocker_receipt.json --output .change_assurance\deployment_upstream_blocker_receipt_validation.json
```

Only after the thirteen private evidence items are proven, rerun the upstream
checker with `--require-ready` in the upstream site repository:

```powershell
node scripts/check-api-production-readiness.mjs --production-image-published --runtime-host-ready --managed-postgres-ready --schema-applied --production-secrets-stored --deploy-env-ready --release-preflight-ready --persistence-ready --host-firewall-configured --tls-certificate-ready --rollback-path-defined --private-runtime-witness-ready --dns-authority-ready --require-ready --json
```

## Non-Claims

This reconciliation does not claim:

1. Managed database persistence is verified.
2. Production secret values are correct.
3. Private runtime witness evidence is complete.
4. Rollback execution has been tested.
5. The upstream site checker is fully aligned with the current Render gateway deployment path.

## Go deeper / where to go next

| You now want to... | Go to |
| --- | --- |
| Understand the big picture in plain words | [Plain-English Overview](explain/PLAIN_ENGLISH.md) |
| Look up a confusing word | [Glossary](GLOSSARY.md) |
| See the whole documentation map | [Start Here](START_HERE.md) |
| See the deployment status witness | [Deployment Status Witness](../DEPLOYMENT_STATUS.md) |
| Monitor the Govern Cloud public route | [Govern Cloud Public Route Monitor Runbook](GOVERN_CLOUD_PUBLIC_ROUTE_MONITOR_RUNBOOK.md) |

Back to [Start Here](START_HERE.md)

STATUS:
  Completeness: 90%
  Invariants verified: [public-route evidence separated from private readiness evidence, no raw secret values recorded, DNS target and DNS resolution evidence named, upstream blocker preserved]
  Open issues: [thirteen private upstream evidence items remain AwaitingEvidence]
  Next action: collect private evidence or update the upstream checker to recognize the current Render gateway deployment path without weakening the private evidence gate
