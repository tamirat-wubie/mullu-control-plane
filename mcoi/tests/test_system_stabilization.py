"""Tests for Phases 186-192 — System Stabilization Program v2."""
import pytest
from hashlib import sha256

from mcoi_runtime.core.system_stabilization import (
    IdentityBindingEngine,
    OntologyEnforcer,
    EquilibriumEngine,
    AdversarialDefenseEngine,
    PredictiveFailureEngine,
    EconomicOptimizer,
    AdaptivePromotionEngine,
)

# ═══ Phase 186 — Cryptographic Identity & Action Binding ═══

class TestIdentityBindingEngine:
    def test_sign_intent(self):
        eng = IdentityBindingEngine()
        si = eng.sign_intent("i1", "actor-a", "deploy", "runtime-x")
        assert si.intent_id == "i1"
        assert si.actor_id == "actor-a"
        expected = sha256(b"actor-a:deploy:runtime-x").hexdigest()
        assert si.intent_hash == expected
        assert eng.intent_count == 1

    def test_bind_action(self):
        eng = IdentityBindingEngine()
        eng.sign_intent("i1", "actor-a", "deploy", "runtime-x")
        ab = eng.bind_action("b1", "i1", "exec-001")
        assert ab.binding_id == "b1"
        assert ab.non_repudiable is True
        assert eng.binding_count == 1

    def test_verify_binding(self):
        eng = IdentityBindingEngine()
        eng.sign_intent("i1", "actor-a", "deploy", "runtime-x")
        eng.bind_action("b1", "i1", "exec-001")
        assert eng.verify_binding("b1") is True
        assert eng.verify_binding("nonexistent") is False

    def test_duplicate_intent_blocked(self):
        eng = IdentityBindingEngine()
        eng.sign_intent("i1", "actor-a", "deploy", "runtime-x")
        with pytest.raises(ValueError, match="^intent already registered$") as exc_info:
            eng.sign_intent("i1", "actor-b", "scale", "runtime-y")
        assert "i1" not in str(exc_info.value)

    def test_unknown_intent_blocked(self):
        eng = IdentityBindingEngine()
        with pytest.raises(ValueError, match="^intent unavailable$") as exc_info:
            eng.bind_action("b1", "no-such-intent", "exec-001")
        assert "no-such-intent" not in str(exc_info.value)

    def test_duplicate_binding_blocked(self):
        eng = IdentityBindingEngine()
        eng.sign_intent("i1", "actor-a", "deploy", "runtime-x")
        eng.bind_action("b1", "i1", "exec-001")
        with pytest.raises(ValueError, match="^binding already registered$") as exc_info:
            eng.bind_action("b1", "i1", "exec-002")
        assert "b1" not in str(exc_info.value)


# ═══ Phase 187 — Global Ontology Enforcement ═══

class TestOntologyEnforcer:
    def test_register_canonical(self):
        oe = OntologyEnforcer()
        oe.register_canonical("Agent", "Autonomous actor in the system")
        assert oe.violation_count == 0

    def test_validate_term_ok(self):
        oe = OntologyEnforcer()
        oe.register_canonical("Agent", "Autonomous actor in the system")
        result = oe.validate_term("mod-a", "agent", "Autonomous actor in the system")
        assert result is None
        assert oe.violation_count == 0

    def test_detect_drift(self):
        oe = OntologyEnforcer()
        oe.register_canonical("Agent", "Autonomous actor in the system")
        v = oe.validate_term("mod-b", "agent", "A software bot")
        assert v is not None
        assert v.severity == "drift"
        assert oe.drift_count() == 1

    def test_detect_missing(self):
        oe = OntologyEnforcer()
        v = oe.validate_term("mod-c", "Widget", "Some widget thing")
        assert v is not None
        assert v.severity == "missing"
        assert v.expected_canonical == "undefined"


# ═══ Phase 188 — Multi-Agent Equilibrium Engine ═══

