<!--
Purpose: define the Foundation Mode hazard-map boundary for local public-safe hazard question drafting without claiming hazard-map completeness, hazard classification readiness, severity closure, mitigation readiness, safety review readiness, runtime readiness, owner approval, test pass, implementation, publication, or deployment.
Governance scope: safety hazard questions, runtime hazard questions, data hazard questions, dependency hazard questions, interface hazard questions, governance hazard questions, evidence hazard questions, rollback hazard questions, operator hazard questions, public-safe planning, and readiness blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_INVARIANT_MAP_BOUNDARY.md, examples/foundation_hazard_map_witness.awaiting_evidence.json, scripts/validate_foundation_hazard_map_boundary.py.
Invariants: no hazard-map completeness claim, no hazard classification readiness claim, no hazard severity closure claim, no mitigation readiness claim, no safety review readiness claim, no runtime hazard readiness claim, no owner approval assignment, no test pass claim, no refactor approval, no implementation approval, no external publication, and no deployment claim.
-->

# Foundation Hazard Map Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** hazard-map preparation means drafting local public-safe
> questions about what could break, expose risk, create false trust, lose data,
> block recovery, or overload the operator. It does not prove hazards are fully
> identified, classified, mitigated, reviewed, tested, ready at runtime,
> implemented, publishable, or deployable.

Witness packet: [`../examples/foundation_hazard_map_witness.awaiting_evidence.json`](../examples/foundation_hazard_map_witness.awaiting_evidence.json)

Rule: Hazard-map preparation is a local planning boundary, not a
hazard-map-completion, hazard-classification-readiness, severity-closure,
mitigation-readiness, safety-review-readiness, runtime-readiness,
owner-approval, test-pass, refactor-approval, implementation-approval,
publication, or deployment certificate.

No hazard-map completeness, hazard classification readiness, hazard severity
closure, mitigation readiness, safety review readiness, runtime hazard
readiness, owner approval assignment, test pass, refactor approval,
implementation approval, external publication, or deployment claim is
permitted by this boundary.

## What This Boundary Solves

Invariants say what must stay true. Hazards name what could violate those
truths or create exposure before the project is ready. This boundary lets the
repository prepare hazard questions without claiming classification, severity
closure, mitigation readiness, safety review, runtime checks, tests, or
implementation approval.

This is preparation only:

1. The repository can name hazard-map surfaces.
2. The witness can prove every surface is still `AwaitingEvidence`.
3. Validators can reject premature hazard classification, severity closure,
   mitigation, review, runtime, owner, test, implementation, publication, or
   deployment claims.
4. Private paths, endpoint targets, provider identifiers, incident details,
   mitigation targets, test results, secrets, credentials, customer data, and
   deployment targets stay out of the public packet.

## Current State

```text
hazard_map_boundary_state=AwaitingEvidence
hazard_map_complete_claimed=false
hazard_classification_ready_claimed=false
hazard_severity_closed_claimed=false
hazard_mitigation_ready_claimed=false
safety_review_ready_claimed=false
runtime_hazard_ready_claimed=false
owner_approval_assigned=false
test_pass_claimed=false
refactor_approval_allowed=false
implementation_approval_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Hazard-Map Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Safety hazards | Draft safety-floor and irreversible-action hazard questions. | Do not claim safety review readiness. |
| Runtime hazards | Draft service, endpoint, migration, and process hazard questions. | Do not claim runtime hazard readiness. |
| Data hazards | Draft data exposure, deletion, retention, and recovery hazard questions. | Do not claim data safety closure. |
| Dependency hazards | Draft package, provider, service, and account hazard questions. | Do not claim dependency hazard closure. |
| Interface hazards | Draft input, output, error-path, and handoff hazard questions. | Do not claim interface hazard closure. |
| Governance hazards | Draft policy, approval, receipt, and bypass hazard questions. | Do not claim governance hazard closure. |
| Evidence hazards | Draft witness, receipt, trace, and false-claim hazard questions. | Do not claim evidence closure. |
| Rollback hazards | Draft rollback, replay, recovery, and reversibility hazard questions. | Do not claim rollback readiness. |
| Operator hazards | Draft solo-operator capacity, support, fatigue, and escalation hazard questions. | Do not claim operator readiness. |

## Operator Procedure

1. Pick one hazard surface from the table.
2. Draft only public-safe hazard questions.
3. Avoid URLs, emails, private paths, endpoint targets, provider targets,
   incident identifiers, mitigation targets, safety-review results, test
   results, secrets, credentials, customer identifiers, implementation ids,
   refactor ids, or deployment targets.
4. Mark unknown classifications, severities, mitigations, reviews, runtime
   behavior, owner approval, tests, implementation, and exposure points as
   `AwaitingEvidence`.
5. Do not use this map to authorize mitigation, refactor, implementation,
   publication, external exposure, customer access, or deployment.

## Validation

Run:

```powershell
python scripts/validate_foundation_hazard_map_boundary.py
```

The validator checks that the hazard-map witness:

1. keeps hazard-map completeness, hazard classification readiness, severity
   closure, mitigation readiness, safety review readiness, runtime readiness,
   owner approval, test pass, refactor approval, implementation approval,
   publication, and deployment disabled;
2. keeps every hazard-map surface in `AwaitingEvidence`;
3. rejects URL, email, private path, endpoint, account, provider, hazard,
   classification, severity, mitigation, review, incident, test, customer,
   secret, credential, implementation, refactor, publication, or deployment
   shaped values; and
4. rejects hazard-readiness promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare invariant maps safely | [Foundation Invariant Map Boundary](FOUNDATION_INVARIANT_MAP_BOUNDARY.md) |
| Prepare local workstation safely | [Foundation Local Workstation Boundary](FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md) |
| Choose one next local action safely | [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: hazard-map completeness blocked, hazard classification readiness blocked, hazard severity closure blocked, mitigation readiness blocked, safety review readiness blocked, runtime hazard readiness blocked, owner approval blocked, test pass blocked, refactor approval blocked, implementation approval blocked, external publication blocked, deployment blocked
  Open issues: safety-hazard evidence, runtime-hazard evidence, data-hazard evidence, dependency-hazard evidence, interface-hazard evidence, governance-hazard evidence, evidence-hazard evidence, rollback-hazard evidence, and operator-hazard evidence remain AwaitingEvidence
  Next action: run the hazard-map validator before using hazard notes as readiness evidence
