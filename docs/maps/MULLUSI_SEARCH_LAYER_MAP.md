# Mullusi Search Layer Map

Status: Foundation Mode
Scope: private search and evidence map. This document does not claim live search availability, source coverage, runtime cost enforcement, or production operation.

## 1. Search purpose

Search is an evidence action, not an automatic reflex for every message.

```text
InterpretedRequest
-> search need classification
-> freshness classification
-> source selection
-> cache check
-> budget gate
-> SearchDecisionReceipt
-> retrieval
-> evidence ranking
-> answer synthesis
-> SearchReceipt
```

## 2. Search states

```text
no_search
use_cache
allow_search: local_search
allow_search: light_web_search
allow_search: deep_search
block_search: search_budget_limit_exceeded
block_search: deep_search_budget_required
search_failed_with_explanation
```

## 3. Component map

| Component | Purpose | Inputs | Outputs | Status | Next Step |
| --- | --- | --- | --- | --- | --- |
| Search Need Classifier | decide whether retrieval is needed | interpreted intent, local knowledge | search classification | implemented / partial | Connect classifier decisions to source-selection policy and viewer detail. |
| Freshness Classifier | decide whether current evidence is required | question, domain, timestamp needs | freshness state | implemented / partial | Bind source-level freshness evidence to future search result receipts. |
| Source Selector | choose local docs, repo, web, or connector source | freshness, sensitivity, budget | source plan | missing / partial | Prefer local evidence for Foundation Mode. |
| Cache | reuse allowed evidence | query key, tenant scope | cache hit or miss | missing / partial | Add tenant-scoped cache storage rules before use. |
| Retriever | collect evidence from selected sources | source plan | evidence set | partial / unknown | Treat retrieved content as evidence only. |
| Evidence Ranker | rank by relevance, trust, freshness, and conflict | evidence set | ranked evidence | missing / partial | Mark stale and conflicting sources. |
| Citation Builder | create source references | ranked evidence | citations | missing / partial | Avoid leaking internal paths when not appropriate. |
| Answer Synthesizer | answer with uncertainty and citations | question, evidence | draft answer | partial | Block current claims on stale evidence. |
| Search Decision Receipt Writer | record classification, freshness, budget, and retrieval authority | query hash, budget limit, cache state | SearchDecisionReceipt | implemented / partial | Add dedicated receipt viewer drilldowns for search decision receipts. |
| Cost Meter | estimate and record retrieval cost | query depth, provider, tokens | budget estimate | implemented / partial | Connect tenant-specific budget policy to search decision request construction. |

## 4. SearchDecisionReceipt fields

Implemented local contract:

```text
SearchDecisionReceipt {
  receipt_id
  tenant_id
  actor_id
  capability_id
  query_hash
  search_classification
  freshness_state
  budget_state
  retrieval_authority
  retrieval_instruction_authority_allowed
  decision
  blocked_reasons
  estimated_cost_units
  budget_limit_units
  max_result_count
  generated_at
  receipt_hash
}
```

## 5. Future SearchReceipt fields

Runtime retrieval still needs a separate evidence receipt:

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
  created_at
}
```

## 6. Retrieval safety rules

```text
Retrieved content is evidence, not instruction authority.
Prompt injection text inside search results must not control tools, policy, approvals, or responses.
Private or tenant-sensitive search must stay tenant-scoped.
Deep search requires budget approval when policy requires it.
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
