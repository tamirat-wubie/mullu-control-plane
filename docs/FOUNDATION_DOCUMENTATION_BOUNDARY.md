<!--
Purpose: define the Foundation Mode documentation boundary before any documentation-complete, canonical-docs, public-launch, customer-readiness, deployment-readiness, legal-clearance, or external-publication claim.
Governance scope: source-of-truth map, plain-language status, glossary questions, prerequisite cross-links, public-copy alignment, evidence index, update cadence, reviewer handoff, private-value exclusion, and claim blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/START_HERE.md, docs/CURRENT_READINESS_SNAPSHOT.md, examples/foundation_documentation_witness.awaiting_evidence.json, scripts/validate_foundation_documentation_boundary.py.
Invariants: no documentation completeness claim, no canonical-docs claim, no public-launch copy claim, no customer-readiness copy claim, no deployment-readiness claim, no legal-clearance claim, no commercial-readiness claim, no private fact recording, no external publication, and no deployment claim.
-->

# Foundation Documentation Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** documentation preparation means keeping the project readable,
> navigable, and honest for a solo operator. It does not mean the docs are
> complete, canonical, legally reviewed, customer-ready, deployment-ready,
> externally published, or suitable for public launch.

Witness packet: [`../examples/foundation_documentation_witness.awaiting_evidence.json`](../examples/foundation_documentation_witness.awaiting_evidence.json)

Rule: Documentation preparation is a local planning boundary, not a readiness certificate.

No documentation completeness claim, canonical-docs claim, public-launch copy
claim, customer-readiness copy claim, deployment-readiness claim,
legal-clearance claim, commercial-readiness claim, private fact recording,
external publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

Foundation Mode now has many small boundary files. That is useful only if a
non-technical reader can still find the right page, understand the current
state, and avoid mistaking draft documentation for readiness evidence.

This boundary keeps documentation useful without overclaiming:

1. Source-of-truth pages can be mapped locally.
2. Plain-language status can be improved without claiming launch readiness.
3. Glossary gaps can be listed without claiming full documentation coverage.
4. Cross-links can be tightened without publishing external materials.
5. Evidence indexes can point to public-safe witnesses only.
6. Reviewer handoff notes can stay local and reversible.

## Current State

```text
documentation_boundary_state=AwaitingEvidence
documentation_complete_claimed=false
canonical_docs_claimed=false
public_launch_copy_claimed=false
customer_ready_copy_claimed=false
deployment_readiness_claimed=false
legal_clearance_claimed=false
commercial_readiness_claimed=false
private_fact_recording_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Documentation Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Source-of-truth map | List which local page answers which question. | Do not claim the documentation set is complete. |
| Plain-language status | Keep status readable for a non-technical operator. | Do not claim customer, launch, or deployment readiness. |
| Glossary questions | List terms that need clearer explanation. | Do not claim full conceptual coverage. |
| Prerequisite cross-links | Keep boundary pages reachable from Start Here and the ledger. | Do not publish external-facing launch copy. |
| Public-copy alignment | Keep public claims Foundation Mode compatible. | Do not invite access, waitlists, customers, or paid use. |
| Evidence index | Link public-safe witnesses and validators. | Do not record private paths, secrets, account IDs, or provider internals. |
| Update cadence | Draft when docs should be revisited. | Do not promise maintenance SLAs or support response times. |
| Reviewer handoff | Draft what a future reviewer should inspect. | Do not imply legal, security, or business approval. |

## Operator Procedure

1. Treat documentation as navigation and preparation, not proof of readiness.
2. Keep private facts, account identifiers, private paths, secrets, and provider
   internals out of public docs and witness packets.
3. Keep every documentation surface in `AwaitingEvidence` until a later signed
   witness promotes it.
4. When improving docs, separate constructive deltas from fracture deltas in the
   source-control packet or handoff note.
5. Do not use documentation polish to justify public launch, customer access,
   deployment, paid infrastructure, legal clearance, or commercial readiness.

## Validation

Run:

```powershell
python scripts/validate_foundation_documentation_boundary.py
```

The validator checks that the documentation witness:

1. keeps every documentation surface in `AwaitingEvidence`;
2. keeps documentation completeness, canonical-docs, public launch, customer
   readiness, deployment readiness, legal clearance, commercial readiness,
   private fact recording, external publication, and deployment blocked;
3. rejects URL, email, private path, account, secret, provider, launch,
   customer, deployment, legal, commercial, or readiness-shaped values; and
4. rejects documentation-readiness promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Start from the front door | [Start Here](START_HERE.md) |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| See current claim truth | [Current Readiness Snapshot](CURRENT_READINESS_SNAPSHOT.md) |
| Prepare source-control safely | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: documentation completeness not claimed, canonical docs not claimed, public launch copy not claimed, customer-ready copy not claimed, deployment readiness not claimed, legal clearance not claimed, commercial readiness not claimed, private fact recording blocked, external publication blocked, deployment blocked
  Open issues: source-of-truth map evidence, plain-language status evidence, glossary evidence, cross-link evidence, public-copy alignment evidence, evidence-index evidence, update-cadence evidence, and reviewer-handoff evidence remain AwaitingEvidence
  Next action: run the documentation boundary validator before any future documentation-readiness claim
