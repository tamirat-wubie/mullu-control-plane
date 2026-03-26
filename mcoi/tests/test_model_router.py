"""Phase 214A — Model router tests."""

import pytest
from mcoi_runtime.core.model_router import ModelProfile, ModelRouter, TaskComplexity


def _router():
    r = ModelRouter()
    r.register(ModelProfile(model_id="fast", name="Fast", provider="p", cost_per_1k_input=0.1, cost_per_1k_output=0.5, max_context=100000, speed_tier="fast", capability_tier="basic"))
    r.register(ModelProfile(model_id="balanced", name="Balanced", provider="p", cost_per_1k_input=3.0, cost_per_1k_output=15.0, max_context=200000, speed_tier="medium", capability_tier="standard"))
    r.register(ModelProfile(model_id="powerful", name="Powerful", provider="p", cost_per_1k_input=15.0, cost_per_1k_output=75.0, max_context=1000000, speed_tier="slow", capability_tier="advanced"))
    return r


class TestModelRouter:
    def test_classify_simple(self):
        r = _router()
        assert r.classify_complexity("What is 2+2?") == TaskComplexity.SIMPLE

    def test_classify_moderate(self):
        r = _router()
        assert r.classify_complexity("Analyze the following data and provide insights: " + "x " * 60) == TaskComplexity.MODERATE

    def test_classify_complex(self):
        r = _router()
        assert r.classify_complexity("Implement a function that sorts a list and debug it step by step") == TaskComplexity.COMPLEX

    def test_route_simple(self):
        r = _router()
        decision = r.route("What is 2+2?")
        assert decision.complexity == TaskComplexity.SIMPLE
        assert decision.model_id in ("fast", "balanced")  # Should prefer fast/cheap

    def test_route_complex(self):
        r = _router()
        decision = r.route("Implement a recursive function for tree traversal and debug it")
        assert decision.complexity == TaskComplexity.COMPLEX

    def test_force_model(self):
        r = _router()
        decision = r.route("hello", force_model="powerful")
        assert decision.model_id == "powerful"
        assert "forced" in decision.reason

    def test_no_models(self):
        r = ModelRouter()
        decision = r.route("test")
        assert decision.model_id == ""
        assert "no models" in decision.reason

    def test_alternatives(self):
        r = _router()
        decision = r.route("moderate analysis task")
        assert isinstance(decision.alternatives, tuple)

    def test_history(self):
        r = _router()
        r.route("a")
        r.route("b")
        assert len(r.history()) == 2

    def test_summary(self):
        r = _router()
        r.route("simple")
        s = r.summary()
        assert s["models"] == 3
        assert s["routing_decisions"] == 1

    def test_disabled_model_excluded(self):
        r = ModelRouter()
        r.register(ModelProfile(model_id="off", name="Off", provider="p", cost_per_1k_input=0.1, cost_per_1k_output=0.1, max_context=100000, speed_tier="fast", capability_tier="basic", enabled=False))
        decision = r.route("test")
        assert decision.model_id == ""  # No enabled models
