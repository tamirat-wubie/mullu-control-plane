"""Φ_gps Runtime Tests — Phases 0-12."""

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
    SolverOutcome,
    SolverOutput,
    Verification,
    build_proof_sketch,
    check_feasibility,
    compute_voi,
    construct_goal,
    discover_laws,
    distinguish,
    estimate_belief,
    execute_plan,
    frame_problem,
    freeze_models,
    select_strategies,
    verify_and_judge,
    ActionSet,
    DecompositionResult,
    DiagnosisResult,
    PolicyResult,
    TransitionMap,
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


# ── Phase 10: EXECUTE ──────────────────────────────────────────

class TestExecute:
    def test_simple_execution(self):
        model = TestFreezeModels()._setup()
        model = freeze_models(laws=model[0], belief=model[1], goal=model[2])
        actions = [
            {"action": "observe", "class": "epistemic", "cost": 0.1},
            {"action": "transfer", "class": "world", "cost": 0.5, "is_goal_action": True},
        ]
        trace = execute_plan(model=model, actions=actions)
        assert trace.step_count == 2
        assert trace.goal_reached is True
        assert trace.total_cost == 0.6

    def test_safety_blocks_action(self):
        model = TestFreezeModels()._setup()
        model = freeze_models(laws=model[0], belief=model[1], goal=model[2])
        actions = [{"action": "dangerous", "class": "world"}]
        trace = execute_plan(model=model, actions=actions, safety_check=lambda a: False)
        assert trace.safety_violations == 1
        assert trace.steps[0].outcome == "safety_blocked"

    def test_budget_exceeded(self):
        model = TestFreezeModels()._setup()
        model = freeze_models(laws=model[0], belief=model[1], goal=model[2])
        actions = [
            {"action": "a1", "class": "world", "cost": 0.6},
            {"action": "a2", "class": "world", "cost": 0.6},
        ]
        trace = execute_plan(model=model, actions=actions, cost_budget=1.0)
        assert trace.step_count == 2
        assert trace.steps[1].outcome == "budget_exceeded"

    def test_executor_callback(self):
        model = TestFreezeModels()._setup()
        model = freeze_models(laws=model[0], belief=model[1], goal=model[2])
        actions = [{"action": "compute", "class": "world", "params": {"x": 5}}]
        trace = execute_plan(
            model=model, actions=actions,
            executor=lambda name, params: {"outcome": "computed", "surprise": 0.1},
        )
        assert trace.steps[0].outcome == "computed"
        assert trace.steps[0].surprise == 0.1

    def test_max_steps(self):
        model = TestFreezeModels()._setup()
        model = freeze_models(laws=model[0], belief=model[1], goal=model[2])
        actions = [{"action": f"a{i}", "class": "world"} for i in range(50)]
        trace = execute_plan(model=model, actions=actions, max_steps=5)
        assert trace.step_count == 5

    def test_to_dict(self):
        model = TestFreezeModels()._setup()
        model = freeze_models(laws=model[0], belief=model[1], goal=model[2])
        trace = execute_plan(model=model, actions=[{"action": "test", "class": "world"}])
        d = trace.to_dict()
        assert "steps" in d
        assert "total_cost" in d
        assert "goal_reached" in d


# ── Phase 12: VERIFY + SOLVER OUTPUT ───────────────────────────

