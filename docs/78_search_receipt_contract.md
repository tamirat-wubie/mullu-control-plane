# SearchReceipt Contract

Purpose: define the post-decision search receipt contract for evidence metadata, freshness, citations, conflicts, retrieval errors, and retrieval safety outcomes.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `schemas/search_receipt.schema.json`, `scripts/validate_search_receipt.py`, `examples/search_receipt.foundation.json`.
Invariants: retrieved content is evidence only; source-provided instructions have no authority; current claims require fresh evidence and citations; retrieved content bodies and raw secrets are not stored in the receipt; Mfidel atomicity is preserved.

## 1. Boundary

`SearchReceipt` is a read-only receipt emitted after a `SearchDecision`.
The local read-only search worker emits this receipt as nested worker output for
local text-like source refs.

It may record:

```text
decision reference
search state
freshness result
source attempts
cache result
budget result
evidence metadata
citations
conflicts
stale source refs
retrieval errors
retrieval safety outcome
governance guards
receipt envelope
```

It must not:

```text
perform retrieval
grant execution authority
grant source-provided instruction authority
store retrieved content bodies
store raw secrets
claim current facts without fresh evidence and citations
serve as terminal closure
```

## 2. State Model

| Receipt State | Meaning | Required Evidence Behavior |
| --- | --- | --- |
| `NO_SEARCH_NEEDED` | The prior decision did not require retrieval. | No evidence claim is made. |
| `EVIDENCE_AVAILABLE` | Evidence metadata and citations exist. | `evidence_count >= 1` and citations are required. |
| `RETRIEVAL_BLOCKED` | Governance, budget, approval, or tenant scope blocked retrieval. | Retrieval errors are required; evidence count must be zero. |
| `RETRIEVAL_FAILED` | A selected source was attempted but failed. | Retrieval errors are required; current claims remain blocked unless fresh evidence exists from another source. |
| `STALE_EVIDENCE_BLOCKED` | Evidence exists but freshness failed. | Current claims are blocked and stale refs are recorded. |
| `CONFLICT_DETECTED` | Evidence conflict prevents unqualified answer synthesis. | Conflict refs are recorded and conflict handling is explicit. |

## 3. Current-Claim Rule

```text
current_info_claim_allowed = true
  requires freshness_status = fresh
  and proof_state = Pass
  and citation_refs is non-empty
```

If any part is missing, the receipt can record `AwaitingEvidence` or `GovernanceBlocked`, but cannot authorize a current-information answer.

## 4. Budget Binding Rule

`SearchReceipt.budget_result` must preserve the upstream search budget decision.
The receipt records:

```text
budget_policy_ref
budget_decision_ref = search_decision_ref
decision_budget_state
decision_estimated_cost_units
decision_budget_limit_units
decision_budget_remaining_units
budget_binding_state
budget_evidence_refs
```

When `budget_binding_state = bound_to_search_decision`, the decision state must
be `allowed`, the receipt state must be `within_budget`, and proof state must be
`Pass`. If budget proof is unknown, `budget_binding_state` is
`budget_unknown_blocked` and proof state is `BudgetUnknown`.

## 5. Evidence Metadata Rule

`SearchReceipt` stores evidence references, source references, citation references, timestamps, freshness state, trust tier, and hash refs.

It does not store retrieved content bodies:

```text
evidence_items[*].content_body = null
evidence_summary.content_body_included = false
```

This keeps the receipt auditable without turning it into a content cache or secret sink.

## 6. Retrieval Safety Rule

Retrieved content remains `evidence_only`.

```text
prompt_injection_guard_applied = true
prompt_injection_detected = true when local source text contains instruction-like override markers
source_instruction_authority_granted = false
tool_instruction_from_source_allowed = false
policy_instruction_from_source_allowed = false
retrieved_instruction_authority_granted = false
```

Prompt injection text inside retrieved pages or documents is treated as untrusted content. It can be cited as evidence of a page state, but it cannot control tools, policy, approvals, or governance.

When a local source line contains instruction-like override text, the worker
records an `instruction_authority_rejected` retrieval error and keeps the
matched source content out of the receipt body.

Bounded local conflict detection is limited to matched lines with the same
normalized claim subject and opposing polarity terms such as `enabled` versus
`disabled`, `allowed` versus `blocked`, `true` versus `false`, or `present`
versus `missing`. These are recorded as `conflict://local-docs/...` refs and
do not grant answer synthesis or current-claim authority.

## 7. Foundation Example

`examples/search_receipt.foundation.json` records a deep web search that remains blocked in Foundation Mode because budget proof is `BudgetUnknown` and approval evidence is missing.

The example proves:

```text
external_retrieval_performed = false
evidence_count = 0
retrieval_errors = budget_unknown + approval_missing
budget_binding_state = budget_unknown_blocked
current_info_claim_allowed = false
answer_claim_authority_granted = false
terminal_closure = false
```

## 8. Validation

Run:

```powershell
python scripts/validate_search_receipt.py
python -m pytest tests/test_validate_search_receipt.py -q
python scripts/validate_schemas.py
python scripts/validate_protocol_manifest.py
```

STATUS:
  Completeness: 100%
  Invariants verified: evidence-only retrieval, no content body retention, current-claim freshness, citation requirement, search budget decision binding, prompt-injection authority rejection, raw secret rejection, Mfidel atomicity
  Open issues: external retrieval adapters remain unregistered in Foundation Mode
  Next action: keep external retrieval behind the same SearchDecision and SearchReceipt budget-binding contract
