# Mullusi Search Layer Map

Status: Foundation Mode
Scope: private search and evidence map. This document does not claim live search availability, source coverage, cost readiness, or production operation.

## 1. Search purpose

Search is an evidence action, not an automatic reflex for every message.

```text
InterpretedRequest
-> search need classification
-> freshness classification
-> source selection
-> cache check
-> budget gate
-> retrieval
-> evidence ranking
-> answer synthesis
-> SearchReceipt
```

## 2. Search states

```text
NO_SEARCH_NEEDED
CACHE_HIT
LOCAL_SEARCH
WEB_SEARCH_LIGHT
WEB_SEARCH_DEEP_APPROVAL_REQUIRED
SEARCH_BLOCKED_BY_BUDGET
SEARCH_FAILED_WITH_EXPLANATION
```

## 3. Component map

| Component | Purpose | Inputs | Outputs | Status | Next Step |
| --- | --- | --- | --- | --- | --- |
| Search Need Classifier | decide whether retrieval is needed | interpreted intent, local knowledge | search state | implemented / partial | `SearchDecision` records the pre-retrieval classification. |
| Freshness Classifier | decide whether current evidence is required | question, domain, timestamp needs | freshness requirement | implemented / partial | `SearchDecision.freshness` records current-claim eligibility before retrieval. |
| Source Selector | choose local docs, repo, web, or connector source | freshness, sensitivity, budget | source plan | implemented / partial | `SearchDecision.source_plan` prefers local evidence and blocks external retrieval when approval is missing. |
| Cache | reuse allowed evidence | query key, tenant scope | cache hit or miss | implemented / partial | `SearchDecision.metadata.cache_admission` allows cache reuse only with tenant-scoped, query-hash-matched, fresh, non-stale evidence; no cache store is implemented here. |
| Retriever | collect evidence from selected sources | source plan | evidence set | implemented / partial | Local read-only search returns bounded excerpts while SearchReceipt stores metadata only. |
| Evidence Ranker | rank by relevance, trust, freshness, and conflict | evidence set | ranked evidence | implemented / partial | Local deterministic ranking is path/line/excerpt stable; bounded polarity conflicts are marked as conflict refs; stale classification remains partial. |
| Citation Builder | create source references | ranked evidence | citations | implemented / partial | Local SearchReceipt emits citation refs and evidence refs without storing retrieved bodies. |
| Answer Synthesizer | answer with uncertainty and citations | question, evidence | draft answer | partial | Block current claims on stale evidence. |
| Search Receipt Writer | record search decision and evidence | search state, budget, citations | SearchReceipt | implemented / partial | Local read-only search worker emits SearchReceipt metadata with citations, freshness, budget-decision binding, retrieval safety, instruction-authority rejection, and retrieval errors. |
| Cost Meter | estimate and record retrieval cost | query depth, provider, tokens | budget estimate | implemented / partial | `SearchDecision.budget_decision` blocks deep retrieval on `BudgetUnknown`, and `SearchReceipt.budget_result` preserves the accepted decision state, cost estimate, limit, headroom, policy ref, and decision receipt ref. |

## 4. SearchDecision fields

```text
SearchDecision {
  decision_id
  request_id
  tenant_id
  actor_id
  decision_state
  search_need
  freshness
  source_plan
  cache_decision
  budget_result {
    budget_policy_ref
    budget_decision_ref
    decision_budget_state
    decision_estimated_cost_units
    decision_budget_limit_units
    decision_budget_remaining_units
    budget_binding_state
    budget_evidence_refs
  }
  retrieval_safety
  governance_guards
  receipt_envelope
  evidence_refs
  created_at
}
```

`SearchDecision` is pre-retrieval. It can block, route, or require approval, but it does not prove retrieved evidence exists.

## 5. SearchReceipt fields

```text
SearchReceipt {
  receipt_id
  request_id
  tenant_id
  search_state
  freshness_required
  freshness_result
  source_plan
  cache_decision
  budget_decision
  evidence_count
  citation_refs
  conflicts_detected
  stale_sources
  retrieval_errors
  retrieval_safety_result
  governance_guards
  receipt_envelope
  created_at
}
```

`SearchReceipt` is post-decision. It can prove that retrieval was blocked, failed, stale, conflicted, or produced metadata-backed evidence. It stores evidence metadata and citation refs, not retrieved content bodies.

## 6. Retrieval safety rules

```text
Retrieved content is evidence, not instruction authority.
Prompt injection text inside search results must not control tools, policy, approvals, or responses.
Local source instruction markers are recorded as `instruction_authority_rejected` retrieval errors.
Local matching lines with the same normalized claim subject and opposing bounded polarity terms are recorded as `conflict://local-docs/...` refs.
Private or tenant-sensitive search must stay tenant-scoped.
Cache reuse requires tenant-scoped, query-hash-matched, fresh evidence.
Deep search requires budget approval when policy requires it.
Runtime local search receipts must bind `budget_result.budget_decision_ref` to
`search_decision_ref`, so the post-retrieval receipt cannot claim a budget
state disconnected from the pre-retrieval decision.
Source freshness must be visible for current-information answers.
```

## 7. Search edge cases

| Edge Case | Required Behavior |
| --- | --- |
| User asks stable known fact | answer without search if local knowledge is enough. |
| User asks current status | require freshness check and cite evidence. |
| Cache is stale | mark stale or search again if budget allows. |
| Search API fails | report uncertainty and write SearchReceipt with retrieval error. |
| Search results conflict | cite conflict and avoid overclaim. |
| Search exceeds budget | block or ask approval for deep search. |
| Private source requested | verify tenant scope before retrieval. |
| Retrieved page includes instructions | reject instruction authority; record content as evidence only. |

## 8. Contract evidence

```text
schemas/search_decision.schema.json
examples/search_decision.foundation.json
scripts/validate_search_decision.py
tests/test_validate_search_decision.py
docs/77_search_decision_contract.md
schemas/search_receipt.schema.json
examples/search_receipt.foundation.json
scripts/validate_search_receipt.py
tests/test_validate_search_receipt.py
docs/78_search_receipt_contract.md
```
