<!--
Purpose: define the Foundation Mode learning-path boundary for a solo beginner preparing skills locally without claiming readiness, certification, training completion, hiring capacity, public teaching, customer support, or deployment authority.
Governance scope: learning goal inventory, glossary loop, command practice, reading queue, local exercise design, error log, verification habit, help-request boundary, public-safe planning, and external-action blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_OPERATOR_READINESS_BOUNDARY.md, docs/FOUNDATION_NEXT_ACTION_BOUNDARY.md, examples/foundation_learning_path_witness.awaiting_evidence.json, scripts/validate_foundation_learning_path_boundary.py.
Invariants: no skill-readiness claim, no training-completion claim, no certification claim, no paid-course activation, no mentor assignment, no hiring-readiness claim, no delegation-readiness claim, no public tutorial publication, no curriculum-completion claim, no production-operation readiness claim, no customer-support readiness claim, no external account use, and no deployment claim.
-->

# Foundation Learning Path Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** learning-path preparation means turning skill gaps into small
> local practice loops. It does not prove skill readiness, finish training,
> certify competence, buy courses, assign a mentor, prepare hiring, delegate
> work, publish tutorials, complete a curriculum, prove production operation,
> open customer support, use external accounts, or deploy anything.

Witness packet: [`../examples/foundation_learning_path_witness.awaiting_evidence.json`](../examples/foundation_learning_path_witness.awaiting_evidence.json)

Rule: Learning-path preparation is a local planning boundary, not a skill,
training, certification, hiring, support, publication, or deployment
certificate.

No skill-readiness claim, training-completion claim, certification claim,
paid-course activation, mentor assignment, hiring-readiness claim,
delegation-readiness claim, public tutorial publication, curriculum-completion
claim, production-operation readiness claim, customer-support readiness claim,
external account use, or deployment claim is permitted by this boundary.

## What This Boundary Solves

Foundation Mode assumes a solo operator can learn carefully without pretending
to be ready. That requires a public-safe learning plan that is smaller than a
course, cheaper than a vendor dependency, and safer than production practice.

This is preparation only:

1. The repository can name learning surfaces without recording private study
   schedules or private accounts.
2. The witness can prove every learning surface is still `AwaitingEvidence`.
3. Validators can reject premature readiness, certification, paid course,
   mentor, hiring, support, publication, account-use, or deployment claims.
4. Each learning loop stays local, reversible, and evidence-bound.

## Current State

```text
learning_path_boundary_state=AwaitingEvidence
skill_readiness_claimed=false
training_completion_claimed=false
certification_claimed=false
paid_course_allowed=false
mentor_assignment_allowed=false
hiring_readiness_claimed=false
delegation_readiness_claimed=false
public_tutorial_publication_allowed=false
curriculum_completion_claimed=false
production_operation_readiness_claimed=false
customer_support_readiness_claimed=false
external_account_use_allowed=false
deployment_allowed=false
```

## Learning-Path Surfaces

| Surface | Prepare now | Blocked now |
| --- | --- | --- |
| Learning goal inventory | Name one small topic to understand. | Do not claim skill readiness. |
| Glossary loop | Link confusing words to local docs. | Do not claim training completion. |
| Command practice loop | Practice harmless local commands. | Do not mutate services, accounts, or deployment state. |
| Reading queue | List local docs to read next. | Do not buy courses or activate paid learning. |
| Local exercise design | Draft one tiny exercise with expected output. | Do not claim production-operation readiness. |
| Error log | Record public-safe error categories and fixes. | Do not record private paths, accounts, secrets, or health details. |
| Verification habit | Pair each exercise with a local validator or test. | Do not claim certification or curriculum completion. |
| Help-request boundary | Draft when outside help may be useful. | Do not assign mentors, hire, delegate, or expose private details. |

## Operator Procedure

1. Pick one confusing topic from a Foundation document.
2. Link the topic to one local source-of-truth page.
3. Run or inspect one harmless local command related to that topic.
4. Record only public-safe category-level notes.
5. Pair the exercise with one validator, test, or expected output.
6. Keep the result in `AwaitingEvidence` until repeated practice and later
   review justify promotion.
7. Do not treat local practice as customer, support, deployment, hiring,
   certification, or business readiness.

## Validation

Run:

```powershell
python scripts/validate_foundation_learning_path_boundary.py
```

The validator checks that the learning-path witness:

1. keeps skill readiness, training completion, certification, paid courses,
   mentor assignment, hiring readiness, delegation readiness, public tutorial
   publication, curriculum completion, production-operation readiness,
   customer-support readiness, external account use, and deployment disabled;
2. keeps every learning surface in `AwaitingEvidence`;
3. rejects URL, email, private path, schedule, person, mentor, account,
   provider, paid-course, certificate, secret, credential, customer, support,
   publication, service, or deployment shaped values; and
4. rejects readiness-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare operator readiness safely | [Foundation Operator Readiness Boundary](FOUNDATION_OPERATOR_READINESS_BOUNDARY.md) |
| Choose one next local action safely | [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) |
| Keep local workstation practice bounded | [Foundation Local Workstation Boundary](FOUNDATION_LOCAL_WORKSTATION_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: skill-readiness claim blocked, training-completion claim blocked, certification claim blocked, paid-course activation blocked, mentor assignment blocked, hiring-readiness claim blocked, delegation-readiness claim blocked, public tutorial publication blocked, curriculum-completion claim blocked, production-operation readiness blocked, customer-support readiness blocked, external account use blocked, deployment blocked
  Open issues: learning-goal evidence, glossary-loop evidence, command-practice evidence, reading-queue evidence, local-exercise evidence, error-log evidence, verification-habit evidence, and help-request-boundary evidence remain AwaitingEvidence
  Next action: run the learning-path boundary validator before using learning notes as readiness evidence
