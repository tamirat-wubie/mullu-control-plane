"""Tests for default governed skill descriptor catalog.

Purpose: verify bootstrap-admitted workflow descriptors do not create raw authority.
Governance scope: default SkillDescriptor catalog, registry admission, and bootstrap binding.
Dependencies: default skill catalog, skill contracts, bootstrap runtime.
Invariants:
  - Default skills are candidate descriptors only.
  - Default skills compose existing capability ids and grant no new capability authority.
  - Bootstrap installs the catalog deterministically.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from mcoi_runtime.app.bootstrap import bootstrap_runtime
from mcoi_runtime.contracts.skill import EffectClass, SkillLifecycle
from mcoi_runtime.core import default_skill_catalog as catalog_module
from mcoi_runtime.core.default_skill_catalog import (
    default_skill_descriptors,
    register_default_skill_descriptors,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.skills import SkillRegistry


EXPECTED_SKILL_IDS = (
    "finance.approval_packet.v1",
    "document.intake_summary.v1",
    "software_dev.change_closure.v1",
    "deployment.witness_publication.v1",
    "adapter.evidence_closure.v1",
    "workflow.governed_composition.v1",
    "incident.rollback_recovery.v1",
    "release.pr_handoff_closure.v1",
    "telemetry.monitoring_triage.v1",
    "agentic_control.project_discipline_mesh.v1",
    "agentic_control.resource_governor.v1",
    "agentic_control.temporal_governor.v1",
    "agentic_control.memory_governor.v1",
    "agentic_control.evidence_governor.v1",
    "agentic_control.math_governor.v1",
    "agentic_control.algorithm_governor.v1",
    "agentic_control.security_governor.v1",
    "agentic_control.swarm_governor.v1",
    "agentic_control.coding_governor.v1",
    "agentic_control.autonomous_operations.v1",
)


def test_default_skill_catalog_names_required_workflows() -> None:
    descriptors = default_skill_descriptors()
    skill_ids = tuple(descriptor.skill_id for descriptor in descriptors)

    assert skill_ids == EXPECTED_SKILL_IDS
    assert all(descriptor.lifecycle is SkillLifecycle.CANDIDATE for descriptor in descriptors)
    assert all(descriptor.metadata["grants_new_capability_authority"] is False for descriptor in descriptors)
    assert all(descriptor.verification_strength.value == "mandatory" for descriptor in descriptors)


def test_default_skill_descriptors_have_governed_boundaries() -> None:
    descriptors = default_skill_descriptors()

    assert all(descriptor.preconditions for descriptor in descriptors)
    assert all(descriptor.postconditions for descriptor in descriptors)
    assert all(descriptor.steps for descriptor in descriptors)
    assert all(descriptor.provider_requirements for descriptor in descriptors)
    assert all(step.action_type for descriptor in descriptors for step in descriptor.steps)


def test_default_skill_effect_classes_match_strongest_workflow_effect() -> None:
    descriptors = {descriptor.skill_id: descriptor for descriptor in default_skill_descriptors()}

    assert descriptors["finance.approval_packet.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["document.intake_summary.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["software_dev.change_closure.v1"].effect_class is EffectClass.EXTERNAL_WRITE
    assert descriptors["deployment.witness_publication.v1"].effect_class is EffectClass.EXTERNAL_WRITE
    assert descriptors["adapter.evidence_closure.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["workflow.governed_composition.v1"].effect_class is EffectClass.EXTERNAL_WRITE
    assert descriptors["incident.rollback_recovery.v1"].effect_class is EffectClass.EXTERNAL_WRITE
    assert descriptors["release.pr_handoff_closure.v1"].effect_class is EffectClass.EXTERNAL_WRITE
    assert descriptors["telemetry.monitoring_triage.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["agentic_control.project_discipline_mesh.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["agentic_control.resource_governor.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["agentic_control.temporal_governor.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["agentic_control.memory_governor.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["agentic_control.evidence_governor.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["agentic_control.math_governor.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["agentic_control.algorithm_governor.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["agentic_control.security_governor.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["agentic_control.swarm_governor.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["agentic_control.coding_governor.v1"].effect_class is EffectClass.EXTERNAL_READ
    assert descriptors["agentic_control.autonomous_operations.v1"].effect_class is EffectClass.EXTERNAL_WRITE
    assert all(
        descriptor.metadata["approval_expected"] is True
        for descriptor in descriptors.values()
        if descriptor.effect_class is EffectClass.EXTERNAL_WRITE
    )


def test_default_skill_provider_requirements_match_step_boundaries() -> None:
    descriptors = default_skill_descriptors()

    assert descriptors
    assert all(
        tuple(
            sorted(
                {
                    step.provider_class_required
                    for step in descriptor.steps
                    if step.provider_class_required is not None
                }
            )
        )
        == tuple(sorted(descriptor.provider_requirements))
        for descriptor in descriptors
    )
    assert all(
        step.provider_class_required in descriptor.provider_requirements
        for descriptor in descriptors
        for step in descriptor.steps
        if step.provider_class_required is not None
    )


def test_project_discipline_mesh_skill_scans_management_surfaces_without_write_authority() -> None:
    descriptor = next(
        descriptor
        for descriptor in default_skill_descriptors()
        if descriptor.skill_id == "agentic_control.project_discipline_mesh.v1"
    )
    steps = {step.step_id: step for step in descriptor.steps}
    action_order = tuple(step.action_type for step in descriptor.steps)
    step_order = tuple(step.step_id for step in descriptor.steps)

    assert descriptor.effect_class is EffectClass.EXTERNAL_READ
    assert descriptor.metadata["project_discipline_mesh"] is True
    assert descriptor.metadata["grants_new_capability_authority"] is False
    assert descriptor.metadata["disciplines"] == (
        "strategy_product",
        "design_research",
        "engineering",
        "quality_security",
        "operations",
        "business_gtm",
    )
    assert action_order == (
        "agentic_control.mission.define",
        "agentic_control.priority.rank",
        "agentic_control.product_management.plan",
        "agentic_control.verification.plan",
        "agentic_control.interrogation.plan",
        "agentic_control.self_audit.refine",
        "agentic_control.memory_admission.plan",
    )
    assert all(
        step_order.index(dependency) < step_order.index(step.step_id)
        for step in descriptor.steps
        for dependency in step.depends_on
    )
    assert steps["scan_strategy_product"].input_bindings["priority_order_ref"] == (
        "rank_discipline_questions.discipline_question_order_ref"
    )
    assert steps["plan_quality_verification"].input_bindings["product_plan_ref"] == (
        "scan_strategy_product.strategy_delta_ref"
    )
    assert steps["interrogate_unknowns"].input_bindings["verification_plan_ref"] == (
        "plan_quality_verification.quality_verification_plan_ref"
    )
    assert steps["refine_cross_discipline_gaps"].input_bindings["interrogation_plan_ref"] == (
        "interrogate_unknowns.interrogation_plan_ref"
    )
    assert steps["plan_learning_admission"].input_bindings["refinement_plan_ref"] == (
        "refine_cross_discipline_gaps.discipline_mesh_ref"
    )


def test_agentic_resource_governor_bounds_budget_before_effect_bearing_work() -> None:
    descriptor = next(
        descriptor
        for descriptor in default_skill_descriptors()
        if descriptor.skill_id == "agentic_control.resource_governor.v1"
    )
    steps = {step.step_id: step for step in descriptor.steps}
    action_order = tuple(step.action_type for step in descriptor.steps)
    step_order = tuple(step.step_id for step in descriptor.steps)

    assert descriptor.effect_class is EffectClass.EXTERNAL_READ
    assert descriptor.metadata["resource_governor"] is True
    assert descriptor.metadata["grants_new_capability_authority"] is False
    assert descriptor.metadata["protected_variables"] == (
        "resource_floor",
        "halt_thresholds",
        "budget_envelope_ref",
        "proof_state",
    )
    assert action_order == (
        "agentic_control.mission.define",
        "agentic_control.priority.rank",
        "agentic_control.governance_gate.evaluate",
        "agentic_control.resource_budget.bound",
        "agentic_control.verification.plan",
        "agentic_control.self_audit.refine",
        "agentic_control.memory_admission.plan",
    )
    assert "agentic_control.evidence.append" not in action_order
    assert all(
        step_order.index(dependency) < step_order.index(step.step_id)
        for step in descriptor.steps
        for dependency in step.depends_on
    )
    assert steps["rank_resource_pressures"].input_bindings["mission_contract_ref"] == (
        "define_governed_mission.mission_contract_ref"
    )
    assert steps["evaluate_budget_governance"].input_bindings["priority_order_ref"] == (
        "rank_resource_pressures.resource_pressure_order_ref"
    )
    assert steps["bound_execution_budget"].input_bindings["gate_decision_ref"] == (
        "evaluate_budget_governance.gate_decision_ref"
    )
    assert steps["plan_budget_verification"].input_bindings["budget_envelope_ref"] == (
        "bound_execution_budget.budget_envelope_ref"
    )
    assert steps["refine_resource_gaps"].input_bindings["budget_envelope_ref"] == (
        "bound_execution_budget.budget_envelope_ref"
    )
    assert steps["refine_resource_gaps"].input_bindings["verification_plan_ref"] == (
        "plan_budget_verification.budget_verification_plan_ref"
    )
    assert steps["plan_budget_memory_admission"].input_bindings["refinement_plan_ref"] == (
        "refine_resource_gaps.resource_refinement_plan_ref"
    )


def test_agentic_temporal_governor_blocks_stale_time_windows_without_effects() -> None:
    descriptor = next(
        descriptor
        for descriptor in default_skill_descriptors()
        if descriptor.skill_id == "agentic_control.temporal_governor.v1"
    )
    steps = {step.step_id: step for step in descriptor.steps}
    action_order = tuple(step.action_type for step in descriptor.steps)
    step_order = tuple(step.step_id for step in descriptor.steps)

    assert descriptor.effect_class is EffectClass.EXTERNAL_READ
    assert descriptor.metadata["temporal_governor"] is True
    assert descriptor.metadata["grants_new_capability_authority"] is False
    assert descriptor.metadata["time_surfaces"] == (
        "temporal_boundary_ref",
        "time_budget_ref",
        "freshness_window_ref",
        "lease_window_ref",
        "retry_window_ref",
        "stale_evidence_blockers",
    )
    assert action_order == (
        "agentic_control.mission.define",
        "agentic_control.priority.rank",
        "agentic_control.governance_gate.evaluate",
        "agentic_control.resource_budget.bound",
        "agentic_control.verification.plan",
        "agentic_control.interrogation.plan",
        "agentic_control.telemetry_triage.plan",
        "agentic_control.self_audit.refine",
        "agentic_control.memory_admission.plan",
    )
    assert "agentic_control.code_change.plan" not in action_order
    assert "agentic_control.release_handoff.plan" not in action_order
    assert "agentic_control.evidence.append" not in action_order
    assert all(
        step_order.index(dependency) < step_order.index(step.step_id)
        for step in descriptor.steps
        for dependency in step.depends_on
    )
    assert steps["rank_temporal_constraints"].input_bindings["mission_contract_ref"] == (
        "define_temporal_mission.mission_contract_ref"
    )
    assert steps["evaluate_temporal_governance"].input_bindings["priority_order_ref"] == (
        "rank_temporal_constraints.temporal_constraint_order_ref"
    )
    assert steps["bound_temporal_budget"].input_bindings["gate_decision_ref"] == (
        "evaluate_temporal_governance.gate_decision_ref"
    )
    assert steps["plan_temporal_verification"].input_bindings["temporal_boundary_ref"] == (
        "define_temporal_mission.temporal_boundary_ref"
    )
    assert steps["plan_temporal_verification"].input_bindings["budget_envelope_ref"] == (
        "bound_temporal_budget.budget_envelope_ref"
    )
    assert steps["plan_temporal_verification"].input_bindings["time_budget_ref"] == (
        "bound_temporal_budget.time_budget_ref"
    )
    assert steps["plan_temporal_interrogation"].input_bindings["verification_plan_ref"] == (
        "plan_temporal_verification.temporal_verification_plan_ref"
    )
    assert steps["plan_temporal_triage"].input_bindings["verification_plan_ref"] == (
        "plan_temporal_verification.temporal_verification_plan_ref"
    )
    assert steps["plan_temporal_triage"].input_bindings["interrogation_plan_ref"] == (
        "plan_temporal_interrogation.temporal_interrogation_plan_ref"
    )
    assert steps["plan_temporal_triage"].input_bindings["time_budget_ref"] == (
        "bound_temporal_budget.time_budget_ref"
    )
    assert steps["refine_temporal_gaps"].input_bindings["temporal_triage_plan_ref"] == (
        "plan_temporal_triage.temporal_triage_plan_ref"
    )
    assert steps["plan_temporal_memory_admission"].input_bindings["refinement_plan_ref"] == (
        "refine_temporal_gaps.temporal_refinement_plan_ref"
    )


def test_agentic_memory_governor_scopes_recall_and_forget_paths_without_effects() -> None:
    descriptor = next(
        descriptor
        for descriptor in default_skill_descriptors()
        if descriptor.skill_id == "agentic_control.memory_governor.v1"
    )
    steps = {step.step_id: step for step in descriptor.steps}
    action_order = tuple(step.action_type for step in descriptor.steps)
    step_order = tuple(step.step_id for step in descriptor.steps)

    assert descriptor.effect_class is EffectClass.EXTERNAL_READ
    assert descriptor.metadata["memory_governor"] is True
    assert descriptor.metadata["grants_new_capability_authority"] is False
    assert descriptor.metadata["memory_surfaces"] == (
        "memory_boundary_ref",
        "memory_scope_ref",
        "retention_window_ref",
        "recall_guard_ref",
        "redaction_plan_ref",
        "forget_path_ref",
        "retention_policy_ref",
    )
    assert action_order == (
        "agentic_control.mission.define",
        "agentic_control.priority.rank",
        "agentic_control.governance_gate.evaluate",
        "agentic_control.resource_budget.bound",
        "agentic_control.verification.plan",
        "agentic_control.interrogation.plan",
        "agentic_control.self_audit.refine",
        "agentic_control.memory_admission.plan",
    )
    assert "agentic_control.code_change.plan" not in action_order
    assert "agentic_control.release_handoff.plan" not in action_order
    assert "agentic_control.evidence.append" not in action_order
    assert all(
        step_order.index(dependency) < step_order.index(step.step_id)
        for step in descriptor.steps
        for dependency in step.depends_on
    )
    assert steps["rank_memory_constraints"].input_bindings["mission_contract_ref"] == (
        "define_memory_mission.mission_contract_ref"
    )
    assert steps["evaluate_memory_governance"].input_bindings["priority_order_ref"] == (
        "rank_memory_constraints.memory_constraint_order_ref"
    )
    assert steps["bound_memory_budget"].input_bindings["gate_decision_ref"] == (
        "evaluate_memory_governance.gate_decision_ref"
    )
    assert steps["plan_memory_verification"].input_bindings["memory_boundary_ref"] == (
        "define_memory_mission.memory_boundary_ref"
    )
    assert steps["plan_memory_verification"].input_bindings["budget_envelope_ref"] == (
        "bound_memory_budget.budget_envelope_ref"
    )
    assert steps["plan_memory_interrogation"].input_bindings["verification_plan_ref"] == (
        "plan_memory_verification.memory_verification_plan_ref"
    )
    assert steps["refine_memory_gaps"].input_bindings["memory_scope_ref"] == (
        "plan_memory_verification.memory_scope_ref"
    )
    assert steps["refine_memory_gaps"].input_bindings["recall_guard_ref"] == (
        "plan_memory_verification.recall_guard_ref"
    )
    assert steps["refine_memory_gaps"].input_bindings["interrogation_plan_ref"] == (
        "plan_memory_interrogation.memory_interrogation_plan_ref"
    )
    assert steps["plan_governed_memory_admission"].input_bindings["refinement_plan_ref"] == (
        "refine_memory_gaps.memory_refinement_plan_ref"
    )
    assert steps["plan_governed_memory_admission"].input_bindings["memory_scope_ref"] == (
        "plan_memory_verification.memory_scope_ref"
    )
    assert steps["plan_governed_memory_admission"].input_bindings["retention_window_ref"] == (
        "plan_memory_verification.retention_window_ref"
    )
    assert steps["plan_governed_memory_admission"].input_bindings["recall_guard_ref"] == (
        "plan_memory_verification.recall_guard_ref"
    )


def test_agentic_evidence_governor_plans_claim_proof_without_appending_evidence() -> None:
    descriptor = next(
        descriptor
        for descriptor in default_skill_descriptors()
        if descriptor.skill_id == "agentic_control.evidence_governor.v1"
    )
    steps = {step.step_id: step for step in descriptor.steps}
    action_order = tuple(step.action_type for step in descriptor.steps)
    step_order = tuple(step.step_id for step in descriptor.steps)

    assert descriptor.effect_class is EffectClass.EXTERNAL_READ
    assert descriptor.metadata["evidence_governor"] is True
    assert descriptor.metadata["grants_new_capability_authority"] is False
    assert descriptor.metadata["evidence_surfaces"] == (
        "claim_boundary_ref",
        "source_requirement_refs",
        "contradiction_check_ref",
        "independent_support_rule",
        "proof_state",
        "evidence_requests",
    )
    assert action_order == (
        "agentic_control.mission.define",
        "agentic_control.priority.rank",
        "agentic_control.governance_gate.evaluate",
        "agentic_control.resource_budget.bound",
        "agentic_control.verification.plan",
        "agentic_control.interrogation.plan",
        "agentic_control.self_audit.refine",
        "agentic_control.memory_admission.plan",
    )
    assert "agentic_control.code_change.plan" not in action_order
    assert "agentic_control.release_handoff.plan" not in action_order
    assert "agentic_control.evidence.append" not in action_order
    assert all(
        step_order.index(dependency) < step_order.index(step.step_id)
        for step in descriptor.steps
        for dependency in step.depends_on
    )
    assert steps["rank_evidence_requirements"].input_bindings["mission_contract_ref"] == (
        "define_evidence_mission.mission_contract_ref"
    )
    assert steps["evaluate_evidence_governance"].input_bindings["priority_order_ref"] == (
        "rank_evidence_requirements.evidence_requirement_order_ref"
    )
    assert steps["bound_evidence_budget"].input_bindings["gate_decision_ref"] == (
        "evaluate_evidence_governance.gate_decision_ref"
    )
    assert steps["plan_claim_verification"].input_bindings["claim_boundary_ref"] == (
        "define_evidence_mission.claim_boundary_ref"
    )
    assert steps["plan_claim_verification"].input_bindings["budget_envelope_ref"] == (
        "bound_evidence_budget.budget_envelope_ref"
    )
    assert steps["plan_evidence_interrogation"].input_bindings["verification_plan_ref"] == (
        "plan_claim_verification.claim_verification_plan_ref"
    )
    assert steps["refine_evidence_gaps"].input_bindings["verification_plan_ref"] == (
        "plan_claim_verification.claim_verification_plan_ref"
    )
    assert steps["refine_evidence_gaps"].input_bindings["interrogation_plan_ref"] == (
        "plan_evidence_interrogation.evidence_interrogation_plan_ref"
    )
    assert steps["refine_evidence_gaps"].input_bindings["contradiction_check_ref"] == (
        "plan_claim_verification.contradiction_check_ref"
    )
    assert steps["refine_evidence_gaps"].input_bindings["source_requirement_refs"] == (
        "plan_claim_verification.source_requirement_refs"
    )
    assert steps["plan_evidence_memory_admission"].input_bindings["refinement_plan_ref"] == (
        "refine_evidence_gaps.evidence_refinement_plan_ref"
    )
    assert steps["plan_evidence_memory_admission"].input_bindings["verification_plan_ref"] == (
        "plan_claim_verification.claim_verification_plan_ref"
    )
    assert steps["plan_evidence_memory_admission"].input_bindings["interrogation_plan_ref"] == (
        "plan_evidence_interrogation.evidence_interrogation_plan_ref"
    )


def test_agentic_math_governor_bounds_proof_work_before_algorithm_or_code() -> None:
    descriptor = next(
        descriptor
        for descriptor in default_skill_descriptors()
        if descriptor.skill_id == "agentic_control.math_governor.v1"
    )
    steps = {step.step_id: step for step in descriptor.steps}
    action_order = tuple(step.action_type for step in descriptor.steps)
    step_order = tuple(step.step_id for step in descriptor.steps)

    assert descriptor.effect_class is EffectClass.EXTERNAL_READ
    assert descriptor.metadata["math_governor"] is True
    assert descriptor.metadata["grants_new_capability_authority"] is False
    assert descriptor.metadata["proof_surfaces"] == (
        "proof_boundary_ref",
        "mathematical_model_ref",
        "proof_obligation_refs",
        "counterexample_search_ref",
        "closure_rule",
    )
    assert action_order == (
        "agentic_control.mission.define",
        "agentic_control.priority.rank",
        "agentic_control.governance_gate.evaluate",
        "agentic_control.resource_budget.bound",
        "agentic_control.math_algorithm.analyze",
        "agentic_control.verification.plan",
        "agentic_control.interrogation.plan",
        "agentic_control.self_audit.refine",
        "agentic_control.memory_admission.plan",
    )
    assert "agentic_control.code_change.plan" not in action_order
    assert "agentic_control.evidence.append" not in action_order
    assert all(
        step_order.index(dependency) < step_order.index(step.step_id)
        for step in descriptor.steps
        for dependency in step.depends_on
    )
    assert steps["rank_math_constraints"].input_bindings["mission_contract_ref"] == (
        "define_math_problem.mission_contract_ref"
    )
    assert steps["evaluate_math_governance"].input_bindings["priority_order_ref"] == (
        "rank_math_constraints.math_constraint_order_ref"
    )
    assert steps["bound_math_budget"].input_bindings["gate_decision_ref"] == (
        "evaluate_math_governance.gate_decision_ref"
    )
    assert steps["analyze_math_structure"].input_bindings["proof_boundary_ref"] == (
        "define_math_problem.proof_boundary_ref"
    )
    assert steps["analyze_math_structure"].input_bindings["budget_envelope_ref"] == (
        "bound_math_budget.budget_envelope_ref"
    )
    assert steps["plan_math_verification"].input_bindings["mathematical_model_ref"] == (
        "analyze_math_structure.mathematical_model_ref"
    )
    assert steps["plan_math_verification"].input_bindings["proof_obligation_refs"] == (
        "analyze_math_structure.proof_obligation_refs"
    )
    assert steps["plan_math_verification"].input_bindings["counterexample_search_ref"] == (
        "analyze_math_structure.counterexample_search_ref"
    )
    assert steps["plan_math_interrogation"].input_bindings["verification_plan_ref"] == (
        "plan_math_verification.math_verification_plan_ref"
    )
    assert steps["refine_math_gaps"].input_bindings["mathematical_model_ref"] == (
        "analyze_math_structure.mathematical_model_ref"
    )
    assert steps["refine_math_gaps"].input_bindings["counterexample_search_ref"] == (
        "analyze_math_structure.counterexample_search_ref"
    )
    assert steps["refine_math_gaps"].input_bindings["interrogation_plan_ref"] == (
        "plan_math_interrogation.math_interrogation_plan_ref"
    )
    assert steps["plan_math_memory_admission"].input_bindings["refinement_plan_ref"] == (
        "refine_math_gaps.math_refinement_plan_ref"
    )


def test_agentic_algorithm_governor_bounds_complexity_before_code_planning() -> None:
    descriptor = next(
        descriptor
        for descriptor in default_skill_descriptors()
        if descriptor.skill_id == "agentic_control.algorithm_governor.v1"
    )
    steps = {step.step_id: step for step in descriptor.steps}
    action_order = tuple(step.action_type for step in descriptor.steps)
    step_order = tuple(step.step_id for step in descriptor.steps)

    assert descriptor.effect_class is EffectClass.EXTERNAL_READ
    assert descriptor.metadata["algorithm_governor"] is True
    assert descriptor.metadata["grants_new_capability_authority"] is False
    assert descriptor.metadata["analysis_dimensions"] == (
        "problem_boundary",
        "complexity_bound",
        "failure_modes",
        "threat_model",
        "verification_gates",
    )
    assert action_order == (
        "agentic_control.mission.define",
        "agentic_control.priority.rank",
        "agentic_control.governance_gate.evaluate",
        "agentic_control.resource_budget.bound",
        "agentic_control.math_algorithm.analyze",
        "agentic_control.security_threat_model.build",
        "agentic_control.verification.plan",
        "agentic_control.self_audit.refine",
        "agentic_control.memory_admission.plan",
    )
    assert "agentic_control.code_change.plan" not in action_order
    assert "agentic_control.evidence.append" not in action_order
    assert all(
        step_order.index(dependency) < step_order.index(step.step_id)
        for step in descriptor.steps
        for dependency in step.depends_on
    )
    assert steps["rank_algorithm_constraints"].input_bindings["mission_contract_ref"] == (
        "define_algorithm_problem.mission_contract_ref"
    )
    assert steps["evaluate_algorithm_governance"].input_bindings["priority_order_ref"] == (
        "rank_algorithm_constraints.constraint_order_ref"
    )
    assert steps["bound_algorithm_budget"].input_bindings["gate_decision_ref"] == (
        "evaluate_algorithm_governance.gate_decision_ref"
    )
    assert steps["analyze_algorithm_design"].input_bindings["problem_boundary_ref"] == (
        "define_algorithm_problem.problem_boundary_ref"
    )
    assert steps["analyze_algorithm_design"].input_bindings["budget_envelope_ref"] == (
        "bound_algorithm_budget.budget_envelope_ref"
    )
    assert steps["build_algorithm_threat_model"].input_bindings["algorithm_analysis_ref"] == (
        "analyze_algorithm_design.algorithm_analysis_ref"
    )
    assert steps["plan_algorithm_verification"].input_bindings["algorithm_analysis_ref"] == (
        "analyze_algorithm_design.algorithm_analysis_ref"
    )
    assert steps["plan_algorithm_verification"].input_bindings["threat_model_ref"] == (
        "build_algorithm_threat_model.threat_model_ref"
    )
    assert steps["refine_algorithm_gaps"].input_bindings["verification_plan_ref"] == (
        "plan_algorithm_verification.algorithm_verification_plan_ref"
    )
    assert steps["plan_algorithm_memory_admission"].input_bindings["refinement_plan_ref"] == (
        "refine_algorithm_gaps.algorithm_refinement_plan_ref"
    )


def test_agentic_security_governor_plans_threat_recovery_without_effects() -> None:
    descriptor = next(
        descriptor
        for descriptor in default_skill_descriptors()
        if descriptor.skill_id == "agentic_control.security_governor.v1"
    )
    steps = {step.step_id: step for step in descriptor.steps}
    action_order = tuple(step.action_type for step in descriptor.steps)
    step_order = tuple(step.step_id for step in descriptor.steps)

    assert descriptor.effect_class is EffectClass.EXTERNAL_READ
    assert descriptor.metadata["security_governor"] is True
    assert descriptor.metadata["grants_new_capability_authority"] is False
    assert descriptor.metadata["protected_surfaces"] == (
        "security_boundary_ref",
        "threat_model_ref",
        "mitigation_refs",
        "incident_recovery_plan_ref",
        "redaction_plan_ref",
    )
    assert action_order == (
        "agentic_control.mission.define",
        "agentic_control.priority.rank",
        "agentic_control.governance_gate.evaluate",
        "agentic_control.security_threat_model.build",
        "agentic_control.verification.plan",
        "agentic_control.interrogation.plan",
        "agentic_control.self_audit.refine",
        "agentic_control.incident_recovery.plan",
        "agentic_control.memory_admission.plan",
    )
    assert "agentic_control.code_change.plan" not in action_order
    assert "agentic_control.evidence.append" not in action_order
    assert all(
        step_order.index(dependency) < step_order.index(step.step_id)
        for step in descriptor.steps
        for dependency in step.depends_on
    )
    assert steps["rank_security_constraints"].input_bindings["mission_contract_ref"] == (
        "define_security_boundary.mission_contract_ref"
    )
    assert steps["evaluate_security_governance"].input_bindings["priority_order_ref"] == (
        "rank_security_constraints.security_constraint_order_ref"
    )
    assert steps["build_security_threat_model"].input_bindings["security_boundary_ref"] == (
        "define_security_boundary.security_boundary_ref"
    )
    assert steps["build_security_threat_model"].input_bindings["gate_decision_ref"] == (
        "evaluate_security_governance.gate_decision_ref"
    )
    assert steps["plan_security_verification"].input_bindings["threat_model_ref"] == (
        "build_security_threat_model.threat_model_ref"
    )
    assert steps["plan_security_interrogation"].input_bindings["verification_plan_ref"] == (
        "plan_security_verification.security_verification_plan_ref"
    )
    assert steps["refine_security_gaps"].input_bindings["threat_model_ref"] == (
        "build_security_threat_model.threat_model_ref"
    )
    assert steps["refine_security_gaps"].input_bindings["interrogation_plan_ref"] == (
        "plan_security_interrogation.security_interrogation_plan_ref"
    )
    assert steps["plan_security_incident_recovery"].input_bindings["refinement_plan_ref"] == (
        "refine_security_gaps.security_refinement_plan_ref"
    )
    assert steps["plan_security_memory_admission"].input_bindings["incident_recovery_plan_ref"] == (
        "plan_security_incident_recovery.incident_recovery_plan_ref"
    )


def test_agentic_swarm_governor_coordinates_without_spawning_agents() -> None:
    descriptor = next(
        descriptor
        for descriptor in default_skill_descriptors()
        if descriptor.skill_id == "agentic_control.swarm_governor.v1"
    )
    steps = {step.step_id: step for step in descriptor.steps}
    action_order = tuple(step.action_type for step in descriptor.steps)
    step_order = tuple(step.step_id for step in descriptor.steps)

    assert descriptor.effect_class is EffectClass.EXTERNAL_READ
    assert descriptor.metadata["swarm_governor"] is True
    assert descriptor.metadata["grants_new_capability_authority"] is False
    assert descriptor.metadata["coordination_surfaces"] == (
        "swarm_boundary_ref",
        "swarm_plan_ref",
        "role_assignment_hash",
        "shard_boundaries",
        "consensus_rule",
    )
    assert action_order == (
        "agentic_control.mission.define",
        "agentic_control.priority.rank",
        "agentic_control.governance_gate.evaluate",
        "agentic_control.resource_budget.bound",
        "agentic_control.security_threat_model.build",
        "agentic_control.swarm.coordinate",
        "agentic_control.verification.plan",
        "agentic_control.interrogation.plan",
        "agentic_control.self_audit.refine",
        "agentic_control.memory_admission.plan",
    )
    assert "agentic_control.code_change.plan" not in action_order
    assert "agentic_control.evidence.append" not in action_order
    assert all(
        step_order.index(dependency) < step_order.index(step.step_id)
        for step in descriptor.steps
        for dependency in step.depends_on
    )
    assert steps["rank_swarm_work"].input_bindings["mission_contract_ref"] == (
        "define_swarm_mission.mission_contract_ref"
    )
    assert steps["evaluate_swarm_governance"].input_bindings["priority_order_ref"] == (
        "rank_swarm_work.swarm_priority_order_ref"
    )
    assert steps["bound_swarm_budget"].input_bindings["gate_decision_ref"] == (
        "evaluate_swarm_governance.gate_decision_ref"
    )
    assert steps["build_swarm_threat_model"].input_bindings["swarm_boundary_ref"] == (
        "define_swarm_mission.swarm_boundary_ref"
    )
    assert steps["build_swarm_threat_model"].input_bindings["budget_envelope_ref"] == (
        "bound_swarm_budget.budget_envelope_ref"
    )
    assert steps["coordinate_swarm_plan"].input_bindings["threat_model_ref"] == (
        "build_swarm_threat_model.threat_model_ref"
    )
    assert steps["coordinate_swarm_plan"].input_bindings["budget_envelope_ref"] == (
        "bound_swarm_budget.budget_envelope_ref"
    )
    assert steps["plan_swarm_verification"].input_bindings["swarm_plan_ref"] == (
        "coordinate_swarm_plan.swarm_plan_ref"
    )
    assert steps["plan_swarm_interrogation"].input_bindings["verification_plan_ref"] == (
        "plan_swarm_verification.swarm_verification_plan_ref"
    )
    assert steps["refine_swarm_gaps"].input_bindings["swarm_plan_ref"] == (
        "coordinate_swarm_plan.swarm_plan_ref"
    )
    assert steps["plan_swarm_memory_admission"].input_bindings["refinement_plan_ref"] == (
        "refine_swarm_gaps.swarm_refinement_plan_ref"
    )


def test_agentic_coding_governor_plans_code_changes_without_write_authority() -> None:
    descriptor = next(
        descriptor
        for descriptor in default_skill_descriptors()
        if descriptor.skill_id == "agentic_control.coding_governor.v1"
    )
    steps = {step.step_id: step for step in descriptor.steps}
    action_order = tuple(step.action_type for step in descriptor.steps)
    step_order = tuple(step.step_id for step in descriptor.steps)

    assert descriptor.effect_class is EffectClass.EXTERNAL_READ
    assert descriptor.metadata["coding_governor"] is True
    assert descriptor.metadata["grants_new_capability_authority"] is False
    assert descriptor.metadata["code_surfaces"] == (
        "repo_boundary_ref",
        "code_change_plan_ref",
        "change_boundary",
        "test_contract",
        "rollback_plan",
    )
    assert action_order == (
        "agentic_control.mission.define",
        "agentic_control.priority.rank",
        "agentic_control.governance_gate.evaluate",
        "agentic_control.resource_budget.bound",
        "agentic_control.security_threat_model.build",
        "agentic_control.code_change.plan",
        "agentic_control.verification.plan",
        "agentic_control.interrogation.plan",
        "agentic_control.self_audit.refine",
        "agentic_control.memory_admission.plan",
    )
    assert "agentic_control.release_handoff.plan" not in action_order
    assert "agentic_control.evidence.append" not in action_order
    assert all(
        step_order.index(dependency) < step_order.index(step.step_id)
        for step in descriptor.steps
        for dependency in step.depends_on
    )
    assert steps["rank_code_constraints"].input_bindings["mission_contract_ref"] == (
        "define_code_mission.mission_contract_ref"
    )
    assert steps["evaluate_code_governance"].input_bindings["priority_order_ref"] == (
        "rank_code_constraints.code_constraint_order_ref"
    )
    assert steps["bound_code_budget"].input_bindings["gate_decision_ref"] == (
        "evaluate_code_governance.gate_decision_ref"
    )
    assert steps["build_code_threat_model"].input_bindings["repo_boundary_ref"] == (
        "define_code_mission.repo_boundary_ref"
    )
    assert steps["build_code_threat_model"].input_bindings["budget_envelope_ref"] == (
        "bound_code_budget.budget_envelope_ref"
    )
    assert steps["plan_code_change_boundary"].input_bindings["repo_boundary_ref"] == (
        "define_code_mission.repo_boundary_ref"
    )
    assert steps["plan_code_change_boundary"].input_bindings["threat_model_ref"] == (
        "build_code_threat_model.threat_model_ref"
    )
    assert steps["plan_code_change_boundary"].input_bindings["budget_envelope_ref"] == (
        "bound_code_budget.budget_envelope_ref"
    )
    assert steps["plan_code_verification"].input_bindings["code_change_plan_ref"] == (
        "plan_code_change_boundary.code_change_plan_ref"
    )
    assert steps["plan_code_interrogation"].input_bindings["verification_plan_ref"] == (
        "plan_code_verification.code_verification_plan_ref"
    )
    assert steps["refine_code_gaps"].input_bindings["code_change_plan_ref"] == (
        "plan_code_change_boundary.code_change_plan_ref"
    )
    assert steps["refine_code_gaps"].input_bindings["verification_plan_ref"] == (
        "plan_code_verification.code_verification_plan_ref"
    )
    assert steps["refine_code_gaps"].input_bindings["interrogation_plan_ref"] == (
        "plan_code_interrogation.code_interrogation_plan_ref"
    )
    assert steps["refine_code_gaps"].input_bindings["threat_model_ref"] == (
        "build_code_threat_model.threat_model_ref"
    )
    assert steps["plan_code_memory_admission"].input_bindings["refinement_plan_ref"] == (
        "refine_code_gaps.code_refinement_plan_ref"
    )


def test_agentic_control_skill_plans_telemetry_triage_before_code_release_and_evidence() -> None:
    descriptor = next(
        descriptor
        for descriptor in default_skill_descriptors()
        if descriptor.skill_id == "agentic_control.autonomous_operations.v1"
    )
    steps = {step.step_id: step for step in descriptor.steps}
    action_order = tuple(step.action_type for step in descriptor.steps)
    step_order = tuple(step.step_id for step in descriptor.steps)

    assert "agentic_control.code_change.plan" in action_order
    assert "agentic_control.telemetry_triage.plan" in action_order
    assert "agentic_control.interrogation.plan" in action_order
    assert "agentic_control.self_audit.refine" in action_order
    assert "agentic_control.memory_admission.plan" in action_order
    assert "agentic_control.incident_recovery.plan" in action_order
    assert "agentic_control.release_handoff.plan" in action_order
    assert all(
        step_order.index(dependency) < step_order.index(step.step_id)
        for step in descriptor.steps
        for dependency in step.depends_on
    )
    assert action_order.index("agentic_control.verification.plan") < action_order.index(
        "agentic_control.interrogation.plan"
    )
    assert action_order.index("agentic_control.interrogation.plan") < action_order.index(
        "agentic_control.self_audit.refine"
    )
    assert action_order.index("agentic_control.self_audit.refine") < action_order.index(
        "agentic_control.memory_admission.plan"
    )
    assert action_order.index("agentic_control.memory_admission.plan") < action_order.index(
        "agentic_control.incident_recovery.plan"
    )
    assert action_order.index("agentic_control.incident_recovery.plan") < action_order.index(
        "agentic_control.telemetry_triage.plan"
    )
    assert action_order.index("agentic_control.telemetry_triage.plan") < action_order.index(
        "agentic_control.code_change.plan"
    )
    assert action_order.index("agentic_control.code_change.plan") < action_order.index(
        "agentic_control.release_handoff.plan"
    )
    assert action_order.index("agentic_control.release_handoff.plan") < action_order.index(
        "agentic_control.evidence.append"
    )
    assert steps["plan_interrogation"].depends_on == ("plan_verification",)
    assert steps["refine_weakness_gaps"].depends_on == ("plan_interrogation",)
    assert steps["plan_memory_admission"].depends_on == ("refine_weakness_gaps",)
    assert steps["plan_incident_recovery"].depends_on == ("refine_weakness_gaps", "plan_memory_admission")
    assert steps["plan_telemetry_triage"].depends_on == (
        "plan_verification",
        "refine_weakness_gaps",
        "plan_incident_recovery",
    )
    assert steps["plan_code_change"].depends_on == ("plan_verification", "plan_telemetry_triage")
    assert steps["plan_release_handoff"].depends_on == ("plan_code_change",)
    assert steps["append_evidence"].depends_on == ("plan_release_handoff",)
    assert steps["plan_interrogation"].input_bindings["verification_plan_ref"] == (
        "plan_verification.verification_plan_ref"
    )
    assert steps["refine_weakness_gaps"].input_bindings["verification_plan_ref"] == (
        "plan_verification.verification_plan_ref"
    )
    assert steps["refine_weakness_gaps"].input_bindings["interrogation_plan_ref"] == (
        "plan_interrogation.interrogation_plan_ref"
    )
    assert steps["plan_memory_admission"].input_bindings["refinement_plan_ref"] == (
        "refine_weakness_gaps.refinement_plan_ref"
    )
    assert steps["plan_incident_recovery"].input_bindings["refinement_plan_ref"] == (
        "refine_weakness_gaps.refinement_plan_ref"
    )
    assert steps["plan_incident_recovery"].input_bindings["memory_admission_plan_ref"] == (
        "plan_memory_admission.memory_admission_plan_ref"
    )
    assert steps["plan_telemetry_triage"].input_bindings["verification_plan_ref"] == (
        "plan_verification.verification_plan_ref"
    )
    assert steps["plan_telemetry_triage"].input_bindings["refinement_plan_ref"] == (
        "refine_weakness_gaps.refinement_plan_ref"
    )
    assert steps["plan_telemetry_triage"].input_bindings["incident_recovery_plan_ref"] == (
        "plan_incident_recovery.incident_recovery_plan_ref"
    )
    assert steps["plan_code_change"].input_bindings["telemetry_triage_plan_ref"] == (
        "plan_telemetry_triage.telemetry_triage_plan_ref"
    )
    assert steps["plan_release_handoff"].input_bindings["code_change_plan_ref"] == (
        "plan_code_change.code_change_plan_ref"
    )
    assert steps["append_evidence"].input_bindings["code_change_plan_ref"] == (
        "plan_code_change.code_change_plan_ref"
    )
    assert steps["append_evidence"].input_bindings["interrogation_plan_ref"] == (
        "plan_interrogation.interrogation_plan_ref"
    )
    assert steps["append_evidence"].input_bindings["refinement_plan_ref"] == (
        "refine_weakness_gaps.refinement_plan_ref"
    )
    assert steps["append_evidence"].input_bindings["memory_admission_plan_ref"] == (
        "plan_memory_admission.memory_admission_plan_ref"
    )
    assert steps["append_evidence"].input_bindings["incident_recovery_plan_ref"] == (
        "plan_incident_recovery.incident_recovery_plan_ref"
    )
    assert steps["append_evidence"].input_bindings["telemetry_triage_plan_ref"] == (
        "plan_telemetry_triage.telemetry_triage_plan_ref"
    )
    assert steps["append_evidence"].input_bindings["release_handoff_plan_ref"] == (
        "plan_release_handoff.release_handoff_plan_ref"
    )


def test_register_default_skill_descriptors_is_idempotent_for_identical_catalog() -> None:
    registry = SkillRegistry()

    first = register_default_skill_descriptors(registry)
    second = register_default_skill_descriptors(registry)

    assert tuple(descriptor.skill_id for descriptor in first) == EXPECTED_SKILL_IDS
    assert tuple(descriptor.skill_id for descriptor in second) == EXPECTED_SKILL_IDS
    assert registry.size == len(EXPECTED_SKILL_IDS)
    assert first == second


def test_register_default_skill_descriptors_rejects_conflicting_existing_id() -> None:
    registry = SkillRegistry()
    conflicting = default_skill_descriptors()[0]
    registry.register(
        conflicting.__class__(
            skill_id=conflicting.skill_id,
            name="Conflicting descriptor",
            skill_class=conflicting.skill_class,
            effect_class=conflicting.effect_class,
            determinism_class=conflicting.determinism_class,
            trust_class=conflicting.trust_class,
            verification_strength=conflicting.verification_strength,
            lifecycle=conflicting.lifecycle,
            preconditions=conflicting.preconditions,
            postconditions=conflicting.postconditions,
            steps=conflicting.steps,
            provider_requirements=conflicting.provider_requirements,
            description=conflicting.description,
            confidence=conflicting.confidence,
            metadata=conflicting.metadata,
        )
    )

    with pytest.raises(RuntimeCoreInvariantError, match="default skill descriptor conflict"):
        register_default_skill_descriptors(registry)

    assert registry.size == 1
    assert registry.get("finance.approval_packet.v1").name == "Conflicting descriptor"
    assert registry.get("document.intake_summary.v1") is None


def test_register_default_skill_descriptors_rejects_provider_boundary_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broken = replace(default_skill_descriptors()[0], provider_requirements=())
    monkeypatch.setattr(catalog_module, "default_skill_descriptors", lambda: (broken,))
    registry = SkillRegistry()

    with pytest.raises(RuntimeCoreInvariantError, match="provider boundary mismatch"):
        register_default_skill_descriptors(registry)

    assert registry.size == 0
    assert registry.get("finance.approval_packet.v1") is None
    assert broken.skill_id == "finance.approval_packet.v1"


def test_register_default_skill_descriptors_rejects_external_write_without_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor = next(
        descriptor
        for descriptor in default_skill_descriptors()
        if descriptor.skill_id == "incident.rollback_recovery.v1"
    )
    broken = replace(
        descriptor,
        metadata={**descriptor.metadata, "approval_expected": False},
    )
    monkeypatch.setattr(catalog_module, "default_skill_descriptors", lambda: (broken,))
    registry = SkillRegistry()

    with pytest.raises(RuntimeCoreInvariantError, match="approval boundary missing"):
        register_default_skill_descriptors(registry)

    assert registry.size == 0
    assert registry.get("incident.rollback_recovery.v1") is None
    assert broken.effect_class is EffectClass.EXTERNAL_WRITE


def test_bootstrap_installs_default_skill_catalog() -> None:
    runtime = bootstrap_runtime(clock=lambda: "2026-05-27T00:00:00+00:00")

    listed_ids = tuple(descriptor.skill_id for descriptor in runtime.skill_registry.list_skills())

    assert listed_ids == tuple(sorted(EXPECTED_SKILL_IDS))
    assert runtime.skill_registry.size == len(EXPECTED_SKILL_IDS)
    assert runtime.skill_registry.get("software_dev.change_closure.v1").metadata["risk_floor"] == "high"
    assert runtime.skill_registry.get("finance.approval_packet.v1").metadata["grants_new_capability_authority"] is False
    assert runtime.skill_registry.get("deployment.witness_publication.v1").metadata["approval_expected"] is True
    assert runtime.skill_registry.get("workflow.governed_composition.v1").metadata["approval_expected"] is True
    assert runtime.skill_registry.get("incident.rollback_recovery.v1").metadata["risk_floor"] == "critical"
    assert runtime.skill_registry.get("release.pr_handoff_closure.v1").metadata["approval_expected"] is True
    assert runtime.skill_registry.get("telemetry.monitoring_triage.v1").metadata["risk_floor"] == "medium"
    assert runtime.skill_registry.get("agentic_control.project_discipline_mesh.v1").metadata["risk_floor"] == "medium"
    assert runtime.skill_registry.get("agentic_control.project_discipline_mesh.v1").effect_class is EffectClass.EXTERNAL_READ
    assert runtime.skill_registry.get("agentic_control.resource_governor.v1").metadata["risk_floor"] == "medium"
    assert runtime.skill_registry.get("agentic_control.resource_governor.v1").effect_class is EffectClass.EXTERNAL_READ
    assert runtime.skill_registry.get("agentic_control.temporal_governor.v1").metadata["risk_floor"] == "medium"
    assert runtime.skill_registry.get("agentic_control.temporal_governor.v1").effect_class is EffectClass.EXTERNAL_READ
    assert runtime.skill_registry.get("agentic_control.memory_governor.v1").metadata["risk_floor"] == "medium"
    assert runtime.skill_registry.get("agentic_control.memory_governor.v1").effect_class is EffectClass.EXTERNAL_READ
    assert runtime.skill_registry.get("agentic_control.evidence_governor.v1").metadata["risk_floor"] == "medium"
    assert runtime.skill_registry.get("agentic_control.evidence_governor.v1").effect_class is EffectClass.EXTERNAL_READ
    assert runtime.skill_registry.get("agentic_control.math_governor.v1").metadata["risk_floor"] == "medium"
    assert runtime.skill_registry.get("agentic_control.math_governor.v1").effect_class is EffectClass.EXTERNAL_READ
    assert runtime.skill_registry.get("agentic_control.algorithm_governor.v1").metadata["risk_floor"] == "medium"
    assert runtime.skill_registry.get("agentic_control.algorithm_governor.v1").effect_class is EffectClass.EXTERNAL_READ
    assert runtime.skill_registry.get("agentic_control.security_governor.v1").metadata["risk_floor"] == "medium"
    assert runtime.skill_registry.get("agentic_control.security_governor.v1").effect_class is EffectClass.EXTERNAL_READ
    assert runtime.skill_registry.get("agentic_control.swarm_governor.v1").metadata["risk_floor"] == "medium"
    assert runtime.skill_registry.get("agentic_control.swarm_governor.v1").effect_class is EffectClass.EXTERNAL_READ
    assert runtime.skill_registry.get("agentic_control.coding_governor.v1").metadata["risk_floor"] == "medium"
    assert runtime.skill_registry.get("agentic_control.coding_governor.v1").effect_class is EffectClass.EXTERNAL_READ
    assert runtime.skill_registry.get("agentic_control.autonomous_operations.v1").metadata["risk_floor"] == "high"
