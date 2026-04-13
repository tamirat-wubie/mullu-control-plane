"""Φ_gps Runtime Tests — Phase 0 (FRAME) + Phase 1 (DISTINGUISH)."""

import pytest
from mcoi_runtime.core.phi_gps import (
    AgentMode,
    DistinguishResult,
    FrameResult,
    IgnoranceMap,
    KnowledgeLevel,
    ProfileVector,
    ResourceLevel,
    Symbol,
    distinguish,
    frame_problem,
    select_strategies,
)


# ── Phase 0: FRAME ────────────────────────────────────────────

class TestFrame:
    def test_fully_known_problem(self):
        result = frame_problem(
            world_known=True, goal_known=True,
            laws_known=True, actions_known=True, transitions_known=True,
        )
        assert result.profile.unknowns == 0
        assert result.ignorance.critical_unknowns == 0
        assert "phase_0_frame" in result.recommended_phases
        assert "phase_12_verify" in result.recommended_phases

    def test_fully_unknown_problem(self):
        result = frame_problem()
        assert result.profile.unknowns >= 3
        assert result.ignorance.critical_unknowns >= 1
        assert "phase_2_estimate_belief" in result.recommended_phases

    def test_partial_world(self):
        result = frame_problem(world_partial=True, goal_known=True)
        assert result.profile.k_world == KnowledgeLevel.PARTIAL
        assert result.profile.k_goal == KnowledgeLevel.KNOWN

    def test_adversarial_mode(self):
        result = frame_problem(adversarial=True)
        assert result.profile.mode == AgentMode.ADVERSARIAL

    def test_cooperative_mode(self):
        result = frame_problem(multi_agent=True)
        assert result.profile.mode == AgentMode.COOPERATIVE

    def test_critical_resource_limits_phases(self):
        result = frame_problem(resource_pressure="critical")
        assert result.resource_envelope["max_phases"] == 5
        assert result.resource_envelope["max_reentries"] == 1
        assert "phase_11_diagnose" not in result.recommended_phases

    def test_ignorance_map_entries(self):
        result = frame_problem()
        entries = result.ignorance.entries
        dims = [e.dimension for e in entries]
        assert "world_state" in dims
        assert "goal" in dims

    def test_ignorance_resolution_strategies(self):
        result = frame_problem()
        for entry in result.ignorance.entries:
            assert entry.resolution in ("observe", "query", "test", "assume")

    def test_to_dict(self):
        result = frame_problem(world_known=True, goal_known=True)
        d = result.to_dict()
        assert "profile" in d
        assert "ignorance" in d
        assert "recommended_phases" in d

    def test_model_freeze_always_included(self):
        result = frame_problem()
        assert "phase_4_5_freeze_models" in result.recommended_phases


# ── Profile Vector ─────────────────────────────────────────────

class TestProfileVector:
    def test_dominance_unknown(self):
        p = ProfileVector(
            k_world=KnowledgeLevel.UNKNOWN, k_goal=KnowledgeLevel.KNOWN,
            k_laws=KnowledgeLevel.KNOWN, k_actions=KnowledgeLevel.KNOWN,
            k_transitions=KnowledgeLevel.KNOWN,
            mode=AgentMode.SINGLE, resource=ResourceLevel.MEDIUM,
        )
        assert p.dominance == "world"

    def test_dominance_partial(self):
        p = ProfileVector(
            k_world=KnowledgeLevel.KNOWN, k_goal=KnowledgeLevel.PARTIAL,
            k_laws=KnowledgeLevel.KNOWN, k_actions=KnowledgeLevel.KNOWN,
            k_transitions=KnowledgeLevel.KNOWN,
            mode=AgentMode.SINGLE, resource=ResourceLevel.MEDIUM,
        )
        assert p.dominance == "goal"

    def test_dominance_none(self):
        p = ProfileVector(
            k_world=KnowledgeLevel.KNOWN, k_goal=KnowledgeLevel.KNOWN,
            k_laws=KnowledgeLevel.KNOWN, k_actions=KnowledgeLevel.KNOWN,
            k_transitions=KnowledgeLevel.KNOWN,
            mode=AgentMode.SINGLE, resource=ResourceLevel.MEDIUM,
        )
        assert p.dominance == "none"

    def test_to_dict(self):
        p = ProfileVector(
            k_world=KnowledgeLevel.PARTIAL, k_goal=KnowledgeLevel.KNOWN,
            k_laws=KnowledgeLevel.KNOWN, k_actions=KnowledgeLevel.PARTIAL,
            k_transitions=KnowledgeLevel.UNKNOWN,
            mode=AgentMode.COOPERATIVE, resource=ResourceLevel.LOW,
        )
        d = p.to_dict()
        assert d["k_world"] == "partial"
        assert d["mode"] == "cooperative"


