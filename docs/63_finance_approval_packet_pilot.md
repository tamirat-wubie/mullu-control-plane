# Finance Approval Packet Pilot

> **In one box:** How to run the finance-approval pilot end-to-end: invoice
> packet → policy check → approval → effect → proof. A concrete worked example
> of governance over money. New here? →
> [Plain-English Overview](explain/PLAIN_ENGLISH.md). *(Doc type: How-to.)*

Purpose: operate the governed finance approval packet pilot from invoice packet creation through policy evaluation, approval, effect handoff, proof export, and operator read-model inspection.
Governance scope: finance packet contracts, policy decisions, approval/effect receipts, persistent packet store, proof export, route proof coverage, and static operator summary rendering.
Dependencies: `mcoi_runtime.app.routers.finance_approval`, `mcoi_runtime.persistence.finance_approval_store`, `schemas/finance_approval_packet_proof.schema.json`, `schemas/finance_approval_operator_summary.schema.json`, `scripts/render_finance_approval_operator_page.py`, `examples/finance_approval_packet_blocked.json`, and `examples/finance_approval_packet_success.json`.
Invariants:
- Money uses integer minor units, never floats.
- Packet creation evaluates policy before the packet is exposed.
- Blocked or review-bound packets emit no effect receipts.
- Approval actions record explicit approval receipts.
- Effect handoffs record explicit effect receipts.
- Closed packet proof requires a closure certificate id.
- `closed_sent` proof requires at least one effect reference.
- The operator read model is bounded by `limit`.
- The static operator page renders only from a schema-valid redacted summary and contains no JavaScript.

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
  tests\test_render_finance_approval_operator_page.py `
  tests\test_proof_coverage_matrix.py -q
```

Expected result:

```text
238 passed
```

Schema/protocol verification:

```powershell
python scripts\validate_protocol_manifest.py
```

Expected result:

```text
protocol manifest ok: 223 schemas
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
finance_email_calendar_binding_receipt_not_ready
email_calendar_live_evidence_missing
```

Credential binding receipt:

```powershell
python scripts\validate_finance_email_calendar_recovery_env_example.py --template examples\finance_email_calendar_recovery.env.example --strict --json
python scripts\emit_finance_approval_email_calendar_binding_receipt.py --output .change_assurance\finance_approval_email_calendar_binding_receipt.json --json
python scripts\emit_finance_approval_email_calendar_operator_input_request.py --receipt .change_assurance\finance_approval_email_calendar_binding_receipt.json --output .change_assurance\finance_approval_email_calendar_operator_input_request.json --json
python scripts\validate_finance_approval_email_calendar_operator_input_request.py --request .change_assurance\finance_approval_email_calendar_operator_input_request.json --output .change_assurance\finance_approval_email_calendar_operator_input_request_validation.json --json
python scripts\validate_finance_approval_email_calendar_binding_receipt.py --receipt .change_assurance\finance_approval_email_calendar_binding_receipt.json --require-ready --json
python scripts\validate_finance_approval_email_calendar_live_receipt.py --require-ready --json
python scripts\preflight_finance_email_calendar_recovery.py --receipt .change_assurance\email_calendar_live_receipt.json --output .change_assurance\finance_email_calendar_recovery_preflight.json --json
python scripts\run_finance_approval_live_handoff_closure.py --output .change_assurance\finance_approval_live_handoff_closure_run.json --strict --json
python scripts\validate_finance_approval_live_handoff_closure_run_schema.py --strict --json
python scripts\preflight_finance_approval_live_handoff.py --strict --json
python scripts\validate_finance_approval_live_handoff_preflight_schema.py --strict --json
python scripts\produce_finance_approval_handoff_packet.py --live-receipt .change_assurance\email_calendar_live_receipt.json --output .change_assurance\finance_approval_handoff_packet.json --json
python scripts\validate_finance_approval_handoff_packet_schema.py --strict --json
python scripts\validate_finance_approval_live_handoff_chain.py --strict --json
python scripts\validate_finance_approval_live_handoff_chain.py --strict --require-ready --json
python scripts\validate_finance_approval_live_handoff_chain_schema.py --strict --json
python scripts\produce_finance_approval_operator_summary.py --output .change_assurance\finance_approval_operator_summary.json --strict --json
python scripts\validate_finance_approval_operator_summary_schema.py --strict --json
python scripts\render_finance_approval_operator_page.py --summary .change_assurance\finance_approval_operator_summary.json --output .change_assurance\finance_approval_operator_page.html --strict --json
```

Use `examples\finance_email_calendar_recovery.env.example` as the redacted binding template; validate it before replacing secret placeholders through a secrets manager.
The receipt records only binding-name presence for the email/calendar worker endpoint, worker signing secret, connector token family, and scope witness family. It also records scope witness classification as read-only or invalid by binding name. It never serializes worker URLs, token values, secrets, or scope values.
The operator input request translates a blocked binding receipt into public-safe missing input names and blocked actions. It never serializes worker URLs, signing secrets, connector tokens, scope values, provider account details, or mailbox contents.
The recovery preflight receipt records redacted recovery checks for worker reachability inputs, connector token presence, read-only scope review, and live probe rerun readiness.
Email/calendar recovery requires four binding groups before rerunning the live receipt probe:

```text
MULLU_EMAIL_CALENDAR_WORKER_URL and MULLU_EMAIL_CALENDAR_WORKER_SECRET
one connector token: EMAIL_CALENDAR_CONNECTOR_TOKEN, GMAIL_ACCESS_TOKEN, GOOGLE_CALENDAR_ACCESS_TOKEN, or MICROSOFT_GRAPH_ACCESS_TOKEN
one read-only scope witness: EMAIL_CALENDAR_CONNECTOR_SCOPE_ID=gmail.readonly or GOOGLE_CALENDAR_SCOPE_ID=calendar.events.readonly
```

Do not use write-capable scope witnesses such as `calendar.events`, `mail.send`, or `compose` for the finance pilot recovery path.
The handoff packet carries `promotion_boundary.ok` separately from `promotion_boundary.ready`. `ok=true` means the packet artifacts are structurally usable. `ready=false` means live handoff promotion remains blocked. The packet must include the `email_calendar_live_receipt` artifact, and `ready=true` requires that receipt to validate as passed, read-only, worker-bound, and effect-free. The strict promotion command is `python scripts\validate_finance_approval_live_handoff_chain.py --strict --require-ready --json`.
The operator summary is a redacted read-only artifact that copies packet readiness, chain readiness, readiness blockers, artifact statuses, next actions, and must-not-claim boundaries into `.change_assurance\finance_approval_operator_summary.json`.
The static operator page renders that validated redacted summary into `.change_assurance\finance_approval_operator_page.html`. It performs no live adapter action, contains no JavaScript, escapes rendered text, and must not be used as a production finance automation or live email delivery claim.
The closure runner is a dry-run artifact by default. It validates the redacted recovery env template before binding receipt emission, marks the read-only email/calendar live receipt command as the only live connector touchpoint, validates that receipt before adapter evidence collection, validates the aggregate handoff chain, produces the operator summary, validates the operator summary schema, and blocks until the binding receipt, live receipt, preflight, packet, and pilot readiness are closed.

Payment-provider binding receipt:

```powershell
python scripts\emit_finance_approval_payment_provider_binding_receipt.py --provider stripe --output .change_assurance\finance_approval_payment_provider_binding_receipt.json --strict --json
python scripts\validate_finance_approval_payment_provider_binding_receipt.py --receipt .change_assurance\finance_approval_payment_provider_binding_receipt.json --require-ready --json
python scripts\produce_finance_approval_payment_closure_receipt.py --provider stripe --provider-binding-receipt .change_assurance\finance_approval_payment_provider_binding_receipt.json --output .change_assurance\finance_approval_payment_closure_receipt.json --strict --json
python scripts\validate_finance_approval_payment_closure_receipt.py --receipt .change_assurance\finance_approval_payment_closure_receipt.json --provider-binding-receipt .change_assurance\finance_approval_payment_provider_binding_receipt.json --require-ready --json
```

The payment-provider binding receipt records only provider-scoped credential name presence for `PAYMENT_PROVIDER_CONNECTOR_TOKEN`, `STRIPE_API_KEY`, `BANK_ACH_CONNECTOR_TOKEN`, or `MANUAL_BANK_PORTAL_TOKEN`. It never serializes credential values. The payment closure receipt remains blocked unless the binding receipt is ready, provider-matched, and its `provider-binding:{provider}:...` ref is present in both root evidence and provider receipt evidence.

Reviewer fixtures:

```powershell
python scripts\validate_finance_approval_payment_provider_binding_receipt.py --receipt examples\finance_payment_provider_binding_receipt_stripe.json --require-ready --json
python scripts\validate_finance_approval_payment_closure_receipt.py --receipt examples\finance_payment_closure_receipt_stripe_bound.json --provider-binding-receipt examples\finance_payment_provider_binding_receipt_stripe.json --require-ready --json
```

These fixtures are deterministic Stripe-scoped evidence examples. They prove the validator path and provider-binding reference contract, but they do not prove live provider execution.

This is still not a production payment claim. It is a governed closure-evidence path for non-sandbox provider labels. Live payment execution still requires provider-live receipt certification, reconciliation evidence, and approval-bound dispatch controls.

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
  Invariants verified: no-float money, policy-before-exposure, no effect on blocked packets, explicit approval/effect receipts, proof schema, bounded operator read model, deterministic persistence, finance-scoped live handoff plan, dry-run live handoff closure sequence, payment-provider binding receipt validation, static redacted HTML operator page
  Open issues: no PostgreSQL finance store; no live email/calendar adapter closure
  Next action: close live email/calendar adapter evidence before claiming production finance operations