class TestEquilibriumEngine:
    def test_register_agent(self):
        ee = EquilibriumEngine()
        load = ee.register_agent("a1")
        assert load.agent_id == "a1"
        assert ee.agent_count == 1

    def test_action_allowed(self):
        ee = EquilibriumEngine(max_total_pending=10)
        ee.register_agent("a1")
        assert ee.record_action("a1") is True

    def test_action_blocked_at_cap(self):
        ee = EquilibriumEngine(max_total_pending=2)
        ee.register_agent("a1")
        ee.record_action("a1")
        ee.record_action("a1")
        assert ee.record_action("a1") is False

    def test_conflict_reduces_efficiency(self):
        ee = EquilibriumEngine()
        ee.register_agent("a1")
        ee.record_conflict("a1")
        agent = ee._agents["a1"]
        assert agent.efficiency == pytest.approx(0.9)
        assert agent.conflicts == 1

    def test_equilibrium_score(self):
        ee = EquilibriumEngine()
        ee.register_agent("a1")
        ee.register_agent("a2")
        assert ee.equilibrium_score() == pytest.approx(1.0)
        ee.record_conflict("a1")
        # avg_eff = (0.9 + 1.0)/2 = 0.95; penalty = 1*0.05 = 0.05; score = 0.90
        assert ee.equilibrium_score() == pytest.approx(0.9)

    def test_is_stable(self):
        ee = EquilibriumEngine()
        ee.register_agent("a1")
        assert ee.is_stable() is True
        # 4 conflicts -> efficiency 0.6, penalty 4*0.05=0.2 -> score 0.4
        for _ in range(4):
            ee.record_conflict("a1")
        assert ee.is_stable() is False


# ═══ Phase 189 — Adversarial Ground Truth Defense ═══

class TestAdversarialDefenseEngine:
    def test_register_source(self):
        ade = AdversarialDefenseEngine()
        r = ade.register_source("s1", 0.9)
        assert r.initial_trust == 0.9
        assert r.current_trust == 0.9

    def test_contradiction_decays_trust(self):
        ade = AdversarialDefenseEngine()
        ade.register_source("s1", 0.8)
        r = ade.record_contradiction("s1")
        assert r.current_trust == pytest.approx(0.65)
        assert r.decay_events == 1

    def test_poisoning_detected(self):
        ade = AdversarialDefenseEngine()
        ade.register_source("s1", 0.8)
        # Decay trust below 0.3: need 4 contradictions -> 0.8 - 4*0.15 = 0.2
        for _ in range(4):
            ade.record_contradiction("s1")
        assert ade.detect_poisoning("s1", confidence=0.9) is True
        assert ade.anomaly_count >= 1

    def test_trusted_check(self):
        ade = AdversarialDefenseEngine()
        ade.register_source("s1", 0.8)
        assert ade.is_trusted("s1") is True
        # 3 contradictions -> 0.8 - 0.45 = 0.35 < 0.5
        for _ in range(3):
            ade.record_contradiction("s1")
        assert ade.is_trusted("s1") is False

    def test_anomaly_count(self):
        ade = AdversarialDefenseEngine()
        ade.register_source("s1")
        assert ade.anomaly_count == 0
        for _ in range(3):
            ade.record_contradiction("s1")
        # At 3rd contradiction, anomaly is recorded
        assert ade.anomaly_count >= 1

    def test_unknown_source_blocked(self):
        ade = AdversarialDefenseEngine()
        with pytest.raises(ValueError, match="^source unavailable$") as exc_info:
            ade.record_contradiction("ghost-source")
        assert "ghost-source" not in str(exc_info.value)


# ═══ Phase 190 — Predictive Failure Engine ═══

class TestPredictiveFailureEngine:
    def test_predict_proceed(self):
        pfe = PredictiveFailureEngine()
        p = pfe.predict("p1", "target-a")
        assert p.recommendation == "proceed"
        assert p.risk_score == 0.0

    def test_predict_reroute_after_failures(self):
        pfe = PredictiveFailureEngine()
        pfe.record_failure("target-a")
        pfe.record_failure("target-a")
        pfe.record_failure("target-a")
        p = pfe.predict("p1", "target-a")
        # risk = 3*0.2 = 0.6 -> reroute
        assert p.recommendation == "reroute"

    def test_predict_abort_high_risk(self):
        pfe = PredictiveFailureEngine()
        for _ in range(4):
            pfe.record_failure("target-a")
        p = pfe.predict("p1", "target-a")
        # risk = 4*0.2 = 0.8 -> abort
        assert p.recommendation == "abort"

    def test_record_failure_increases_risk(self):
        pfe = PredictiveFailureEngine()
        p1 = pfe.predict("p1", "target-a")
        pfe.record_failure("target-a")
        p2 = pfe.predict("p2", "target-a")
        assert p2.risk_score > p1.risk_score


# ═══ Phase 191 — Economic Optimization Engine ═══

