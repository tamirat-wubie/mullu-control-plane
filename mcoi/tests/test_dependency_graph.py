"""Phase 218B — Dependency graph tests."""

import pytest
from mcoi_runtime.core.dependency_graph import DependencyGraph, SubsystemNode


class TestDependencyGraph:
    def _graph(self):
        g = DependencyGraph()
        g.add(SubsystemNode(name="store", version="1.0"))
        g.add(SubsystemNode(name="llm", version="1.0", dependencies=("store",)))
        g.add(SubsystemNode(name="agents", version="1.0", dependencies=("llm", "store")))
        g.add(SubsystemNode(name="workflows", version="1.0", dependencies=("agents", "llm")))
        g.add(SubsystemNode(name="api", version="1.0", dependencies=("workflows",)))
        return g

    def test_dependencies_of(self):
        g = self._graph()
        assert g.dependencies_of("agents") == ["llm", "store"]

    def test_dependents_of(self):
        g = self._graph()
        deps = g.dependents_of("llm")
        assert "agents" in deps
        assert "workflows" in deps

    def test_transitive_deps(self):
        g = self._graph()
        deps = g.transitive_deps("api")
        assert "store" in deps
        assert "llm" in deps
        assert "agents" in deps
        assert "workflows" in deps

    def test_impact_of_failure(self):
        g = self._graph()
        impacted = g.impact_of_failure("store")
        assert "llm" in impacted
        assert "agents" in impacted
        assert "workflows" in impacted
        assert "api" in impacted

    def test_no_cycle(self):
        g = self._graph()
        assert g.detect_cycle() is None

    def test_topological_sort(self):
        g = self._graph()
        order = g.topological_sort()
        # store must come before llm, llm before agents, etc.
        assert order.index("store") < order.index("llm")
        assert order.index("llm") < order.index("agents")
        assert order.index("agents") < order.index("workflows")

    def test_summary(self):
        g = self._graph()
        s = g.summary()
        assert s["subsystems"] == 5
        assert s["has_cycle"] is False
