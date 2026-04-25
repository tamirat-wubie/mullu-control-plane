# Governed Semantic Cache Protocol

Purpose: define cache reuse for model responses when prompts are identical or semantically equivalent under the same governance context.

Governance scope: response reuse only. Cached responses are not trusted world state and do not bypass request-envelope governance.

## Invariants

1. Cache identity includes `tenant_id`, `provider`, `model`, `prompt`, and `policy_context_hash`.
2. `policy_context_hash` is the deterministic hash of the approval policy context.
3. Each cache entry records the policy context, approval proof id, and guard-chain stages that approved storage.
4. Semantic hits are allowed only within the same `tenant_id`, `provider`, `model`, and `policy_context_hash`.
5. Policy version changes are cache misses unless the new version hashes to the same policy context.
6. Explicit policy invalidation removes all entries approved under the affected policy version or context.
7. TTL and LRU limits still apply before exact or semantic reuse.

## Lookup Semantics

| Stage | Condition | Result |
| --- | --- | --- |
| Exact lookup | Key matches and TTL is valid | `hit_kind=exact`, `similarity=1.0` |
| Semantic lookup | Exact key misses, semantic lookup enabled, same policy hash, similarity >= threshold | `hit_kind=semantic` |
| Policy mismatch | Prompt matches but policy context differs | miss |
| Expired entry | TTL exceeded | miss with `invalidation_reason=ttl_expired` |
| Version invalidation | `invalidate_policy_version(version)` called | matching entries removed |

## Current Implementation

Runtime: `mcoi_runtime.core.llm_cache.LLMResponseCache`

Deterministic similarity: normalized token-overlap. This is intentionally simple until a governed embedding backend is available. Any future embedding implementation must preserve the policy-context partition and must not reuse responses across policy versions.

Session integration: `GovernedSession.llm()` binds cache calls to a stable `session-governance:v1` policy context so equivalent governed requests can reuse entries after the normal session guard path has run.

STATUS:
  Completeness: 100%
  Invariants verified: [tenant partition, policy partition, semantic threshold, TTL, LRU, explicit invalidation]
  Open issues: none
  Next action: benchmark hit ratio and governance-correctness once pilot traces exist