class TestEconomicOptimizer:
    def test_estimate_execute(self):
        eo = EconomicOptimizer(budget=1000.0)
        e = eo.estimate("e1", "task-a", cost=100.0, value=500.0)
        assert e.recommendation == "execute"
        assert e.net_value == 400.0

    def test_estimate_reject_over_budget(self):
        eo = EconomicOptimizer(budget=50.0)
        e = eo.estimate("e1", "task-a", cost=100.0, value=500.0)
        assert e.recommendation == "reject"

    def test_commit_spend(self):
        eo = EconomicOptimizer(budget=100.0)
        assert eo.commit_spend(60.0) is True
        assert eo.remaining_budget == pytest.approx(40.0)
        assert eo.commit_spend(50.0) is False  # exceeds budget

    def test_utilization(self):
        eo = EconomicOptimizer(budget=200.0)
        eo.commit_spend(100.0)
        assert eo.utilization == pytest.approx(0.5)


# ═══ Phase 192 — Adaptive Sim->Real Promotion Engine ═══

class TestAdaptivePromotionEngine:
    def test_promote_high_confidence(self):
        ape = AdaptivePromotionEngine()
        d = ape.evaluate_promotion("d1", "scope-a", confidence=0.9, risk=0.1, evidence=("sim_pass",))
        assert d.decision == "promote"

    def test_hold_moderate(self):
        ape = AdaptivePromotionEngine()  # threshold=0.85
        # confidence >= 0.85*0.8=0.68 but < 0.85 or risk > ceiling
        d = ape.evaluate_promotion("d1", "scope-a", confidence=0.75, risk=0.2)
        assert d.decision == "hold"

    def test_reject_low(self):
        ape = AdaptivePromotionEngine()
        d = ape.evaluate_promotion("d1", "scope-a", confidence=0.3, risk=0.9)
        assert d.decision == "reject"

    def test_promoted_count(self):
        ape = AdaptivePromotionEngine()
        ape.evaluate_promotion("d1", "s1", 0.9, 0.1)
        ape.evaluate_promotion("d2", "s2", 0.3, 0.9)
        ape.evaluate_promotion("d3", "s3", 0.95, 0.05)
        assert ape.promoted_count() == 2
        assert ape.decision_count == 3


# ═══ Golden — Full Lifecycle Integration ═══

class TestGoldenLifecycle:
    def test_trust_to_promotion_lifecycle(self):
        """Full pipeline: identity -> ontology -> equilibrium -> defense -> prediction -> economics -> promotion."""
        # Phase 186: sign and bind
        ibe = IdentityBindingEngine()
        si = ibe.sign_intent("i1", "agent-alpha", "validate", "runtime-prod")
        ab = ibe.bind_action("b1", "i1", "exec-100")
        assert ibe.verify_binding("b1") is True

        # Phase 187: ontology check
        oe = OntologyEnforcer()
        oe.register_canonical("validate", "Run validation suite against target")
        assert oe.validate_term("core", "validate", "Run validation suite against target") is None

        # Phase 188: equilibrium
        ee = EquilibriumEngine(max_total_pending=50)
        ee.register_agent("agent-alpha")
        assert ee.record_action("agent-alpha") is True
        assert ee.is_stable() is True

        # Phase 189: adversarial defense
        ade = AdversarialDefenseEngine()
        ade.register_source("data-feed-1")
        assert ade.is_trusted("data-feed-1") is True

        # Phase 190: predictive failure
        pfe = PredictiveFailureEngine()
        p = pfe.predict("p1", "runtime-prod")
        assert p.recommendation == "proceed"

        # Phase 191: economics
        eo = EconomicOptimizer(budget=5000.0)
        e = eo.estimate("e1", "runtime-prod", cost=200.0, value=1000.0)
        assert e.recommendation == "execute"
        assert eo.commit_spend(200.0) is True

        # Phase 192: promotion
        ape = AdaptivePromotionEngine()
        d = ape.evaluate_promotion("d1", "runtime-prod", confidence=0.92, risk=0.1, evidence=("identity_bound", "ontology_clean", "equilibrium_stable"))
        assert d.decision == "promote"

    def test_degraded_lifecycle_blocks_promotion(self):
        """When adversarial defense flags poisoning, promotion is rejected."""
        # Adversarial: poison a source
        ade = AdversarialDefenseEngine()
        ade.register_source("bad-feed", 0.8)
        for _ in range(4):
            ade.record_contradiction("bad-feed")
        assert ade.detect_poisoning("bad-feed", 0.9) is True
        assert ade.is_trusted("bad-feed") is False

        # Prediction: failures pile up
        pfe = PredictiveFailureEngine()
        for _ in range(5):
            pfe.record_failure("runtime-suspect")
        p = pfe.predict("p1", "runtime-suspect")
        assert p.recommendation == "abort"

        # Promotion: low confidence due to failures -> reject
        ape = AdaptivePromotionEngine()
        d = ape.evaluate_promotion("d1", "runtime-suspect", confidence=0.4, risk=0.8)
        assert d.decision == "reject"
