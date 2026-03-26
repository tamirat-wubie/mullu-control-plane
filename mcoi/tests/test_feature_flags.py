"""Phase 220 — Feature flags tests."""

import pytest
from mcoi_runtime.core.feature_flags import FeatureFlag, FeatureFlagEngine


class TestFeatureFlags:
    def test_default_disabled(self):
        eng = FeatureFlagEngine()
        eng.register(FeatureFlag(flag_id="dark_mode", name="Dark Mode"))
        assert eng.is_enabled("dark_mode") is False

    def test_enabled(self):
        eng = FeatureFlagEngine()
        eng.register(FeatureFlag(flag_id="v2", name="V2", enabled=True))
        assert eng.is_enabled("v2") is True

    def test_unknown_flag(self):
        eng = FeatureFlagEngine()
        assert eng.is_enabled("nonexistent") is False

    def test_tenant_override(self):
        eng = FeatureFlagEngine()
        eng.register(FeatureFlag(
            flag_id="beta", name="Beta", enabled=False,
            tenant_overrides={"t1": True, "t2": False},
        ))
        assert eng.is_enabled("beta") is False
        assert eng.is_enabled("beta", tenant_id="t1") is True
        assert eng.is_enabled("beta", tenant_id="t2") is False
        assert eng.is_enabled("beta", tenant_id="t3") is False  # Falls back to default

    def test_set_enabled(self):
        eng = FeatureFlagEngine()
        eng.register(FeatureFlag(flag_id="x", name="X"))
        assert eng.is_enabled("x") is False
        eng.set_enabled("x", True)
        assert eng.is_enabled("x") is True

    def test_list_flags(self):
        eng = FeatureFlagEngine()
        eng.register(FeatureFlag(flag_id="b", name="B"))
        eng.register(FeatureFlag(flag_id="a", name="A"))
        flags = eng.list_flags()
        assert flags[0].flag_id == "a"

    def test_summary(self):
        eng = FeatureFlagEngine()
        eng.register(FeatureFlag(flag_id="on", name="On", enabled=True))
        eng.register(FeatureFlag(flag_id="off", name="Off", enabled=False))
        s = eng.summary()
        assert s["total"] == 2
        assert s["enabled"] == 1
