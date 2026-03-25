"""Tests for Phase 162 — Self-Serve Enterprise Expansion."""
from mcoi_runtime.pilot.enterprise_expansion import (
    PACK_TO_BUNDLE_MAP,
    BUNDLE_SAVINGS,
    BundleUpgradeOffer,
    recommend_bundle_upgrade,
    InProductExpansionEngine,
    LowTouchBundleFlow,
)

# --- recommend_bundle_upgrade ---

def test_recommend_eligible():
    offer = recommend_bundle_upgrade("regulated_ops", 0.8, 9.0, 4)
    assert offer is not None
    assert offer.recommended_bundle == "regulated_financial_bundle"
    assert offer.monthly_savings == 1200.0

def test_recommend_low_activation_returns_none():
    assert recommend_bundle_upgrade("regulated_ops", 0.3, 9.0, 4) is None

def test_recommend_low_satisfaction_returns_none():
    assert recommend_bundle_upgrade("regulated_ops", 0.8, 5.0, 4) is None

def test_recommend_too_few_months_returns_none():
    assert recommend_bundle_upgrade("regulated_ops", 0.8, 9.0, 1) is None

def test_recommend_unknown_pack_returns_none():
    assert recommend_bundle_upgrade("unknown_pack", 0.9, 10.0, 12) is None

# --- PACK_TO_BUNDLE_MAP ---

def test_pack_to_bundle_map_coverage():
    for pack, bundle in PACK_TO_BUNDLE_MAP.items():
        assert bundle in BUNDLE_SAVINGS, f"Bundle {bundle} missing from BUNDLE_SAVINGS"

# --- InProductExpansionEngine ---

def test_engine_suggest_and_accept():
    engine = InProductExpansionEngine()
    offer = engine.suggest("acct-1", "financial_control", {"activation_rate": 0.7, "satisfaction": 8, "months_active": 3})
    assert offer is not None
    engine.accept("acct-1")
    assert engine.conversion_rate == 1.0

def test_engine_suggest_and_decline():
    engine = InProductExpansionEngine()
    engine.suggest("acct-2", "enterprise_service", {"activation_rate": 0.65, "satisfaction": 7.5, "months_active": 2})
    engine.decline("acct-2")
    assert engine.conversion_rate == 0.0

def test_engine_summary():
    engine = InProductExpansionEngine()
    engine.suggest("a1", "regulated_ops", {"activation_rate": 0.8, "satisfaction": 9, "months_active": 6})
    engine.suggest("a2", "factory_quality", {"activation_rate": 0.7, "satisfaction": 7, "months_active": 3})
    engine.accept("a1")
    engine.decline("a2")
    s = engine.summary()
    assert s["recommended"] == 2
    assert s["accepted"] == 1
    assert s["declined"] == 1
    assert s["pending"] == 0

# --- LowTouchBundleFlow ---

def test_low_touch_eligible():
    flow = LowTouchBundleFlow()
    assert flow.qualify_for_bundle("acct-10", "regulated_ops", 0.75, 8.5) == "eligible"

def test_low_touch_sales_assist():
    flow = LowTouchBundleFlow()
    assert flow.qualify_for_bundle("acct-11", "regulated_ops", 0.55, 6.5) == "sales_assist"

def test_low_touch_not_ready():
    flow = LowTouchBundleFlow()
    assert flow.qualify_for_bundle("acct-12", "regulated_ops", 0.3, 4.0) == "not_ready"

# --- Golden Proof: Pack → Recommendation → Accept → Bundle ---

def test_golden_pack_to_bundle_flow():
    engine = InProductExpansionEngine()
    acct = "golden-acct"
    pack = "healthcare"
    metrics = {"activation_rate": 0.85, "satisfaction": 9.5, "months_active": 5}
    offer = engine.suggest(acct, pack, metrics)
    assert offer is not None
    assert offer.current_pack == pack
    assert offer.recommended_bundle == "healthcare_financial_bundle"
    engine.accept(acct)
    s = engine.summary()
    assert s["accepted"] == 1
    assert s["conversion_rate"] == 1.0