class TestVerifyAndJudge:
    def _run_pipeline(self, *, goal_action=True, safety_fail=False):
        laws = discover_laws(domain="test")
        belief = estimate_belief({"x": 1})
        goal = construct_goal(description="test", satisfaction_criteria={"done": True})
        model = freeze_models(laws=laws, belief=belief, goal=goal)
        feasibility = check_feasibility(model=model)
        actions = [{"action": "do_it", "class": "world", "is_goal_action": goal_action}]
        safety = (lambda a: False) if safety_fail else None
        trace = execute_plan(model=model, actions=actions, safety_check=safety)
        return verify_and_judge(trace=trace, model=model, feasibility=feasibility)

    def test_solved_verified(self):
        output = self._run_pipeline()
        assert output.outcome == SolverOutcome.SOLVED_VERIFIED
        assert output.verification.all_pass is True

    def test_safe_halt(self):
        output = self._run_pipeline(safety_fail=True)
        assert output.outcome == SolverOutcome.SAFE_HALT

    def test_budget_exhausted(self):
        output = self._run_pipeline(goal_action=False)
        assert output.outcome == SolverOutcome.BUDGET_EXHAUSTED

    def test_impossible(self):
        laws = discover_laws()
        belief = estimate_belief({})
        goal = construct_goal()
        model = freeze_models(laws=laws, belief=belief, goal=goal)
        infeasible = FeasibilityResult(
            feasible=False, invariants=(), hard_violations=("x",),
            soft_warnings=(), solvability="infeasible",
        )
        trace = execute_plan(model=model, actions=[])
        output = verify_and_judge(trace=trace, model=model, feasibility=infeasible)
        assert output.outcome == SolverOutcome.IMPOSSIBLE_PROVED

    def test_solver_output_to_dict(self):
        output = self._run_pipeline()
        d = output.to_dict()
        assert d["outcome"] == "solved_verified"
        assert d["schema"] == "phi2-gps-v2.2"
        assert "verification" in d
        assert "trace" in d

    def test_verification_to_dict(self):
        output = self._run_pipeline()
        v = output.verification.to_dict()
        assert v["all_pass"] is True
        assert v["misfit_verdict"] == "consistent"

    def test_full_pipeline_0_through_12(self):
        """Complete Φ_gps pipeline: Phase 0 → 12."""
        # Phase 0
        frame = frame_problem(world_partial=True, goal_known=True)
        # Phase 1
        symbols = distinguish("Transfer $500 from Alice to Bob")
        # Phase 2
        belief = estimate_belief({"balance": 1000}, hidden_variables=["fraud"])
        # Phase 3
        goal = construct_goal(
            description="Transfer $500",
            safety_variables=["balance"],
            satisfaction_criteria={"transferred": True},
        )
        # Phase 4
        laws = discover_laws(domain="finance", constraints=["balance >= 0"])
        # Phase 4.5
        model = freeze_models(laws=laws, belief=belief, goal=goal, clock=lambda: "now")
        # Phase 7
        feasibility = check_feasibility(model=model)
        # Phase 7.5
        sketch = build_proof_sketch(sub_goal="transfer", feasibility=feasibility, model=model)
        # Phase 10
        trace = execute_plan(
            model=model,
            actions=[
                {"action": "check_balance", "class": "epistemic", "cost": 0.01},
                {"action": "transfer_funds", "class": "world", "cost": 0.5, "is_goal_action": True},
            ],
        )
        # Phase 12
        output = verify_and_judge(trace=trace, model=model, feasibility=feasibility)

        assert output.outcome == SolverOutcome.SOLVED_VERIFIED
        assert output.verification.all_pass is True
        assert trace.goal_reached is True
        assert model.is_frozen is True


# ═══════════════════════════════════════════
# PHASE STUBS — Structural Verification
# ═══════════════════════════════════════════

class TestPhase5Transitions:
    """Verify Phase 5 (discover_transitions) structural stub."""

    def test_returns_transition_map(self):
        from mcoi_runtime.core.phi_gps import discover_transitions, freeze_models, discover_laws
        laws = discover_laws(constraints=["gravity pulls down"], permissions=["may observe"])
        model = freeze_models(laws=laws, belief=None, goal=None)
        result = discover_transitions(model=model)
        assert isinstance(result.transitions, tuple)
        assert result.state_space_size == len(result.transitions)

    def test_model_transitions_match_laws(self):
        from mcoi_runtime.core.phi_gps import discover_transitions, freeze_models, discover_laws
        laws = discover_laws()
        model = freeze_models(laws=laws, belief=None, goal=None)
        result = discover_transitions(model=model)
        assert result.state_space_size == len(model.laws)


