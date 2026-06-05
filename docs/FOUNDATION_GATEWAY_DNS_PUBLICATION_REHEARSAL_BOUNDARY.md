<!--
Purpose: define the Foundation Mode boundary for rehearsing issue #330 gateway DNS publication steps without mutating DNS or recording live DNS values.
Governance scope: issue #330, gateway DNS publication rehearsal, local gate labels, DNS mutation blocking, provider/account exclusion, record-value exclusion, repository-variable binding blocking, workflow dispatch blocking, proof blocking, external publication blocking, and deployment restraint.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md, docs/FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md, examples/foundation_gateway_dns_publication_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_gateway_dns_publication_rehearsal_boundary.py.
Invariants: no DNS provider account value, no DNS zone value, no DNS record name value, no DNS record type value, no DNS record value, no TTL value, no DNS mutation, no repository-variable binding, no workflow dispatch, no propagation proof, no rollback proof, no DNS resolution proof, no endpoint reachability proof, no artifact publication, no operator approval claim, no readiness claim, no customer access, no personal-data collection, no money movement, no legal-clearance claim, no company-formation claim, no patent claim, no external publication, and no deployment claim.
-->

# Foundation Gateway DNS Publication Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** gateway DNS publication rehearsal means naming the local
> stop-rule labels a future operator must satisfy before publishing issue #330
> gateway DNS records. It does not choose a provider, record DNS values, mutate
> DNS, bind repository variables, dispatch workflows, prove propagation, publish
> artifacts, approve readiness, open access, move money, make legal/business
> claims, publish externally, or deploy.

