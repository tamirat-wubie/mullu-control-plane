"""Phase 216B — A/B testing tests."""

import pytest
from mcoi_runtime.core.ab_testing import ABTestEngine

FIXED_CLOCK = lambda: "2026-03-26T12:00:00Z"


class _StubResult:
    def __init__(self, content, cost=0.001, tokens=10):
        self.content = content
        self.cost = cost
        self.total_tokens = tokens
        self.succeeded = True


class TestABTestEngine:
    def test_single_model(self):
        eng = ABTestEngine(clock=FIXED_CLOCK)
        result = eng.run_experiment("test", {"model_a": lambda p: _StubResult("hello")})
        assert result.winner == "model_a"
        assert len(result.variants) == 1

    def test_two_models_cost(self):
        eng = ABTestEngine(clock=FIXED_CLOCK)
        result = eng.run_experiment("test", {
            "cheap": lambda p: _StubResult("ok", cost=0.001),
            "expensive": lambda p: _StubResult("ok", cost=0.010),
        }, criteria="cost")
        assert result.winner == "cheap"

    def test_two_models_speed(self):
        eng = ABTestEngine(clock=FIXED_CLOCK)
        # Both instant — first should win by default
        result = eng.run_experiment("test", {
            "a": lambda p: _StubResult("a"),
            "b": lambda p: _StubResult("b"),
        }, criteria="speed")
        assert result.winner in ("a", "b")

    def test_quality_criteria(self):
        eng = ABTestEngine(clock=FIXED_CLOCK)
        result = eng.run_experiment("test", {
            "short": lambda p: _StubResult("ok"),
            "long": lambda p: _StubResult("a very long detailed answer"),
        }, criteria="quality")
        assert result.winner == "long"

    def test_failed_model(self):
        eng = ABTestEngine(clock=FIXED_CLOCK)
        result = eng.run_experiment("test", {
            "good": lambda p: _StubResult("ok"),
            "broken": lambda p: (_ for _ in ()).throw(RuntimeError("fail")),
        })
        assert result.winner == "good"

    def test_all_failed(self):
        eng = ABTestEngine(clock=FIXED_CLOCK)
        result = eng.run_experiment("test", {
            "a": lambda p: (_ for _ in ()).throw(RuntimeError("fail")),
        })
        assert result.winner == ""

    def test_win_rates(self):
        eng = ABTestEngine(clock=FIXED_CLOCK)
        eng.run_experiment("a", {"x": lambda p: _StubResult("a", cost=0.001), "y": lambda p: _StubResult("b", cost=0.01)}, criteria="cost")
        eng.run_experiment("b", {"x": lambda p: _StubResult("a", cost=0.001), "y": lambda p: _StubResult("b", cost=0.01)}, criteria="cost")
        rates = eng.win_rates()
        assert rates["x"] == 1.0

    def test_summary(self):
        eng = ABTestEngine(clock=FIXED_CLOCK)
        eng.run_experiment("test", {"a": lambda p: _StubResult("ok")})
        s = eng.summary()
        assert s["total_experiments"] == 1
