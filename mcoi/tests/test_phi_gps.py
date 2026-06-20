"""Φ_gps Runtime Tests — Phases 0-12."""

import pytest

from mcoi_runtime.core.phi_gps import (
    AdapterReceipt,
    AgentMode,
    ActionSet,
    BeliefLedger,
    FeasibilityResult,
    GoalStatus,
    KnowledgeLevel,
    ModelStatus,
    NormKind,
    PHI_GPS_V3_SCHEMA_VERSION,
    PROBLEM_STAR_FIELD_NAMES,
    CompiledProblem,
    CompilerAssumption,
    CompilerContradiction,
    CompilerProofRequirement,
    CompilerRisk,
    CompilerUnknown,
    ContradictionLedger,
    CounterfactualLab,
    DeterministicPlatformAdapter,
    FailureKind,
    GovernancePreflight,
    LearningSchemaLibrary,
    PlatformProofReceipt,
    PlatformActionClass,
    PlatformExecutionResult,
    PlatformPolicy,
    PlatformTrace,
    PlatformTraceEventKind,
    PlatformVerdict,
    PolicyHint,
    PolicyClass,
    ProblemCompiler,
    ProblemDomainClass,
    ProblemEvidenceInput,
    ProblemFieldStatus,
    ProblemShapeMetrics,
    ProblemStar,
    ProblemStarField,
    ProfileVector,
    ProofState,
    RepresentationLab,
    RegistryKind,
    ResourceLevel,
    RequiredCertainty,
    RawProblemEnvelope,
    SolverMode,
    SolverOutcome,
    build_proof_sketch,
    build_platform_registry,
    build_problem_star,
    check_feasibility,
    compute_voi,
    construct_goal,
    discover_laws,
    distinguish,
    emit_platform_proof_receipt,
    estimate_belief,
    execute_plan,
    frame_problem,
    freeze_models,
    repair_for_failure,
    profile_problem_star,
    route_solver,
    run_platform_cycle,
    select_strategies,
    synthesize_platform_policy,
    verify_and_judge,
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


# ── Phi2-GPS v3 Platform Data Model ───────────────────────────

class TestPhiGpsV3PlatformDataModel:
    def test_problem_star_builder_preserves_kernel_contract(self):
        problem = build_problem_star(
            problem_id="problem-1",
            values={
                "W": {"state": "latent"},
                "B": {"hypothesis": "candidate"},
                "G": {"done": True},
                "Lambda": ("no_silent_failure",),
            },
            statuses={"G": ProblemFieldStatus.PARTIAL},
            evidence_refs={"W": ("evidence:world-1",)},
            input_hash="sha256:input-1",
        )
        payload = problem.to_dict()

        assert tuple(payload["fields"]) == PROBLEM_STAR_FIELD_NAMES
        assert problem.field("W").status == ProblemFieldStatus.KNOWN
        assert problem.field("G").status == ProblemFieldStatus.PARTIAL
        assert "O" in problem.unknown_fields
        assert payload["schema"] == PHI_GPS_V3_SCHEMA_VERSION

    def test_problem_star_rejects_incomplete_or_invalid_fields(self):
        valid_fields = tuple(
            ProblemStarField(name=field_name, status=ProblemFieldStatus.UNKNOWN)
            for field_name in PROBLEM_STAR_FIELD_NAMES
        )

        try:
            ProblemStar(problem_id="bad-problem", fields=valid_fields[:-1])
        except ValueError as exc:
            observed_message = str(exc)
        else:
            observed_message = ""

        assert "canonical P* field order" in observed_message
        assert len(valid_fields) == len(PROBLEM_STAR_FIELD_NAMES)
        assert valid_fields[0].name == "W"

    def test_platform_profile_vector_uses_domain_certainty_and_shape(self):
        problem = build_problem_star(
            problem_id="problem-profile",
            values={"W": "observed", "A_e": ("observe",), "A_w": ("commit",), "Pi": ("proof-needed",)},
            statuses={"A_w": ProblemFieldStatus.HYPOTHESIZED, "T": ProblemFieldStatus.UNKNOWN},
        )
        shape = ProblemShapeMetrics(
            branching_factor=0.2,
            constraint_density=0.4,
            uncertainty_density=0.8,
            irreversibility_score=0.6,
            goal_sharpness=0.1,
            adversarial_pressure=0.0,
            resource_pressure=0.5,
            proof_burden=0.7,
            coupling_strength=0.3,
        )
        profile = profile_problem_star(
            problem,
            domain=ProblemDomainClass.SOFTWARE_REPAIR,
            required_certainty=RequiredCertainty.FORMAL,
            shape_metrics=shape,
        )
        payload = profile.to_dict()

        assert profile.domain == ProblemDomainClass.SOFTWARE_REPAIR
        assert profile.required_certainty == RequiredCertainty.FORMAL
        assert profile.k_actions == ProblemFieldStatus.HYPOTHESIZED
        assert profile.dominant_shape == "uncertainty_density"
        assert payload["shape_metrics"]["uncertainty_density"] == 0.8

    def test_platform_trace_records_append_only_events(self):
        trace = PlatformTrace(problem_id="problem-trace")
        compiled_trace = trace.record(
            kind=PlatformTraceEventKind.COMPILED,
            cause="problem compiler separated evidence from assumptions",
            payload={"compiled": True},
            proof_state=ProofState.PASS,
        )
        executed_trace = compiled_trace.record(
            kind=PlatformTraceEventKind.EXECUTED,
            cause="governed adapter preflight passed",
            payload={"action": "run_focused_tests"},
            proof_state=ProofState.PASS,
        )

        assert trace.event_count == 0
        assert compiled_trace.event_count == 1
        assert executed_trace.events[1].event_id == 1
        assert executed_trace.events_by_kind(PlatformTraceEventKind.EXECUTED)[0].payload["action"] == "run_focused_tests"
        assert executed_trace.to_dict()["events"][0]["proof_state"] == "pass"

    def test_platform_records_freeze_mapping_payloads(self):
        trace = PlatformTrace(problem_id="problem-immutable").record(
            kind=PlatformTraceEventKind.COMPILED,
            cause="compile trace payload is retained",
            payload={"count": 1},
            proof_state=ProofState.PASS,
        )
        problem = build_problem_star(
            problem_id="problem-immutable",
            values={"W": "known"},
            confidences={"W": 1.0},
        )
        receipt = emit_platform_proof_receipt(
            problem=problem,
            trace=trace,
            terminal_verdict=PlatformVerdict.AWAITING_EVIDENCE,
            verification_result={"checked": True},
        )
        compiled = ProblemCompiler.compile(RawProblemEnvelope(
            id="problem-compiler-immutable",
            input_type="text",
            raw_content="Need verify local proof before any action.",
            declared_goal="local proof only",
        ))

        try:
            trace.events[0].payload["count"] = 2
        except TypeError as exc:
            payload_error = str(exc)
        else:
            payload_error = ""
        try:
            receipt.verification_result["checked"] = False
        except TypeError as exc:
            receipt_error = str(exc)
        else:
            receipt_error = ""
        try:
            compiled.confidence_map["W"] = 0.0
        except TypeError as exc:
            confidence_error = str(exc)
        else:
            confidence_error = ""

        assert payload_error
        assert receipt_error
        assert confidence_error
        assert trace.to_dict()["events"][0]["payload"]["count"] == 1

    def test_problem_compiler_separates_assumptions_unknowns_risks_and_proof(self):
        envelope = RawProblemEnvelope(
            id="problem-compile",
            input_type="text",
            raw_content=(
                "Assumption: maybe the local runtime can deploy safely. "
                "Need evidence before any irreversible customer deployment. "
                "This conflicts with no deployment."
            ),
            source="local",
            declared_goal="prepare local proof without deployment",
            declared_constraints=("no deployment", "no customer access"),
        )

        compiled = ProblemCompiler.compile(envelope)
        payload = compiled.to_dict()

        assert isinstance(compiled, CompiledProblem)
        assert any(isinstance(item, CompilerAssumption) for item in compiled.assumptions)
        assert any(isinstance(item, CompilerUnknown) for item in compiled.unknowns)
        assert any(isinstance(item, CompilerRisk) for item in compiled.risks)
        assert any(isinstance(item, CompilerContradiction) for item in compiled.contradictions)
        assert any(isinstance(item, CompilerProofRequirement) for item in compiled.proof_requirements)
        assert compiled.safe_default_policy in (PolicyHint.EPISTEMIC_FIRST, PolicyHint.AUTHORITY_REVIEW)
        assert compiled.kernel_draft.input_hash == envelope.input_hash
        assert compiled.trace.event_count == 2
        assert payload["safe_default_policy"] == compiled.safe_default_policy.value

    def test_platform_proof_receipt_binds_problem_trace_and_verdict(self):
        problem = build_problem_star(
            problem_id="problem-receipt",
            values={"W": "known", "B": "belief", "G": "goal", "A_w": ("commit",), "Pi": ("verification",)},
            input_hash="sha256:receipt-input",
        )
        trace = (
            PlatformTrace(problem_id=problem.problem_id)
            .record(
                kind=PlatformTraceEventKind.EXECUTED,
                cause="adapter receipt emitted",
                payload={"action": "commit_change"},
                proof_state=ProofState.PASS,
            )
            .record(
                kind=PlatformTraceEventKind.VERIFIED,
                cause="dual verifier passed",
                payload={"evidence_ref": "receipt:verify-1"},
                proof_state=ProofState.PASS,
            )
        )
        receipt = emit_platform_proof_receipt(
            problem=problem,
            trace=trace,
            terminal_verdict=PlatformVerdict.SOLVED_VERIFIED,
            policy_selected="proof_policy",
            constraints_satisfied=("no_silent_failure",),
            verification_result={"all_pass": True},
        )
        payload = receipt.to_dict()

        assert isinstance(receipt, PlatformProofReceipt)
        assert receipt.receipt_id.startswith("phi-gps-v3-receipt-")
        assert payload["input_hash"] == "sha256:receipt-input"
        assert payload["terminal_verdict"] == "solved_verified"
        assert payload["action_trace"] == ["commit_change"]
        assert payload["evidence_trace"] == ["receipt:verify-1"]


class TestPhiGpsV3ProblemCompiler:
    def test_compiler_separates_evidence_assumptions_and_kernel_fields(self):
        envelope = RawProblemEnvelope(
            id="compile-1",
            input_type="natural_language",
            raw_content=(
                "Observed state: service failing. "
                "Assume cache is stale. "
                "Create repair plan after diagnosis changes to healthy and verify receipt."
            ),
            source="unit-test",
            requester="operator",
            authority_context="local-proof",
            declared_goal="restore service health",
            declared_constraints=("must preserve rollback",),
        )
        compiled = ProblemCompiler.compile(envelope)

        assert isinstance(compiled, CompiledProblem)
        assert any(isinstance(item, CompilerAssumption) for item in compiled.assumptions)
        assert compiled.kernel_draft.field("W").status == ProblemFieldStatus.PARTIAL
        assert compiled.kernel_draft.field("G").status == ProblemFieldStatus.KNOWN
        assert compiled.trace.event_count == 2

    def test_compiler_emits_epistemic_policy_for_vague_problem(self):
        envelope = RawProblemEnvelope(
            id="compile-vague",
            input_type="natural_language",
            raw_content="make this better",
            source="unit-test",
        )
        compiled = ProblemCompiler.compile(envelope)
        unknown_dimensions = {unknown.dimension for unknown in compiled.unknowns}

        assert any(isinstance(item, CompilerUnknown) for item in compiled.unknowns)
        assert {"goal", "world_state", "proof"}.issubset(unknown_dimensions)
        assert compiled.safe_default_policy == PolicyHint.EPISTEMIC_FIRST
        assert compiled.required_clarifications
        assert compiled.kernel_draft.field("G").status == ProblemFieldStatus.UNKNOWN

    def test_compiler_records_declared_constraint_contradiction(self):
        envelope = RawProblemEnvelope(
            id="compile-conflict",
            input_type="natural_language",
            raw_content="Observed state: release candidate ready. deploy service and verify proof.",
            source="unit-test",
            declared_goal="deploy service",
            declared_constraints=("must deploy", "must not deploy"),
        )
        compiled = ProblemCompiler.compile(envelope)

        assert any(isinstance(item, CompilerContradiction) for item in compiled.contradictions)
        assert compiled.contradictions[0].severity == "critical"
        assert compiled.safe_default_policy == PolicyHint.AUTHORITY_REVIEW
        assert compiled.kernel_draft.field("Lambda").status == ProblemFieldStatus.CONFLICTING
        assert "contradiction_resolution" in {unknown.dimension for unknown in compiled.unknowns}

    def test_compiler_sets_proof_first_for_critical_risk(self):
        envelope = RawProblemEnvelope(
            id="compile-risk",
            input_type="natural_language",
            raw_content=(
                "Observed state: invoice approved. "
                "Send payment after approval changes to paid and verify payment receipt."
            ),
            source="unit-test",
            declared_goal="close approved payment",
            declared_constraints=("must require approval",),
        )
        compiled = ProblemCompiler.compile(envelope)

        assert any(isinstance(item, CompilerRisk) for item in compiled.risks)
        assert any(isinstance(item, CompilerProofRequirement) for item in compiled.proof_requirements)
        assert compiled.risks[0].severity == "critical"
        assert compiled.safe_default_policy == PolicyHint.PROOF_FIRST
        assert compiled.kernel_draft.field("A_w").status == ProblemFieldStatus.HYPOTHESIZED

    def test_raw_problem_envelope_hash_is_deterministic(self):
        first = RawProblemEnvelope(
            id="compile-hash",
            input_type="json",
            raw_content={"goal": "verify", "state": "observed"},
            source="unit-test",
            declared_constraints=("must verify",),
        )
        second = RawProblemEnvelope(
            id="compile-hash",
            input_type="json",
            raw_content={"state": "observed", "goal": "verify"},
            source="unit-test",
            declared_constraints=("must verify",),
        )

        assert first.input_hash == second.input_hash
        assert first.to_dict()["input_hash"] == first.input_hash
        assert first.declared_constraints == ("must verify",)

    def test_compiler_binds_repository_world_state_projection_evidence(self):
        binding = _repository_world_state_binding()
        evidence_inputs = _problem_evidence_inputs_from_binding(binding)
        envelope = RawProblemEnvelope(
            id="compile-repository-world-state",
            input_type="natural_language",
            raw_content="Route repository observation into planning input.",
            source="unit-test",
            requester="operator",
            authority_context="local-proof",
            declared_goal="verify repository planning input",
            evidence_inputs=evidence_inputs,
        )

        compiled = ProblemCompiler.compile(envelope)
        world_field = compiled.kernel_draft.field("W")
        evidence_field = compiled.kernel_draft.field("O")
        knowledge_field = compiled.kernel_draft.field("K")
        proof_field = compiled.kernel_draft.field("Pi")

        assert isinstance(evidence_inputs[0], ProblemEvidenceInput)
        assert world_field.status == ProblemFieldStatus.KNOWN
        assert evidence_field.status == ProblemFieldStatus.KNOWN
        assert evidence_inputs[0].evidence_id in world_field.evidence_refs
        assert evidence_inputs[0].evidence_id in evidence_field.evidence_refs
        assert evidence_inputs[0].evidence_id in knowledge_field.evidence_refs
        assert evidence_inputs[0].evidence_id in proof_field.evidence_refs
        assert not any(unknown.dimension == "world_state" for unknown in compiled.unknowns)
        assert compiled.trace.events[-1].payload["evidence_input_count"] == len(evidence_inputs) == 8

    def test_repository_world_state_projection_with_contradiction_fails_closed(self):
        binding = _repository_world_state_binding(failing_command="git_status")

        assert binding.admitted is False
        assert binding.evidence_items == ()
        assert binding.proof_obligations[0]["proof_state"] == "Fail"
        assert _problem_evidence_inputs_from_binding(binding) == ()


# ── Phase 1: DISTINGUISH ──────────────────────────────────────

class TestPhiGpsV3PlatformRuntime:
    def test_registry_loads_compiler_outputs_and_adapter_contract(self):
        compiled = ProblemCompiler.compile(RawProblemEnvelope(
            id="platform-registry",
            input_type="natural_language",
            raw_content="Observed state: ServiceAlpha requires approval and validate local proof receipt.",
            source="unit-test",
            authority_context="local-proof",
            declared_goal="validate local proof",
            declared_constraints=("must preserve audit trail",),
        ))
        registry = build_platform_registry(compiled)

        assert registry.latest(RegistryKind.ADAPTER, DeterministicPlatformAdapter.id) is not None
        assert len(registry.records_by_kind(RegistryKind.PROOF)) >= 1
        assert len(registry.records_by_kind(RegistryKind.LAW)) >= 1
        assert registry.register(registry.records[0]).to_dict()["record_count"] == len(registry.records) + 1

    def test_router_prioritizes_uncertainty_and_formal_proof_modes(self):
        compiled = ProblemCompiler.compile(RawProblemEnvelope(
            id="platform-route",
            input_type="natural_language",
            raw_content="make this better",
            source="unit-test",
        ))
        profile = profile_problem_star(
            compiled.kernel_draft,
            required_certainty=RequiredCertainty.FORMAL,
            domain=ProblemDomainClass.SOFTWARE_REPAIR,
        )
        route = route_solver(profile, compiled.kernel_draft)

        assert SolverMode.DIAGNOSIS in route.mode_stack
        assert SolverMode.PROOF_CONSTRUCTION in route.mode_stack
        assert SolverMode.SOFTWARE_REPAIR in route.mode_stack
        assert route.profile_hash
        assert route.to_dict()["primary_mode"] == route.primary_mode.value

    def test_router_accepts_inceptadive_advisory_report_without_execution_authority(self):
        from mcoi_runtime.core.phi_inceptadive_bridge import build_phi_inceptadive_report

        kernel = build_problem_star(
            problem_id="platform-advisory-route",
            values={
                "W": "observed",
                "G": "verified closure",
                "Lambda": ("must preserve audit trail",),
                "Pi": ("receipt proof",),
            },
            statuses={
                "B": ProblemFieldStatus.HYPOTHESIZED,
                "A_w": ProblemFieldStatus.HYPOTHESIZED,
                "T": ProblemFieldStatus.UNKNOWN,
                "Pi": ProblemFieldStatus.PARTIAL,
            },
            evidence_refs={"W": ("unit-world",), "Lambda": ("unit-law",), "Pi": ("unit-proof",)},
            input_hash="sha256:advisory-route",
        )
        profile = profile_problem_star(kernel)
        advisory_report = build_phi_inceptadive_report(kernel, max_findings=10)
        route = route_solver(profile, kernel, advisory_report=advisory_report)
        payload = route.to_dict()

        assert advisory_report.execution_approval is False
        assert advisory_report.report_id in route.advisory_report_ids
        assert SolverMode.PROOF_CONSTRUCTION in route.mode_stack
        assert SolverMode.RISK_CONTAINMENT in route.mode_stack
        assert any("advisory report" in reason for reason in route.routing_reasons)
        assert payload["advisory_report_ids"] == [advisory_report.report_id]

    def test_router_rejects_advisory_report_with_execution_approval(self):
        class BadAdvisoryReport:
            report_id = "bad-report"
            problem_id = "platform-bad-advisory"
            execution_approval = True
            suggested_solver_modes = (SolverMode.SEARCH,)
            proof_gaps = ()
            hidden_assumptions = ()
            repair_recommendations = ()
            fracture_count = 0

        kernel = build_problem_star(problem_id="platform-bad-advisory", values={"W": "observed"})
        profile = profile_problem_star(kernel)

        with pytest.raises(ValueError, match="cannot approve execution"):
            route_solver(profile, kernel, advisory_report=BadAdvisoryReport())

    def test_policy_synthesizer_emits_proof_and_world_action_candidates(self):
        compiled = ProblemCompiler.compile(RawProblemEnvelope(
            id="platform-policy",
            input_type="natural_language",
            raw_content=(
                "Observed state: invoice approved. "
                "Send payment after approval changes to paid and verify payment receipt."
            ),
            source="unit-test",
            authority_context="finance-approval",
            declared_goal="close approved payment",
            declared_constraints=("must require approval",),
        ))
        profile = profile_problem_star(compiled.kernel_draft)
        route = route_solver(profile, compiled.kernel_draft)
        policy = synthesize_platform_policy(compiled, route, profile)
        action_classes = {action.action_class for action in policy.actions}

        assert isinstance(policy, PlatformPolicy)
        assert policy.policy_class == PolicyClass.PROOF
        assert PlatformActionClass.EPISTEMIC in action_classes
        assert PlatformActionClass.WORLD_CHANGING in action_classes
        assert policy.requires_counterfactual is True

    def test_counterfactual_and_preflight_block_unsafe_world_action(self):
        compiled = ProblemCompiler.compile(RawProblemEnvelope(
            id="platform-unsafe",
            input_type="natural_language",
            raw_content=(
                "Observed state: invoice approved. "
                "Send payment after approval changes to paid and verify payment receipt."
            ),
            source="unit-test",
            authority_context="finance-approval",
            declared_goal="close approved payment",
            declared_constraints=("must require approval",),
        ))
        profile = profile_problem_star(compiled.kernel_draft)
        route = route_solver(profile, compiled.kernel_draft)
        policy = synthesize_platform_policy(compiled, route, profile)
        report = CounterfactualLab.test(policy, compiled.kernel_draft)
        world_action = next(action for action in policy.actions if action.action_class == PlatformActionClass.WORLD_CHANGING)
        preflight = GovernancePreflight.preflight(world_action, compiled, report)

        assert report.unsafe is True
        assert report.recommendation == "reject_policy"
        assert preflight.passed is False
        assert preflight.proof_state == ProofState.FAIL
        assert "risk" in preflight.blocked_level or preflight.blocked_level == "permission_check"

    def test_run_platform_cycle_vague_problem_returns_awaiting_evidence(self):
        compiled = ProblemCompiler.compile(RawProblemEnvelope(
            id="platform-cycle-vague",
            input_type="natural_language",
            raw_content="make this better",
            source="unit-test",
        ))
        result = run_platform_cycle(compiled)
        event_kinds = {event.kind for event in result.trace.events}

        assert isinstance(result, PlatformExecutionResult)
        assert result.verdict == PlatformVerdict.AWAITING_EVIDENCE
        assert PlatformTraceEventKind.ROUTED in event_kinds
        assert PlatformTraceEventKind.VERIFIED in event_kinds
        assert result.receipt.policy_selected == result.policy.policy_id

    def test_run_platform_cycle_complete_local_problem_admits_learning_transfer(self):
        compiled = ProblemCompiler.compile(RawProblemEnvelope(
            id="platform-cycle-solved",
            input_type="natural_language",
            raw_content="Observed state: local proof verified. Proof receipt proves goal.",
            source="unit-test",
            authority_context="local-proof",
            declared_goal="local proof verified",
            declared_constraints=("must preserve audit trail",),
        ))
        result = run_platform_cycle(compiled, learning_library=LearningSchemaLibrary())
        retrieved = result.learning_library.retrieve(result.route.profile_hash)

        assert result.verdict == PlatformVerdict.SOLVED_VERIFIED
        assert result.verification.all_pass is True
        assert len(retrieved) == 1
        assert retrieved[0].policy_id == result.policy.policy_id
        assert result.receipt.learning_updates

    def test_representation_lab_accepts_only_governed_mutations(self):
        accepted_problem = build_problem_star(
            problem_id="platform-representation",
            values={"W": "observed", "Lambda": ("must preserve evidence",)},
            evidence_refs={"W": ("unit-evidence",), "Lambda": ("unit-law",)},
            input_hash="sha256:representation",
        )
        rejected_problem = build_problem_star(
            problem_id="platform-representation-conflict",
            values={"W": "observed", "Lambda": ("must deploy", "must not deploy")},
            statuses={"Lambda": ProblemFieldStatus.CONFLICTING},
            evidence_refs={"W": ("unit-evidence",), "Lambda": ("unit-law",)},
            input_hash="sha256:representation-conflict",
        )
        accepted = RepresentationLab.mutate(
            accepted_problem,
            failure_kind=FailureKind.REPRESENTATION_FAILURE,
            operator="causalize",
        )
        rejected = RepresentationLab.mutate(
            rejected_problem,
            failure_kind=FailureKind.REPRESENTATION_FAILURE,
            operator="causalize",
        )

        assert accepted.accepted is True
        assert accepted.search_burden_delta < 0
        assert rejected.accepted is False
        assert repair_for_failure(FailureKind.REPRESENTATION_FAILURE) == "representation_mutation"

    def test_ledgers_and_adapter_receipts_reject_missing_identity_or_observation(self):
        with pytest.raises(ValueError, match="contradiction ledger problem_id"):
            ContradictionLedger(problem_id="")
        with pytest.raises(ValueError, match="belief ledger problem_id"):
            BeliefLedger(problem_id="")
        with pytest.raises(ValueError, match="adapter receipt observation"):
            AdapterReceipt(adapter_id="adapter", action_id="action", outcome="ok", observation="")

    def test_policy_synthesizer_preserves_dict_action_values_in_ids(self):
        kernel = build_problem_star(
            problem_id="platform-dict-actions",
            values={
                "W": "observed",
                "I": "local authority",
                "G": "audit records exist",
                "Lambda": ("must preserve audit trail",),
                "A_w": {"create": ["invoice record", "audit log"]},
                "Pi": "receipt proof",
            },
            evidence_refs={
                "W": ("unit-observation",),
                "I": ("unit-authority",),
                "G": ("unit-goal",),
                "Lambda": ("unit-law",),
                "A_w": ("unit-actions",),
                "Pi": ("unit-proof",),
            },
            input_hash="sha256:dict-actions",
        )
        compiled = CompiledProblem(
            kernel_draft=kernel,
            symbols=(),
            assumptions=(),
            unknowns=(),
            contradictions=(),
            risks=(),
            proof_requirements=(CompilerProofRequirement("proof-1", "Verify receipt"),),
            confidence_map={"A_w": 1.0},
            required_clarifications=(),
            safe_default_policy=PolicyHint.PROOF_FIRST,
            trace=PlatformTrace(problem_id=kernel.problem_id),
        )
        profile = profile_problem_star(kernel)
        policy = synthesize_platform_policy(compiled, route_solver(profile, kernel), profile)
        world_action_ids = tuple(
            action.id for action in policy.actions
            if action.action_class == PlatformActionClass.WORLD_CHANGING
        )

        assert "simulate_world:create_invoice_record" in world_action_ids
        assert "simulate_world:create_audit_log" in world_action_ids
        assert len(world_action_ids) == 2
        assert len(set(world_action_ids)) == len(world_action_ids)

    def test_authorized_local_world_actions_require_executed_receipt_coverage(self):
        compiled = ProblemCompiler.compile(RawProblemEnvelope(
            id="platform-authorized-world",
            input_type="natural_language",
            raw_content=(
                "Observed state: local record approved. "
                "Create audit record after approval changes to recorded and verify receipt."
            ),
            source="unit-test",
            authority_context="local-authority",
            declared_goal="audit record is recorded",
            declared_constraints=("must preserve audit trail",),
        ))
        result = run_platform_cycle(compiled, allow_world_actions=True)
        executed_events = result.trace.events_by_kind(PlatformTraceEventKind.EXECUTED)

        assert executed_events
        assert result.verification.pi_side_effect == ProofState.PASS
        assert result.verdict == PlatformVerdict.SOLVED_VERIFIED
        assert "world-changing actions have executed adapter receipts" in result.verification.reasons


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
        assert any(law.name == "domain_boundary" for law in result.laws)

    def test_constraints_become_laws(self):
        result = discover_laws(constraints=["balance >= 0", "amount > 0"])
        assert len(result.laws) >= 4  # 2 constraints + 2 universal

    def test_universal_governance_laws(self):
        result = discover_laws()
        names = {law.name for law in result.laws}
        assert "identity_preservation" in names
        assert "audit_completeness" in names

    def test_hard_law_confidence(self):
        result = discover_laws()
        for law in result.laws:
            if law.name in ("identity_preservation", "audit_completeness"):
                assert law.confidence == 1.0

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
        assert frame.profile.k_world == KnowledgeLevel.PARTIAL
        assert symbols.symbol_count > 0
        assert sketch.has_unknown is True
        assert trace.goal_reached is True
        assert model.is_frozen is True


# ═══════════════════════════════════════════
# PHASE SOLVER SURFACES — Structural Verification
# ═══════════════════════════════════════════

class TestPhase5Transitions:
    """Verify Phase 5 (discover_transitions) bounded transition contracts."""

    def test_returns_transition_map(self):
        from mcoi_runtime.core.phi_gps import discover_transitions, freeze_models, discover_laws
        laws = discover_laws(constraints=["gravity pulls down"], permissions=["may observe"])
        model = freeze_models(laws=laws, belief=None, goal=None)
        result = discover_transitions(model=model)
        assert isinstance(result.transitions, tuple)
        assert result.state_space_size == len(result.transitions)
        assert {transition["origin"] for transition in result.transitions} == {"law"}
        assert all(transition["action"].startswith("preserve_") for transition in result.transitions)

    def test_observation_transitions_are_preserved_and_bounded(self):
        from mcoi_runtime.core.phi_gps import discover_transitions, freeze_models, discover_laws
        laws = discover_laws(constraints=["audit required"])
        model = freeze_models(laws=laws, belief=None, goal=None)
        result = discover_transitions(
            model=model,
            observation_data=[
                {
                    "source": "queued",
                    "action": "dispatch",
                    "target": "running",
                    "probability": 1.7,
                    "evidence_ref": "trace:1",
                }
            ],
        )
        observed = result.transitions[0]
        assert observed["origin"] == "observation"
        assert observed["probability"] == 1.0
        assert observed["evidence_ref"] == "trace:1"
        assert result.state_space_size == len(model.laws) + 2


class TestPhase6Actions:
    """Verify Phase 6 (synthesize_actions) bounded action contracts."""

    def test_returns_action_set(self):
        from mcoi_runtime.core.phi_gps import synthesize_actions, freeze_models, discover_laws
        laws = discover_laws(constraints=["must not harm"], permissions=["may act"])
        model = freeze_models(laws=laws, belief=None, goal=None)
        result = synthesize_actions(model=model)
        assert isinstance(result.actions, tuple)
        assert result.composite_count == 0
        assert result.primitive_count == len(result.actions)
        assert all("action" in action for action in result.actions)

    def test_with_transitions(self):
        from mcoi_runtime.core.phi_gps import (
            synthesize_actions, discover_transitions, freeze_models, discover_laws,
        )
        laws = discover_laws(constraints=["gravity"], permissions=["fly"])
        model = freeze_models(laws=laws, belief=None, goal=None)
        transitions = discover_transitions(model=model)
        result = synthesize_actions(model=model, transitions=transitions)
        assert isinstance(result, ActionSet)
        assert result.primitive_count >= len(model.norms)
        assert result.composite_count == 1
        assert any(action["name"] == "complete_transition_sequence" for action in result.actions)


class TestPhase8Decompose:
    """Verify Phase 8 (decompose_problem) bounded decomposition."""

    def test_returns_structured_subproblems(self):
        from mcoi_runtime.core.phi_gps import (
            build_proof_sketch, check_feasibility, construct_goal, decompose_problem, freeze_models, discover_laws,
        )
        laws = discover_laws(constraints=["c1"])
        goal = construct_goal(
            description="complete governed transfer",
            safety_variables=["balance"],
            satisfaction_criteria={"transferred": True},
        )
        model = freeze_models(laws=laws, belief=None, goal=goal)
        feasibility = check_feasibility(model=model)
        proof_sketch = build_proof_sketch(sub_goal="transfer", feasibility=feasibility, model=model)
        result = decompose_problem(model=model, feasibility=feasibility, proof_sketch=proof_sketch)
        kinds = {subproblem["kind"] for subproblem in result.subproblems}
        assert {"safety", "norms", "goal", "evidence"}.issubset(kinds)
        assert (0, 2) in result.dependency_edges
        assert any(subproblem["description"] == "complete governed transfer" for subproblem in result.subproblems)


class TestPhase9Policy:
    """Verify Phase 9 (select_policy) bounded policy selection."""

    def test_returns_safe_default(self):
        from mcoi_runtime.core.phi_gps import select_policy, freeze_models, discover_laws
        laws = discover_laws()
        model = freeze_models(laws=laws, belief=None, goal=None)
        result = select_policy(model=model, feasibility=None)
        assert result.strategy == "safe_default"
        assert result.action_sequence == ()
        assert result.expected_cost == 0.0

    def test_selects_composite_policy_when_actions_are_available(self):
        from mcoi_runtime.core.phi_gps import (
            check_feasibility, decompose_problem, discover_laws, discover_transitions,
            freeze_models, select_policy, synthesize_actions,
        )
        laws = discover_laws(permissions=["may dispatch"])
        model = freeze_models(laws=laws, belief=None, goal=None)
        feasibility = check_feasibility(model=model)
        transitions = discover_transitions(
            model=model,
            observation_data=[{"source": "ready", "action": "dispatch", "target": "done"}],
        )
        actions = synthesize_actions(model=model, transitions=transitions)
        decomposition = decompose_problem(model=model, feasibility=feasibility)
        result = select_policy(model=model, feasibility=feasibility, actions=actions, decomposition=decomposition)
        assert result.strategy == "greedy"
        assert result.action_sequence == ("complete_transition_sequence",)
        assert result.expected_cost > 0.0


class TestPhase11Diagnose:
    """Verify Phase 11 (diagnose_failure) bounded failure diagnosis."""

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

    def test_diagnose_budget_and_model_drift(self):
        from mcoi_runtime.core.phi_gps import diagnose_failure, freeze_models, discover_laws, ExecutionStep
        from dataclasses import dataclass

        @dataclass
        class FakeTrace:
            safety_violations: int = 0
            stall_count: int = 0
            goal_reached: bool = False
            steps: tuple[ExecutionStep, ...] = (
                ExecutionStep(
                    step_id=0,
                    action="expensive_action",
                    action_class="world",
                    outcome="budget_exceeded",
                    surprise=0.9,
                ),
            )

        laws = discover_laws()
        model = freeze_models(laws=laws, belief=None, goal=None)
        result = diagnose_failure(trace=FakeTrace(), model=model, feasibility=None)
        assert "budget_exhausted" in result.root_causes
        assert "model_drift" in result.root_causes
        assert result.model_drift_detected is True


class TestExports:
    """Verify __all__ exports are importable."""

    def test_all_exports_importable(self):
        from mcoi_runtime.core import phi_gps
        for name in phi_gps.__all__:
            assert hasattr(phi_gps, name), f"__all__ lists '{name}' but it doesn't exist"


def _repository_world_state_binding(failing_command: str = ""):
    from datetime import UTC, datetime
    from pathlib import Path

    from gateway.world_state import (
        InMemoryWorldStateStore,
        bind_repository_world_state_projection_to_problem_star_evidence,
        project_repository_observation_packet_to_world_state,
    )
    from scripts.produce_repository_observation_evidence_packet import (
        READ_ONLY_GIT_COMMANDS,
        RepositoryCommandObservation,
        build_repository_observation_evidence_packet,
    )

    observations = []
    for command_name, argv in READ_ONLY_GIT_COMMANDS.items():
        observations.append(
            RepositoryCommandObservation(
                command_name=command_name,
                argv=argv,
                returncode=1 if command_name == failing_command else 0,
                stdout_digest_ref=f"hash://sha256/{command_name}-stdout",
                stderr_digest_ref=f"hash://sha256/{command_name}-stderr",
            )
        )
    packet = build_repository_observation_evidence_packet(
        workspace_root=Path(__file__).resolve().parents[2],
        observed_at=datetime(2026, 6, 20, 12, 0, 0, tzinfo=UTC),
        command_observations=tuple(observations),
    )
    store = InMemoryWorldStateStore(clock=lambda: "2026-06-20T12:00:00Z")
    projection = project_repository_observation_packet_to_world_state(packet, store)
    return bind_repository_world_state_projection_to_problem_star_evidence(
        projection,
        store.planning_claims(tenant_id="foundation-local-only"),
    )


def _problem_evidence_inputs_from_binding(binding):
    if not binding.admitted:
        return ()
    return tuple(
        ProblemEvidenceInput(
            evidence_id=item["evidence_id"],
            source_ref=item["source_ref"],
            statement=item["statement"],
            confidence=item["confidence"],
            field_refs=("W", "O", "K", "Pi"),
        )
        for item in binding.as_problem_star_evidence()
    )
