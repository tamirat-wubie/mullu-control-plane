<!--
Purpose: define the Foundation Mode website-posture boundary before any website mutation, external publication, access invitation, waitlist opening, beta invitation, pilot signup, customer intake, production-runtime claim, endpoint-readiness claim, paid-launch claim, or deployment claim.
Governance scope: static website copy, product-route copy, proof-route copy, access-language scan, waitlist/beta language scan, runtime/endpoint language scan, public-naming alignment, website evidence receipts, private-value exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_CLAIM_BOUNDARY.md, docs/PUBLIC_NAMING_READINESS.md, examples/foundation_website_posture_witness.awaiting_evidence.json, scripts/validate_foundation_website_posture_boundary.py.
Invariants: no website mutation, no external website publication, no access invitation, no waitlist opening, no beta invitation, no pilot signup, no customer intake, no production-runtime claim, no endpoint-readiness claim, no paid-launch claim, and no deployment claim.
-->

# Foundation Website Posture Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** website-posture preparation means checking that website copy
> stays inside Foundation Mode. It does not mutate the website, publish a new
> route, invite access, open a waitlist, open beta, accept pilot signups,
> collect customers, claim production runtime, claim endpoint readiness, launch
> paid use, or deploy anything.

Witness packet: [`../examples/foundation_website_posture_witness.awaiting_evidence.json`](../examples/foundation_website_posture_witness.awaiting_evidence.json)

Rule: Website-posture preparation is a local planning boundary, not a website publication or access-opening certificate.

No website mutation, external website publication, access invitation, waitlist
opening, beta invitation, pilot signup, customer intake, production-runtime
claim, endpoint-readiness claim, paid-launch claim, or deployment claim is
permitted by this boundary.

## What This Boundary Solves

Foundation Mode can keep a public site and local site files while still not
opening access. The risk is language drift: a helpful homepage edit can sound
like a launch, beta, waitlist, customer intake, production-runtime, or endpoint
readiness claim.

This boundary keeps website work narrow:

1. Static homepage copy can be reviewed locally.
2. Product-route copy can stay aligned with Foundation Mode.
3. Proof-route copy can describe evidence without implying customer access.
4. Access, waitlist, beta, and pilot language can be blocked before publication.
5. Runtime and endpoint claims can remain separated from website copy.
6. Website evidence receipts can be public-safe and non-promotional.

## Current State

```text
website_posture_boundary_state=AwaitingEvidence
website_mutation_allowed=false
external_publication_allowed=false
access_invitation_allowed=false
waitlist_open=false
beta_invitation_allowed=false
pilot_signup_allowed=false
customer_intake_allowed=false
production_runtime_claimed=false
endpoint_readiness_claimed=false
paid_launch_allowed=false
deployment_allowed=false
```

## Website Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Static homepage copy | Draft local review questions. | Do not mutate or publish website files. |
| Product-route copy | Check Foundation Mode wording. | Do not invite access, beta, waitlist, pilot, customers, or paid use. |
| Proof-route copy | Check local evidence wording. | Do not imply production runtime or endpoint readiness. |
| Access-language scan | List phrases that need blocking. | Do not create access flows or contact targets. |
| Waitlist/beta language scan | List phrases that need blocking. | Do not open waitlists, beta, or pilot signup. |
| Runtime/endpoint language scan | List readiness phrases that need blocking. | Do not claim public health, API readiness, or deployment. |
| Public-naming alignment | Keep product naming and launch posture separated. | Do not claim legal, trademark, domain, or paid-launch clearance. |
| Website evidence receipts | Draft public-safe evidence categories. | Do not store live URLs, private paths, account IDs, or provider internals. |

## Operator Procedure

1. Treat website work as local copy review unless a later explicit request
   names a publication action.
2. Do not publish or mutate website files through this boundary.
3. Do not add access, waitlist, beta, pilot-signup, customer-intake, paid-use,
   runtime-readiness, endpoint-readiness, or deployment wording.
4. Keep private paths, route targets, provider details, account identifiers,
   live URLs, mailto targets, and secrets out of the witness packet.
5. Keep every website surface in `AwaitingEvidence` until a later signed witness
   promotes it.

## Validation

Run:

```powershell
python scripts/validate_foundation_website_posture_boundary.py
```

The validator checks that the website-posture witness:

1. keeps every website surface in `AwaitingEvidence`;
2. keeps website mutation, external publication, access invitation, waitlist,
   beta invitation, pilot signup, customer intake, production-runtime,
   endpoint-readiness, paid-launch, and deployment blocked;
3. rejects URL, email, mailto, private path, route target, provider, account,
   access target, waitlist target, deployment target, or secret-shaped values;
   and
4. rejects website-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Separate public claims safely | [Foundation Claim Boundary](FOUNDATION_CLAIM_BOUNDARY.md) |
| Check public naming posture | [Public Naming Readiness](PUBLIC_NAMING_READINESS.md) |
| Check deployment truth | [Deployment Status](../DEPLOYMENT_STATUS.md) |

STATUS:
  Completeness: 100%
  Invariants verified: website mutation blocked, external publication blocked, access invitation blocked, waitlist opening blocked, beta invitation blocked, pilot signup blocked, customer intake blocked, production-runtime claim blocked, endpoint-readiness claim blocked, paid-launch claim blocked, deployment blocked
  Open issues: static homepage copy evidence, product-route copy evidence, proof-route copy evidence, access-language scan evidence, waitlist/beta language scan evidence, runtime/endpoint language scan evidence, public-naming alignment evidence, and website evidence receipt evidence remain AwaitingEvidence
  Next action: run the website-posture boundary validator before any future website-publication or access-language request