Witness packet: [`../examples/foundation_gateway_dns_publication_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_gateway_dns_publication_rehearsal_witness.awaiting_evidence.json)

Rule: Gateway DNS publication rehearsal is a local stop-rule map for a later
external operator step. It is not DNS publication, not provider authorization,
not a DNS change receipt, not DNS propagation proof, not DNS resolution proof,
and not deployment witness readiness.

No DNS provider account value, DNS zone value, DNS record name value, DNS
record type value, DNS record value, TTL value, DNS mutation,
repository-variable binding, workflow dispatch, propagation proof, rollback
proof, DNS resolution proof, endpoint reachability proof, artifact publication,
operator approval claim, readiness claim, customer access, personal-data
collection, money movement, legal-clearance claim, company-formation claim,
patent claim, external publication, or deployment claim is permitted by this
boundary.

## What This Boundary Solves

Issue #330 requires DNS publication only after upstream readiness and DNS target
binding are proven by later evidence. In Foundation Mode, the safe work is not
to publish DNS. The safe work is to name the gates that must block publication
until the future operator has real authority and evidence.

Use it when the question is:

1. Which require-ready gate must be true before DNS publication?
2. Which provider, zone, record, and TTL fields must stay out of Git?
3. Which dry-run command label can be prepared without mutation?
4. Which rollback and post-publication checks must remain future evidence?
5. Which reassessment gate prevents rehearsal text from becoming approval?

## Current State

```text
gateway_dns_publication_rehearsal_state=AwaitingEvidence
dns_provider_account_recorded=false
dns_zone_value_recorded=false
dns_record_name_recorded=false
dns_record_type_value_recorded=false
dns_record_value_recorded=false
ttl_value_recorded=false
dns_mutation_allowed=false
repository_variable_bound=false
workflow_dispatch_allowed=false
dns_propagation_claimed=false
dns_rollback_claimed=false
dns_resolution_claimed=false
endpoint_reachability_claimed=false
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

## Public-Safe Gate Labels

These labels are questions only. They are not provider account identifiers, DNS
zone identifiers, record names, record types, record values, TTL values, command
outputs, workflow run identifiers, artifact identifiers, approval identifiers,
rollback receipts, propagation evidence, or deployment witness evidence.

| Label | Later question | Boundary |
| --- | --- | --- |
| `target_binding_receipt_dependency_label` | Which target-binding receipt must exist first? | Do not promote target binding. |
| `dns_provider_boundary_label` | Which provider boundary will later be used? | Do not record provider account data. |
| `dns_zone_boundary_label` | Which DNS zone boundary will later be used? | Do not record zone values. |
| `record_name_publication_label` | Which record-name field will later be written? | Do not record record names. |
| `record_type_publication_label` | Which record-type field will later be written? | Do not record record types. |
| `record_value_publication_label` | Which record-value field will later be written? | Do not record record values. |
| `ttl_publication_label` | Which TTL field will later be used? | Do not record TTL values. |
| `pre_publication_require_ready_gate_label` | Which require-ready gate blocks publication? | Do not approve publication. |
| `dry_run_publication_command_label` | Which dry-run command family can be named? | Do not mutate DNS. |
| `post_publication_resolution_gate_label` | Which later DNS resolution receipt is required? | Do not claim DNS proof. |
| `dns_rollback_label` | Which rollback field must exist later? | Do not claim rollback proof. |
| `operator_reassessment_gate` | Which later gate prevents promotion? | Do not approve reassessment. |

## Rehearsal Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Target-binding dependency label | Record the dependency label. | Do not promote target binding. |
| Provider boundary label | Record the boundary label. | Do not record provider account values. |
| Zone boundary label | Record the boundary label. | Do not record DNS zone values. |
| Record-name publication label | Record the field label. | Do not record record names. |
| Record-type publication label | Record the field label. | Do not record record types. |
| Record-value publication label | Record the field label. | Do not record record values. |
| TTL publication label | Record the field label. | Do not record TTL values. |
| Require-ready gate label | Record the blocking gate label. | Do not approve publication. |
| Dry-run publication command label | Record the command-family label. | Do not mutate DNS. |
| Post-publication resolution gate label | Record the later receipt label. | Do not claim DNS proof. |
| DNS rollback label | Record the rollback field label. | Do not claim rollback proof. |
| Operator reassessment gate | Record the gate label. | Do not approve DNS publication or deployment. |

## Allowed Names

These names are allowed as names only, not values:

```text
MULLU_GATEWAY_DNS_TARGET
MULLU_GATEWAY_URL
MULLU_EXPECTED_RUNTIME_ENV
```

Do not write values for these names in this document, witness packet, tests, or
future Foundation Mode artifacts.

## Operator Procedure

1. Treat this boundary as a rehearsal map, not DNS publication.
2. Keep only public-safe gate labels and variable names in Git.
3. Do not place real hosts, URLs, DNS zones, DNS record names, DNS record
   types, DNS record values, TTL values, provider identifiers, account
   identifiers, repository variable values, secret values, workflow run ids,
   artifact ids, approval ids, rollback receipt ids, personal data, payment
   details, private paths, or customer information in this witness.
4. Stop if the next step requires provider login, DNS mutation,
   repository-variable binding, workflow dispatch, propagation proof, rollback
   proof, DNS resolution proof, endpoint proof, secret handling, artifact
   publication, operator approval, readiness promotion, customer access,
   payment, legal/business action, publication, or deployment.
5. Keep the rehearsal in `AwaitingEvidence` until an external operator thread,
   upstream readiness receipt, target-binding receipt, publication receipt, DNS
   resolution receipt, endpoint preflight receipt, rollback evidence, and
   reassessment gate all exist.

## Validation

Run:

```powershell
python scripts/validate_foundation_gateway_dns_publication_rehearsal_boundary.py
```

The validator checks that the gateway DNS publication rehearsal witness:

1. keeps every rehearsal surface in `AwaitingEvidence`;
2. keeps provider accounts, DNS zones, record names, record types, record
   values, TTL values, DNS mutation, repository-variable binding, workflow
   dispatch, propagation proof, rollback proof, DNS proof, endpoint proof,
   artifact publication, operator approval, readiness, customer access, money,
   legal/business claims, publication, and deployment blocked;
3. allows only public-safe gate labels and allowed variable names;
4. rejects live URLs, host-looking values, IP-looking values, private paths,
   email-like identifiers, secret/key material, timestamps, numeric TTL
   assignments, and assignment shapes for provider, zone, record, TTL, DNS,
   target, URL, repository variable, workflow, artifact, approval, customer,
   money, legal/business, and deployment facts; and
5. rejects DNS publication, propagation, rollback, resolution, endpoint,
   readiness, approval, publication, and deployment promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Rehearse DNS target binding without publication | [Foundation Gateway DNS Target Binding Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_TARGET_BINDING_REHEARSAL_BOUNDARY.md) |
| Rehearse DNS resolution receipts without live queries | [Foundation Gateway DNS Resolution Receipt Rehearsal Boundary](FOUNDATION_GATEWAY_DNS_RESOLUTION_RECEIPT_REHEARSAL_BOUNDARY.md) |
| Prepare external infrastructure questions | [Foundation External Infrastructure Boundary](FOUNDATION_EXTERNAL_INFRASTRUCTURE_BOUNDARY.md) |
| Rehearse deployment witness preflight labels | [Foundation Deployment Witness Preflight Rehearsal Boundary](FOUNDATION_DEPLOYMENT_WITNESS_PREFLIGHT_REHEARSAL_BOUNDARY.md) |
| Reassess without promotion | [Foundation Reassessment Gate Boundary](FOUNDATION_REASSESSMENT_GATE_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: provider account value blocked, DNS zone value blocked, record name value blocked, record type value blocked, record value blocked, TTL value blocked, DNS mutation blocked, repository-variable binding blocked, workflow dispatch blocked, propagation proof not claimed, rollback proof not claimed, DNS proof not claimed, endpoint proof not claimed, artifact publication blocked, operator approval not claimed, readiness not claimed, customer access blocked, money movement blocked, legal/company/patent claims blocked, external publication blocked, deployment blocked
  Open issues: all gateway DNS publication rehearsal surfaces remain AwaitingEvidence
  Next action: validate this rehearsal boundary before any future DNS publication or DNS resolution receipt work
