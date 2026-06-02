<!--
Purpose: define the Foundation Mode product-scope learning lane without opening pilot, customer, market, launch, or deployment claims.
Governance scope: product scope, narrow learning lane, platform non-restriction, pilot blocking, customer blocking, market-claim blocking, and deployment-restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_product_scope_witness.awaiting_evidence.json, scripts/validate_foundation_product_scope_boundary.py.
Invariants: one selected local learning lane does not restrict the long-term platform; no pilot access, customer access, market validation, paid launch, deployment readiness, or legal readiness claim.
-->

# Foundation Product Scope Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** product-scope preparation means choosing one tiny local
> learning lane so the project can make progress without pretending the whole
> product is ready. The selected lane is a proof lane, not a permanent
> restriction on Mullu Govern.

Witness packet: [`../examples/foundation_product_scope_witness.awaiting_evidence.json`](../examples/foundation_product_scope_witness.awaiting_evidence.json)

Rule: One narrow learning lane is a local proof lane, not a permanent platform restriction.

No pilot access, customer access, market-validation, paid-launch, deployment-readiness, legal-readiness, or company-readiness claim is permitted by this boundary.

## What This Boundary Solves

A broad platform can become too large to prove all at once. Foundation Mode
needs one small lane that can be tested locally while the larger platform stays
open for future evolution.

This boundary separates three ideas:

1. Long-term product direction remains broad.
2. Current learning must be narrow and local.
3. Pilot, customer, market, legal, and deployment claims remain blocked.

## Current State

```text
product_scope_boundary_state=AwaitingEvidence
scope_mode=foundation_learning_lane
selected_learning_lane=local_governed_task_receipt
long_term_platform_restricted=false
pilot_access_allowed=false
customer_access_allowed=false
market_validation_claimed=false
paid_launch_allowed=false
deployment_dependency_allowed=false
```

## Selected Learning Lane

The selected lane is:

```text
local request
  -> classify intent
  -> check policy and authority
  -> require local approval if needed
  -> perform one harmless local action
  -> write a receipt
  -> verify result
  -> name rollback or recovery path
```

This lane tests the control shape: intent, policy, approval, receipt,
verification, and rollback. It does not test customer demand, public hosting,
market value, legal clearance, payment readiness, or company readiness.

## Why Narrow Does Not Mean Restrictive

The selected learning lane is a microscope, not a cage:

| Meaning | Boundary |
| --- | --- |
| Narrow for execution | Only one local path is tested at a time. |
| Broad for architecture | The product can still support many future governed task families. |
| Local for proof | No external user, endpoint, payment, or deployment is required. |
| Reversible for safety | If the lane is weak, change the lane before opening exposure. |

## Operator Procedure

1. Keep the selected lane local and harmless.
2. Use the witness packet to preserve the non-restriction rule.
3. Do not treat the selected lane as a customer pilot.
4. Do not treat a passing local lane as market validation.
5. Promote a future pilot only after support, terms, recovery, deployment,
   legal, and operator-readiness evidence exist.

## Validation

Run:

```powershell
python scripts/validate_foundation_product_scope_boundary.py
```

The validator checks that the witness packet:

1. keeps the selected lane in `AwaitingEvidence`;
2. keeps long-term platform restriction disabled;
3. blocks pilot access, customer access, market validation, paid launch, and
   deployment dependency claims; and
4. rejects product-scope readiness-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare source-control safely | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |
| Run the first local proof lane | [Foundation Local Proof Thread](FOUNDATION_LOCAL_PROOF_THREAD.md) |

STATUS:
  Completeness: 100%
  Invariants verified: selected local learning lane, long-term platform not restricted, pilot access blocked, customer access blocked, market validation not claimed, deployment dependency blocked
  Open issues: future pilot readiness, customer evidence, market evidence, support plan, and deployment witness remain AwaitingEvidence
  Next action: run the product-scope boundary validator, then keep the selected lane local until external prerequisites close
