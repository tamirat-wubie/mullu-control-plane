<!--
Purpose: define the Foundation Mode boundary for rehearsing issue #330 gateway DNS target binding decisions without recording live targets or publishing DNS.
Governance scope: issue #330, gateway DNS target binding rehearsal, local question labels, repository-variable binding blocking, DNS publication blocking, DNS resolution proof blocking, endpoint proof blocking, provider/account blocking, secret exclusion, external publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md, docs/FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md, examples/foundation_gateway_dns_target_binding_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_gateway_dns_target_binding_rehearsal_boundary.py.
Invariants: no live DNS target value, no gateway URL value, no provider account value, no repository-variable binding, no DNS record publication, no DNS resolution proof, no endpoint reachability proof, no secret-presence claim, no workflow dispatch, no artifact publication, no operator approval claim, no readiness claim, no customer access, no personal-data collection, no money movement, no legal-clearance claim, no company-formation claim, no patent claim, no external publication, and no deployment claim.
-->

# Foundation Gateway DNS Target Binding Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** gateway DNS target binding rehearsal means naming the local
> questions a future operator must answer before binding issue #330 gateway DNS
> values. It does not record a real DNS target, real gateway URL, provider
> account, repository variable value, DNS publication, DNS proof, endpoint
> proof, workflow dispatch, artifact publication, customer access, money,
> legal/business action, external publication, or deployment.