# ── Phase 1: DISTINGUISH ──────────────────────────────────────

class TestDistinguish:
    def test_extract_entities(self):
        result = distinguish("Alice sent a payment to Bob via Stripe")
        entities = result.symbols_by_kind("entity")
        names = {s.name for s in entities}
        assert "Alice" in names
        assert "Bob" in names
        assert "Stripe" in names

    def test_extract_actions(self):
        result = distinguish("create a new account and send notification")
        actions = result.symbols_by_kind("action")
        names = {s.name for s in actions}
        assert "create" in names
        assert "send" in names

    def test_extract_relations(self):
        result = distinguish("payment requires approval and depends on balance")
        relations = result.symbols_by_kind("relation")
        names = {s.name for s in relations}
        assert "requires" in names
        assert "depends" in names

    def test_extract_properties(self):
        result = distinguish("the amount exceeds the threshold and the rate is high")
        properties = result.symbols_by_kind("property")
        names = {s.name for s in properties}
        assert "amount" in names
        assert "threshold" in names

    def test_extract_boundaries(self):
        result = distinguish("stay within the budget and respect the deadline")
        boundaries = result.symbols_by_kind("boundary")
        names = {s.name for s in boundaries}
        assert "budget" in names
        assert "deadline" in names

    def test_confidence_levels(self):
        result = distinguish("Alice sent payment to Bob")
        for s in result.symbols:
            assert 0.0 <= s.confidence <= 1.0

    def test_low_confidence_tracking(self):
        result = distinguish("something between things", kappa_min=0.9)
        # All symbols should be below 0.9 confidence
        assert result.low_confidence_count >= 0

    def test_epistemic_actions_generated(self):
        result = distinguish("X relates to Y", kappa_min=0.9)
        # Low confidence symbols should generate epistemic actions
        for action in result.epistemic_actions_needed:
            assert any(prefix in action for prefix in ("query:", "observe:", "test:"))

    def test_empty_text(self):
        result = distinguish("")
        assert result.symbol_count == 0

    def test_to_dict(self):
        result = distinguish("Alice creates account")
        d = result.to_dict()
        assert "symbols" in d
        assert "low_confidence_count" in d
        assert "epistemic_actions" in d

    def test_dedup(self):
        result = distinguish("create create create")
        actions = result.symbols_by_kind("action")
        assert len(actions) == 1  # Deduped


# ── Strategy Selection ─────────────────────────────────────────

class TestStrategySelection:
    def test_select_top_3(self):
        profile = ProfileVector(
            k_world=KnowledgeLevel.KNOWN, k_goal=KnowledgeLevel.KNOWN,
            k_laws=KnowledgeLevel.KNOWN, k_actions=KnowledgeLevel.KNOWN,
            k_transitions=KnowledgeLevel.KNOWN,
            mode=AgentMode.SINGLE, resource=ResourceLevel.MEDIUM,
        )
        strategies = select_strategies(profile)
        assert len(strategies) == 3
        assert strategies[0].score >= strategies[1].score

    def test_critical_resource_selects_one(self):
        profile = ProfileVector(
            k_world=KnowledgeLevel.UNKNOWN, k_goal=KnowledgeLevel.PARTIAL,
            k_laws=KnowledgeLevel.PARTIAL, k_actions=KnowledgeLevel.PARTIAL,
            k_transitions=KnowledgeLevel.UNKNOWN,
            mode=AgentMode.SINGLE, resource=ResourceLevel.CRITICAL,
        )
        strategies = select_strategies(profile)
        assert len(strategies) == 1

    def test_strategy_has_name_and_score(self):
        profile = ProfileVector(
            k_world=KnowledgeLevel.KNOWN, k_goal=KnowledgeLevel.KNOWN,
            k_laws=KnowledgeLevel.KNOWN, k_actions=KnowledgeLevel.KNOWN,
            k_transitions=KnowledgeLevel.KNOWN,
            mode=AgentMode.SINGLE, resource=ResourceLevel.LOW,
        )
        strategies = select_strategies(profile, top_k=5)
        for s in strategies:
            assert s.name != ""
            assert isinstance(s.score, (int, float))
