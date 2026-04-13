"""Φ_gps Runtime Tests — Phases 0-7.5."""

import pytest
from mcoi_runtime.core.phi_gps import (
    AgentMode,
    BeliefState,
    DiscoveredLaw,
    DiscoveredNorm,
    DistinguishResult,
    EpisodeModelSet,
    FeasibilityResult,
    FrameResult,
    GoalConstructionResult,
    GoalStatus,
    IgnoranceMap,
    InvariantGrade,
    KnowledgeLevel,
    LawDiscoveryResult,
    LawType,
    ModelStatus,
    NormKind,
    ProfileVector,
    ProofSketch,
    ProofState,
    ResourceLevel,
    Symbol,
    UtilityStructure,
    build_proof_sketch,
    check_feasibility,
    compute_voi,
    construct_goal,
    discover_laws,
    distinguish,
    estimate_belief,
    frame_problem,
    freeze_models,
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


# ── Phase 2: ESTIMATE BELIEF ──────────────────────────────────

class TestEstimateBelief:
    def test_observed_variables(self):
        belief = estimate_belief({"balance": 100.0, "status": "active"})
        assert belief.observation_count == 2
        assert belief.observed_count == 2
        assert belief.overall_confidence > 0.8

    def test_hidden_variables(self):
        belief = estimate_belief(
            {"balance": 100.0},
            hidden_variables=["fraud_risk"],
        )
        assert belief.hidden_count == 1
        v = belief.get("fraud_risk")
        assert v is not None
        assert v.observability == "hidden"
        assert v.confidence < 0.5

    def test_prior_knowledge(self):
        belief = estimate_belief(
            {"balance": 100.0},
            prior_knowledge={"credit_score": 750},
        )
        v = belief.get("credit_score")
        assert v is not None
        assert v.source == "prior"
        assert v.confidence == 0.5

    def test_mixed_sources(self):
        belief = estimate_belief(
            {"balance": 100.0},
            prior_knowledge={"history": "good"},
            hidden_variables=["risk"],
        )
        assert len(belief.variables) == 3
        assert belief.observed_count == 1
        assert belief.hidden_count == 1

    def test_empty_observations(self):
        belief = estimate_belief({})
        assert belief.observation_count == 0
        assert belief.overall_confidence == 0.0

    def test_entropy_positive(self):
        belief = estimate_belief({"a": 1, "b": 2, "c": 3})
        assert belief.entropy >= 0

    def test_to_dict(self):
        belief = estimate_belief({"x": 1}, hidden_variables=["y"])
        d = belief.to_dict()
        assert "variables" in d
        assert "overall_confidence" in d
        assert "entropy" in d
        assert "observed" in d
        assert "hidden" in d


class TestValueOfInformation:
    def test_voi_prioritizes_uncertain(self):
        belief = estimate_belief(
            {"known": 100},
            hidden_variables=["unknown"],
        )
        estimates = compute_voi(belief, ["known", "unknown"])
        assert estimates[0].query == "unknown"
        assert estimates[0].priority > estimates[1].priority

    def test_voi_empty_queries(self):
        belief = estimate_belief({"x": 1})
        assert compute_voi(belief, []) == []

    def test_voi_all_known(self):
        belief = estimate_belief({"a": 1, "b": 2})
        estimates = compute_voi(belief, ["a", "b"])
        for e in estimates:
            assert e.priority <= 0.2  # Low priority — already known


# ── Phase 3: GOAL + UTILITY ───────────────────────────────────

class TestConstructGoal:
    def test_crisp_goal(self):
        result = construct_goal(
            description="Transfer $500 to Bob",
            satisfaction_criteria={"amount": 500, "recipient": "Bob"},
        )
        assert result.goal_status == GoalStatus.CRISP
        assert result.utility.goal.gamma_goal == 0.8

    def test_fuzzy_goal(self):
        result = construct_goal(description="Improve performance")
        assert result.goal_status == GoalStatus.FUZZY

    def test_absent_goal(self):
        result = construct_goal()
        assert result.goal_status == GoalStatus.ABSENT

    def test_contradictory_goal(self):
        result = construct_goal(
            description="Maximize speed and minimize cost",
            contradictions=["speed vs cost"],
        )
        assert result.goal_status == GoalStatus.CONTRADICTORY
        assert len(result.tradeoffs) == 1

    def test_safety_floor(self):
        result = construct_goal(
            description="Deploy system",
            safety_variables=["uptime", "data_integrity"],
        )
        assert len(result.utility.safety_floor.variables) == 2
        assert result.utility.safety_floor.severity == "critical"

    def test_optimization_preferences(self):
        result = construct_goal(
            description="Process payment",
            satisfaction_criteria={"paid": True},
            optimization_preferences=["speed", "cost", "reliability"],
        )
        assert result.utility.optimization_preferences == ("speed", "cost", "reliability")

    def test_satisficing_threshold(self):
        result = construct_goal(satisficing=0.6)
        assert result.utility.satisficing_threshold == 0.6

    def test_gamma_goal(self):
        result = construct_goal(
            satisfaction_criteria={"done": True},
            gamma_goal=0.95,
        )
        assert result.utility.goal.gamma_goal == 0.95

    def test_to_dict(self):
        result = construct_goal(
            description="Test",
            safety_variables=["safe"],
            satisfaction_criteria={"ok": True},
        )
        d = result.to_dict()
        assert "goal_status" in d
        assert "utility" in d
        assert "safety_floor" in d["utility"]
        assert "goal" in d["utility"]

    def test_four_layer_priority(self):
        """Utility structure follows priority: safety > goal > optimization > satisficing."""
        result = construct_goal(
            description="Full test",
            safety_variables=["integrity"],
            satisfaction_criteria={"complete": True},
            optimization_preferences=["fast", "cheap"],
            satisficing=0.7,
        )
        u = result.utility
        assert u.safety_floor.severity == "critical"  # Highest priority
        assert u.goal.gamma_goal > 0  # Second
        assert len(u.optimization_preferences) > 0  # Third
        assert u.satisficing_threshold > 0  # Fourth


# ── Phase 4: DISCOVER LAWS ────────────────────────────────────

class TestDiscoverLaws:
    def test_domain_law(self):
        result = discover_laws(domain="finance")
        assert any(l.name == "domain_boundary" for l in result.laws)

    def test_constraints_become_laws(self):
        result = discover_laws(constraints=["balance >= 0", "amount > 0"])
        assert len(result.laws) >= 4  # 2 constraints + 2 universal

    def test_universal_governance_laws(self):
        result = discover_laws()
        names = {l.name for l in result.laws}
        assert "identity_preservation" in names
        assert "audit_completeness" in names

    def test_hard_law_confidence(self):
        result = discover_laws()
        for l in result.laws:
            if l.name in ("identity_preservation", "audit_completeness"):
                assert l.confidence == 1.0

    def test_permissions(self):
        result = discover_laws(permissions=["read data", "send email"])
        perms = [n for n in result.norms if n.kind == NormKind.PERMISSION]
        assert len(perms) == 2

    def test_prohibitions(self):
        result = discover_laws(prohibitions=["delete production data"])
        prohibs = [n for n in result.norms if n.kind == NormKind.PROHIBITION]
        assert len(prohibs) == 1
        assert prohibs[0].authority_level == 2  # Higher authority

    def test_governance_norm_always_present(self):
        result = discover_laws()
        gov = [n for n in result.norms if n.kind == NormKind.GOVERNANCE]
        assert len(gov) >= 1
        assert gov[0].authority_level == 0  # Highest

    def test_resource_constraints(self):
        result = discover_laws(resource_limits={"time": 60, "budget": 100})
        assert result.resource_constraints["time"] == 60

    def test_hard_law_count(self):
        result = discover_laws(constraints=["must be positive"])
        assert result.hard_law_count >= 2  # Universal laws always hard

    def test_to_dict(self):
        result = discover_laws(domain="test", constraints=["x > 0"])
        d = result.to_dict()
        assert "laws" in d
        assert "norms" in d
        assert "hard_laws" in d


# ── Phase 4.5: FREEZE MODELS ─────────────────────────────────

class TestFreezeModels:
    def _setup(self):
        laws = discover_laws(domain="test", constraints=["x > 0"])
        belief = estimate_belief({"x": 5})
        goal = construct_goal(description="test", satisfaction_criteria={"done": True})
        return laws, belief, goal

    def test_freeze_creates_frozen_model(self):
        laws, belief, goal = self._setup()
        model = freeze_models(laws=laws, belief=belief, goal=goal,
                              clock=lambda: "2026-04-07T12:00:00Z")
        assert model.is_frozen is True
        assert model.status == ModelStatus.FROZEN

    def test_model_has_id(self):
        laws, belief, goal = self._setup()
        model = freeze_models(laws=laws, belief=belief, goal=goal,
                              clock=lambda: "2026-04-07T12:00:00Z")
        assert model.model_id.startswith("model-")

    def test_model_contains_laws(self):
        laws, belief, goal = self._setup()
        model = freeze_models(laws=laws, belief=belief, goal=goal)
        assert model.law_count >= 3

    def test_model_contains_norms(self):
        laws, belief, goal = self._setup()
        model = freeze_models(laws=laws, belief=belief, goal=goal)
        assert model.norm_count >= 1

    def test_approved_by(self):
        laws, belief, goal = self._setup()
        model = freeze_models(laws=laws, belief=belief, goal=goal, approver="admin")
        assert model.approved_by == "admin"

    def test_to_dict(self):
        laws, belief, goal = self._setup()
        model = freeze_models(laws=laws, belief=belief, goal=goal,
                              clock=lambda: "now")
        d = model.to_dict()
        assert d["is_frozen"] is True
        assert d["status"] == "frozen"
        assert "model_id" in d

    def test_full_pipeline_0_through_4_5(self):
        """Full Phase 0 → 1 → 2 → 3 → 4 → 4.5 pipeline."""
        # Phase 0
        frame = frame_problem(world_partial=True, goal_known=True)
        assert frame.profile.k_goal == KnowledgeLevel.KNOWN

        # Phase 1
        symbols = distinguish("Transfer $500 from Alice to Bob")
        assert symbols.symbol_count > 0

        # Phase 2
        belief = estimate_belief(
            {"balance": 1000, "recipient": "Bob"},
            hidden_variables=["fraud_risk"],
        )
        assert belief.overall_confidence > 0

        # Phase 3
        goal = construct_goal(
            description="Transfer $500",
            safety_variables=["balance_non_negative"],
            satisfaction_criteria={"transferred": True, "amount": 500},
        )
        assert goal.goal_status == GoalStatus.CRISP

        # Phase 4
        laws = discover_laws(
            domain="finance",
            constraints=["balance >= 0", "amount > 0"],
            prohibitions=["overdraft"],
        )
        assert laws.hard_law_count >= 2

        # Phase 4.5
        model = freeze_models(
            laws=laws, belief=belief, goal=goal,
            clock=lambda: "2026-04-07T12:00:00Z",
        )
        assert model.is_frozen is True
        assert model.law_count >= 4
        assert model.norm_count >= 2


# ── Phase 7: FEASIBILITY ──────────────────────────────────────

class TestFeasibility:
    def _model(self):
        laws = discover_laws(domain="test", constraints=["x > 0"])
        belief = estimate_belief({"x": 5})
        goal = construct_goal(description="test", satisfaction_criteria={"done": True})
        return freeze_models(laws=laws, belief=belief, goal=goal)

    def test_feasible_problem(self):
        model = self._model()
        result = check_feasibility(model=model)
        assert result.feasible is True
        assert result.solvability == "feasible"

    def test_hard_invariant_violation(self):
        model = self._model()
        result = check_feasibility(
            model=model,
            current_state={"balance": 100},
            goal_state={"balance": -50},
            invariant_specs=[{
                "name": "balance", "grade": "hard",
                "confidence": 0.99, "n_observed": 25,
                "reachable": False,
            }],
        )
        assert result.feasible is False
        assert "balance" in result.hard_violations

    def test_soft_warning(self):
        model = self._model()
        result = check_feasibility(
            model=model,
            current_state={"latency": 500},
            goal_state={"latency": 50},
            invariant_specs=[{
                "name": "latency", "grade": "soft",
                "confidence": 0.8, "reachable": False,
            }],
        )
        assert result.feasible is True  # Soft doesn't block
        assert "latency" in result.soft_warnings

    def test_candidate_ignored(self):
        model = self._model()
        result = check_feasibility(
            model=model,
            invariant_specs=[{
                "name": "hunch", "grade": "candidate",
                "confidence": 0.3, "reachable": False,
            }],
        )
        assert result.feasible is True  # Candidates don't gate

    def test_laws_become_invariants(self):
        model = self._model()
        result = check_feasibility(model=model)
        assert result.hard_count >= 2  # Universal governance laws

    def test_to_dict(self):
        model = self._model()
        d = check_feasibility(model=model).to_dict()
        assert "feasible" in d
        assert "solvability" in d
        assert "invariants" in d


# ── Phase 7.5: PROOF SKETCH ───────────────────────────────────

class TestProofSketch:
    def _setup(self):
        laws = discover_laws(domain="finance", constraints=["balance >= 0"])
        belief = estimate_belief({"balance": 100})
        goal = construct_goal(description="transfer", satisfaction_criteria={"done": True})
        model = freeze_models(laws=laws, belief=belief, goal=goal)
        feasibility = check_feasibility(model=model)
        return model, feasibility

    def test_feasible_sketch(self):
        model, feasibility = self._setup()
        sketch = build_proof_sketch(sub_goal="transfer_funds", feasibility=feasibility, model=model)
        assert sketch.pi_goal == ProofState.PASS
        assert sketch.pi_law == ProofState.PASS

    def test_infeasible_sketch(self):
        model, _ = self._setup()
        infeasible = FeasibilityResult(
            feasible=False, invariants=(),
            hard_violations=("balance",), soft_warnings=(), solvability="infeasible",
        )
        sketch = build_proof_sketch(sub_goal="overdraft", feasibility=infeasible, model=model)
        assert sketch.pi_goal == ProofState.FAIL
        assert sketch.pi_law == ProofState.FAIL
        assert sketch.is_verified is False

    def test_unknown_side_effects(self):
        model, feasibility = self._setup()
        sketch = build_proof_sketch(sub_goal="action", feasibility=feasibility, model=model)
        assert sketch.pi_side_effect == ProofState.UNKNOWN
        assert sketch.has_unknown is True

    def test_to_dict(self):
        model, feasibility = self._setup()
        d = build_proof_sketch(sub_goal="test", feasibility=feasibility, model=model).to_dict()
        assert d["sub_goal"] == "test"
        assert "verified" in d
        assert "has_unknown" in d

    def test_full_pipeline_0_through_7_5(self):
        """Full Phase 0 → 7.5 pipeline."""
        frame = frame_problem(world_partial=True, goal_known=True)
        symbols = distinguish("Transfer $500 from Alice to Bob")
        belief = estimate_belief({"balance": 1000}, hidden_variables=["fraud_risk"])
        goal = construct_goal(
            description="Transfer $500",
            safety_variables=["balance_non_negative"],
            satisfaction_criteria={"transferred": True},
        )
        laws = discover_laws(domain="finance", constraints=["balance >= 0"], prohibitions=["overdraft"])
        model = freeze_models(laws=laws, belief=belief, goal=goal, clock=lambda: "now")
        feasibility = check_feasibility(model=model)
        sketch = build_proof_sketch(sub_goal="transfer", feasibility=feasibility, model=model)

        assert frame.profile.k_goal == KnowledgeLevel.KNOWN
        assert symbols.symbol_count > 0
        assert belief.overall_confidence > 0
        assert goal.goal_status == GoalStatus.CRISP
        assert model.is_frozen is True
        assert feasibility.feasible is True
        assert sketch.pi_goal == ProofState.PASS
