# Finance Approval Packet Pilot

Purpose: operate the governed finance approval packet pilot from invoice packet creation through policy evaluation, approval, effect handoff, proof export, and operator read-model inspection.
Governance scope: finance packet contracts, policy decisions, approval/effect receipts, persistent packet store, proof export, and route proof coverage.
Dependencies: `mcoi_runtime.app.routers.finance_approval`, `mcoi_runtime.persistence.finance_approval_store`, `schemas/finance_approval_packet_proof.schema.json`, `examples/finance_approval_packet_blocked.json`, and `examples/finance_approval_packet_success.json`.
Invariants:
- Money uses integer minor units, never floats.
- Packet creation evaluates policy before the packet is exposed.
- Blocked or review-bound packets emit no effect receipts.
- Approval actions record explicit approval receipts.
- Effect handoffs record explicit effect receipts.
- Closed packet proof requires a closure certificate id.
- `closed_sent` proof requires at least one effect reference.
- The operator read model is bounded by `limit`.

## Capability

The pilot proves one governed finance workflow:

```text
invoice packet
  -> policy evaluation
  -> review or approval state
  -> explicit approval receipt
  -> optional email handoff effect receipt
  -> closure certificate id
  -> proof export
  -> operator read model
```

This is a finance approval packet preparation and proof-export pilot. It does not claim autonomous payment execution, bank settlement, ERP reconciliation, or live email delivery.

## Persistence

By default the runtime uses an in-memory packet store. To persist packet state to deterministic JSON, set:

```powershell
$env:MULLU_FINANCE_APPROVAL_STORE_PATH="C:\mullu\finance_approval_packets.json"
```

The file-backed store persists `cases[]`, `decisions[]`, `approvals[]`, and `effects[]`. Malformed store payloads fail closed at startup/load time.

## API

### Create Packet

```text
POST /api/v1/finance/approval-packets
```

Required fields:

| Field | Meaning |
| --- | --- |
| `case_id` | Stable packet identity |
| `tenant_id` | Tenant boundary |
| `actor_id` | Requesting actor |
| `vendor_id` | Vendor identity |
| `invoice_id` | Invoice identity |
| `minor_units` | Currency amount in minor units |
| `source_evidence_ref` | Source invoice evidence reference |
| `actor_limit_minor_units` | Actor spend boundary |
| `tenant_limit_minor_units` | Tenant spend boundary |

Optional fields:

| Field | Meaning |
| --- | --- |
| `currency` | ISO 4217 code, defaults to `USD` |
| `risk` | `low`, `medium`, `high`, or `critical` |
| `vendor_evidence_status` | `fresh`, `stale`, or `missing` |
| `approval_status` | `absent`, `granted`, `rejected`, or `expired` |
| `duplicate_invoice` | Duplicate-invoice review flag |
| `recovery_path_present` | Whether effect-bearing recovery is available |
| `capability_maturity_level` | Current capability maturity level |
| `metadata` | Bounded operator metadata |

### List, Get, Approve, And Prove

```text
GET  /api/v1/finance/approval-packets
GET  /api/v1/finance/approval-packets?tenant_id=tenant-demo
GET  /api/v1/finance/approval-packets?state=requires_review
GET  /api/v1/finance/approval-packets/{case_id}
POST /api/v1/finance/approval-packets/{case_id}/approval
GET  /api/v1/finance/approval-packets/{case_id}/proof
```

Approval request:

```json
{
  "approver_id": "finance-admin",
  "approver_role": "finance_admin",
  "status": "granted",
  "create_email_handoff": true
}
```

If `create_email_handoff=true`, the pilot creates an `email_handoff_created` effect receipt and closes the packet as `closed_sent`. This is a handoff receipt, not proof of live email delivery.

The proof response conforms to `schemas/finance_approval_packet_proof.schema.json`.

### Operator Read Model

```text
GET /api/v1/finance/approval-packets/operator/read-model
GET /api/v1/finance/approval-packets/operator/read-model?tenant_id=tenant-demo&limit=50
```

The read model returns store summary counts, visible packet count, blocked count, approval-wait count, proof-ready count, and bounded packet projections with latest policy reasons.

`limit` must be between 1 and 200.

## Blocked Demo

Create a review-bound packet:

```powershell
$body = @{
  case_id = "case-blocked-001"
  tenant_id = "tenant-demo"
  actor_id = "user-requester"
  vendor_id = "vendor-acme"
  invoice_id = "INV-BLOCKED-001"
  minor_units = 1200000
  source_evidence_ref = "evidence:invoice:blocked"
  risk = "high"
  actor_limit_minor_units = 500000
  tenant_limit_minor_units = 5000000
  vendor_evidence_status = "stale"
  approval_status = "absent"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/finance/approval-packets" `
  -ContentType "application/json" `
  -Body $body
```

Expected policy reasons include:

```text
budget_exceeded_actor_limit
vendor_evidence_stale
approval_required
approval_missing
```

Expected packet state:

```text
requires_review
```

