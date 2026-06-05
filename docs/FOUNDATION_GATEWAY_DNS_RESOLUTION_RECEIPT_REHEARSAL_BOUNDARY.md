<!--
Purpose: define the Foundation Mode boundary for rehearsing issue #330 gateway DNS resolution receipt questions without running live DNS queries or recording resolution evidence.
Governance scope: issue #330, gateway DNS resolution receipt rehearsal, local question labels, live DNS probe blocking, host-value blocking, resolved-address blocking, resolver-error proof blocking, receipt-writing blocking, endpoint proof blocking, secret exclusion, external publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md, docs/FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md, examples/foundation_gateway_dns_resolution_receipt_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_gateway_dns_resolution_receipt_rehearsal_boundary.py.
Invariants: no live DNS query, no host value, no gateway URL value, no resolved address, no resolver-error proof, no DNS resolution proof, no DNS receipt-writing claim, no endpoint reachability proof, no repository-variable binding, no secret-presence claim, no workflow dispatch, no artifact publication, no operator approval claim, no readiness claim, no customer access, no personal-data collection, no money movement, no legal-clearance claim, no company-formation claim, no patent claim, no external publication, and no deployment claim.
-->

# Foundation Gateway DNS Resolution Receipt Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** gateway DNS resolution receipt rehearsal means naming the
> local questions a future operator must answer before collecting a DNS
> resolution receipt for issue #330. It does not run DNS queries, record host
> values, record gateway URL values, record resolved addresses, write DNS
> receipts, prove endpoints, dispatch workflows, publish artifacts, approve
> readiness, open access, move money, make legal/business claims, publish
> externally, or deploy.

