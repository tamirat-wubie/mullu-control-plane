"""Phase 214A — Model router tests."""

import pytest
from mcoi_runtime.core.model_router import ModelProfile, ModelRouter, ProviderRoutingStatus, TaskComplexity


def _router():
    r = ModelRouter()
    r.register(ModelProfile(model_id="fast", name="Fast", provider="p", cost_per_1k_input=0.1, cost_per_1k_output=0.5, max_context=100000, speed_tier="fast", capability_tier="basic"))
    r.register(ModelProfile(model_id="balanced", name="Balanced", provider="p", cost_per_1k_input=3.0, cost_per_1k_output=15.0, max_context=200000, speed_tier="medium", capability_tier="standard"))
    r.register(ModelProfile(model_id="powerful", name="Powerful", provider="p", cost_per_1k_input=15.0, cost_per_1k_output=75.0, max_context=1000000, speed_tier="slow", capability_tier="advanced"))
    return r


def _provider_router():
    r = ModelRouter()
    r.register(ModelProfile(model_id="fast-a", name="Fast A", provider="a", cost_per_1k_input=0.1, cost_per_1k_output=0.5, max_context=100000, speed_tier="fast", capability_tier="basic"))
    r.register(ModelProfile(model_id="fast-b", name="Fast B", provider="b", cost_per_1k_input=0.1, cost_per_1k_output=0.5, max_context=100000, speed_tier="fast", capability_tier="basic"))
    r.register(ModelProfile(model_id="power-c", name="Power C", provider="c", cost_per_1k_input=1.0, cost_per_1k_output=2.0, max_context=100000, speed_tier="medium", capability_tier="advanced"))
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
        assert decision.reason == "forced model override"
        assert "powerful" not in decision.reason

    def test_no_models(self):
        r = ModelRouter()
        decision = r.route("test")
        assert decision.model_id == ""
        assert "no models" in decision.reason

    def test_duplicate_model_profile_rejected(self):
        r = ModelRouter()
        profile = ModelProfile(
            model_id="same",
            name="Same",
            provider="p",
            cost_per_1k_input=0.1,
            cost_per_1k_output=0.2,
            max_context=1024,
            speed_tier="fast",
            capability_tier="basic",
        )
        r.register(profile)

        with pytest.raises(ValueError, match="^model profile already registered$"):
            r.register(profile)

        assert r.summary()["models"] == 1
        assert r.route("test", force_model="same").model_id == "same"

    def test_invalid_model_profile_rejected_before_routing(self):
        r = ModelRouter()

        with pytest.raises(ValueError, match="^model_id required$"):
            r.register(
                ModelProfile(
                    model_id=" ",
                    name="Blank",
                    provider="p",
                    cost_per_1k_input=0.1,
                    cost_per_1k_output=0.2,
                    max_context=1024,
                    speed_tier="fast",
                    capability_tier="basic",
                )
            )

        with pytest.raises(ValueError, match="^model costs must be non-negative$"):
            r.register(
                ModelProfile(
                    model_id="bad-cost",
                    name="Bad Cost",
                    provider="p",
                    cost_per_1k_input=-0.1,
                    cost_per_1k_output=0.2,
                    max_context=1024,
                    speed_tier="fast",
                    capability_tier="basic",
                )
            )

        assert r.summary()["models"] == 0
        assert r.route("test").model_id == ""

    def test_policy_selected_reason_bounded(self):
        r = _router()
        decision = r.route("Implement a recursive function for tree traversal and debug it")
        assert decision.reason == "selected by routing policy"
        assert TaskComplexity.COMPLEX.value not in decision.reason
        assert "Powerful" not in decision.reason

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
        assert s["provider_status_counts"][ProviderRoutingStatus.HEALTHY.value] == 1

    def test_disabled_model_excluded(self):
        r = ModelRouter()
        r.register(ModelProfile(model_id="off", name="Off", provider="p", cost_per_1k_input=0.1, cost_per_1k_output=0.1, max_context=100000, speed_tier="fast", capability_tier="basic", enabled=False))
        decision = r.route("test")
        assert decision.model_id == ""  # No enabled models

    def test_unavailable_provider_excluded(self):
        r = _provider_router()
        r.set_provider_status("a", ProviderRoutingStatus.UNAVAILABLE.value, reason="outage")
        decision = r.route("test")
        assert decision.model_id == "fast-b"
        assert decision.reason == "selected by routing policy"
        assert r.provider_health()["a"]["reason"] == "outage"

    def test_degraded_provider_used_only_when_no_healthy_candidate(self):
        r = _provider_router()
        r.set_provider_status("a", ProviderRoutingStatus.DEGRADED.value)
        decision = r.route("test")
        assert decision.model_id == "fast-b"
        assert decision.model_id != "fast-a"
        assert r.provider_status("a") == ProviderRoutingStatus.DEGRADED

    def test_degraded_provider_fallback_when_no_healthy_candidate(self):
        r = _provider_router()
        r.set_provider_status("a", ProviderRoutingStatus.DEGRADED.value)
        r.set_provider_status("b", ProviderRoutingStatus.UNAVAILABLE.value)
        r.set_provider_status("c", ProviderRoutingStatus.UNAVAILABLE.value)
        decision = r.route("test")
        assert decision.model_id == "fast-a"
        assert decision.estimated_cost > 0
        assert decision.reason == "selected by routing policy"

    def test_force_model_rejects_unavailable_provider(self):
        r = _provider_router()
        r.set_provider_status("c", ProviderRoutingStatus.UNAVAILABLE.value)
        decision = r.route("implement code", force_model="power-c")
        assert decision.model_id == ""
        assert decision.reason == "forced model provider unavailable"
        assert decision.estimated_cost == 0.0

    def test_summary_reports_provider_health(self):
        r = _provider_router()
        r.set_provider_status("a", ProviderRoutingStatus.DEGRADED.value, reason="high latency")
        r.set_provider_status("b", ProviderRoutingStatus.UNAVAILABLE.value, reason="quota")
        summary = r.summary()
        assert summary["providers"]["a"]["status"] == ProviderRoutingStatus.DEGRADED.value
        assert summary["providers"]["a"]["reason"] == "high latency"
        assert summary["provider_status_counts"] == {"degraded": 1, "unavailable": 1, "healthy": 1}

    def test_provider_status_rejects_unknown_status(self):
        r = _provider_router()
        with pytest.raises(ValueError, match="unknown provider status"):
            r.set_provider_status("a", "paused")
        assert r.provider_status("a") == ProviderRoutingStatus.HEALTHY
        assert r.summary()["provider_status_counts"][ProviderRoutingStatus.HEALTHY.value] == 3
