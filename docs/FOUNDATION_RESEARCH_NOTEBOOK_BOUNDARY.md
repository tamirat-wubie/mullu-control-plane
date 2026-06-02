<!--
Purpose: define the Foundation Mode research-notebook boundary before any patent-protection, trade-secret-protection, scientific-validation, physical-world-validation, market-validation, customer, publication, paid-launch, secret-evidence, or deployment claim.
Governance scope: concept notes, assumption register, prior-art questions, proof-status map, experiment boundary, evidence-promotion questions, authorship-lineage notes, public-claim language, private-value exclusion, and deployment blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_CLAIM_BOUNDARY.md, docs/FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md, examples/foundation_research_notebook_witness.awaiting_evidence.json, scripts/validate_foundation_research_notebook_boundary.py.
Invariants: no patent-protection claim, no trade-secret-protection claim, no scientific-validation claim, no physical-world-validation claim, no market-validation claim, no customer claim, no external publication, no paid-launch claim, no secret-evidence claim, and no deployment claim.
-->

# Foundation Research Notebook Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** research-notebook preparation means organizing concepts,
> assumptions, proof status, and future evidence questions locally. It does not
> prove patent protection, trade-secret protection, scientific validation,
> physical-world validation, market validation, customer readiness, public
> publication, paid launch, secret evidence, or deployment readiness.

Witness packet: [`../examples/foundation_research_notebook_witness.awaiting_evidence.json`](../examples/foundation_research_notebook_witness.awaiting_evidence.json)

Rule: Research-notebook preparation is a local planning boundary, not a patent, secrecy, validation, publication, market, or deployment certificate.

No patent protection, trade-secret protection, scientific validation,
physical-world validation, market validation, customer claim, external
publication, paid-launch, secret-evidence, or deployment claim is permitted by
this boundary.

## What This Boundary Solves

Foundation Mode includes conceptual work, architecture claims, and symbolic
intelligence research notes. Those notes are useful, but they do not prove legal
protection, public validation, scientific validation, market demand, customer
readiness, or deployment readiness.

This boundary keeps research work narrow:

1. Concept notes can be organized locally.
2. Assumptions can be named without treating them as facts.
3. Prior-art and invention questions can be prepared for later qualified review.
4. Proof status can stay separate from public claims.
5. Experiments can be planned without claiming physical-world validation.
6. Authorship and lineage notes can be public-safe and non-secret.
7. Evidence-promotion questions can remain `AwaitingEvidence`.

## Current State

```text
research_notebook_boundary_state=AwaitingEvidence
patent_protection_claimed=false
trade_secret_protection_claimed=false
scientific_validation_claimed=false
physical_world_validation_claimed=false
market_validation_claimed=false
customer_claim_allowed=false
external_publication_allowed=false
paid_launch_allowed=false
secret_evidence_claimed=false
deployment_allowed=false
```

## Research Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Concept inventory | List concept names, boundaries, and unresolved definitions. | Do not claim invention scope is legally protected. |
| Assumption register | Record assumptions and evidence needed. | Do not treat assumptions as validated facts. |
| Prior-art question list | Draft questions for later qualified review. | Do not claim novelty, patentability, or clearance. |
| Proof-status map | Separate local proof, conjecture, and missing evidence. | Do not claim scientific, physical-world, market, or customer validation. |
| Experiment boundary | Draft future local experiments and stop rules. | Do not run external experiments or claim real-world validation. |
| Evidence-promotion questions | Name what future evidence would promote a claim. | Do not promote a claim without a later signed witness. |
| Authorship-lineage notes | Keep public-safe dated authorship notes. | Do not store private communications, secrets, or reviewer identities. |
| Public-claim language | Keep language cautious and Foundation Mode aligned. | Do not publish research, invite customers, launch paid use, or deploy. |

## Operator Procedure

1. Treat research notes as local concept organization unless a later explicit
   request names a qualified review or publication action.
2. Mark every unproven concept as `AwaitingEvidence`.
3. Keep legal, patent, secrecy, scientific, physical-world, market, customer,
   paid-launch, and deployment claims separate from local notes.
4. Keep private paths, reviewer identities, provider details, account
   identifiers, live URLs, private communications, and secrets out of the
   witness packet.
5. Promote one claim only when a later signed witness names the exact evidence
   and scope of that claim.

## Validation

Run:

```powershell
python scripts/validate_foundation_research_notebook_boundary.py
```

The validator checks that the research-notebook witness:

1. keeps every research surface in `AwaitingEvidence`;
2. keeps patent protection, trade-secret protection, scientific validation,
   physical-world validation, market validation, customer claims, external
   publication, paid launch, secret evidence, and deployment blocked;
3. rejects URL, email, private path, reviewer, provider, account, confidential,
   patent-filing, or secret-shaped values; and
4. rejects research-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Separate public claims safely | [Foundation Claim Boundary](FOUNDATION_CLAIM_BOUNDARY.md) |
| Prepare legal/business questions safely | [Foundation Legal Business Boundary](FOUNDATION_LEGAL_BUSINESS_BOUNDARY.md) |
| Check deployment truth | [Deployment Status](../DEPLOYMENT_STATUS.md) |

STATUS:
  Completeness: 100%
  Invariants verified: patent protection not claimed, trade-secret protection not claimed, scientific validation not claimed, physical-world validation not claimed, market validation not claimed, customer claim blocked, external publication blocked, paid launch blocked, secret evidence not claimed, deployment blocked
  Open issues: concept inventory evidence, assumption evidence, prior-art question evidence, proof-status evidence, experiment-boundary evidence, evidence-promotion evidence, authorship-lineage evidence, and public-claim language evidence remain AwaitingEvidence
  Next action: run the research-notebook boundary validator before any future research, patent, secrecy, validation, publication, market, customer, paid-launch, or deployment claim
