"""Phase 218C — Backpressure engine tests."""

import pytest
from mcoi_runtime.core.backpressure import BackpressureEngine, PressureLevel


class TestBackpressure:
    def test_normal(self):
        bp = BackpressureEngine()
        bp.update_load(30.0)
        state = bp.evaluate()
        assert state.level == PressureLevel.NORMAL
        assert state.should_shed is False
        assert state.delay_ms == 0.0

    def test_elevated(self):
        bp = BackpressureEngine()
        bp.update_load(70.0)
        state = bp.evaluate()
        assert state.level == PressureLevel.ELEVATED
        assert state.delay_ms > 0

    def test_high(self):
        bp = BackpressureEngine()
        bp.update_load(90.0)
        state = bp.evaluate()
        assert state.level == PressureLevel.HIGH
        assert state.delay_ms >= 500.0

    def test_critical(self):
        bp = BackpressureEngine()
        bp.update_load(98.0)
        state = bp.evaluate()
        assert state.level == PressureLevel.CRITICAL
        assert state.delay_ms >= 1000.0

    def test_critical_sheds_non_essential(self):
        bp = BackpressureEngine()
        bp.update_load(98.0)
        state = bp.evaluate(is_essential=False)
        assert state.should_shed is True

    def test_critical_keeps_essential(self):
        bp = BackpressureEngine()
        bp.update_load(98.0)
        state = bp.evaluate(is_essential=True)
        assert state.should_shed is False

    def test_recovery(self):
        bp = BackpressureEngine()
        bp.update_load(95.0)
        assert bp.current_level == PressureLevel.CRITICAL  # 95 >= 95 threshold
        bp.update_load(30.0)
        assert bp.current_level == PressureLevel.NORMAL

    def test_clamp(self):
        bp = BackpressureEngine()
        bp.update_load(150.0)
        assert bp.evaluate().load_pct == 100.0
        bp.update_load(-10.0)
        assert bp.evaluate().load_pct == 0.0

    def test_custom_thresholds(self):
        bp = BackpressureEngine(elevated_threshold=40.0)
        bp.update_load(50.0)
        assert bp.current_level == PressureLevel.ELEVATED

    def test_status(self):
        bp = BackpressureEngine()
        bp.update_load(50.0)
        s = bp.status()
        assert s["level"] == "normal"
        assert s["load_pct"] == 50.0