Witness packet: [`../examples/foundation_gateway_dns_target_binding_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_gateway_dns_target_binding_rehearsal_witness.awaiting_evidence.json)

Rule: Gateway DNS target binding rehearsal is a local question map for a later
external operator step. It is not DNS target selection, not repository-variable
binding, not DNS publication, not DNS resolution evidence, and not deployment
witness readiness.

No live DNS target value, gateway URL value, provider account value,
repository-variable binding, DNS record publication, DNS resolution proof,
endpoint reachability proof, secret-presence claim, workflow dispatch, artifact
publication, operator approval claim, readiness claim, customer access,
personal-data collection, money movement, legal-clearance claim,
company-formation claim, patent claim, external publication, or deployment
claim is permitted by this boundary.

## What This Boundary Solves

Issue #330 remains `AwaitingEvidence` until a real gateway DNS target and
runtime endpoints exist. In Foundation Mode, the safe work is not to choose or
publish that target. The safe work is to name the questions that must be
answered later.

Use it when the question is:

1. Which DNS target binding questions must a future operator answer?
2. Which repository-variable names are involved without storing values now?
3. Which DNS, endpoint, and witness checks stay blocked until later?
4. Which provider/account details must stay out of Git?
5. Which later reassessment gate prevents rehearsal text from becoming a
   readiness or deployment claim?

## Current State

```text
gateway_dns_target_binding_rehearsal_state=AwaitingEvidence
candidate_target_value_recorded=false
gateway_url_recorded=false
provider_account_recorded=false
repository_variable_bound=false
dns_record_published=false
dns_resolution_claimed=false
endpoint_reachability_claimed=false
secret_presence_claimed=false
workflow_dispatch_allowed=false
artifact_publication_allowed=false
operator_approval_claimed=false
readiness_claimed=false
customer_access_allowed=false
personal_data_collection_allowed=false
money_movement_allowed=false
legal_clearance_claimed=false
company_formation_claimed=false
patent_claimed=false
external_publication_allowed=false
deployment_allowed=false
```

## Public-Safe Question Labels

These labels are questions only. They are not hostnames, URLs, DNS targets,
record values, provider names, provider account identifiers, repository variable
values, workflow run identifiers, artifact identifiers, approval identifiers,
or deployment witness evidence.

| Label | Later question | Boundary |
| --- | --- | --- |
| `dns_target_candidate_label` | Which gateway DNS target should later be evaluated? | Do not record a target value. |
| `record_type_candidate_label` | Which DNS record type should later be evaluated? | Do not publish a record. |
| `dns_provider_boundary_label` | Which provider boundary will later be used? | Do not record provider account data. |
| `repository_variable_binding_question` | Which repository variables would later be bound? | Do not bind variables. |
| `gateway_url_binding_question` | Which gateway URL would later be derived? | Do not record a URL value. |
| `expected_environment_binding_question` | Which environment label would later be used? | Do not claim environment readiness. |
| `dns_resolution_receipt_question` | Which DNS receipt would later prove resolution? | Do not claim DNS proof. |
| `endpoint_preflight_receipt_question` | Which endpoint preflight receipt would later be required? | Do not claim endpoint proof. |
| `runtime_secret_handoff_question` | Which runtime secret handoff questions remain? | Do not claim secret presence. |
| `operator_reassessment_gate` | Which later gate prevents promotion? | Do not approve reassessment. |

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| DNS target candidate question | Record the question label. | Do not record a real target value. |
| Record type candidate question | Record the question label. | Do not publish or validate a live record. |
| Provider boundary question | Record the question label. | Do not record provider account values. |
| Repository variable binding question | Record the variable-name family. | Do not bind repository variables. |
| Gateway URL binding question | Record that a URL will be derived later. | Do not record a live URL. |
| Expected environment binding question | Record the environment question. | Do not claim environment readiness. |
| DNS resolution receipt question | Record the receipt question. | Do not claim DNS proof. |
| Endpoint preflight receipt question | Record the receipt question. | Do not claim endpoint proof. |
| Runtime secret handoff question | Record the handoff question. | Do not claim secret presence or print values. |
| Operator reassessment gate | Record the gate label. | Do not approve DNS publication or deployment. |

## Repository Variable Names

These names are allowed as names only, not values:

```text
MULLU_GATEWAY_DNS_TARGET
MULLU_GATEWAY_URL
MULLU_EXPECTED_RUNTIME_ENV
```

Do not write values for these names in this document, witness packet, tests, or
future Foundation Mode artifacts.

## Operator Procedure

1. Treat this boundary as a rehearsal map, not a DNS target binding.
2. Keep only public-safe question labels and variable names in Git.
3. Do not place real hosts, URLs, DNS targets, DNS record values, provider
   identifiers, account identifiers, repository variable values, secret values,
   workflow run ids, artifact ids, approval ids, personal data, payment details,
   private paths, or customer information in this witness.
4. Stop if the next step requires repository-variable binding, DNS publication,
   DNS resolution proof, endpoint proof, secret handling, workflow dispatch,
   artifact publication, operator approval, readiness promotion, customer
   access, payment, legal/business action, publication, or deployment.
5. Keep the rehearsal in `AwaitingEvidence` until an external operator thread,
   DNS authority evidence, target-binding receipt, DNS resolution receipt,
   endpoint preflight receipt, and reassessment gate all exist.

## Validation

Run:

```powershell
python scripts/validate_foundation_gateway_dns_target_binding_rehearsal_boundary.py
```

The validator checks that the gateway DNS target binding rehearsal witness:

1. keeps every rehearsal surface in `AwaitingEvidence`;
2. keeps live target values, gateway URLs, provider accounts, repository
   variable binding, DNS publication, DNS proof, endpoint proof, secret
   presence, workflow dispatch, artifact publication, operator approval,
   readiness, customer access, money, legal/business claims, publication, and
   deployment blocked;
3. allows only public-safe question labels and repository variable names;
4. rejects live URLs, host-looking values, private paths, email-like
   identifiers, assignment shapes for targets, URLs, DNS, providers, accounts,
   repository variables, secrets, workflows, artifacts, approvals, customers,
   money, legal/business facts, and deployment facts; and
5. rejects DNS, endpoint, readiness, approval, publication, and deployment
   promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Prepare external infrastructure questions | [Foundation External Infrastructure Boundary](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md) |
| Name deployment witness inputs | [Foundation Deployment Witness Input Boundary](FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md) |
| Rehearse deployment witness preflight labels | [Foundation Deployment Witness Preflight Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md) |
| Name evidence handoff slots | [Foundation Deployment Witness Evidence Handoff Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md) |
| Route evidence slots without ledger append | [Foundation Deployment Witness Evidence Ledger Routing Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_LEDGER_ROUTING_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: live DNS target value blocked, gateway URL value blocked, provider account value blocked, repository-variable binding blocked, DNS publication blocked, DNS proof not claimed, endpoint proof not claimed, secret presence not claimed, workflow dispatch blocked, artifact publication blocked, operator approval not claimed, readiness not claimed, customer access blocked, money movement blocked, legal/company/patent claims blocked, external publication blocked, deployment blocked
  Open issues: all gateway DNS target binding rehearsal surfaces remain AwaitingEvidence
  Next action: validate this rehearsal boundary before any future DNS target binding or publication work
