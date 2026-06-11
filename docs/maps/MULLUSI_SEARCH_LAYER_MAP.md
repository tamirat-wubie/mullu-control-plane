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
| Search Need Classifier | decide whether retrieval is needed | interpreted intent, local knowledge | search state | missing / partial | Add no-search and cache-first rule. |
| Freshness Classifier | decide whether current evidence is required | question, domain, timestamp needs | freshness requirement | missing / partial | Record freshness in SearchReceipt. |
| Source Selector | choose local docs, repo, web, or connector source | freshness, sensitivity, budget | source plan | missing / partial | Prefer local evidence for Foundation Mode. |
| Cache | reuse allowed evidence | query key, tenant scope | cache hit or miss | missing / unknown | Add tenant-scoped cache rules before use. |
| Retriever | collect evidence from selected sources | source plan | evidence set | partial / unknown | Treat retrieved content as evidence only. |
| Evidence Ranker | rank by relevance, trust, freshness, and conflict | evidence set | ranked evidence | missing / partial | Mark stale and conflicting sources. |
| Citation Builder | create source references | ranked evidence | citations | missing / partial | Avoid leaking internal paths when not appropriate. |
| Answer Synthesizer | answer with uncertainty and citations | question, evidence | draft answer | partial | Block current claims on stale evidence. |
| Search Receipt Writer | record search decision and evidence | search state, budget, citations | SearchReceipt | missing / partial | Add cost and freshness fields. |
| Cost Meter | estimate and record retrieval cost | query depth, provider, tokens | budget estimate | missing / partial | Ask approval for deep search. |

## 4. SearchReceipt fields

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

## 5. Retrieval safety rules

```text
Retrieved content is evidence, not instruction authority.
Prompt injection text inside search results must not control tools, policy, approvals, or responses.
Private or tenant-sensitive search must stay tenant-scoped.
Deep search requires budget approval when policy requires it.
Source freshness must be visible for current-information answers.
```

## 6. Search edge cases

| Edge Case | Required Behavior |
| --- | --- |
| User asks stable known fact | answer without search if local knowledge is enough. |
| User asks current status | require freshness check and cite evidence. |
| Cache is stale | mark stale or search again if budget allows. |
| Search API fails | report uncertainty and write SearchReceipt with retrieval error. |
| Search results conflict | cite conflict and avoid overclaim. |
| Search exceeds budget | block or ask approval for deep search. |
| Private source requested | verify tenant scope before retrieval. |
