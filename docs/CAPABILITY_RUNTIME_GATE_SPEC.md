# Capability Runtime Gate Specification

Purpose: convert capability maturity from documentation into runtime admission policy.
Governance scope: capability identifiers, maturity levels, environments, risk classes, approval requirements, evidence requirements, rollback paths, and autonomous-execution boundaries.
Dependencies: `docs/62_governed_operational_intelligence.md`, `docs/EVIDENCE_CLASSIFICATION.md`, `docs/RECEIPT_VIEWER_V1_SPEC.md`, `DEPLOYMENT_STATUS.md`.
Invariants: no capability may execute above its certified maturity, no malformed capability identifier may be coerced into authority, and no production high-risk action may execute without production-grade capability evidence.

## Capability admission rule

```text
capability_execution_allowed(action, capability, environment) <=>
  capability.id is explicit text
  and capability.maturity_level >= required_level(environment, action.risk_class, action.autonomy_mode)
  and environment in capability.allowed_environments
  and action.input matches capability.input_schema
  and action.expected_receipt matches capability.receipt_schema
  and capability.evidence_requirements are satisfied
  and rollback_path_exists_when_required(action, capability)
```

## Required capability record

| Field | Purpose |
| --- | --- |
| `capability_id` | stable explicit identifier |
| `owner` | accountable operator or team |
| `risk_class` | maximum risk profile |
| `maturity_level` | C0-C7 certification level |
| `maturity_label` | derived operator label: Specified, Implemented, or Verified |
| `allowed_environments` | local, ci, staging, pilot, production |
| `input_schema` | admitted input contract |
| `output_schema` | returned result contract |
| `receipt_schema` | proof object contract |
| `approval_policy` | authority/approval requirement |
| `budget_policy` | resource or spend boundary |
| `tenant_scope` | cross-tenant isolation boundary |
| `side_effects` | possible external effects |
| `rollback_path` | compensation/recovery path |
| `evidence_requirements` | evidence needed before/after execution |
| `last_verified_at` | freshness anchor |
| `known_failure_modes` | bounded operator-facing failures |

## Maturity levels

| Level | Meaning | Runtime permission |
| --- | --- | --- |
| `C0` | described only | no execution |
| `C1` | unit tested | local only |
| `C2` | mock tested | local/CI dry-run |
| `C3` | sandbox tested | staging dry-run or sandbox write |
| `C4` | live read-only receipt exists | pilot read-only |
| `C5` | live write receipt exists with approval | pilot write with approval |
| `C6` | production certified | production bounded execution |
| `C7` | autonomy certified | autonomy under policy and risk limits |

## Read-model labels

`maturity_label` is a read-model projection over `maturity_level`, not a second authority source.

| Label | Levels | Meaning |
| --- | --- | --- |
| `Specified` | C0-C2 | contract, policy, or mock-evaluation evidence exists but no sandbox implementation closure is present |
| `Implemented` | C3-C5 | sandbox or live implementation evidence exists, but production readiness is not closed |
| `Verified` | C6-C7 | production-ready or autonomy-ready evidence gates are closed |

## Required level matrix

| Environment | Low risk | Medium risk | High risk | Autonomous high risk |
| --- | --- | --- | --- | --- |
| `local` | C1 | C2 | C3 | blocked |
| `ci` | C2 | C2 | C3 dry-run | blocked |
| `staging` | C3 | C3 | C4 | blocked |
| `pilot` | C4 | C5 with approval | C5 with approval + reconciliation | blocked unless C7 pilot-scoped |
| `production` | C5 | C6 | C6 + approval + reconciliation | C7 only |

## Failure states

| Failure | Required response |
| --- | --- |
| malformed capability id | reject before binding |
| unknown capability | deny with explicit blocker |
| maturity too low | block and report required level |
| environment not allowed | deny with environment blocker |
| missing approval | escalate or deny according to policy |
| missing rollback for high-risk action | deny |
| stale capability evidence | escalate for re-verification |
| receipt schema missing | deny for effect-bearing action |

## Initial API/read-model target

```text
GET /api/v1/simple/capabilities
GET /api/v1/simple/capabilities/{capability_id}
POST /api/v1/simple/capabilities/{capability_id}/check
```

The first version may be read-only plus check-only. It must not grant execution authority from the simple surface.

## Product value

This gate lets Mullu say a capability is not merely present. It is allowed only in the environments, risk classes, and evidence conditions it has earned.
