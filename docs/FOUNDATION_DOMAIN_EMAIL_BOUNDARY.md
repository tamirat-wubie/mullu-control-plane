<!--
Purpose: define the public-safe domain and email witness boundary for Foundation Mode.
Governance scope: public identity labels, DNS/email posture, provider-private exclusion, no DNS mutation, no endpoint readiness, no email deliverability claim, and no deployment claim.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_domain_email_witness.awaiting_evidence.json, scripts/validate_foundation_domain_email_boundary.py.
Invariants: no provider account IDs, no private DNS target values, no admin-console details, no secret values, no DNS mutation claim, no endpoint readiness claim, no email deliverability claim, no deployment claim.
-->

# Foundation Domain Email Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** domain and email preparation means recording public-safe
> labels for the project identity. It does not mutate DNS, publish API DNS,
> expose provider account IDs, expose private DNS targets, prove endpoint
> readiness, prove email deliverability, or deploy anything.

Witness packet: [`../examples/foundation_domain_email_witness.awaiting_evidence.json`](../examples/foundation_domain_email_witness.awaiting_evidence.json)

Rule: Public identity labels may be recorded, but DNS/email readiness remains
`AwaitingEvidence` until manual verification or a later signed witness promotes
a specific item.

No provider account IDs, private DNS target values, admin-console details,
secret values, DNS mutation claim, endpoint readiness claim, email deliverability
claim, or deployment claim is permitted in this repository.

## What This Boundary Solves

The project already has public names and public contact labels. The risky part
is not naming them; the risky part is mixing public labels with private provider
material or claiming live readiness without a witness.

This boundary keeps the work small:

1. Public labels can be listed as planned or known identity surfaces.
2. Private provider data stays outside Git.
3. DNS mutation, API DNS publication, and endpoint readiness remain blocked.
4. Email deliverability and mailbox administration remain `AwaitingEvidence`.

## Public-Safe Surfaces

| Surface | Public-safe record here | Do not store here |
| --- | --- | --- |
| Website names | Public host labels only. | DNS targets, provider IDs, account screenshots. |
| API/admin/docs names | Public host labels only. | Gateway targets, origin hosts, TLS private material. |
| Sandbox/metrics names | Public host labels only. | Private infrastructure targets. |
| Email domain | Public domain label only. | Admin console IDs, recovery paths, private routing values. |
| Public mailbox labels | Public mailbox labels only. | Passwords, recovery codes, delegate details, inbox content. |
| DNS/email security | Question checklist only. | DKIM private keys, hidden routing, provider account material. |

## Current State

```text
domain_email_boundary_state=AwaitingEvidence
dns_mutation_allowed=false
api_dns_publication_allowed=false
endpoint_readiness_claimed=false
email_deliverability_claimed=false
provider_account_ids_stored_in_git=false
private_dns_targets_stored_in_git=false
```

## Operator Procedure

1. Use the witness packet as a public-safe checklist.
2. Keep provider account IDs, private DNS targets, admin-console details, and
   secrets outside Git.
3. Record only public labels and `AwaitingEvidence` states in this repository.
4. Promote a single domain or email item only after manual verification or a
   signed witness exists.
5. Do not treat this packet as deployment, endpoint health, DNS publication, or
   email deliverability evidence.

## Validation

Run:

```powershell
python scripts/validate_foundation_domain_email_boundary.py
```

The validator checks that the witness packet:

1. keeps every public surface in `AwaitingEvidence`;
2. keeps DNS mutation, API DNS publication, endpoint readiness, and email
   deliverability blocked;
3. rejects provider-private fields and target-shaped values; and
4. preserves the expected public-label inventory.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare source-control safely | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |
| Prepare private recovery safely | [Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: public labels only, DNS mutation blocked, API DNS publication blocked, endpoint readiness not claimed, email deliverability not claimed, private provider data excluded
  Open issues: manual DNS/email verification remains AwaitingEvidence
  Next action: run the domain/email boundary validator, then promote no item without manual verification or signed witness evidence
