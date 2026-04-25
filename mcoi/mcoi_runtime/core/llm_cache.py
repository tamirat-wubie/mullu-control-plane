"""LLM Response Cache — Avoid redundant provider calls for identical prompts.

Purpose: Cache LLM responses keyed on (provider, model, prompt_hash) so
    identical requests return cached results without calling the provider.
    Saves cost, reduces latency, and protects against provider outages
    for repeated queries.
Governance scope: caching only — does not modify LLM behavior.
Dependencies: none (pure algorithm + threading).
Invariants:
  - Cache key is SHA-256 of (provider, model, prompt) — no collisions.
  - Cache is TTL-bounded — stale results expire automatically.
  - Cache is tenant-scoped — cross-tenant cache pollution impossible.
  - Bounded capacity with LRU eviction.
  - Thread-safe — concurrent reads/writes are safe.
  - Cache misses are transparent — caller doesn't know if cached.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable, Mapping


NO_POLICY_CONTEXT_HASH = "policy:none"


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """A cached LLM response."""

    cache_key: str
    tenant_id: str
    provider: str
    model: str
    prompt_hash: str
    prompt_text: str
    response: Any  # The LLM result object
    cached_at: float
    ttl_seconds: float
    policy_context_hash: str = NO_POLICY_CONTEXT_HASH
    policy_context: Mapping[str, Any] | None = None
    approval_proof_id: str = ""
    approval_guard_chain: tuple[str, ...] = ()
    token_count: int = 0  # Total tokens (for cost tracking)


@dataclass(frozen=True, slots=True)
class CacheLookupResult:
    """Result of a cache lookup."""

    hit: bool
    response: Any | None = None
    cache_key: str = ""
    age_seconds: float = 0.0
    hit_kind: str = "miss"
    similarity: float = 0.0
    policy_context_hash: str = NO_POLICY_CONTEXT_HASH
    invalidation_reason: str = ""


class LLMResponseCache:
    """TTL-bounded LRU cache for LLM responses.

    Usage:
        cache = LLMResponseCache()

        # Check cache before calling provider
        result = cache.get("t1", "anthropic", "claude-sonnet", "What is 2+2?")
        if result.hit:
            return result.response

        # Call provider, then cache
        llm_result = provider.complete(prompt)
        cache.put("t1", "anthropic", "claude-sonnet", "What is 2+2?", llm_result)
    """

    MAX_ENTRIES = 10_000
    DEFAULT_TTL = 300.0  # 5 minutes

    def __init__(
        self,
        *,
        default_ttl: float = DEFAULT_TTL,
        max_entries: int = MAX_ENTRIES,
        clock: Callable[[], float] | None = None,
        enable_semantic_lookup: bool = False,
        semantic_threshold: float = 0.8,
    ) -> None:
        if default_ttl <= 0:
            raise ValueError("default_ttl must be > 0")
        if max_entries <= 0:
            raise ValueError("max_entries must be > 0")
        if semantic_threshold < 0.0 or semantic_threshold > 1.0:
            raise ValueError("semantic_threshold must be between 0 and 1")
        self._default_ttl = default_ttl
        self._max_entries = max_entries
        self._clock = clock or time.monotonic
        self._enable_semantic_lookup = enable_semantic_lookup
        self._semantic_threshold = semantic_threshold
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.Lock()
        self._hit_count = 0
        self._miss_count = 0
        self._evicted_count = 0
        self._saved_cost = 0.0

    @staticmethod
    def _make_key(
        tenant_id: str,
        provider: str,
        model: str,
        prompt: str,
        policy_context_hash: str = NO_POLICY_CONTEXT_HASH,
    ) -> str:
        """Build cache key from tenant, provider, model, prompt, and policy hash."""
        content = f"{tenant_id}:{provider}:{model}:{policy_context_hash}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()[:24]

    @staticmethod
    def _prompt_hash(prompt: str) -> str:
        return hashlib.sha256(prompt.encode()).hexdigest()[:16]

    @staticmethod
    def _policy_context_hash(policy_context: Mapping[str, Any] | None) -> str:
        """Return deterministic governance context hash for cache identity."""
        if not policy_context:
            return NO_POLICY_CONTEXT_HASH
        canonical = json.dumps(dict(policy_context), sort_keys=True, separators=(",", ":"), default=str)
        return f"policy:{hashlib.sha256(canonical.encode()).hexdigest()[:16]}"

    def get(
        self,
        tenant_id: str,
        provider: str,
        model: str,
        prompt: str,
        *,
        policy_context: Mapping[str, Any] | None = None,
        semantic: bool | None = None,
    ) -> CacheLookupResult:
        """Look up a cached LLM response."""
        policy_context_hash = self._policy_context_hash(policy_context)
        key = self._make_key(tenant_id, provider, model, prompt, policy_context_hash)
        semantic_lookup_enabled = self._enable_semantic_lookup if semantic is None else semantic

        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                if semantic_lookup_enabled:
                    semantic_result = self._semantic_lookup(
                        tenant_id=tenant_id,
                        provider=provider,
                        model=model,
                        prompt=prompt,
                        policy_context_hash=policy_context_hash,
                    )
                    if semantic_result is not None:
                        self._hit_count += 1
                        return semantic_result
                self._miss_count += 1
                return CacheLookupResult(
                    hit=False,
                    cache_key=key,
                    policy_context_hash=policy_context_hash,
                    invalidation_reason="miss",
                )

            now = self._clock()
            age = now - entry.cached_at
            if age > entry.ttl_seconds:
                # Expired
                del self._entries[key]
                self._evicted_count += 1
                self._miss_count += 1
                return CacheLookupResult(
                    hit=False,
                    cache_key=key,
                    policy_context_hash=policy_context_hash,
                    invalidation_reason="ttl_expired",
                )

            # Cache hit — move to end (most recently used)
            self._entries.move_to_end(key)
            self._hit_count += 1
            return CacheLookupResult(
                hit=True,
                response=entry.response,
                cache_key=key,
                age_seconds=round(age, 2),
                hit_kind="exact",
                similarity=1.0,
                policy_context_hash=policy_context_hash,
            )

    def put(
        self,
        tenant_id: str,
        provider: str,
        model: str,
        prompt: str,
        response: Any,
        *,
        ttl: float = 0.0,
        cost: float = 0.0,
        token_count: int = 0,
        policy_context: Mapping[str, Any] | None = None,
        approval_proof_id: str = "",
        approval_guard_chain: tuple[str, ...] = (),
    ) -> str:
        """Cache an LLM response. Returns the cache key."""
        policy_context_hash = self._policy_context_hash(policy_context)
        key = self._make_key(tenant_id, provider, model, prompt, policy_context_hash)
        effective_ttl = ttl if ttl > 0 else self._default_ttl

        with self._lock:
            # Capacity enforcement — evict LRU
            if len(self._entries) >= self._max_entries and key not in self._entries:
                self._entries.popitem(last=False)
                self._evicted_count += 1

            self._entries[key] = CacheEntry(
                cache_key=key,
                tenant_id=tenant_id,
                provider=provider,
                model=model,
                prompt_hash=self._prompt_hash(prompt),
                prompt_text=prompt,
                response=response,
                cached_at=self._clock(),
                ttl_seconds=effective_ttl,
                policy_context_hash=policy_context_hash,
                policy_context=dict(policy_context) if policy_context is not None else None,
                approval_proof_id=approval_proof_id,
                approval_guard_chain=tuple(approval_guard_chain),
                token_count=token_count,
            )
            self._entries.move_to_end(key)
            if cost > 0:
                self._saved_cost += cost

        return key

    def invalidate(
        self,
        tenant_id: str,
        provider: str,
        model: str,
        prompt: str,
        *,
        policy_context: Mapping[str, Any] | None = None,
    ) -> bool:
        """Remove a specific cached response."""
        key = self._make_key(
            tenant_id,
            provider,
            model,
            prompt,
            self._policy_context_hash(policy_context),
        )
        with self._lock:
            if key in self._entries:
                del self._entries[key]
                return True
            return False

    def invalidate_policy_context(self, policy_context: Mapping[str, Any] | None) -> int:
        """Remove all cached responses bound to one policy context."""
        policy_context_hash = self._policy_context_hash(policy_context)
        with self._lock:
            to_remove = [k for k, e in self._entries.items() if e.policy_context_hash == policy_context_hash]
            for k in to_remove:
                del self._entries[k]
            return len(to_remove)

    def invalidate_policy_version(self, policy_version: str) -> int:
        """Remove all cached responses approved under one policy version."""
        with self._lock:
            to_remove = [
                key for key, entry in self._entries.items()
                if entry.policy_context is not None
                and str(entry.policy_context.get("policy_version", "")) == policy_version
            ]
            for key in to_remove:
                del self._entries[key]
            return len(to_remove)

    def invalidate_tenant(self, tenant_id: str) -> int:
        """Remove all cached responses for a tenant."""
        with self._lock:
            to_remove = [k for k, e in self._entries.items() if e.tenant_id == tenant_id]
            for k in to_remove:
                del self._entries[k]
            return len(to_remove)

    def clear(self) -> int:
        """Clear entire cache. Returns count of entries removed."""
        with self._lock:
            count = len(self._entries)
            self._entries.clear()
            return count

    def _semantic_lookup(
        self,
        *,
        tenant_id: str,
        provider: str,
        model: str,
        prompt: str,
        policy_context_hash: str,
    ) -> CacheLookupResult | None:
        now = self._clock()
        best_entry: CacheEntry | None = None
        best_score = 0.0

        for key, entry in list(self._entries.items()):
            age = now - entry.cached_at
            if age > entry.ttl_seconds:
                del self._entries[key]
                self._evicted_count += 1
                continue
            if entry.tenant_id != tenant_id:
                continue
            if entry.provider != provider or entry.model != model:
                continue
            if entry.policy_context_hash != policy_context_hash:
                continue
            score = _semantic_similarity(prompt, entry.prompt_text)
            if score >= self._semantic_threshold and score > best_score:
                best_entry = entry
                best_score = score

        if best_entry is None:
            return None
        self._entries.move_to_end(best_entry.cache_key)
        return CacheLookupResult(
            hit=True,
            response=best_entry.response,
            cache_key=best_entry.cache_key,
            age_seconds=round(now - best_entry.cached_at, 2),
            hit_kind="semantic",
            similarity=round(best_score, 4),
            policy_context_hash=policy_context_hash,
        )

    @property
    def entry_count(self) -> int:
        return len(self._entries)

    @property
    def hit_count(self) -> int:
        return self._hit_count

    @property
    def miss_count(self) -> int:
        return self._miss_count

    def hit_rate(self) -> float:
        total = self._hit_count + self._miss_count
        return round(self._hit_count / total, 4) if total > 0 else 0.0

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "entries": len(self._entries),
                "capacity": self._max_entries,
                "hits": self._hit_count,
                "misses": self._miss_count,
                "hit_rate": self.hit_rate(),
                "evicted": self._evicted_count,
                "saved_cost": round(self._saved_cost, 4),
                "default_ttl": self._default_ttl,
                "semantic_lookup_enabled": self._enable_semantic_lookup,
                "semantic_threshold": self._semantic_threshold,
            }


def _semantic_similarity(left: str, right: str) -> float:
    """Return deterministic token-overlap similarity for semantic cache reuse."""
    left_terms = set(_tokenize_for_semantic_cache(left))
    right_terms = set(_tokenize_for_semantic_cache(right))
    if not left_terms or not right_terms:
        return 0.0
    union = len(left_terms | right_terms)
    if union == 0:
        return 0.0
    return len(left_terms & right_terms) / union


def _tokenize_for_semantic_cache(text: str) -> tuple[str, ...]:
    return tuple(
        token.strip(".,!?;:'\"()[]{}").lower()
        for token in text.split()
        if len(token.strip(".,!?;:'\"()[]{}")) > 1
    )
