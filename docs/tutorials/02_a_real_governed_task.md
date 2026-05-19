# Tutorial 2 — Watch Mullu Govern Real Money

> **In one box:** In [Tutorial 1](01_first_governed_task.md) you got Mullu
> running and saw that powerful features are off until turned on. Now you'll
> turn on one real governed workflow — a **finance approval** — and watch the
> safety machinery work with your own eyes: first Mullu **refuses** a payment
> that breaks a spending limit, then **approves** a valid one and hands you a
> tamper-evident **proof**. About 25 minutes, hands-on. Do Tutorial 1 first.
>
> This uses the documented Finance Approval Packet pilot. The authoritative
> spec is [63_finance_approval_packet_pilot.md](../63_finance_approval_packet_pilot.md);
> if any step here differs from it, the spec wins — tell us, that's a doc bug.

Any unfamiliar word is one click away in the [Glossary](../GLOSSARY.md). The
"big picture, no jargon" version of what you're about to see is the
[Plain-English Overview](../explain/PLAIN_ENGLISH.md) (this is rules #1 and #2 —
the [approval gate](../GLOSSARY.md#approval-gate) and the
[budget](../GLOSSARY.md#budget-spend-budget) — happening for real).

Commands are PowerShell (Windows), matching the spec. On Mac/Linux use the same
URLs with `curl`.

---

## Step 1 — Start the server with a finance store

**What we're doing:** starting Mullu like in Tutorial 1, but pointing the
finance pilot at a file so the packets and decisions are saved and you can
inspect them. The path is yours to choose; it's created on first write.

```powershell
$env:MULLU_ENV = "local_dev"
$env:MULLU_FINANCE_APPROVAL_STORE_PATH = "$HOME\mullu_finance_packets.json"
uvicorn mcoi_runtime.app.server:app --port 8000
```

**What you should see:** the same `Uvicorn running on http://127.0.0.1:8000`
line as before. Leave this terminal running and open a **second** PowerShell
window for the next steps.

**If it fails:** revisit [Tutorial 1 Step 4](01_first_governed_task.md) — it's
the same server, so any failure here is a setup issue covered there.

---

## Step 2 — Try to overspend (watch the gate STOP it)

**What we're doing:** asking Mullu to prepare a $12,000 invoice payment when the
requesting actor's limit is only $5,000. A naive AI would just do it. Mullu must
refuse. (Money is in *minor units* — cents — so 1200000 = $12,000.)

In the **second** window:

```powershell
$body = @{
  case_id                 = "case-blocked-001"
  tenant_id               = "tenant-demo"
  actor_id                = "user-requester"
  vendor_id               = "vendor-acme"
  invoice_id              = "INV-BLOCKED-001"
  minor_units             = 1200000
  source_evidence_ref     = "evidence:invoice:blocked"
  risk                    = "high"
  actor_limit_minor_units = 500000
  tenant_limit_minor_units = 5000000
  vendor_evidence_status  = "stale"
  approval_status         = "absent"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/finance/approval-packets" `
  -ContentType "application/json" -Body $body
```

**What you should see:** the packet is created but comes back **blocked /
requires review**, with policy reasons such as `budget_exceeded_actor_limit`
(per the spec, stale vendor evidence and high risk also raise reasons). It did
**not** become payable. You just watched the [budget](../GLOSSARY.md#budget-spend-budget)
invariant — *"the AI cannot raise its own limit"* — enforced mechanically.

> One of the pilot's stated invariants is: *blocked or review-bound packets
> emit no [effect](../GLOSSARY.md#effect) receipts.* Nothing happened in the
> real world. That is the whole point.

---

## Step 3 — Submit a valid payment

**What we're doing:** the same request, but within limits and with fresh
evidence — a $1,200 invoice, actor limit $5,000. This one should pass policy.

```powershell
$ok = @{
  case_id                 = "case-ok-001"
  tenant_id               = "tenant-demo"
  actor_id                = "user-requester"
  vendor_id               = "vendor-acme"
  invoice_id              = "INV-OK-001"
  minor_units             = 120000
  source_evidence_ref     = "evidence:invoice:INV-OK-001"
  risk                    = "medium"
  actor_limit_minor_units = 500000
  tenant_limit_minor_units = 5000000
  vendor_evidence_status  = "fresh"
  approval_status         = "granted"
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/finance/approval-packets" `
  -ContentType "application/json" -Body $ok
```

**What you should see:** a packet created in a passed/awaiting-approval state
(policy reason `policy_passed`). It is *ready for a human decision* — note it
still does not pay anyone yet. That's rule #1: nothing consequential without an
explicit sign-off.

---

## Step 4 — Give the human approval

**What we're doing:** acting as the finance admin who signs off. This records an
explicit [approval receipt](../GLOSSARY.md#receipt) and (because we ask for an
email handoff) closes the packet as `closed_sent`.

```powershell
$appr = @{
  approver_id           = "finance-admin"
  approver_role         = "finance_admin"
  status                = "granted"
  create_email_handoff  = $true
} | ConvertTo-Json

Invoke-RestMethod -Method Post `
  -Uri "http://localhost:8000/api/v1/finance/approval-packets/case-ok-001/approval" `
  -ContentType "application/json" -Body $appr
```

**What you should see:** confirmation that the packet is approved and closed,
with an `email_handoff_created` effect receipt. Per the spec this is a *handoff*
receipt — proof the governed step happened, **not** proof an email was actually
delivered. Mullu is careful to claim only what it can prove.

---

## Step 5 — Collect the proof

**What we're doing:** asking for the tamper-evident
[proof receipt](../GLOSSARY.md#proof-receipt--execution-receipt) — the evidence
that this whole sequence followed the rules.

```powershell
Invoke-RestMethod -Method Get `
  -Uri "http://localhost:8000/api/v1/finance/approval-packets/case-ok-001/proof"
```

**What you should see:** a structured proof document (it conforms to
`schemas/finance_approval_packet_proof.schema.json`) containing the closure
certificate id and references to the approval and effect receipts. *This* is
what "every governed action is auditable" means concretely — you can hand this
to an auditor.

---

## Step 6 — See it from the operator's chair

**What we're doing:** viewing the bounded operator summary — what someone
running Mullu would actually watch.

```powershell
Invoke-RestMethod -Method Get `
  -Uri "http://localhost:8000/api/v1/finance/approval-packets/operator/read-model?tenant_id=tenant-demo&limit=50"
```

**What you should see:** summary counts — total packets, blocked count,
approval-wait count, proof-ready count — including the blocked `case-blocked-001`
and the closed `case-ok-001`. One refused, one approved-with-proof. That
contrast *is* the product.

You can also open `$HOME\mullu_finance_packets.json` in a text editor: the
`cases[]`, `decisions[]`, `approvals[]`, and `effects[]` were persisted
deterministically.

---

## Step 7 — Stop

Back in the server window, press `Ctrl + C`. Nothing was sent to a real bank or
mailbox — this pilot prepares and proves; it does not settle payments.

---

## What you just learned

- You watched the [budget](../GLOSSARY.md#budget-spend-budget) gate **mechanically
  refuse** an over-limit payment — not "decline politely", *structurally cannot
  proceed*.
- You saw a valid request stop and **wait for an explicit human approval**
  before anything closed.
- You collected a **proof** an auditor could verify, and viewed the **operator
  read model**.
- The four plain-English office rules from the
  [Overview](../explain/PLAIN_ENGLISH.md) are now things you've *seen run*, not
  claims.

## Where to go next

| You now want to... | Go to |
| --- | --- |
| Understand every rule precisely | [04_policy_and_verification.md](../04_policy_and_verification.md), [01_shared_invariants.md](../01_shared_invariants.md) |
| The full finance pilot spec | [63_finance_approval_packet_pilot.md](../63_finance_approval_packet_pilot.md) |
| More end-to-end worked flows | [Pilot Workflows](../../PILOT_WORKFLOWS_v0.1.md) |
| Run Mullu for real | [Operator Guide](../../OPERATOR_GUIDE_v0.1.md), [Deployment Matrix](../../DEPLOYMENT.md) |
| The whole doc map | [Start Here](../START_HERE.md) |

If a step misbehaved, compare it against the authoritative spec
[63_finance_approval_packet_pilot.md](../63_finance_approval_packet_pilot.md)
and report the difference — this tutorial's promise is that following it works.

← Back to [Tutorial 1](01_first_governed_task.md) · [Start Here](../START_HERE.md)
