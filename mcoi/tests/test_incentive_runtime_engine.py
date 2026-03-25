"""Tests for incentive runtime engine (Phase 115).

Covers: IncentiveRuntimeEngine lifecycle, gaming detection, violation detection,
        snapshots, state hashing, replay, and golden scenarios.
"""

import pytest

from mcoi_runtime.core.engine_protocol import FixedClock, MonotonicClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.incentive_runtime import IncentiveRuntimeEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.incentive_runtime import (
    BehaviorDisposition,
    IncentiveKind,
    IncentiveStatus,
    PolicyEffectKind,
    RiskOfGaming,
)


FIXED_TS = "2026-01-01T00:00:00+00:00"


def _make_engine(*, clock=None):
    es = EventSpineEngine()
    clk = clock or FixedClock(FIXED_TS)
    eng = IncentiveRuntimeEngine(es, clock=clk)
    return eng, es


# ===================================================================
# Constructor
# ===================================================================

class TestConstructor:
    def test_valid_event_spine(self):
        eng, _ = _make_engine()
        assert eng.incentive_count == 0

    def test_invalid_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            IncentiveRuntimeEngine("not_an_engine")

    def test_default_clock(self):
        es = EventSpineEngine()
        eng = IncentiveRuntimeEngine(es)
        assert eng.incentive_count == 0

    def test_fixed_clock_injected(self):
        eng, _ = _make_engine(clock=FixedClock("2025-01-01T00:00:00+00:00"))
        i = eng.register_incentive("i1", "t1", "Reward A")
        assert i.created_at == "2025-01-01T00:00:00+00:00"


# ===================================================================
# Incentive registration
# ===================================================================

