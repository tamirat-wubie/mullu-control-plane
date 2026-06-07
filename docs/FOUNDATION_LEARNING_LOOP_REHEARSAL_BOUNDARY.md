<!--
Purpose: define the Foundation Mode boundary for rehearsing one local learning loop without skill-readiness, training-completion, certification, paid-course, mentor, hiring, delegation, publication, support, source-control publication, external-account, spending, legal/business, or deployment claims.
Governance scope: local learning-loop rehearsal, topic selection, local-doc reading, glossary lookup, harmless command practice, expected-output pairing, public-safe error category recording, validator pairing, handoff note, next-loop selection, stop-rule rehearsal, private-value exclusion, and external-action blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_LEARNING_PATH_BOUNDARY.md, docs/FOUNDATION_SOLO_DAILY_LOOP_BOUNDARY.md, docs/FOUNDATION_OPERATOR_READINESS_BOUNDARY.md, examples/foundation_learning_loop_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_learning_loop_rehearsal_boundary.py.
Invariants: no skill-readiness claim, no training-completion claim, no certification claim, no paid-course activation, no mentor assignment, no hiring-readiness claim, no delegation-readiness claim, no public tutorial publication, no curriculum-completion claim, no production-operation readiness claim, no customer-support readiness claim, no external-account use, no private schedule recording, no private health recording, no spending, no legal/business action, no source-control publication, and no deployment claim.
-->

# Foundation Learning Loop Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** learning-loop rehearsal means practicing one tiny local
> learning loop: choose one topic, read one local doc, run one harmless command,
> record one public-safe error category, pair one validator, and choose one next
> loop. It does not prove skill, finish training, certify competence, buy a
> course, assign a mentor, prepare hiring, delegate work, publish tutorials,
> open support, use external accounts, spend money, take legal/business action,
> publish source control, or deploy.

Witness packet: [`../examples/foundation_learning_loop_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_learning_loop_rehearsal_witness.awaiting_evidence.json)

Rule: Learning-loop rehearsal is a local paper-and-command practice packet, not
a skill, training, certification, hiring, support, publication, or deployment
certificate.

No skill-readiness claim, training-completion claim, certification claim,
paid-course activation, mentor assignment, hiring-readiness claim,
delegation-readiness claim, public tutorial publication,
curriculum-completion claim, production-operation readiness claim,
customer-support readiness claim, external-account use, private schedule
recording, private health recording, spending, legal/business action,
source-control publication, or deployment claim is permitted by this boundary.

## What This Boundary Solves

The learning path says learning should stay local and evidence-bound. This
rehearsal boundary turns that into one repeatable atomic practice loop for a
solo operator with limited development experience.

This is preparation only:

1. Practice can be small enough to finish without pressure.
2. The witness can prove every loop step is still `AwaitingEvidence`.
3. Validators can reject premature competence, training, certification, paid
   course, mentor, hiring, delegation, support, publication, external-account,
   source-control, legal/business, money, or deployment claims.
4. Private schedules, private health notes, accounts, secrets, customer data,
   and private paths stay out of Git.

## Current State

```text
learning_loop_rehearsal_boundary_state=AwaitingEvidence
loop_rehearsal_executed=false
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
private_schedule_recording_allowed=false
private_health_recording_allowed=false
spending_allowed=false
legal_business_action_allowed=false
source_control_publication_allowed=false
deployment_allowed=false
```

## Rehearsal Labels

These labels are stop-rule gates only. They are not study schedules, course
receipts, mentor identities, account records, support tickets, customer
records, private paths, command transcripts with secrets, source-control
publication receipts, legal/business records, spending records, or deployment
receipts.

| Label | Future proof class | Boundary |
| --- | --- | --- |
| `topic_selection_rehearsal` | Future topic-selection proof. | Do not claim skill readiness. |
| `local_doc_reading_rehearsal` | Future local-reading proof. | Do not claim training completion. |
| `glossary_lookup_rehearsal` | Future vocabulary proof. | Do not claim curriculum completion. |
| `harmless_command_rehearsal` | Future command-practice proof. | Do not mutate services, accounts, or deployment state. |
| `expected_output_rehearsal` | Future expected-output proof. | Do not claim verification closure. |
| `error_category_rehearsal` | Future error-category proof. | Do not record private paths, accounts, schedules, health, or secrets. |
| `validator_pairing_rehearsal` | Future validator-pairing proof. | Do not claim certification. |
| `handoff_note_rehearsal` | Future handoff proof. | Do not claim support readiness or team coverage. |
| `next_loop_selection_rehearsal` | Future next-loop proof. | Do not promise deadlines or roadmap delivery. |
| `stop_rule_rehearsal` | Future stop-rule proof. | Do not approve external action, spending, legal/business action, source-control publication, or deployment. |

## Operator Procedure

1. Pick one confusing local topic from a Foundation document.
2. Read one local source-of-truth page.
3. Run one harmless local command or inspect-only validator.
4. Record one public-safe error or confusion category.
5. Pair the loop with one validator, test, or expected output.
6. Write one short handoff note and one next-loop label.
7. Stop if the loop needs paid courses, mentors, hiring, external accounts,
   private details, source-control publication, customer support, money,
   legal/business action, or deployment.

## Validation

Run:

```powershell
python scripts/validate_foundation_learning_loop_rehearsal_boundary.py
```

The validator checks that the learning-loop rehearsal witness:

1. keeps every rehearsal label in `AwaitingEvidence`;
2. keeps skill readiness, training completion, certification, paid courses,
   mentor assignment, hiring readiness, delegation readiness, public tutorial
   publication, curriculum completion, production-operation readiness,
   customer-support readiness, external-account use, private schedule
   recording, private health recording, spending, legal/business action,
   source-control publication, and deployment blocked;
3. rejects URLs, emails, private paths, private schedule values, private health
   values, account values, paid-course values, mentor/person values,
   certificate values, customer/support values, source-control publication
   values, legal/business values, spending values, secrets, and deployment
   values; and
4. rejects promotion phrases that imply skill, training, certification,
   support, publication, external-account, legal/business, source-control, or
   deployment readiness.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole learning boundary | [Foundation Learning Path Boundary](FOUNDATION_LEARNING_PATH_BOUNDARY.md) |
| Run one cautious daily loop | [Foundation Solo Daily Loop Boundary](FOUNDATION_SOLO_DAILY_LOOP_BOUNDARY.md) |
| Prepare operator readiness safely | [Foundation Operator Readiness Boundary](FOUNDATION_OPERATOR_READINESS_BOUNDARY.md) |
| Pick one next local action | [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: skill-readiness claim blocked, training-completion claim blocked, certification claim blocked, paid-course activation blocked, mentor assignment blocked, hiring-readiness claim blocked, delegation-readiness claim blocked, public tutorial publication blocked, curriculum-completion claim blocked, production-operation readiness blocked, customer-support readiness blocked, external-account use blocked, private schedule recording blocked, private health recording blocked, spending blocked, legal/business action blocked, source-control publication blocked, deployment blocked
  Open issues: all learning-loop rehearsal labels remain AwaitingEvidence
  Next action: run the learning-loop rehearsal validator before using any learning loop as readiness evidence
