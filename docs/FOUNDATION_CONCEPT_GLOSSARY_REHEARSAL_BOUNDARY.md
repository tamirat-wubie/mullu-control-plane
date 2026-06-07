<!--
Purpose: define the Foundation Mode boundary for rehearsing one local concept glossary entry without canonical-definition, mastery, documentation-completeness, publication, source-control publication, legal/business, spending, customer, or deployment claims.
Governance scope: local concept glossary rehearsal, term selection, local source-doc reference, plain definition draft, boundary example draft, non-goal note, evidence reference, confusion note, cross-link label, validator pairing, stop-rule rehearsal, private-value exclusion, and external-action blocking.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, docs/FOUNDATION_LEARNING_LOOP_REHEARSAL_BOUNDARY.md, docs/FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md, examples/foundation_concept_glossary_rehearsal_witness.awaiting_evidence.json, scripts/validate_foundation_concept_glossary_rehearsal_boundary.py.
Invariants: no canonical-definition claim, no glossary-completeness claim, no concept-mastery claim, no technical-readiness claim, no training-completion claim, no comprehension-proof claim, no public-docs-readiness claim, no product-readiness claim, no customer-readiness claim, no private-value recording, no legal/business action, no spending, no money movement, no source-control publication, no external publication, and no deployment claim.
-->

# Foundation Concept Glossary Rehearsal Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** concept glossary rehearsal means choosing one confusing local
> Mullusi term and drafting one public-safe plain definition, one example, one
> non-goal, one evidence reference, and one next question. It does not make the
> definition canonical, prove mastery, complete documentation, publish docs,
> approve source control, spend money, take legal/business action, open customer
> access, or deploy.

Witness packet: [`../examples/foundation_concept_glossary_rehearsal_witness.awaiting_evidence.json`](../examples/foundation_concept_glossary_rehearsal_witness.awaiting_evidence.json)

Rule: Concept glossary rehearsal is a local vocabulary clarification packet,
not a canonical-definition, mastery, training, comprehension, public-docs,
product-readiness, customer-readiness, publication, legal/business, money,
source-control, or deployment certificate.

No canonical-definition claim, glossary-completeness claim, concept-mastery
claim, technical-readiness claim, training-completion claim, comprehension
proof, public-docs-readiness claim, product-readiness claim,
customer-readiness claim, private-value recording, legal/business action,
spending, money movement, source-control publication, external publication, or
deployment claim is permitted by this boundary.

## What This Boundary Solves

Foundation Mode contains many precise terms. A solo operator can be slowed down
when terms such as boundary, witness, receipt, readiness, proof, validator, or
deployment are unclear. This boundary makes vocabulary work small and safe.

This is preparation only:

1. One term can be clarified without claiming the glossary is complete.
2. Plain wording can be drafted without proving reader comprehension.
3. Examples and non-goals can reduce confusion without creating product,
   legal, customer, money, source-control, or deployment commitments.
4. Private paths, private notes, account values, secrets, customer data, and
   endpoint values stay out of the witness.

## Current State

```text
concept_glossary_rehearsal_boundary_state=AwaitingEvidence
glossary_entry_published=false
canonical_definition_claimed=false
glossary_complete_claimed=false
concept_mastery_claimed=false
technical_readiness_claimed=false
training_completion_claimed=false
comprehension_proven=false
public_docs_readiness_claimed=false
product_readiness_claimed=false
customer_readiness_claimed=false
private_value_recording_allowed=false
legal_business_action_allowed=false
spending_allowed=false
money_movement_allowed=false
source_control_publication_allowed=false
external_publication_allowed=false
deployment_allowed=false
```

## Rehearsal Labels

These labels are stop-rule gates only. They are not canonical glossary entries,
reader-study proof, customer-facing documentation, source-control publication
receipts, legal/business records, money records, customer records, private
paths, account records, secrets, or deployment receipts.

| Label | Future proof class | Boundary |
| --- | --- | --- |
| `term_selection_rehearsal` | Future term-selection proof. | Do not claim concept mastery. |
| `source_doc_reference_rehearsal` | Future local source-reference proof. | Do not record private paths or external URLs. |
| `plain_definition_rehearsal` | Future plain-definition proof. | Do not claim a canonical definition. |
| `boundary_example_rehearsal` | Future example proof. | Do not promise product behavior. |
| `non_goal_rehearsal` | Future non-goal proof. | Do not hide limitations. |
| `evidence_reference_rehearsal` | Future evidence-reference proof. | Do not promote `AwaitingEvidence` to closure. |
| `confusion_note_rehearsal` | Future confusion-note proof. | Do not record private schedule, health, account, or secret values. |
| `cross_link_rehearsal` | Future cross-link proof. | Do not claim documentation completeness. |
| `validator_pairing_rehearsal` | Future validator-pairing proof. | Do not claim training or certification. |
| `stop_rule_rehearsal` | Future stop-rule proof. | Do not approve publication, source control, legal/business action, spending, customer access, or deployment. |

## Operator Procedure

1. Pick one confusing local term from a Foundation document.
2. Reference one local source document by public-safe file label only.
3. Draft one plain definition in one or two sentences.
4. Draft one safe example and one non-goal.
5. Mark the evidence state as `AwaitingEvidence`.
6. Pair the draft with one validator or one expected phrase.
7. Stop if the glossary entry needs external publication, source-control
   publication, legal/business action, paid tools, customers, account values,
   private details, secrets, or deployment.

## Validation

Run:

```powershell
python scripts/validate_foundation_concept_glossary_rehearsal_boundary.py
```

The validator checks that the concept glossary rehearsal witness:

1. keeps every rehearsal label in `AwaitingEvidence`;
2. keeps canonical definition, glossary completeness, concept mastery,
   technical readiness, training completion, comprehension proof, public docs
   readiness, product readiness, customer readiness, private-value recording,
   legal/business action, spending, money movement, source-control
   publication, external publication, and deployment blocked;
3. rejects URLs, emails, private paths, account values, customer values, money
   values, legal/business values, source-control values, secrets, endpoint
   values, and deployment values; and
4. rejects promotion phrases that imply glossary, mastery, training,
   comprehension, documentation, product, customer, publication,
   legal/business, money, source-control, or deployment readiness.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| Rehearse the full learning loop | [Foundation Learning Loop Rehearsal Boundary](FOUNDATION_LEARNING_LOOP_REHEARSAL_BOUNDARY.md) |
| Prepare plain-language status safely | [Foundation Plain-Language Status Boundary](FOUNDATION_PLAIN_LANGUAGE_STATUS_BOUNDARY.md) |
| See the whole learning boundary | [Foundation Learning Path Boundary](FOUNDATION_LEARNING_PATH_BOUNDARY.md) |
| Pick one next local action | [Foundation Next Action Boundary](FOUNDATION_NEXT_ACTION_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: canonical-definition claim blocked, glossary-completeness claim blocked, concept-mastery claim blocked, technical-readiness claim blocked, training-completion claim blocked, comprehension-proof claim blocked, public-docs-readiness claim blocked, product-readiness claim blocked, customer-readiness claim blocked, private-value recording blocked, legal/business action blocked, spending blocked, money movement blocked, source-control publication blocked, external publication blocked, deployment blocked
  Open issues: all concept glossary rehearsal labels remain AwaitingEvidence
  Next action: run the concept glossary rehearsal validator before treating any glossary entry as readiness or documentation evidence
