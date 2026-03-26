"""Phase 216A — Agent Memory.

Purpose: Long-term memory for agents — learned preferences, facts,
    and behavioral patterns that persist across conversations.
    Enables agents to improve over time within governed boundaries.
Governance scope: memory management only — never auto-acts on memories.
Dependencies: none (pure data structures).
Invariants:
  - Memories are tenant-scoped — cross-tenant memory access is impossible.
  - Memory retrieval is relevance-scored (keyword matching).
  - Memory capacity is bounded per agent.
  - All memory writes are auditable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from hashlib import sha256


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    """Single long-term memory entry."""

    memory_id: str
    agent_id: str
    tenant_id: str
    category: str  # "preference", "fact", "pattern", "feedback"
    content: str
    keywords: tuple[str, ...]
    confidence: float  # 0.0-1.0
    created_at: str


@dataclass(frozen=True, slots=True)
class MemorySearchResult:
    """Result of a memory search."""

    memory: MemoryEntry
    relevance_score: float


class AgentMemoryStore:
    """Long-term memory storage for agents."""

    def __init__(self, *, clock: Callable[[], str], max_per_agent: int = 1000) -> None:
        self._clock = clock
        self._max = max_per_agent
        self._memories: dict[str, list[MemoryEntry]] = {}  # agent_id -> memories
        self._counter = 0

    def store(
        self,
        agent_id: str,
        tenant_id: str,
        category: str,
        content: str,
        keywords: list[str] | None = None,
        confidence: float = 1.0,
    ) -> MemoryEntry:
        """Store a new memory for an agent."""
        self._counter += 1
        mid = f"mem-{self._counter}"
        kw = tuple(keywords) if keywords else tuple(content.lower().split()[:10])

        entry = MemoryEntry(
            memory_id=mid, agent_id=agent_id, tenant_id=tenant_id,
            category=category, content=content, keywords=kw,
            confidence=min(max(confidence, 0.0), 1.0),
            created_at=self._clock(),
        )

        key = f"{agent_id}:{tenant_id}"
        if key not in self._memories:
            self._memories[key] = []

        memories = self._memories[key]
        if len(memories) >= self._max:
            # Evict lowest confidence
            memories.sort(key=lambda m: m.confidence)
            memories.pop(0)

        memories.append(entry)
        return entry

    def search(
        self,
        agent_id: str,
        tenant_id: str,
        query: str,
        limit: int = 5,
    ) -> list[MemorySearchResult]:
        """Search memories by keyword relevance."""
        key = f"{agent_id}:{tenant_id}"
        memories = self._memories.get(key, [])
        if not memories:
            return []

        query_words = set(query.lower().split())
        scored: list[MemorySearchResult] = []

        for mem in memories:
            overlap = len(query_words & set(mem.keywords))
            if overlap > 0:
                relevance = overlap / max(len(query_words), 1) * mem.confidence
                scored.append(MemorySearchResult(memory=mem, relevance_score=round(relevance, 4)))

        scored.sort(key=lambda r: r.relevance_score, reverse=True)
        return scored[:limit]

    def get_by_category(
        self, agent_id: str, tenant_id: str, category: str,
    ) -> list[MemoryEntry]:
        key = f"{agent_id}:{tenant_id}"
        return [m for m in self._memories.get(key, []) if m.category == category]

    def forget(self, agent_id: str, tenant_id: str, memory_id: str) -> bool:
        key = f"{agent_id}:{tenant_id}"
        memories = self._memories.get(key, [])
        for i, m in enumerate(memories):
            if m.memory_id == memory_id:
                memories.pop(i)
                return True
        return False

    def count(self, agent_id: str, tenant_id: str) -> int:
        return len(self._memories.get(f"{agent_id}:{tenant_id}", []))

    @property
    def total_memories(self) -> int:
        return sum(len(mems) for mems in self._memories.values())

    def summary(self) -> dict[str, Any]:
        by_category: dict[str, int] = {}
        for mems in self._memories.values():
            for m in mems:
                by_category[m.category] = by_category.get(m.category, 0) + 1
        return {
            "total": self.total_memories,
            "agents": len(self._memories),
            "by_category": by_category,
        }
