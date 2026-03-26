"""Phase 218B — Dependency Graph Engine.

Purpose: Tracks subsystem dependencies for startup ordering,
    impact analysis, and failure propagation understanding.
Governance scope: dependency metadata only.
Invariants:
  - Circular dependencies are detected.
  - Topological sort produces valid startup order.
  - Impact analysis is computed, never hardcoded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SubsystemNode:
    """A subsystem in the dependency graph."""

    name: str
    version: str
    healthy: bool = True
    dependencies: tuple[str, ...] = ()


class DependencyGraph:
    """Directed acyclic graph of subsystem dependencies."""

    def __init__(self) -> None:
        self._nodes: dict[str, SubsystemNode] = {}

    def add(self, node: SubsystemNode) -> None:
        self._nodes[node.name] = node

    def get(self, name: str) -> SubsystemNode | None:
        return self._nodes.get(name)

    def dependencies_of(self, name: str) -> list[str]:
        """Direct dependencies of a subsystem."""
        node = self._nodes.get(name)
        return list(node.dependencies) if node else []

    def dependents_of(self, name: str) -> list[str]:
        """Subsystems that depend on this one."""
        return sorted(n.name for n in self._nodes.values() if name in n.dependencies)

    def transitive_deps(self, name: str, _visited: set[str] | None = None) -> set[str]:
        """All transitive dependencies."""
        if _visited is None:
            _visited = set()
        node = self._nodes.get(name)
        if not node:
            return _visited
        for dep in node.dependencies:
            if dep not in _visited:
                _visited.add(dep)
                self.transitive_deps(dep, _visited)
        return _visited

    def impact_of_failure(self, name: str) -> list[str]:
        """All subsystems impacted if this one fails (transitive dependents)."""
        impacted: set[str] = set()
        queue = [name]
        while queue:
            current = queue.pop(0)
            for dep in self.dependents_of(current):
                if dep not in impacted:
                    impacted.add(dep)
                    queue.append(dep)
        return sorted(impacted)

    def detect_cycle(self) -> list[str] | None:
        """Detect circular dependencies. Returns cycle path or None."""
        visited: set[str] = set()
        in_stack: set[str] = set()
        path: list[str] = []

        def dfs(name: str) -> list[str] | None:
            visited.add(name)
            in_stack.add(name)
            path.append(name)
            node = self._nodes.get(name)
            if node:
                for dep in node.dependencies:
                    if dep not in visited:
                        result = dfs(dep)
                        if result:
                            return result
                    elif dep in in_stack:
                        idx = path.index(dep)
                        return path[idx:] + [dep]
            path.pop()
            in_stack.discard(name)
            return None

        for name in self._nodes:
            if name not in visited:
                result = dfs(name)
                if result:
                    return result
        return None

    def topological_sort(self) -> list[str]:
        """Startup order — dependencies first."""
        visited: set[str] = set()
        order: list[str] = []

        def dfs(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            node = self._nodes.get(name)
            if node:
                for dep in node.dependencies:
                    dfs(dep)
            order.append(name)

        for name in sorted(self._nodes):
            dfs(name)
        return order

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    def summary(self) -> dict[str, Any]:
        healthy = sum(1 for n in self._nodes.values() if n.healthy)
        return {
            "subsystems": self.node_count,
            "healthy": healthy,
            "unhealthy": self.node_count - healthy,
            "has_cycle": self.detect_cycle() is not None,
        }