Witness packet: [`../examples/foundation_gateway_dns_resolution_receipt_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_gateway_dns_resolution_receipt_rehearsal_witness.awaiting_evidence.json)

Rule: Gateway DNS resolution receipt rehearsal is a local question map for a
later DNS receipt. It is not live DNS resolution, not a DNS receipt, not DNS
proof, not endpoint proof, and not deployment witness readiness.

No live DNS query, host value, gateway URL value, resolved address,
resolver-error proof, DNS resolution proof, DNS receipt writing, endpoint
reachability proof, repository-variable binding, secret-presence claim,
workflow dispatch, artifact publication, operator approval claim, readiness
claim, customer access, personal-data collection, money movement,
legal-clearance claim, company-formation claim, patent claim, external
publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

After a future DNS target is selected, issue #330 still needs a DNS resolution
receipt. In Foundation Mode, the safe work is not to query DNS. The safe work
is to name the receipt fields and stop rules that will be required later.

Use it when the question is:

1. Which DNS resolution receipt questions must a future operator answer?
2. Which receipt labels are safe to store publicly?
3. Which host, address, resolver, and timestamp values must stay out of Git?
4. Which endpoint preflight checks still wait for a later receipt?
5. Which reassessment gate prevents rehearsal text from becoming DNS proof?

## Current State

```text
gateway_dns_resolution_receipt_rehearsal_state=AwaitingEvidence
live_dns_query_allowed=false
host_value_recorded=false
gateway_url_recorded=false
resolved_address_recorded=false
resolver_error_proof_claimed=false
dns_resolution_claimed=false
dns_receipt_written=false
endpoint_reachability_claimed=false
repository_variable_bound=false
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

These labels are questions only. They are not hostnames, URLs, resolved
addresses, resolver outputs, timestamps, receipt identifiers, workflow run
identifiers, artifact identifiers, provider identifiers, account identifiers,
approval identifiers, or deployment witness evidence.

| Label | Later question | Boundary |
| --- | --- | --- |
| `dns_query_scope_question` | Which future query scope must be observed? | Do not run DNS queries. |
| `resolver_context_question` | Which resolver context must be named later? | Do not record resolver output. |
| `resolved_address_set_question` | Which address-set field must be verified later? | Do not record addresses. |
| `resolver_error_state_question` | Which error-state field must be captured later? | Do not claim error proof. |
| `ttl_observation_question` | Which TTL observation belongs in a future receipt? | Do not record TTL values. |
| `receipt_timestamp_question` | Which timestamp field belongs in a future receipt? | Do not record timestamps. |
| `target_binding_dependency_question` | Which target-binding receipt must precede DNS resolution? | Do not promote target binding. |
| `endpoint_preflight_dependency_question` | Which endpoint preflight waits after DNS resolution? | Do not claim endpoint proof. |
| `publication_stop_rule_question` | Which stop rule blocks publication? | Do not publish artifacts. |
| `operator_reassessment_gate` | Which later gate prevents promotion? | Do not approve reassessment. |

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| DNS query scope question | Record the question label. | Do not run live DNS queries. |
| Resolver context question | Record the question label. | Do not record resolver output. |
| Resolved address set question | Record the question label. | Do not record IP addresses or address counts. |
| Resolver error state question | Record the question label. | Do not claim resolver error proof. |
| TTL observation question | Record the question label. | Do not record TTL values. |
| Receipt timestamp question | Record the question label. | Do not record timestamps. |
| Target binding dependency question | Record the dependency label. | Do not promote target binding. |
| Endpoint preflight dependency question | Record the dependency label. | Do not claim endpoint proof. |
| Publication stop rule question | Record the stop-rule label. | Do not publish receipts or artifacts. |
| Operator reassessment gate | Record the gate label. | Do not approve DNS proof or deployment. |

## Operator Procedure

1. Treat this boundary as a rehearsal map, not a DNS resolution receipt.
2. Keep only public-safe question labels and blocked-gate labels in Git.
3. Do not place real hosts, URLs, DNS targets, resolved addresses, address
   counts, TTL values, timestamps, resolver outputs, resolver error values,
   receipt ids, provider identifiers, account identifiers, repository variable
   values, secret values, workflow run ids, artifact ids, approval ids,
   personal data, payment details, private paths, or customer information in
   this witness.
4. Stop if the next step requires live DNS query, host-value recording,
   gateway URL recording, address recording, resolver proof, receipt writing,
   endpoint proof, secret handling, workflow dispatch, artifact publication,
   operator approval, readiness promotion, customer access, payment,
   legal/business action, publication, or deployment.
5. Keep the rehearsal in `AwaitingEvidence` until an external operator thread,
   target-binding receipt, DNS resolution receipt, endpoint preflight receipt,
   and reassessment gate all exist.

## Validation

Run:

```powershell
python scripts/validate_foundation_gateway_dns_resolution_receipt_rehearsal_boundary.py
```

The validator checks that the gateway DNS resolution receipt rehearsal witness:

1. keeps every rehearsal surface in `AwaitingEvidence`;
2. keeps live DNS queries, host values, gateway URL values, resolved addresses,
   resolver-error proof, DNS proof, receipt writing, endpoint proof,
   repository-variable binding, secret presence, workflow dispatch, artifact
   publication, operator approval, readiness, customer access, money,
   legal/business claims, publication, and deployment blocked;
3. allows only public-safe question labels and blocked-gate notes;
4. rejects live URLs, host-looking values, IP-looking values, timestamps,
   private paths, email-like identifiers, and assignment shapes for hosts, DNS,
   resolvers, addresses, receipts, providers, accounts, repository variables,
   secrets, workflows, artifacts, approvals, customers, money, legal/business
   facts, and deployment facts; and
5. rejects DNS, endpoint, receipt, readiness, approval, publication, and
   deployment promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Rehearse DNS target binding without publication | [Foundation Gateway DNS Target Binding Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md) |
| Prepare external infrastructure questions | [Foundation External Infrastructure Boundary](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md) |
| Name deployment witness inputs | [Foundation Deployment Witness Input Boundary](FOUNDATION_DEPLOYMENT_WITNESS_INPUT_BOUNDARY.md) |
| Rehearse deployment witness preflight labels | [Foundation Deployment Witness Preflight Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md) |
| Name evidence handoff slots | [Foundation Deployment Witness Evidence Handoff Boundary](FOUNDATION_DEPLOYMENT_WITNESS_EVIDENCE_HANDOFF_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: live DNS query blocked, host value blocked, gateway URL value blocked, resolved address blocked, resolver-error proof not claimed, DNS resolution not claimed, DNS receipt writing blocked, endpoint proof not claimed, repository-variable binding blocked, secret presence not claimed, workflow dispatch blocked, artifact publication blocked, operator approval not claimed, readiness not claimed, customer access blocked, money movement blocked, legal/company/patent claims blocked, external publication blocked, deployment blocked
  Open issues: all gateway DNS resolution receipt rehearsal surfaces remain AwaitingEvidence
  Next action: validate this rehearsal boundary before any future DNS resolution receipt collection or endpoint preflight work
