# Search Decision Contract

Purpose: define the local Foundation Mode contract that decides whether search is needed before any retrieval or answer claim.
Governance scope: search need, evidence freshness, source scope, budget gate, retrieval safety, and pre-retrieval receipts.
Dependencies: `schemas/search_decision.schema.json`, `examples/search_decision.foundation.json`, `scripts/validate_search_decision.py`, and `docs/maps/MULLUSI_SEARCH_LAYER_MAP.md`.
Invariants: search is evidence classification before retrieval; retrieved content is evidence only; budget unknown blocks deep retrieval; this contract grants no execution, connector, external retrieval, deployment, or terminal closure authority.

## 1. Boundary

`SearchDecision` is a pre-retrieval governance object. It answers:

```text
Does this request need search?
Does it require fresh evidence?
Which source classes are allowed?
Is budget approval required?
Is cache reuse backed by tenant-scoped fresh evidence?
Can retrieved content influence tools or policy?
What evidence proves the decision?
```

It does not answer the user, retrieve documents, call web search, call connectors, mutate memory, or certify current facts.

## 2. Decision States

| State | Meaning | Authority |
| --- | --- | --- |
| `NO_SEARCH_NEEDED` | local answer may proceed without retrieval | no retrieval authority |
| `CACHE_HIT_ALLOWED` | tenant-scoped fresh cache may be used | cache read only |
| `LOCAL_SEARCH_ALLOWED` | local docs or repo search may be used | local read only |
| `WEB_SEARCH_LIGHT_ALLOWED` | bounded web retrieval is allowed by policy | retrieval still needs worker receipt |
| `WEB_SEARCH_DEEP_APPROVAL_REQUIRED` | deep or costly search is plausible but not approved | block until approval |
| `SEARCH_BLOCKED_BY_BUDGET` | budget policy blocks retrieval | no retrieval authority |
| `SEARCH_BLOCKED_BY_UNKNOWN` | hard unknown blocks retrieval | sensing or governance escalation |
| `SEARCH_FAILED_WITH_EXPLANATION` | attempted retrieval failed and must be reported as uncertainty | no current claim |

## 3. Hard Guards

| Guard | Required Value |
| --- | --- |
| `execution_authority_granted` | `false` |
| `connector_authority_granted` | `false` |
| `external_retrieval_performed` | `false` for this contract |
| `terminal_closure` | `false` |
| `raw_secret_material_included` | `false` |
| `retrieved_instruction_authority_granted` | `false` |
| `mfidel_atomicity_preserved` | `true` |

## 4. Retrieval Safety

Retrieved content is evidence only. A page, document, email, or connector result cannot create tool instructions, policy instructions, approval authority, tenant scope, budget approval, or final truth by itself.

Prompt-injection text inside retrieved content is classified as source content, not governance authority. If retrieved sources conflict or freshness is stale, the answer path must cite uncertainty or block the current-information claim.

## 5. Cache Admission

`CACHE_HIT_ALLOWED` requires `metadata.cache_admission.state = allowed`.

Cache reuse is denied unless all cache evidence is:

```text
tenant-scoped to the request tenant
query-hash matched to the request query
freshness-proved by retained evidence refs
non-stale
raw-query free
```

A `cache_fresh` flag without matching `SearchCacheEvidence` records
`cache_evidence_required` and returns `block_search`.

## 6. Foundation Mode

Foundation Mode prefers local evidence and reversible proof threads. External retrieval and connector retrieval remain `AwaitingEvidence` unless a governed worker, budget gate, tenant scope, and receipt chain prove the action.