Export review proof:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/finance/approval-packets/case-blocked-001/proof"
```

The proof has no `effect_refs`.

## Successful Demo

Create an approval-ready packet:

```powershell
$body = @{
  case_id = "case-success-001"
  tenant_id = "tenant-demo"
  actor_id = "user-requester"
  vendor_id = "vendor-acme"
  invoice_id = "INV-OK-001"
  minor_units = 120000
  source_evidence_ref = "evidence:invoice:success"
  risk = "medium"
  actor_limit_minor_units = 500000
  tenant_limit_minor_units = 5000000
  vendor_evidence_status = "fresh"
  approval_status = "granted"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/finance/approval-packets" `
  -ContentType "application/json" `
  -Body $body
```

Record explicit approval and create an email handoff receipt:

```powershell
$approval = @{
  approver_id = "finance-admin"
  approver_role = "finance_admin"
  status = "granted"
  create_email_handoff = $true
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/finance/approval-packets/case-success-001/approval" `
  -ContentType "application/json" `
  -Body $approval
```

Expected packet state:

```text
closed_sent
```

Export closure proof:

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/finance/approval-packets/case-success-001/proof"
```

Expected proof fields:

```text
final_state = closed_sent
approval_refs has at least one item
effect_refs has at least one item
closure_certificate_id is present
```

## Operator Inspection

```powershell
Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/finance/approval-packets/operator/read-model?tenant_id=tenant-demo&limit=50"
```

Expected after both demos:

```text
visible_count = 2
blocked_count = 1
proof_ready_count = 2
```

## Verification

Focused verification:

```powershell
$env:PYTHONPATH=".;mcoi"
pytest mcoi\tests\test_finance_approval_packet.py `
  mcoi\tests\test_finance_approval_router.py `
  mcoi\tests\test_finance_approval_store.py `
  tests\test_validate_protocol_manifest.py `
  tests\test_proof_coverage_matrix.py -q
```

Expected result:

```text
102 passed
```

Schema/protocol verification:

```powershell
python scripts\validate_protocol_manifest.py
```

Expected result:

```text
protocol manifest ok: 88 schemas
```

Finance pilot readiness verification:

```powershell
python scripts\validate_finance_approval_pilot.py --json
```

Current expected readiness before live email/calendar closure:

```text
readiness_level = proof-pilot-ready
ready = false
blocker = email calendar evidence closed
```

Finance live handoff closure plan:

```powershell
python scripts\plan_finance_approval_live_handoff.py --output .change_assurance\finance_approval_live_handoff_plan.json --json
python scripts\validate_finance_approval_live_handoff_plan_schema.py --strict --json
```

Current expected actions before live email/calendar closure:

```text
email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN
email_calendar_live_evidence_missing
```

Credential binding receipt:

```powershell
python scripts\emit_finance_approval_email_calendar_binding_receipt.py --output .change_assurance\finance_approval_email_calendar_binding_receipt.json --strict --json
python scripts\validate_finance_approval_email_calendar_binding_receipt.py --require-ready --json
python scripts\validate_finance_approval_email_calendar_live_receipt.py --require-ready --json
python scripts\run_finance_approval_live_handoff_closure.py --output .change_assurance\finance_approval_live_handoff_closure_run.json --strict --json
python scripts\validate_finance_approval_live_handoff_closure_run_schema.py --strict --json
python scripts\preflight_finance_approval_live_handoff.py --strict --json
python scripts\validate_finance_approval_live_handoff_preflight_schema.py --strict --json
python scripts\produce_finance_approval_handoff_packet.py --output .change_assurance\finance_approval_handoff_packet.json --json
python scripts\validate_finance_approval_handoff_packet_schema.py --strict --json
python scripts\validate_finance_approval_live_handoff_chain.py --strict --json
python scripts\validate_finance_approval_live_handoff_chain.py --strict --require-ready --json
python scripts\validate_finance_approval_live_handoff_chain_schema.py --strict --json
python scripts\produce_finance_approval_operator_summary.py --output .change_assurance\finance_approval_operator_summary.json --strict --json
python scripts\validate_finance_approval_operator_summary_schema.py --strict --json
```

The receipt records only token-name presence for `EMAIL_CALENDAR_CONNECTOR_TOKEN`, `GMAIL_ACCESS_TOKEN`, `GOOGLE_CALENDAR_ACCESS_TOKEN`, and `MICROSOFT_GRAPH_ACCESS_TOKEN`. It never serializes token values.
The handoff packet carries `promotion_boundary.ok` separately from `promotion_boundary.ready`. `ok=true` means the packet artifacts are structurally usable. `ready=false` means live handoff promotion remains blocked. The strict promotion command is `python scripts\validate_finance_approval_live_handoff_chain.py --strict --require-ready --json`.
The operator summary is a redacted read-only artifact that copies packet readiness, chain readiness, readiness blockers, artifact statuses, next actions, and must-not-claim boundaries into `.change_assurance\finance_approval_operator_summary.json`.
The closure runner is a 16-command dry-run artifact by default. It marks the read-only email/calendar live receipt command as the only live connector touchpoint, validates that receipt before adapter evidence collection, validates the aggregate handoff chain, produces the operator summary, validates the operator summary schema, and blocks until the binding receipt, live receipt, preflight, packet, and pilot readiness are closed.

Deterministic local pilot witness:

```powershell
python scripts\produce_finance_approval_pilot_witness.py --output .change_assurance\finance_approval_pilot_witness.json
```

Expected result:

```text
finance approval pilot witness: passed
```

## Claim Boundary

This pilot can claim:

```text
governed finance approval packet preparation
policy-reasoned blocking
explicit approval receipts
email-handoff effect receipts
terminal closure ids
schema-backed proof export
bounded operator read model
deterministic file persistence
```

This pilot must not claim:

```text
autonomous payment execution
bank settlement
ERP reconciliation
live email delivery
production finance automation
```

STATUS:
  Completeness: 100%
  Invariants verified: no-float money, policy-before-exposure, no effect on blocked packets, explicit approval/effect receipts, proof schema, bounded operator read model, deterministic persistence, finance-scoped live handoff plan, dry-run live handoff closure sequence
  Open issues: no HTML operator page; no PostgreSQL finance store; no live email/calendar adapter closure
  Next action: close live email/calendar adapter evidence before claiming production finance operations
