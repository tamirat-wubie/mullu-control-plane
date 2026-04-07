"""Cross-Session Memory — Agent learning across session boundaries.

Purpose: Consolidates insights from completed sessions into persistent
    memory so agents improve over time.  Tenant-scoped, importance-ranked,
    bounded (low-value memories evicted), GDPR-ready (forget by tenant).
Governance scope: memory management only — no decision-making.
Dependencies: none (pure algorithm + threading).
Invariants:
  - Memories are tenant-scoped (no cross-tenant leakage).
  - Memory store is bounded (max entries per tenant).
  - Low-importance memories are evicted first.
  - Deduplication: same content for same identity is merged (importance boosted).
  - Thread-safe — concurrent consolidation + reads are safe.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass, field
from typing import Any, Callable


class MemoryType:
    FACT = "fact"
    PREFERENCE = "preference"
    CORRECTION = "correction"
    PATTERN = "pattern"
    CONTEXT = "context"


@dataclass
class AgentMemory:
    """A single consolidated memory."""

    memory_id: str
    tenant_id: str
    identity_id: str
    memory_type: str
    content: str
    source_session_id: str
    importance: float  # 0.0 to 1.0
    created_at: str
    last_accessed_at: str = ""
    access_count: int = 0
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "memory_id": self.memory_id,
            "tenant_id": self.tenant_id,
            "memory_type": self.memory_type,
            "content": self.content,
            "importance": self.importance,
            "access_count": self.access_count,
            "tags": self.tags,
        }


@dataclass(frozen=True, slots=True)
class MemoryQuery:
    """Query parameters for memory retrieval."""

    tenant_id: str
    identity_id: str = ""
    memory_type: str = ""
    min_importance: float = 0.0
    tags: frozenset[str] = frozenset()
    limit: int = 10


class CrossSessionMemory:
    """Persistent cross-session memory for agent learning.

    Usage:
        mem = CrossSessionMemory(clock=lambda: "2026-04-07T12:00:00Z")

        # After session closes
        mem.add(tenant_id="t1", identity_id="user1",
            memory_type=MemoryType.PREFERENCE,
            content="User prefers concise answers",
            source_session_id="gs-abc", importance=0.8)

        # Before next session
        context = mem.build_context_prompt(MemoryQuery(
            tenant_id="t1", identity_id="user1", limit=5))
    """

    MAX_PER_TENANT = 1000
    MAX_CONTENT = 2000

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._memories: dict[str, list[AgentMemory]] = {}
        self._lock = threading.Lock()
        self._seq = 0
        self._total_added = 0
        self._total_evicted = 0

    def add(
        self, *, tenant_id: str, identity_id: str = "",
        memory_type: str = MemoryType.FACT, content: str,
        source_session_id: str = "", importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> AgentMemory:
        content = content[:self.MAX_CONTENT]
        importance = max(0.0, min(1.0, importance))
        with self._lock:
            self._seq += 1
            mid = f"mem-{hashlib.sha256(f'{tenant_id}:{self._seq}'.encode()).hexdigest()[:12]}"
            tenant_mems = self._memories.setdefault(tenant_id, [])

            # Dedup
            for existing in tenant_mems:
                if existing.content == content and existing.identity_id == identity_id:
                    existing.importance = max(existing.importance, importance)
                    existing.access_count += 1
                    return existing

            # Evict lowest importance if at capacity
            if len(tenant_mems) >= self.MAX_PER_TENANT:
                tenant_mems.sort(key=lambda m: (m.importance, m.access_count))
                tenant_mems.pop(0)
                self._total_evicted += 1

            memory = AgentMemory(
                memory_id=mid, tenant_id=tenant_id, identity_id=identity_id,
                memory_type=memory_type, content=content,
                source_session_id=source_session_id, importance=importance,
                created_at=self._clock(), tags=tags or [],
            )
            tenant_mems.append(memory)
            self._total_added += 1
            return memory

    def recall(self, query: MemoryQuery) -> list[AgentMemory]:
        with self._lock:
            tenant_mems = self._memories.get(query.tenant_id, [])
            results: list[AgentMemory] = []
            for mem in tenant_mems:
                if query.identity_id and mem.identity_id != query.identity_id:
                    continue
                if query.memory_type and mem.memory_type != query.memory_type:
                    continue
                if mem.importance < query.min_importance:
                    continue
                if query.tags and not query.tags.intersection(set(mem.tags)):
                    continue
                results.append(mem)
                mem.last_accessed_at = self._clock()
                mem.access_count += 1
            results.sort(key=lambda m: (-m.importance, -m.access_count))
            return results[:query.limit]

    def build_context_prompt(self, query: MemoryQuery) -> str:
        memories = self.recall(query)
        if not memories:
            return ""
        lines = ["Known context from previous interactions:"]
        for mem in memories:
            prefix = f"[{mem.memory_type}]" if mem.memory_type else ""
            lines.append(f"- {prefix} {mem.content}")
        return "\n".join(lines)

    def forget(self, tenant_id: str, memory_id: str) -> bool:
        with self._lock:
            for i, mem in enumerate(self._memories.get(tenant_id, [])):
                if mem.memory_id == memory_id:
                    self._memories[tenant_id].pop(i)
                    return True
            return False

    def forget_tenant(self, tenant_id: str) -> int:
        """GDPR right to be forgotten."""
        with self._lock:
            return len(self._memories.pop(tenant_id, []))

    def memory_count(self, tenant_id: str = "") -> int:
        with self._lock:
            if tenant_id:
                return len(self._memories.get(tenant_id, []))
            return sum(len(m) for m in self._memories.values())

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {
                "tenants": len(self._memories),
                "total_memories": sum(len(m) for m in self._memories.values()),
                "total_added": self._total_added,
                "total_evicted": self._total_evicted,
            }