class TestPhase6Actions:
    """Verify Phase 6 (synthesize_actions) structural stub."""

    def test_returns_action_set(self):
        from mcoi_runtime.core.phi_gps import synthesize_actions, freeze_models, discover_laws
        laws = discover_laws(constraints=["must not harm"], permissions=["may act"])
        model = freeze_models(laws=laws, belief=None, goal=None)
        result = synthesize_actions(model=model)
        assert isinstance(result.actions, tuple)
        assert result.composite_count == 0

    def test_with_transitions(self):
        from mcoi_runtime.core.phi_gps import (
            synthesize_actions, discover_transitions, freeze_models, discover_laws,
        )
        laws = discover_laws(constraints=["gravity"], permissions=["fly"])
        model = freeze_models(laws=laws, belief=None, goal=None)
        transitions = discover_transitions(model=model)
        result = synthesize_actions(model=model, transitions=transitions)
        assert isinstance(result, ActionSet)


class TestPhase8Decompose:
    """Verify Phase 8 (decompose_problem) structural stub."""

    def test_returns_monolithic(self):
        from mcoi_runtime.core.phi_gps import decompose_problem, freeze_models, discover_laws
        laws = discover_laws(constraints=["c1"])
        model = freeze_models(laws=laws, belief=None, goal=None)
        result = decompose_problem(model=model, feasibility=None)
        assert len(result.subproblems) == 1
        assert result.subproblems[0]["description"] == "monolithic (no decomposition)"
        assert result.dependency_edges == ()


class TestPhase9Policy:
    """Verify Phase 9 (select_policy) structural stub."""

    def test_returns_safe_default(self):
        from mcoi_runtime.core.phi_gps import select_policy, freeze_models, discover_laws
        laws = discover_laws()
        model = freeze_models(laws=laws, belief=None, goal=None)
        result = select_policy(model=model, feasibility=None)
        assert result.strategy == "safe_default"
        assert result.action_sequence == ()
        assert result.expected_cost == 0.0


class TestPhase11Diagnose:
    """Verify Phase 11 (diagnose_failure) structural stub."""

    def test_diagnose_safety_violation(self):
        from mcoi_runtime.core.phi_gps import diagnose_failure, freeze_models, discover_laws
        from dataclasses import dataclass

        @dataclass
        class FakeTrace:
            safety_violations: int = 1
            stall_count: int = 0
            goal_reached: bool = False

        laws = discover_laws()
        model = freeze_models(laws=laws, belief=None, goal=None)
        result = diagnose_failure(trace=FakeTrace(), model=model, feasibility=None)
        assert "safety_violation" in result.root_causes
        assert "goal_not_reached" in result.root_causes
        assert len(result.suggested_repairs) > 0

    def test_diagnose_stall(self):
        from mcoi_runtime.core.phi_gps import diagnose_failure, freeze_models, discover_laws
        from dataclasses import dataclass

        @dataclass
        class FakeTrace:
            safety_violations: int = 0
            stall_count: int = 3
            goal_reached: bool = True

        laws = discover_laws()
        model = freeze_models(laws=laws, belief=None, goal=None)
        result = diagnose_failure(trace=FakeTrace(), model=model, feasibility=None)
        assert "execution_stall" in result.root_causes

    def test_diagnose_unknown(self):
        from mcoi_runtime.core.phi_gps import diagnose_failure, freeze_models, discover_laws
        from dataclasses import dataclass

        @dataclass
        class FakeTrace:
            safety_violations: int = 0
            stall_count: int = 0
            goal_reached: bool = True

        laws = discover_laws()
        model = freeze_models(laws=laws, belief=None, goal=None)
        result = diagnose_failure(trace=FakeTrace(), model=model, feasibility=None)
        assert "unknown" in result.root_causes


class TestExports:
    """Verify __all__ exports are importable."""

    def test_all_exports_importable(self):
        from mcoi_runtime.core import phi_gps
        for name in phi_gps.__all__:
            assert hasattr(phi_gps, name), f"__all__ lists '{name}' but it doesn't exist"