class TestIncentiveRegistration:
    def test_register_incentive(self):
        eng, _ = _make_engine()
        i = eng.register_incentive("i1", "t1", "Reward A")
        assert i.incentive_id == "i1"
        assert i.status == IncentiveStatus.ACTIVE
        assert eng.incentive_count == 1

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_incentive("i1", "t1", "Reward A")

    def test_get_incentive(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        i = eng.get_incentive("i1")
        assert i.incentive_id == "i1"

    def test_get_unknown_incentive(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.get_incentive("nonexistent")

    def test_register_with_kind(self):
        eng, _ = _make_engine()
        i = eng.register_incentive("i1", "t1", "Bonus", kind=IncentiveKind.BONUS)
        assert i.kind == IncentiveKind.BONUS

    def test_register_with_value(self):
        eng, _ = _make_engine()
        i = eng.register_incentive("i1", "t1", "Reward A", value=500.0)
        assert i.value == 500.0

    def test_emits_event(self):
        eng, es = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        assert es.event_count >= 1


# ===================================================================
# Incentive lifecycle transitions
# ===================================================================

class TestLifecycleTransitions:
    def test_suspend_incentive(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        i = eng.suspend_incentive("i1")
        assert i.status == IncentiveStatus.SUSPENDED

    def test_expire_incentive(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        i = eng.expire_incentive("i1")
        assert i.status == IncentiveStatus.EXPIRED

    def test_retire_incentive(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        i = eng.retire_incentive("i1")
        assert i.status == IncentiveStatus.RETIRED

    def test_terminal_blocks_suspend(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        eng.expire_incentive("i1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.suspend_incentive("i1")

    def test_terminal_blocks_expire(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        eng.retire_incentive("i1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.expire_incentive("i1")

    def test_terminal_blocks_retire(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        eng.expire_incentive("i1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.retire_incentive("i1")

    def test_suspend_then_expire(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        eng.suspend_incentive("i1")
        i = eng.expire_incentive("i1")
        assert i.status == IncentiveStatus.EXPIRED


# ===================================================================
# Behavior observations
# ===================================================================

class TestBehaviorObservations:
    def test_record_observation(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        o = eng.record_behavior_observation("o1", "t1", "actor1", "i1")
        assert o.observation_id == "o1"
        assert eng.observation_count == 1

    def test_duplicate_observation_rejected(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        eng.record_behavior_observation("o1", "t1", "actor1", "i1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.record_behavior_observation("o1", "t1", "actor1", "i1")

    def test_unknown_incentive_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.record_behavior_observation("o1", "t1", "actor1", "nope")

    def test_observation_with_disposition(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        o = eng.record_behavior_observation("o1", "t1", "actor1", "i1",
                                            disposition=BehaviorDisposition.GAMING)
        assert o.disposition == BehaviorDisposition.GAMING

    def test_emits_event(self):
        eng, es = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        before = es.event_count
        eng.record_behavior_observation("o1", "t1", "actor1", "i1")
        assert es.event_count > before


# ===================================================================
# Gaming detection
# ===================================================================

class TestGamingDetection:
    def test_no_gaming_no_detection(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        eng.record_behavior_observation("o1", "t1", "actor1", "i1",
                                        disposition=BehaviorDisposition.ALIGNED)
        result = eng.detect_gaming("d1", "t1", "actor1", "i1")
        assert result is None

    def test_gaming_disposition_detected(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        eng.record_behavior_observation("o1", "t1", "actor1", "i1",
                                        disposition=BehaviorDisposition.GAMING)
        result = eng.detect_gaming("d1", "t1", "actor1", "i1")
        assert result is not None
        assert result.risk == RiskOfGaming.HIGH

    def test_repeated_misaligned_detected(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        eng.record_behavior_observation("o1", "t1", "actor1", "i1",
                                        disposition=BehaviorDisposition.MISALIGNED)
        eng.record_behavior_observation("o2", "t1", "actor1", "i1",
                                        disposition=BehaviorDisposition.MISALIGNED)
        result = eng.detect_gaming("d1", "t1", "actor1", "i1")
        assert result is not None
        assert result.risk == RiskOfGaming.MODERATE

    def test_three_misaligned_high_risk(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        for i in range(3):
            eng.record_behavior_observation(f"o{i}", "t1", "actor1", "i1",
                                            disposition=BehaviorDisposition.MISALIGNED)
        result = eng.detect_gaming("d1", "t1", "actor1", "i1")
        assert result.risk == RiskOfGaming.HIGH

    def test_duplicate_detection_rejected(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        eng.record_behavior_observation("o1", "t1", "actor1", "i1",
                                        disposition=BehaviorDisposition.GAMING)
        eng.detect_gaming("d1", "t1", "actor1", "i1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.detect_gaming("d1", "t1", "actor1", "i1")

    def test_detection_count(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        eng.record_behavior_observation("o1", "t1", "actor1", "i1",
                                        disposition=BehaviorDisposition.GAMING)
        eng.detect_gaming("d1", "t1", "actor1", "i1")
        assert eng.detection_count == 1


# ===================================================================
# Policy effects
# ===================================================================

class TestPolicyEffects:
    def test_record_effect(self):
        eng, _ = _make_engine()
        e = eng.record_policy_effect("e1", "t1", "pol1")
        assert e.effect_id == "e1"
        assert eng.effect_count == 1

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.record_policy_effect("e1", "t1", "pol1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.record_policy_effect("e1", "t1", "pol1")

    def test_effect_with_kind(self):
        eng, _ = _make_engine()
        e = eng.record_policy_effect("e1", "t1", "pol1", kind=PolicyEffectKind.PERVERSE)
        assert e.kind == PolicyEffectKind.PERVERSE


# ===================================================================
# Contract bindings
# ===================================================================

class TestContractBindings:
    def test_bind(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        b = eng.bind_incentive_to_contract("b1", "t1", "con1", "i1")
        assert b.binding_id == "b1"
        assert eng.binding_count == 1

    def test_duplicate_rejected(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        eng.bind_incentive_to_contract("b1", "t1", "con1", "i1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.bind_incentive_to_contract("b1", "t1", "con1", "i1")

    def test_unknown_incentive_rejected(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.bind_incentive_to_contract("b1", "t1", "con1", "nope")


# ===================================================================
# Assessment
# ===================================================================

class TestAssessment:
    def test_basic_assessment(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        a = eng.incentive_assessment("a1", "t1")
        assert a.total_incentives == 1

    def test_alignment_rate(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        eng.record_behavior_observation("o1", "t1", "actor1", "i1",
                                        disposition=BehaviorDisposition.ALIGNED)
        eng.record_behavior_observation("o2", "t1", "actor1", "i1",
                                        disposition=BehaviorDisposition.MISALIGNED)
        a = eng.incentive_assessment("a1", "t1")
        assert a.alignment_rate == 0.5

    def test_no_observations_zero_rate(self):
        eng, _ = _make_engine()
        a = eng.incentive_assessment("a1", "t1")
        assert a.alignment_rate == 0.0


# ===================================================================
# Snapshot and closure
# ===================================================================

class TestSnapshotAndClosure:
    def test_snapshot(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        s = eng.incentive_snapshot("s1", "t1")
        assert s.total_incentives == 1

    def test_closure_report(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        c = eng.incentive_closure_report("cr1", "t1")
        assert c.total_incentives == 1

    def test_engine_snapshot_dict(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        snap = eng.snapshot()
        assert "incentives" in snap
        assert "_state_hash" in snap


# ===================================================================
# Violation detection
# ===================================================================

class TestViolationDetection:
    def test_no_violations_empty(self):
        eng, _ = _make_engine()
        v = eng.detect_incentive_violations()
        assert len(v) == 0

    def test_gaming_unaddressed(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        eng.record_behavior_observation("o1", "t1", "actor1", "i1",
                                        disposition=BehaviorDisposition.GAMING)
        eng.detect_gaming("d1", "t1", "actor1", "i1")
        v = eng.detect_incentive_violations()
        assert any(x.operation == "gaming_unaddressed" for x in v)

    def test_perverse_effect_unresolved(self):
        eng, _ = _make_engine()
        eng.record_policy_effect("e1", "t1", "pol1", kind=PolicyEffectKind.PERVERSE)
        v = eng.detect_incentive_violations()
        assert any(x.operation == "perverse_effect_unresolved" for x in v)

    def test_expired_incentive_still_bound(self):
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        eng.bind_incentive_to_contract("b1", "t1", "con1", "i1")
        eng.expire_incentive("i1")
        v = eng.detect_incentive_violations()
        assert any(x.operation == "expired_incentive_still_bound" for x in v)

    def test_idempotency(self):
        eng, _ = _make_engine()
        eng.record_policy_effect("e1", "t1", "pol1", kind=PolicyEffectKind.PERVERSE)
        v1 = eng.detect_incentive_violations()
        assert len(v1) > 0
        v2 = eng.detect_incentive_violations()
        assert len(v2) == 0

    def test_violation_count_incremented(self):
        eng, _ = _make_engine()
        eng.record_policy_effect("e1", "t1", "pol1", kind=PolicyEffectKind.PERVERSE)
        eng.detect_incentive_violations()
        assert eng.violation_count > 0

    def test_tenant_filter(self):
        eng, _ = _make_engine()
        eng.record_policy_effect("e1", "t1", "pol1", kind=PolicyEffectKind.PERVERSE)
        v = eng.detect_incentive_violations(tenant_id="t-other")
        assert len(v) == 0


# ===================================================================
# State hash
# ===================================================================

class TestStateHash:
    def test_deterministic(self):
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        assert eng1.state_hash() == eng2.state_hash()

    def test_changes_after_mutation(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.register_incentive("i1", "t1", "Reward A")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_same_state_same_hash(self):
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        eng1.register_incentive("i1", "t1", "Reward A")
        eng2.register_incentive("i1", "t1", "Reward A")
        assert eng1.state_hash() == eng2.state_hash()


# ===================================================================
# Golden scenarios
# ===================================================================

class TestGoldenScenarios:
    def test_happy_path_lifecycle(self):
        """Full incentive lifecycle: ACTIVE -> SUSPENDED -> EXPIRED."""
        eng, es = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A", value=100.0)
        eng.record_behavior_observation("o1", "t1", "actor1", "i1",
                                        disposition=BehaviorDisposition.ALIGNED)
        eng.suspend_incentive("i1")
        i = eng.expire_incentive("i1")
        assert i.status == IncentiveStatus.EXPIRED
        assert es.event_count >= 4

    def test_cross_tenant_denied(self):
        """Violation detection filters by tenant."""
        eng, _ = _make_engine()
        eng.record_policy_effect("e1", "t1", "pol1", kind=PolicyEffectKind.PERVERSE)
        v = eng.detect_incentive_violations(tenant_id="t-other")
        assert len(v) == 0

    def test_terminal_state_blocking(self):
        """EXPIRED blocks further transitions."""
        eng, _ = _make_engine()
        eng.register_incentive("i1", "t1", "Reward A")
        eng.expire_incentive("i1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.suspend_incentive("i1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.retire_incentive("i1")

    def test_violation_detection_idempotency(self):
        """First call detects, second returns empty."""
        eng, _ = _make_engine()
        eng.record_policy_effect("e1", "t1", "pol1", kind=PolicyEffectKind.PERVERSE)
        v1 = eng.detect_incentive_violations()
        assert len(v1) > 0
        v2 = eng.detect_incentive_violations()
        assert len(v2) == 0

    def test_state_hash_determinism(self):
        """Two engines with identical operations produce identical state hashes."""
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        for eng in (eng1, eng2):
            eng.register_incentive("i1", "t1", "Reward A")
            eng.record_policy_effect("e1", "t1", "pol1")
        assert eng1.state_hash() == eng2.state_hash()

    def test_replay_consistency(self):
        """Replay with MonotonicClock produces consistent state."""
        clk = MonotonicClock()
        eng1, _ = _make_engine(clock=clk)
        eng1.register_incentive("i1", "t1", "Reward A")
        eng1.suspend_incentive("i1")
        snap1 = eng1.snapshot()
        clk2 = MonotonicClock()
        eng2, _ = _make_engine(clock=clk2)
        eng2.register_incentive("i1", "t1", "Reward A")
        eng2.suspend_incentive("i1")
        snap2 = eng2.snapshot()
        assert snap1["_state_hash"] == snap2["_state_hash"]
