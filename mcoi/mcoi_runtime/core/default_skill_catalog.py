"""Purpose: default governed skill descriptor catalog for runtime bootstrap.
Governance scope: SkillDescriptor construction and registry admission only.
Dependencies: skill contracts and skill registry core.
Invariants:
  - Default skills compose existing capability identifiers; they grant no new execution authority.
  - Every descriptor remains candidate lifecycle until execution and verification evidence promotes it.
  - Effect class is no lower than the strongest step effect implied by the workflow.
  - Registration is idempotent only for identical descriptors; conflicts fail closed.
"""

from __future__ import annotations

from mcoi_runtime.contracts.skill import (
    DeterminismClass,
    EffectClass,
    PostconditionType,
    PreconditionType,
    SkillClass,
    SkillDescriptor,
    SkillLifecycle,
    SkillPostcondition,
    SkillPrecondition,
    SkillStep,
    TrustClass,
    VerificationStrength,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.skills import SkillRegistry


_CATALOG_VERSION = "default-skill-catalog.v1"
_NO_NEW_AUTHORITY = {
    "catalog_version": _CATALOG_VERSION,
    "grants_new_capability_authority": False,
}
_POLICY_PRECONDITION_DESCRIPTIONS = {
    "financial": "financial workflow policy permits descriptor selection",
    "document": "document workflow policy permits descriptor selection",
    "software_dev": "software_dev workflow policy permits descriptor selection",
    "deployment": "deployment workflow policy permits descriptor selection",
    "browser": "adapter evidence workflow policy permits descriptor selection",
    "enterprise": "enterprise workflow policy permits descriptor selection",
    "incident": "incident rollback workflow policy permits descriptor selection",
    "release": "release handoff workflow policy permits descriptor selection",
    "telemetry": "telemetry monitoring workflow policy permits descriptor selection",
    "agentic_control": "agentic control workflow policy permits descriptor selection",
}
_CAPABILITY_PRECONDITION_DESCRIPTIONS = {
    "financial": "financial capability family is admitted in the governed registry",
    "document": "document capability family is admitted in the governed registry",
    "software_dev": "software_dev capability family is admitted in the governed registry",
    "deployment": "deployment capability family is admitted in the governed registry",
    "browser": "browser, document, and voice capability families are admitted in the governed registry",
    "enterprise": "enterprise and creative capability families are admitted in the governed registry",
    "incident": "incident response and recovery capability family is admitted in the governed registry",
    "release": "release management capability family is admitted in the governed registry",
    "telemetry": "telemetry and monitoring capability family is admitted in the governed registry",
    "agentic_control": "agentic control capability family is admitted in the governed registry",
}


def default_skill_descriptors() -> tuple[SkillDescriptor, ...]:
    """Return deterministic built-in workflow descriptors for fresh runtimes."""
    return (
        _finance_approval_packet_skill(),
        _document_intake_summary_skill(),
        _software_change_closure_skill(),
        _deployment_witness_publication_skill(),
        _adapter_evidence_closure_skill(),
        _workflow_governed_composition_skill(),
        _incident_rollback_recovery_skill(),
        _release_handoff_pr_closure_skill(),
        _telemetry_monitoring_triage_skill(),
        _agentic_control_project_discipline_mesh_skill(),
        _agentic_control_resource_governor_skill(),
        _agentic_control_temporal_governor_skill(),
        _agentic_control_memory_governor_skill(),
        _agentic_control_evidence_governor_skill(),
        _agentic_control_math_governor_skill(),
        _agentic_control_algorithm_governor_skill(),
        _agentic_control_security_governor_skill(),
        _agentic_control_swarm_governor_skill(),
        _agentic_control_coding_governor_skill(),
        _agentic_control_runtime_governor_skill(),
        _agentic_control_release_governor_skill(),
        _agentic_control_autonomous_operations_skill(),
    )


def register_default_skill_descriptors(registry: SkillRegistry) -> tuple[SkillDescriptor, ...]:
    """Register default descriptors while rejecting conflicting pre-existing ids."""
    registered: list[SkillDescriptor] = []
    for descriptor in default_skill_descriptors():
        _validate_default_descriptor(descriptor)
        existing = registry.get(descriptor.skill_id)
        if existing is None:
            registered.append(registry.register(descriptor))
            continue
        if existing != descriptor:
            raise RuntimeCoreInvariantError("default skill descriptor conflict")
        registered.append(existing)
    return tuple(registered)


def _validate_default_descriptor(descriptor: SkillDescriptor) -> None:
    """Fail closed if a built-in descriptor drifts beyond catalog authority."""
    if descriptor.lifecycle is not SkillLifecycle.CANDIDATE:
        raise RuntimeCoreInvariantError("default skill descriptor lifecycle rejected")
    if descriptor.metadata.get("grants_new_capability_authority") is not False:
        raise RuntimeCoreInvariantError("default skill descriptor authority grant rejected")

    required_provider_classes = tuple(
        sorted(
            {
                step.provider_class_required
                for step in descriptor.steps
                if step.provider_class_required is not None
            }
        )
    )
    if tuple(sorted(descriptor.provider_requirements)) != required_provider_classes:
        raise RuntimeCoreInvariantError("default skill descriptor provider boundary mismatch")

    if (
        descriptor.effect_class is EffectClass.EXTERNAL_WRITE
        and descriptor.metadata.get("approval_expected") is not True
    ):
        raise RuntimeCoreInvariantError("default skill descriptor approval boundary missing")


def _policy_and_capability_preconditions(*, domain: str) -> tuple[SkillPrecondition, ...]:
    try:
        policy_description = _POLICY_PRECONDITION_DESCRIPTIONS[domain]
        capability_description = _CAPABILITY_PRECONDITION_DESCRIPTIONS[domain]
    except KeyError as exc:
        raise RuntimeCoreInvariantError("unknown default skill domain") from exc
    return (
        SkillPrecondition(
            condition_id=f"{domain}.policy_allows",
            condition_type=PreconditionType.POLICY_ALLOWS,
            description=policy_description,
        ),
        SkillPrecondition(
            condition_id=f"{domain}.capability_available",
            condition_type=PreconditionType.CAPABILITY_AVAILABLE,
            description=capability_description,
        ),
    )


def _verification_postcondition(*, skill_id: str) -> tuple[SkillPostcondition, ...]:
    return (
        SkillPostcondition(
            condition_id=f"{skill_id}.verification_passed",
            condition_type=PostconditionType.VERIFICATION_PASSED,
            description="terminal verification evidence closes the skill execution",
        ),
    )


def _finance_approval_packet_skill() -> SkillDescriptor:
    skill_id = "finance.approval_packet.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Finance approval packet",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="financial"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="read_balance",
                name="Read account balance",
                action_type="financial.balance_check",
                output_keys=("balance", "currency", "receipt_status"),
                provider_class_required="financial_provider",
            ),
            SkillStep(
                step_id="read_transactions",
                name="Read transaction history",
                action_type="financial.transaction_history",
                output_keys=("transactions", "receipt_status"),
                provider_class_required="financial_provider",
            ),
            SkillStep(
                step_id="analyze_spending",
                name="Analyze spending context",
                action_type="financial.spending_insights",
                depends_on=("read_transactions",),
                input_bindings={"transactions": "read_transactions.transactions"},
                output_keys=("insights", "risk_notes", "receipt_status"),
                provider_class_required="financial_provider",
            ),
        ),
        provider_requirements=("financial_provider",),
        description=(
            "Builds the read-only evidence packet needed before a governed payment "
            "or refund approval decision."
        ),
        confidence=0.25,
        metadata={**_NO_NEW_AUTHORITY, "risk_floor": "low"},
    )


def _document_intake_summary_skill() -> SkillDescriptor:
    skill_id = "document.intake_summary.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Document intake summary",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="document"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="extract_text",
                name="Extract document text",
                action_type="document.extract_text",
                output_keys=("text_ref", "text_hash", "parser_id"),
                provider_class_required="document_worker",
            ),
            SkillStep(
                step_id="extract_tables",
                name="Extract document tables",
                action_type="document.extract_tables",
                output_keys=("table_refs", "table_count", "parser_id"),
                provider_class_required="document_worker",
            ),
            SkillStep(
                step_id="summarize_document",
                name="Summarize document",
                action_type="document.summarize",
                depends_on=("extract_text",),
                input_bindings={"text_ref": "extract_text.text_ref"},
                output_keys=("summary_ref", "summary_hash"),
                provider_class_required="document_worker",
            ),
        ),
        provider_requirements=("document_worker",),
        description="Extracts parser-first document evidence and a grounded intake summary.",
        confidence=0.25,
        metadata={**_NO_NEW_AUTHORITY, "risk_floor": "low"},
    )


def _software_change_closure_skill() -> SkillDescriptor:
    skill_id = "software_dev.change_closure.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Software change closure",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_WRITE,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="software_dev"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="read_repo_map",
                name="Read repository map",
                action_type="software_dev.repo_map.read",
                output_keys=("repo_map_ref", "repo_map_hash"),
                provider_class_required="software_dev_capability_fabric",
            ),
            SkillStep(
                step_id="build_context_bundle",
                name="Build bounded code context",
                action_type="software_dev.context_bundle.build",
                depends_on=("read_repo_map",),
                input_bindings={"repo_map_ref": "read_repo_map.repo_map_ref"},
                output_keys=("context_bundle_ref", "context_bundle_hash"),
                provider_class_required="software_dev_capability_fabric",
            ),
            SkillStep(
                step_id="select_gate_plan",
                name="Select software quality gates",
                action_type="software_dev.gate_plan.select",
                depends_on=("build_context_bundle",),
                input_bindings={"context_bundle_ref": "build_context_bundle.context_bundle_ref"},
                output_keys=("gate_plan_ref", "gate_plan_hash"),
                provider_class_required="software_dev_capability_fabric",
            ),
            SkillStep(
                step_id="run_change",
                name="Run governed software change",
                action_type="software_dev.change.run",
                depends_on=("select_gate_plan",),
                input_bindings={"gate_plan_ref": "select_gate_plan.gate_plan_ref"},
                output_keys=("change_receipt_id", "quality_gate_summary", "rollback_snapshot_ref"),
                provider_class_required="software_dev_capability_fabric",
            ),
            SkillStep(
                step_id="prepare_pr_candidate",
                name="Prepare PR candidate",
                action_type="software_dev.pr_candidate.prepare",
                depends_on=("run_change",),
                input_bindings={"change_receipt_id": "run_change.change_receipt_id"},
                output_keys=("pr_candidate_ref", "review_packet_hash"),
                provider_class_required="software_dev_capability_fabric",
            ),
        ),
        provider_requirements=("software_dev_capability_fabric",),
        description=(
            "Composes the governed software-development closure path from context "
            "collection through patch receipt and PR candidate preparation."
        ),
        confidence=0.25,
        metadata={**_NO_NEW_AUTHORITY, "risk_floor": "high", "approval_expected": True},
    )


def _deployment_witness_publication_skill() -> SkillDescriptor:
    skill_id = "deployment.witness_publication.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Deployment witness publication",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_WRITE,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="deployment"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="collect_witness",
                name="Collect deployment witness",
                action_type="deployment.witness.collect",
                output_keys=("deployment_witness_ref", "runtime_conformance_ref", "responsibility_debt"),
                provider_class_required="deployment_witness_plane",
            ),
            SkillStep(
                step_id="publish_witness",
                name="Publish deployment witness with approval",
                action_type="deployment.witness.publish.with_approval",
                depends_on=("collect_witness",),
                input_bindings={"deployment_witness_ref": "collect_witness.deployment_witness_ref"},
                output_keys=("publication_receipt_ref", "public_health_ref"),
                provider_class_required="deployment_witness_plane",
            ),
        ),
        provider_requirements=("deployment_witness_plane",),
        description=(
            "Composes witness collection and approval-bound publication for "
            "deployment health claims."
        ),
        confidence=0.25,
        metadata={**_NO_NEW_AUTHORITY, "risk_floor": "high", "approval_expected": True},
    )


def _adapter_evidence_closure_skill() -> SkillDescriptor:
    skill_id = "adapter.evidence_closure.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Adapter evidence closure",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="browser"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="open_browser_probe",
                name="Open browser probe",
                action_type="browser.open",
                output_keys=("url_after", "screenshot_after_ref"),
                provider_class_required="browser_worker",
            ),
            SkillStep(
                step_id="capture_browser_screenshot",
                name="Capture browser evidence",
                action_type="browser.screenshot",
                depends_on=("open_browser_probe",),
                output_keys=("screenshot_after_ref",),
                provider_class_required="browser_worker",
            ),
            SkillStep(
                step_id="extract_document_text",
                name="Extract parser evidence",
                action_type="document.extract_text",
                output_keys=("document_id", "text_hash", "parser_id"),
                provider_class_required="document_worker",
            ),
            SkillStep(
                step_id="transcribe_voice_probe",
                name="Transcribe voice evidence",
                action_type="voice.speech_to_text",
                output_keys=("transcript_ref", "provider_receipt_ref"),
                provider_class_required="voice_worker",
            ),
            SkillStep(
                step_id="confirm_voice_intent",
                name="Confirm voice intent classification",
                action_type="voice.intent_confirm",
                depends_on=("transcribe_voice_probe",),
                input_bindings={"transcript_ref": "transcribe_voice_probe.transcript_ref"},
                output_keys=("confirmation_ref", "risk_class"),
                provider_class_required="voice_worker",
            ),
        ),
        provider_requirements=("browser_worker", "document_worker", "voice_worker"),
        description=(
            "Collects read-only browser, document, and voice adapter evidence before "
            "promotion or production-readiness claims."
        ),
        confidence=0.25,
        metadata={**_NO_NEW_AUTHORITY, "risk_floor": "medium"},
    )


def _workflow_governed_composition_skill() -> SkillDescriptor:
    skill_id = "workflow.governed_composition.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Governed workflow composition",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_WRITE,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="enterprise"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="search_governance_context",
                name="Search governance context",
                action_type="enterprise.knowledge_search",
                output_keys=("evidence_refs", "policy_refs"),
                provider_class_required="enterprise_knowledge_base",
            ),
            SkillStep(
                step_id="generate_workflow_artifact",
                name="Generate workflow artifact",
                action_type="creative.document_generate",
                depends_on=("search_governance_context",),
                input_bindings={"policy_refs": "search_governance_context.policy_refs"},
                output_keys=("artifact_ref", "artifact_hash"),
                provider_class_required="creative_document_generator",
            ),
            SkillStep(
                step_id="schedule_followup",
                name="Schedule workflow follow-up",
                action_type="enterprise.task_schedule",
                depends_on=("generate_workflow_artifact",),
                input_bindings={"artifact_ref": "generate_workflow_artifact.artifact_ref"},
                output_keys=("task_id", "schedule_receipt_ref"),
                provider_class_required="enterprise_task_scheduler",
            ),
        ),
        provider_requirements=(
            "enterprise_knowledge_base",
            "creative_document_generator",
            "enterprise_task_scheduler",
        ),
        description=(
            "Composes governance context, workflow artifact generation, and bounded "
            "follow-up scheduling for multi-step automation design."
        ),
        confidence=0.25,
        metadata={**_NO_NEW_AUTHORITY, "risk_floor": "medium", "approval_expected": True},
    )


def _incident_rollback_recovery_skill() -> SkillDescriptor:
    skill_id = "incident.rollback_recovery.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Incident rollback recovery",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_WRITE,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="incident"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="collect_incident_evidence",
                name="Collect incident evidence",
                action_type="incident.evidence.collect",
                output_keys=("incident_record_ref", "causal_event_ref", "effect_surface"),
                provider_class_required="incident_response_plane",
            ),
            SkillStep(
                step_id="plan_recovery",
                name="Plan rollback or compensation",
                action_type="incident.recovery_plan.build",
                depends_on=("collect_incident_evidence",),
                input_bindings={
                    "incident_record_ref": "collect_incident_evidence.incident_record_ref",
                    "causal_event_ref": "collect_incident_evidence.causal_event_ref",
                },
                output_keys=("recovery_plan_ref", "safety_floor_ref", "approval_required"),
                provider_class_required="incident_response_plane",
            ),
            SkillStep(
                step_id="execute_recovery_with_approval",
                name="Execute approved recovery action",
                action_type="incident.recovery.execute.with_approval",
                depends_on=("plan_recovery",),
                input_bindings={"recovery_plan_ref": "plan_recovery.recovery_plan_ref"},
                output_keys=("recovery_receipt_ref", "rollback_effect_ref", "recovery_snapshot_ref"),
                provider_class_required="incident_response_plane",
            ),
            SkillStep(
                step_id="validate_replay",
                name="Validate recovery replay",
                action_type="incident.replay.validate",
                depends_on=("execute_recovery_with_approval",),
                input_bindings={
                    "recovery_snapshot_ref": "execute_recovery_with_approval.recovery_snapshot_ref"
                },
                output_keys=("replay_bundle_ref", "terminal_observation_ref", "residual_risk"),
                provider_class_required="incident_response_plane",
            ),
        ),
        provider_requirements=("incident_response_plane",),
        description=(
            "Composes incident evidence collection, recovery planning, approval-bound "
            "rollback execution, and replay validation."
        ),
        confidence=0.25,
        metadata={**_NO_NEW_AUTHORITY, "risk_floor": "critical", "approval_expected": True},
    )


def _release_handoff_pr_closure_skill() -> SkillDescriptor:
    skill_id = "release.pr_handoff_closure.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Release PR handoff closure",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_WRITE,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="release"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="read_commit_boundary",
                name="Read commit boundary",
                action_type="release.commit_boundary.read",
                output_keys=("commit_boundary_ref", "changed_files_ref", "release_target"),
                provider_class_required="release_management_plane",
            ),
            SkillStep(
                step_id="build_release_inventory",
                name="Build release import inventory",
                action_type="release.import_inventory.build",
                depends_on=("read_commit_boundary",),
                input_bindings={"commit_boundary_ref": "read_commit_boundary.commit_boundary_ref"},
                output_keys=("import_inventory_ref", "risk_register_ref"),
                provider_class_required="release_management_plane",
            ),
            SkillStep(
                step_id="validate_release_packet",
                name="Validate release packet",
                action_type="release.packet.validate",
                depends_on=("build_release_inventory",),
                input_bindings={"import_inventory_ref": "build_release_inventory.import_inventory_ref"},
                output_keys=("readiness_ref", "release_manifest_ref", "validation_summary"),
                provider_class_required="release_management_plane",
            ),
            SkillStep(
                step_id="prepare_pr_handoff",
                name="Prepare PR handoff with approval",
                action_type="release.pr_handoff.prepare.with_approval",
                depends_on=("validate_release_packet",),
                input_bindings={"release_manifest_ref": "validate_release_packet.release_manifest_ref"},
                output_keys=("pr_summary_ref", "handoff_packet_ref", "publication_receipt_ref"),
                provider_class_required="release_management_plane",
            ),
        ),
        provider_requirements=("release_management_plane",),
        description=(
            "Composes commit-boundary evidence, release inventory, readiness "
            "validation, and approval-bound PR handoff preparation."
        ),
        confidence=0.25,
        metadata={**_NO_NEW_AUTHORITY, "risk_floor": "high", "approval_expected": True},
    )


def _telemetry_monitoring_triage_skill() -> SkillDescriptor:
    skill_id = "telemetry.monitoring_triage.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Telemetry monitoring triage",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="telemetry"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="collect_telemetry_window",
                name="Collect telemetry window",
                action_type="telemetry.window.collect",
                output_keys=("telemetry_ref", "time_window", "component_boundary"),
                provider_class_required="telemetry_observer",
            ),
            SkillStep(
                step_id="evaluate_thresholds",
                name="Evaluate controller thresholds",
                action_type="telemetry.thresholds.evaluate",
                depends_on=("collect_telemetry_window",),
                input_bindings={"telemetry_ref": "collect_telemetry_window.telemetry_ref"},
                output_keys=("threshold_evaluation_ref", "degradation_class", "unknowns"),
                provider_class_required="telemetry_observer",
            ),
            SkillStep(
                step_id="build_triage_decision",
                name="Build triage decision",
                action_type="telemetry.triage_decision.build",
                depends_on=("evaluate_thresholds",),
                input_bindings={
                    "threshold_evaluation_ref": "evaluate_thresholds.threshold_evaluation_ref"
                },
                output_keys=("triage_decision_ref", "remediation_plan_ref", "residual_risk"),
                provider_class_required="telemetry_observer",
            ),
        ),
        provider_requirements=("telemetry_observer",),
        description=(
            "Composes telemetry collection, threshold evaluation, and read-only "
            "runtime health triage."
        ),
        confidence=0.25,
        metadata={**_NO_NEW_AUTHORITY, "risk_floor": "medium"},
    )


def _agentic_control_project_discipline_mesh_skill() -> SkillDescriptor:
    skill_id = "agentic_control.project_discipline_mesh.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Project discipline mesh scan",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="agentic_control"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="define_project_boundary",
                name="Define project boundary",
                action_type="agentic_control.mission.define",
                output_keys=("mission_contract_ref", "boundary_ref", "halt_conditions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="rank_discipline_questions",
                name="Rank discipline questions",
                action_type="agentic_control.priority.rank",
                depends_on=("define_project_boundary",),
                input_bindings={"mission_contract_ref": "define_project_boundary.mission_contract_ref"},
                output_keys=("discipline_question_order_ref", "critical_gap_refs", "risk_weights"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="scan_strategy_product",
                name="Scan strategy and product",
                action_type="agentic_control.product_management.plan",
                depends_on=("rank_discipline_questions",),
                input_bindings={
                    "priority_order_ref": "rank_discipline_questions.discipline_question_order_ref"
                },
                output_keys=("strategy_delta_ref", "success_metrics", "business_handoff_risks"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_quality_verification",
                name="Plan quality verification",
                action_type="agentic_control.verification.plan",
                depends_on=("scan_strategy_product",),
                input_bindings={"product_plan_ref": "scan_strategy_product.strategy_delta_ref"},
                output_keys=("quality_verification_plan_ref", "required_gates", "closure_rule"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="interrogate_unknowns",
                name="Interrogate discipline unknowns",
                action_type="agentic_control.interrogation.plan",
                depends_on=("plan_quality_verification",),
                input_bindings={
                    "verification_plan_ref": "plan_quality_verification.quality_verification_plan_ref"
                },
                output_keys=("interrogation_plan_ref", "unknowns", "evidence_requests"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="refine_cross_discipline_gaps",
                name="Refine cross-discipline gaps",
                action_type="agentic_control.self_audit.refine",
                depends_on=("interrogate_unknowns",),
                input_bindings={
                    "verification_plan_ref": "plan_quality_verification.quality_verification_plan_ref",
                    "interrogation_plan_ref": "interrogate_unknowns.interrogation_plan_ref",
                },
                output_keys=("discipline_mesh_ref", "handoff_gap_order", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_learning_admission",
                name="Plan learning admission",
                action_type="agentic_control.memory_admission.plan",
                depends_on=("refine_cross_discipline_gaps",),
                input_bindings={
                    "refinement_plan_ref": "refine_cross_discipline_gaps.discipline_mesh_ref"
                },
                output_keys=("memory_admission_plan_ref", "redaction_plan_ref", "forget_path_ref"),
                provider_class_required="agentic_control_plane",
            ),
        ),
        provider_requirements=("agentic_control_plane",),
        description=(
            "Composes a read-only Project Discipline Mesh scan across strategy, "
            "design, engineering, quality, operations, and business handoff risks "
            "before autonomous execution planning."
        ),
        confidence=0.25,
        metadata={
            **_NO_NEW_AUTHORITY,
            "risk_floor": "medium",
            "project_discipline_mesh": True,
            "disciplines": (
                "strategy_product",
                "design_research",
                "engineering",
                "quality_security",
                "operations",
                "business_gtm",
            ),
        },
    )


def _agentic_control_resource_governor_skill() -> SkillDescriptor:
    skill_id = "agentic_control.resource_governor.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Agentic resource governor",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="agentic_control"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="define_governed_mission",
                name="Define governed mission",
                action_type="agentic_control.mission.define",
                output_keys=("mission_contract_ref", "mission_contract_hash", "halt_conditions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="rank_resource_pressures",
                name="Rank resource pressures",
                action_type="agentic_control.priority.rank",
                depends_on=("define_governed_mission",),
                input_bindings={"mission_contract_ref": "define_governed_mission.mission_contract_ref"},
                output_keys=("resource_pressure_order_ref", "dependency_blockers", "risk_weights"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="evaluate_budget_governance",
                name="Evaluate budget governance",
                action_type="agentic_control.governance_gate.evaluate",
                depends_on=("rank_resource_pressures",),
                input_bindings={"priority_order_ref": "rank_resource_pressures.resource_pressure_order_ref"},
                output_keys=("gate_decision_ref", "proof_state", "blocked_actions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="bound_execution_budget",
                name="Bound execution budget",
                action_type="agentic_control.resource_budget.bound",
                depends_on=("evaluate_budget_governance",),
                input_bindings={"gate_decision_ref": "evaluate_budget_governance.gate_decision_ref"},
                output_keys=("budget_envelope_ref", "halt_thresholds", "resource_floor"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_budget_verification",
                name="Plan budget verification",
                action_type="agentic_control.verification.plan",
                depends_on=("bound_execution_budget",),
                input_bindings={"budget_envelope_ref": "bound_execution_budget.budget_envelope_ref"},
                output_keys=("budget_verification_plan_ref", "required_gates", "closure_rule"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="refine_resource_gaps",
                name="Refine resource gaps",
                action_type="agentic_control.self_audit.refine",
                depends_on=("plan_budget_verification",),
                input_bindings={
                    "budget_envelope_ref": "bound_execution_budget.budget_envelope_ref",
                    "verification_plan_ref": "plan_budget_verification.budget_verification_plan_ref",
                },
                output_keys=("resource_refinement_plan_ref", "gap_closure_order", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_budget_memory_admission",
                name="Plan budget memory admission",
                action_type="agentic_control.memory_admission.plan",
                depends_on=("refine_resource_gaps",),
                input_bindings={"refinement_plan_ref": "refine_resource_gaps.resource_refinement_plan_ref"},
                output_keys=("memory_admission_plan_ref", "redaction_plan_ref", "forget_path_ref"),
                provider_class_required="agentic_control_plane",
            ),
        ),
        provider_requirements=("agentic_control_plane",),
        description=(
            "Composes mission definition, priority ranking, governance gating, "
            "resource budget bounding, verification planning, resource-gap "
            "refinement, and memory-admission planning for autonomous execution "
            "before effect-bearing work is selected."
        ),
        confidence=0.25,
        metadata={
            **_NO_NEW_AUTHORITY,
            "risk_floor": "medium",
            "resource_governor": True,
            "protected_variables": (
                "resource_floor",
                "halt_thresholds",
                "budget_envelope_ref",
                "proof_state",
            ),
        },
    )


def _agentic_control_temporal_governor_skill() -> SkillDescriptor:
    skill_id = "agentic_control.temporal_governor.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Agentic temporal governor",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="agentic_control"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="define_temporal_mission",
                name="Define temporal mission",
                action_type="agentic_control.mission.define",
                output_keys=("mission_contract_ref", "temporal_boundary_ref", "halt_conditions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="rank_temporal_constraints",
                name="Rank temporal constraints",
                action_type="agentic_control.priority.rank",
                depends_on=("define_temporal_mission",),
                input_bindings={"mission_contract_ref": "define_temporal_mission.mission_contract_ref"},
                output_keys=("temporal_constraint_order_ref", "dependency_blockers", "risk_weights"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="evaluate_temporal_governance",
                name="Evaluate temporal governance",
                action_type="agentic_control.governance_gate.evaluate",
                depends_on=("rank_temporal_constraints",),
                input_bindings={"priority_order_ref": "rank_temporal_constraints.temporal_constraint_order_ref"},
                output_keys=("gate_decision_ref", "proof_state", "blocked_actions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="bound_temporal_budget",
                name="Bound temporal budget",
                action_type="agentic_control.resource_budget.bound",
                depends_on=("evaluate_temporal_governance",),
                input_bindings={"gate_decision_ref": "evaluate_temporal_governance.gate_decision_ref"},
                output_keys=("budget_envelope_ref", "time_budget_ref", "halt_thresholds", "resource_floor"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_temporal_verification",
                name="Plan temporal verification",
                action_type="agentic_control.verification.plan",
                depends_on=("bound_temporal_budget",),
                input_bindings={
                    "temporal_boundary_ref": "define_temporal_mission.temporal_boundary_ref",
                    "budget_envelope_ref": "bound_temporal_budget.budget_envelope_ref",
                    "time_budget_ref": "bound_temporal_budget.time_budget_ref",
                },
                output_keys=(
                    "temporal_verification_plan_ref",
                    "freshness_window_ref",
                    "lease_window_ref",
                    "retry_window_ref",
                    "closure_rule",
                ),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_temporal_interrogation",
                name="Plan temporal interrogation",
                action_type="agentic_control.interrogation.plan",
                depends_on=("plan_temporal_verification",),
                input_bindings={
                    "verification_plan_ref": "plan_temporal_verification.temporal_verification_plan_ref"
                },
                output_keys=("temporal_interrogation_plan_ref", "unknowns", "evidence_requests"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_temporal_triage",
                name="Plan temporal triage",
                action_type="agentic_control.telemetry_triage.plan",
                depends_on=("plan_temporal_interrogation",),
                input_bindings={
                    "verification_plan_ref": "plan_temporal_verification.temporal_verification_plan_ref",
                    "interrogation_plan_ref": "plan_temporal_interrogation.temporal_interrogation_plan_ref",
                    "time_budget_ref": "bound_temporal_budget.time_budget_ref",
                },
                output_keys=(
                    "temporal_triage_plan_ref",
                    "monitored_time_surfaces",
                    "threshold_contracts",
                    "stale_evidence_blockers",
                ),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="refine_temporal_gaps",
                name="Refine temporal gaps",
                action_type="agentic_control.self_audit.refine",
                depends_on=("plan_temporal_triage",),
                input_bindings={
                    "verification_plan_ref": "plan_temporal_verification.temporal_verification_plan_ref",
                    "interrogation_plan_ref": "plan_temporal_interrogation.temporal_interrogation_plan_ref",
                    "temporal_triage_plan_ref": "plan_temporal_triage.temporal_triage_plan_ref",
                },
                output_keys=("temporal_refinement_plan_ref", "gap_closure_order", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_temporal_memory_admission",
                name="Plan temporal memory admission",
                action_type="agentic_control.memory_admission.plan",
                depends_on=("refine_temporal_gaps",),
                input_bindings={"refinement_plan_ref": "refine_temporal_gaps.temporal_refinement_plan_ref"},
                output_keys=("memory_admission_plan_ref", "redaction_plan_ref", "forget_path_ref"),
                provider_class_required="agentic_control_plane",
            ),
        ),
        provider_requirements=("agentic_control_plane",),
        description=(
            "Composes read-only temporal discipline by linking mission boundary, "
            "time-sensitive constraints, governance gate, bounded time budget, "
            "freshness, lease, retry, and stale-evidence verification surfaces, "
            "temporal triage, refinement, and memory-admission planning before "
            "effect-bearing autonomous work."
        ),
        confidence=0.25,
        metadata={
            **_NO_NEW_AUTHORITY,
            "risk_floor": "medium",
            "temporal_governor": True,
            "time_surfaces": (
                "temporal_boundary_ref",
                "time_budget_ref",
                "freshness_window_ref",
                "lease_window_ref",
                "retry_window_ref",
                "stale_evidence_blockers",
            ),
        },
    )


def _agentic_control_memory_governor_skill() -> SkillDescriptor:
    skill_id = "agentic_control.memory_governor.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Agentic memory governor",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="agentic_control"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="define_memory_mission",
                name="Define memory mission",
                action_type="agentic_control.mission.define",
                output_keys=("mission_contract_ref", "memory_boundary_ref", "halt_conditions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="rank_memory_constraints",
                name="Rank memory constraints",
                action_type="agentic_control.priority.rank",
                depends_on=("define_memory_mission",),
                input_bindings={"mission_contract_ref": "define_memory_mission.mission_contract_ref"},
                output_keys=("memory_constraint_order_ref", "dependency_blockers", "risk_weights"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="evaluate_memory_governance",
                name="Evaluate memory governance",
                action_type="agentic_control.governance_gate.evaluate",
                depends_on=("rank_memory_constraints",),
                input_bindings={"priority_order_ref": "rank_memory_constraints.memory_constraint_order_ref"},
                output_keys=("gate_decision_ref", "proof_state", "blocked_actions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="bound_memory_budget",
                name="Bound memory budget",
                action_type="agentic_control.resource_budget.bound",
                depends_on=("evaluate_memory_governance",),
                input_bindings={"gate_decision_ref": "evaluate_memory_governance.gate_decision_ref"},
                output_keys=("budget_envelope_ref", "halt_thresholds", "resource_floor"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_memory_verification",
                name="Plan memory verification",
                action_type="agentic_control.verification.plan",
                depends_on=("bound_memory_budget",),
                input_bindings={
                    "memory_boundary_ref": "define_memory_mission.memory_boundary_ref",
                    "budget_envelope_ref": "bound_memory_budget.budget_envelope_ref",
                },
                output_keys=(
                    "memory_verification_plan_ref",
                    "memory_scope_ref",
                    "retention_window_ref",
                    "recall_guard_ref",
                    "closure_rule",
                ),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_memory_interrogation",
                name="Plan memory interrogation",
                action_type="agentic_control.interrogation.plan",
                depends_on=("plan_memory_verification",),
                input_bindings={"verification_plan_ref": "plan_memory_verification.memory_verification_plan_ref"},
                output_keys=("memory_interrogation_plan_ref", "unknowns", "evidence_requests"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="refine_memory_gaps",
                name="Refine memory gaps",
                action_type="agentic_control.self_audit.refine",
                depends_on=("plan_memory_interrogation",),
                input_bindings={
                    "memory_scope_ref": "plan_memory_verification.memory_scope_ref",
                    "recall_guard_ref": "plan_memory_verification.recall_guard_ref",
                    "verification_plan_ref": "plan_memory_verification.memory_verification_plan_ref",
                    "interrogation_plan_ref": "plan_memory_interrogation.memory_interrogation_plan_ref",
                },
                output_keys=("memory_refinement_plan_ref", "gap_closure_order", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_governed_memory_admission",
                name="Plan governed memory admission",
                action_type="agentic_control.memory_admission.plan",
                depends_on=("refine_memory_gaps",),
                input_bindings={
                    "refinement_plan_ref": "refine_memory_gaps.memory_refinement_plan_ref",
                    "memory_scope_ref": "plan_memory_verification.memory_scope_ref",
                    "retention_window_ref": "plan_memory_verification.retention_window_ref",
                    "recall_guard_ref": "plan_memory_verification.recall_guard_ref",
                },
                output_keys=(
                    "memory_admission_plan_ref",
                    "redaction_plan_ref",
                    "forget_path_ref",
                    "retention_policy_ref",
                ),
                provider_class_required="agentic_control_plane",
            ),
        ),
        provider_requirements=("agentic_control_plane",),
        description=(
            "Composes read-only memory discipline by linking mission boundary, "
            "memory constraints, governance gate, resource budget, verification, "
            "interrogation, refinement, scoped memory admission, redaction, "
            "retention, recall guards, and forget-path planning before learned "
            "state is reused."
        ),
        confidence=0.25,
        metadata={
            **_NO_NEW_AUTHORITY,
            "risk_floor": "medium",
            "memory_governor": True,
            "memory_surfaces": (
                "memory_boundary_ref",
                "memory_scope_ref",
                "retention_window_ref",
                "recall_guard_ref",
                "redaction_plan_ref",
                "forget_path_ref",
                "retention_policy_ref",
            ),
        },
    )


def _agentic_control_evidence_governor_skill() -> SkillDescriptor:
    skill_id = "agentic_control.evidence_governor.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Agentic evidence governor",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="agentic_control"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="define_evidence_mission",
                name="Define evidence mission",
                action_type="agentic_control.mission.define",
                output_keys=("mission_contract_ref", "claim_boundary_ref", "halt_conditions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="rank_evidence_requirements",
                name="Rank evidence requirements",
                action_type="agentic_control.priority.rank",
                depends_on=("define_evidence_mission",),
                input_bindings={"mission_contract_ref": "define_evidence_mission.mission_contract_ref"},
                output_keys=("evidence_requirement_order_ref", "dependency_blockers", "risk_weights"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="evaluate_evidence_governance",
                name="Evaluate evidence governance",
                action_type="agentic_control.governance_gate.evaluate",
                depends_on=("rank_evidence_requirements",),
                input_bindings={"priority_order_ref": "rank_evidence_requirements.evidence_requirement_order_ref"},
                output_keys=("gate_decision_ref", "proof_state", "blocked_actions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="bound_evidence_budget",
                name="Bound evidence budget",
                action_type="agentic_control.resource_budget.bound",
                depends_on=("evaluate_evidence_governance",),
                input_bindings={"gate_decision_ref": "evaluate_evidence_governance.gate_decision_ref"},
                output_keys=("budget_envelope_ref", "halt_thresholds", "resource_floor"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_claim_verification",
                name="Plan claim verification",
                action_type="agentic_control.verification.plan",
                depends_on=("bound_evidence_budget",),
                input_bindings={
                    "claim_boundary_ref": "define_evidence_mission.claim_boundary_ref",
                    "budget_envelope_ref": "bound_evidence_budget.budget_envelope_ref",
                },
                output_keys=(
                    "claim_verification_plan_ref",
                    "source_requirement_refs",
                    "contradiction_check_ref",
                    "independent_support_rule",
                    "closure_rule",
                ),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_evidence_interrogation",
                name="Plan evidence interrogation",
                action_type="agentic_control.interrogation.plan",
                depends_on=("plan_claim_verification",),
                input_bindings={"verification_plan_ref": "plan_claim_verification.claim_verification_plan_ref"},
                output_keys=("evidence_interrogation_plan_ref", "unknowns", "evidence_requests"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="refine_evidence_gaps",
                name="Refine evidence gaps",
                action_type="agentic_control.self_audit.refine",
                depends_on=("plan_evidence_interrogation",),
                input_bindings={
                    "verification_plan_ref": "plan_claim_verification.claim_verification_plan_ref",
                    "interrogation_plan_ref": "plan_evidence_interrogation.evidence_interrogation_plan_ref",
                    "contradiction_check_ref": "plan_claim_verification.contradiction_check_ref",
                    "source_requirement_refs": "plan_claim_verification.source_requirement_refs",
                },
                output_keys=("evidence_refinement_plan_ref", "gap_closure_order", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_evidence_memory_admission",
                name="Plan evidence memory admission",
                action_type="agentic_control.memory_admission.plan",
                depends_on=("refine_evidence_gaps",),
                input_bindings={
                    "refinement_plan_ref": "refine_evidence_gaps.evidence_refinement_plan_ref",
                    "verification_plan_ref": "plan_claim_verification.claim_verification_plan_ref",
                    "interrogation_plan_ref": "plan_evidence_interrogation.evidence_interrogation_plan_ref",
                },
                output_keys=("memory_admission_plan_ref", "redaction_plan_ref", "forget_path_ref"),
                provider_class_required="agentic_control_plane",
            ),
        ),
        provider_requirements=("agentic_control_plane",),
        description=(
            "Composes read-only evidence discipline by linking claim boundary, "
            "source requirements, governance gate, budget, claim verification, "
            "contradiction checks, independent-support rules, interrogation, "
            "gap refinement, and memory-admission planning before a claim is "
            "reused by autonomous execution."
        ),
        confidence=0.25,
        metadata={
            **_NO_NEW_AUTHORITY,
            "risk_floor": "medium",
            "evidence_governor": True,
            "evidence_surfaces": (
                "claim_boundary_ref",
                "source_requirement_refs",
                "contradiction_check_ref",
                "independent_support_rule",
                "proof_state",
                "evidence_requests",
            ),
        },
    )


def _agentic_control_math_governor_skill() -> SkillDescriptor:
    skill_id = "agentic_control.math_governor.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Agentic math governor",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="agentic_control"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="define_math_problem",
                name="Define math problem",
                action_type="agentic_control.mission.define",
                output_keys=("mission_contract_ref", "proof_boundary_ref", "halt_conditions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="rank_math_constraints",
                name="Rank math constraints",
                action_type="agentic_control.priority.rank",
                depends_on=("define_math_problem",),
                input_bindings={"mission_contract_ref": "define_math_problem.mission_contract_ref"},
                output_keys=("math_constraint_order_ref", "dependency_blockers", "risk_weights"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="evaluate_math_governance",
                name="Evaluate math governance",
                action_type="agentic_control.governance_gate.evaluate",
                depends_on=("rank_math_constraints",),
                input_bindings={"priority_order_ref": "rank_math_constraints.math_constraint_order_ref"},
                output_keys=("gate_decision_ref", "proof_state", "blocked_actions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="bound_math_budget",
                name="Bound math budget",
                action_type="agentic_control.resource_budget.bound",
                depends_on=("evaluate_math_governance",),
                input_bindings={"gate_decision_ref": "evaluate_math_governance.gate_decision_ref"},
                output_keys=("budget_envelope_ref", "halt_thresholds", "resource_floor"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="analyze_math_structure",
                name="Analyze math structure",
                action_type="agentic_control.math_algorithm.analyze",
                depends_on=("bound_math_budget",),
                input_bindings={
                    "proof_boundary_ref": "define_math_problem.proof_boundary_ref",
                    "budget_envelope_ref": "bound_math_budget.budget_envelope_ref",
                },
                output_keys=("mathematical_model_ref", "proof_obligation_refs", "counterexample_search_ref"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_math_verification",
                name="Plan math verification",
                action_type="agentic_control.verification.plan",
                depends_on=("analyze_math_structure",),
                input_bindings={
                    "mathematical_model_ref": "analyze_math_structure.mathematical_model_ref",
                    "proof_obligation_refs": "analyze_math_structure.proof_obligation_refs",
                    "counterexample_search_ref": "analyze_math_structure.counterexample_search_ref",
                },
                output_keys=("math_verification_plan_ref", "required_gates", "closure_rule"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_math_interrogation",
                name="Plan math interrogation",
                action_type="agentic_control.interrogation.plan",
                depends_on=("plan_math_verification",),
                input_bindings={"verification_plan_ref": "plan_math_verification.math_verification_plan_ref"},
                output_keys=("math_interrogation_plan_ref", "unknowns", "evidence_requests"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="refine_math_gaps",
                name="Refine math gaps",
                action_type="agentic_control.self_audit.refine",
                depends_on=("plan_math_interrogation",),
                input_bindings={
                    "mathematical_model_ref": "analyze_math_structure.mathematical_model_ref",
                    "proof_obligation_refs": "analyze_math_structure.proof_obligation_refs",
                    "counterexample_search_ref": "analyze_math_structure.counterexample_search_ref",
                    "verification_plan_ref": "plan_math_verification.math_verification_plan_ref",
                    "interrogation_plan_ref": "plan_math_interrogation.math_interrogation_plan_ref",
                },
                output_keys=("math_refinement_plan_ref", "gap_closure_order", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_math_memory_admission",
                name="Plan math memory admission",
                action_type="agentic_control.memory_admission.plan",
                depends_on=("refine_math_gaps",),
                input_bindings={"refinement_plan_ref": "refine_math_gaps.math_refinement_plan_ref"},
                output_keys=("memory_admission_plan_ref", "redaction_plan_ref", "forget_path_ref"),
                provider_class_required="agentic_control_plane",
            ),
        ),
        provider_requirements=("agentic_control_plane",),
        description=(
            "Composes read-only mathematical proof planning by linking problem "
            "boundary, ranked constraints, governance gate, resource budget, "
            "symbolic structure analysis, proof obligations, counterexample "
            "search, verification, interrogation, refinement, and memory "
            "admission before downstream algorithm or code work."
        ),
        confidence=0.25,
        metadata={
            **_NO_NEW_AUTHORITY,
            "risk_floor": "medium",
            "math_governor": True,
            "proof_surfaces": (
                "proof_boundary_ref",
                "mathematical_model_ref",
                "proof_obligation_refs",
                "counterexample_search_ref",
                "closure_rule",
            ),
        },
    )


def _agentic_control_algorithm_governor_skill() -> SkillDescriptor:
    skill_id = "agentic_control.algorithm_governor.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Agentic algorithm governor",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="agentic_control"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="define_algorithm_problem",
                name="Define algorithm problem",
                action_type="agentic_control.mission.define",
                output_keys=("mission_contract_ref", "problem_boundary_ref", "halt_conditions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="rank_algorithm_constraints",
                name="Rank algorithm constraints",
                action_type="agentic_control.priority.rank",
                depends_on=("define_algorithm_problem",),
                input_bindings={"mission_contract_ref": "define_algorithm_problem.mission_contract_ref"},
                output_keys=("constraint_order_ref", "dependency_blockers", "risk_weights"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="evaluate_algorithm_governance",
                name="Evaluate algorithm governance",
                action_type="agentic_control.governance_gate.evaluate",
                depends_on=("rank_algorithm_constraints",),
                input_bindings={"priority_order_ref": "rank_algorithm_constraints.constraint_order_ref"},
                output_keys=("gate_decision_ref", "proof_state", "blocked_actions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="bound_algorithm_budget",
                name="Bound algorithm budget",
                action_type="agentic_control.resource_budget.bound",
                depends_on=("evaluate_algorithm_governance",),
                input_bindings={"gate_decision_ref": "evaluate_algorithm_governance.gate_decision_ref"},
                output_keys=("budget_envelope_ref", "halt_thresholds", "resource_floor"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="analyze_algorithm_design",
                name="Analyze algorithm design",
                action_type="agentic_control.math_algorithm.analyze",
                depends_on=("bound_algorithm_budget",),
                input_bindings={
                    "problem_boundary_ref": "define_algorithm_problem.problem_boundary_ref",
                    "budget_envelope_ref": "bound_algorithm_budget.budget_envelope_ref",
                },
                output_keys=("algorithm_analysis_ref", "complexity_bound", "failure_modes"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="build_algorithm_threat_model",
                name="Build algorithm threat model",
                action_type="agentic_control.security_threat_model.build",
                depends_on=("analyze_algorithm_design",),
                input_bindings={"algorithm_analysis_ref": "analyze_algorithm_design.algorithm_analysis_ref"},
                output_keys=("threat_model_ref", "mitigation_refs", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_algorithm_verification",
                name="Plan algorithm verification",
                action_type="agentic_control.verification.plan",
                depends_on=("analyze_algorithm_design", "build_algorithm_threat_model"),
                input_bindings={
                    "algorithm_analysis_ref": "analyze_algorithm_design.algorithm_analysis_ref",
                    "threat_model_ref": "build_algorithm_threat_model.threat_model_ref",
                },
                output_keys=("algorithm_verification_plan_ref", "required_gates", "closure_rule"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="refine_algorithm_gaps",
                name="Refine algorithm gaps",
                action_type="agentic_control.self_audit.refine",
                depends_on=("plan_algorithm_verification",),
                input_bindings={
                    "algorithm_analysis_ref": "analyze_algorithm_design.algorithm_analysis_ref",
                    "verification_plan_ref": "plan_algorithm_verification.algorithm_verification_plan_ref",
                    "threat_model_ref": "build_algorithm_threat_model.threat_model_ref",
                },
                output_keys=("algorithm_refinement_plan_ref", "gap_closure_order", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_algorithm_memory_admission",
                name="Plan algorithm memory admission",
                action_type="agentic_control.memory_admission.plan",
                depends_on=("refine_algorithm_gaps",),
                input_bindings={"refinement_plan_ref": "refine_algorithm_gaps.algorithm_refinement_plan_ref"},
                output_keys=("memory_admission_plan_ref", "redaction_plan_ref", "forget_path_ref"),
                provider_class_required="agentic_control_plane",
            ),
        ),
        provider_requirements=("agentic_control_plane",),
        description=(
            "Composes bounded algorithm design review before code planning by "
            "linking mission boundary, priority constraints, governance gate, "
            "resource budget, complexity analysis, threat model, verification "
            "plan, refinement, and memory-admission planning."
        ),
        confidence=0.25,
        metadata={
            **_NO_NEW_AUTHORITY,
            "risk_floor": "medium",
            "algorithm_governor": True,
            "analysis_dimensions": (
                "problem_boundary",
                "complexity_bound",
                "failure_modes",
                "threat_model",
                "verification_gates",
            ),
        },
    )


def _agentic_control_security_governor_skill() -> SkillDescriptor:
    skill_id = "agentic_control.security_governor.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Agentic security governor",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="agentic_control"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="define_security_boundary",
                name="Define security boundary",
                action_type="agentic_control.mission.define",
                output_keys=("mission_contract_ref", "security_boundary_ref", "halt_conditions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="rank_security_constraints",
                name="Rank security constraints",
                action_type="agentic_control.priority.rank",
                depends_on=("define_security_boundary",),
                input_bindings={"mission_contract_ref": "define_security_boundary.mission_contract_ref"},
                output_keys=("security_constraint_order_ref", "dependency_blockers", "risk_weights"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="evaluate_security_governance",
                name="Evaluate security governance",
                action_type="agentic_control.governance_gate.evaluate",
                depends_on=("rank_security_constraints",),
                input_bindings={"priority_order_ref": "rank_security_constraints.security_constraint_order_ref"},
                output_keys=("gate_decision_ref", "proof_state", "blocked_actions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="build_security_threat_model",
                name="Build security threat model",
                action_type="agentic_control.security_threat_model.build",
                depends_on=("evaluate_security_governance",),
                input_bindings={
                    "security_boundary_ref": "define_security_boundary.security_boundary_ref",
                    "gate_decision_ref": "evaluate_security_governance.gate_decision_ref",
                },
                output_keys=("threat_model_ref", "mitigation_refs", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_security_verification",
                name="Plan security verification",
                action_type="agentic_control.verification.plan",
                depends_on=("build_security_threat_model",),
                input_bindings={"threat_model_ref": "build_security_threat_model.threat_model_ref"},
                output_keys=("security_verification_plan_ref", "required_gates", "closure_rule"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_security_interrogation",
                name="Plan security interrogation",
                action_type="agentic_control.interrogation.plan",
                depends_on=("plan_security_verification",),
                input_bindings={
                    "verification_plan_ref": "plan_security_verification.security_verification_plan_ref"
                },
                output_keys=("security_interrogation_plan_ref", "unknowns", "evidence_requests"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="refine_security_gaps",
                name="Refine security gaps",
                action_type="agentic_control.self_audit.refine",
                depends_on=("plan_security_interrogation",),
                input_bindings={
                    "threat_model_ref": "build_security_threat_model.threat_model_ref",
                    "verification_plan_ref": "plan_security_verification.security_verification_plan_ref",
                    "interrogation_plan_ref": "plan_security_interrogation.security_interrogation_plan_ref",
                },
                output_keys=("security_refinement_plan_ref", "gap_closure_order", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_security_incident_recovery",
                name="Plan security incident recovery",
                action_type="agentic_control.incident_recovery.plan",
                depends_on=("refine_security_gaps",),
                input_bindings={"refinement_plan_ref": "refine_security_gaps.security_refinement_plan_ref"},
                output_keys=("incident_recovery_plan_ref", "containment_actions", "verification_steps"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_security_memory_admission",
                name="Plan security memory admission",
                action_type="agentic_control.memory_admission.plan",
                depends_on=("refine_security_gaps", "plan_security_incident_recovery"),
                input_bindings={
                    "refinement_plan_ref": "refine_security_gaps.security_refinement_plan_ref",
                    "incident_recovery_plan_ref": "plan_security_incident_recovery.incident_recovery_plan_ref",
                },
                output_keys=("memory_admission_plan_ref", "redaction_plan_ref", "forget_path_ref"),
                provider_class_required="agentic_control_plane",
            ),
        ),
        provider_requirements=("agentic_control_plane",),
        description=(
            "Composes security-bound autonomous planning by linking mission "
            "boundary, prioritized security constraints, governance gate, threat "
            "model, verification plan, interrogation plan, refinement, incident "
            "recovery, and memory-admission planning before effect-bearing work."
        ),
        confidence=0.25,
        metadata={
            **_NO_NEW_AUTHORITY,
            "risk_floor": "medium",
            "security_governor": True,
            "protected_surfaces": (
                "security_boundary_ref",
                "threat_model_ref",
                "mitigation_refs",
                "incident_recovery_plan_ref",
                "redaction_plan_ref",
            ),
        },
    )


def _agentic_control_swarm_governor_skill() -> SkillDescriptor:
    skill_id = "agentic_control.swarm_governor.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Agentic swarm governor",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="agentic_control"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="define_swarm_mission",
                name="Define swarm mission",
                action_type="agentic_control.mission.define",
                output_keys=("mission_contract_ref", "swarm_boundary_ref", "halt_conditions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="rank_swarm_work",
                name="Rank swarm work",
                action_type="agentic_control.priority.rank",
                depends_on=("define_swarm_mission",),
                input_bindings={"mission_contract_ref": "define_swarm_mission.mission_contract_ref"},
                output_keys=("swarm_priority_order_ref", "dependency_blockers", "risk_weights"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="evaluate_swarm_governance",
                name="Evaluate swarm governance",
                action_type="agentic_control.governance_gate.evaluate",
                depends_on=("rank_swarm_work",),
                input_bindings={"priority_order_ref": "rank_swarm_work.swarm_priority_order_ref"},
                output_keys=("gate_decision_ref", "proof_state", "blocked_actions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="bound_swarm_budget",
                name="Bound swarm budget",
                action_type="agentic_control.resource_budget.bound",
                depends_on=("evaluate_swarm_governance",),
                input_bindings={"gate_decision_ref": "evaluate_swarm_governance.gate_decision_ref"},
                output_keys=("budget_envelope_ref", "halt_thresholds", "resource_floor"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="build_swarm_threat_model",
                name="Build swarm threat model",
                action_type="agentic_control.security_threat_model.build",
                depends_on=("bound_swarm_budget",),
                input_bindings={
                    "swarm_boundary_ref": "define_swarm_mission.swarm_boundary_ref",
                    "budget_envelope_ref": "bound_swarm_budget.budget_envelope_ref",
                },
                output_keys=("threat_model_ref", "mitigation_refs", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="coordinate_swarm_plan",
                name="Coordinate swarm plan",
                action_type="agentic_control.swarm.coordinate",
                depends_on=("build_swarm_threat_model",),
                input_bindings={
                    "threat_model_ref": "build_swarm_threat_model.threat_model_ref",
                    "budget_envelope_ref": "bound_swarm_budget.budget_envelope_ref",
                },
                output_keys=("swarm_plan_ref", "role_assignment_hash", "shard_boundaries", "consensus_rule"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_swarm_verification",
                name="Plan swarm verification",
                action_type="agentic_control.verification.plan",
                depends_on=("coordinate_swarm_plan",),
                input_bindings={"swarm_plan_ref": "coordinate_swarm_plan.swarm_plan_ref"},
                output_keys=("swarm_verification_plan_ref", "required_gates", "closure_rule"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_swarm_interrogation",
                name="Plan swarm interrogation",
                action_type="agentic_control.interrogation.plan",
                depends_on=("plan_swarm_verification",),
                input_bindings={"verification_plan_ref": "plan_swarm_verification.swarm_verification_plan_ref"},
                output_keys=("swarm_interrogation_plan_ref", "unknowns", "evidence_requests"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="refine_swarm_gaps",
                name="Refine swarm gaps",
                action_type="agentic_control.self_audit.refine",
                depends_on=("plan_swarm_interrogation",),
                input_bindings={
                    "swarm_plan_ref": "coordinate_swarm_plan.swarm_plan_ref",
                    "verification_plan_ref": "plan_swarm_verification.swarm_verification_plan_ref",
                    "interrogation_plan_ref": "plan_swarm_interrogation.swarm_interrogation_plan_ref",
                },
                output_keys=("swarm_refinement_plan_ref", "gap_closure_order", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_swarm_memory_admission",
                name="Plan swarm memory admission",
                action_type="agentic_control.memory_admission.plan",
                depends_on=("refine_swarm_gaps",),
                input_bindings={"refinement_plan_ref": "refine_swarm_gaps.swarm_refinement_plan_ref"},
                output_keys=("memory_admission_plan_ref", "redaction_plan_ref", "forget_path_ref"),
                provider_class_required="agentic_control_plane",
            ),
        ),
        provider_requirements=("agentic_control_plane",),
        description=(
            "Composes read-only swarm coordination planning by linking mission "
            "boundary, priority order, governance gate, resource budget, threat "
            "model, role assignment, verification, interrogation, refinement, "
            "and memory-admission planning without spawning subagents."
        ),
        confidence=0.25,
        metadata={
            **_NO_NEW_AUTHORITY,
            "risk_floor": "medium",
            "swarm_governor": True,
            "coordination_surfaces": (
                "swarm_boundary_ref",
                "swarm_plan_ref",
                "role_assignment_hash",
                "shard_boundaries",
                "consensus_rule",
            ),
        },
    )


def _agentic_control_coding_governor_skill() -> SkillDescriptor:
    skill_id = "agentic_control.coding_governor.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Agentic coding governor",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="agentic_control"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="define_code_mission",
                name="Define code mission",
                action_type="agentic_control.mission.define",
                output_keys=("mission_contract_ref", "repo_boundary_ref", "halt_conditions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="rank_code_constraints",
                name="Rank code constraints",
                action_type="agentic_control.priority.rank",
                depends_on=("define_code_mission",),
                input_bindings={"mission_contract_ref": "define_code_mission.mission_contract_ref"},
                output_keys=("code_constraint_order_ref", "dependency_blockers", "risk_weights"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="evaluate_code_governance",
                name="Evaluate code governance",
                action_type="agentic_control.governance_gate.evaluate",
                depends_on=("rank_code_constraints",),
                input_bindings={"priority_order_ref": "rank_code_constraints.code_constraint_order_ref"},
                output_keys=("gate_decision_ref", "proof_state", "blocked_actions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="bound_code_budget",
                name="Bound code budget",
                action_type="agentic_control.resource_budget.bound",
                depends_on=("evaluate_code_governance",),
                input_bindings={"gate_decision_ref": "evaluate_code_governance.gate_decision_ref"},
                output_keys=("budget_envelope_ref", "halt_thresholds", "resource_floor"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="build_code_threat_model",
                name="Build code threat model",
                action_type="agentic_control.security_threat_model.build",
                depends_on=("bound_code_budget",),
                input_bindings={
                    "repo_boundary_ref": "define_code_mission.repo_boundary_ref",
                    "budget_envelope_ref": "bound_code_budget.budget_envelope_ref",
                },
                output_keys=("threat_model_ref", "mitigation_refs", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_code_change_boundary",
                name="Plan code change boundary",
                action_type="agentic_control.code_change.plan",
                depends_on=("build_code_threat_model",),
                input_bindings={
                    "repo_boundary_ref": "define_code_mission.repo_boundary_ref",
                    "threat_model_ref": "build_code_threat_model.threat_model_ref",
                    "budget_envelope_ref": "bound_code_budget.budget_envelope_ref",
                },
                output_keys=("code_change_plan_ref", "change_boundary", "test_contract", "rollback_plan"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_code_verification",
                name="Plan code verification",
                action_type="agentic_control.verification.plan",
                depends_on=("plan_code_change_boundary",),
                input_bindings={"code_change_plan_ref": "plan_code_change_boundary.code_change_plan_ref"},
                output_keys=("code_verification_plan_ref", "required_gates", "closure_rule"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_code_interrogation",
                name="Plan code interrogation",
                action_type="agentic_control.interrogation.plan",
                depends_on=("plan_code_verification",),
                input_bindings={"verification_plan_ref": "plan_code_verification.code_verification_plan_ref"},
                output_keys=("code_interrogation_plan_ref", "unknowns", "evidence_requests"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="refine_code_gaps",
                name="Refine code gaps",
                action_type="agentic_control.self_audit.refine",
                depends_on=("plan_code_interrogation",),
                input_bindings={
                    "code_change_plan_ref": "plan_code_change_boundary.code_change_plan_ref",
                    "verification_plan_ref": "plan_code_verification.code_verification_plan_ref",
                    "interrogation_plan_ref": "plan_code_interrogation.code_interrogation_plan_ref",
                    "threat_model_ref": "build_code_threat_model.threat_model_ref",
                },
                output_keys=("code_refinement_plan_ref", "gap_closure_order", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_code_memory_admission",
                name="Plan code memory admission",
                action_type="agentic_control.memory_admission.plan",
                depends_on=("refine_code_gaps",),
                input_bindings={"refinement_plan_ref": "refine_code_gaps.code_refinement_plan_ref"},
                output_keys=("memory_admission_plan_ref", "redaction_plan_ref", "forget_path_ref"),
                provider_class_required="agentic_control_plane",
            ),
        ),
        provider_requirements=("agentic_control_plane",),
        description=(
            "Composes read-only coding discipline by linking repository boundary, "
            "constraint ranking, governance gate, resource budget, threat model, "
            "code-change boundary, verification, interrogation, refinement, and "
            "memory-admission planning before effect-bearing implementation work."
        ),
        confidence=0.25,
        metadata={
            **_NO_NEW_AUTHORITY,
            "risk_floor": "medium",
            "coding_governor": True,
            "code_surfaces": (
                "repo_boundary_ref",
                "code_change_plan_ref",
                "change_boundary",
                "test_contract",
                "rollback_plan",
            ),
        },
    )


def _agentic_control_runtime_governor_skill() -> SkillDescriptor:
    skill_id = "agentic_control.runtime_governor.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Agentic runtime governor",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="agentic_control"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="define_runtime_boundary",
                name="Define runtime boundary",
                action_type="agentic_control.mission.define",
                output_keys=("mission_contract_ref", "runtime_boundary_ref", "halt_conditions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="rank_runtime_signals",
                name="Rank runtime signals",
                action_type="agentic_control.priority.rank",
                depends_on=("define_runtime_boundary",),
                input_bindings={"mission_contract_ref": "define_runtime_boundary.mission_contract_ref"},
                output_keys=("runtime_signal_order_ref", "dependency_blockers", "risk_weights"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="evaluate_runtime_governance",
                name="Evaluate runtime governance",
                action_type="agentic_control.governance_gate.evaluate",
                depends_on=("rank_runtime_signals",),
                input_bindings={"priority_order_ref": "rank_runtime_signals.runtime_signal_order_ref"},
                output_keys=("gate_decision_ref", "proof_state", "blocked_actions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="bound_runtime_budget",
                name="Bound runtime budget",
                action_type="agentic_control.resource_budget.bound",
                depends_on=("evaluate_runtime_governance",),
                input_bindings={"gate_decision_ref": "evaluate_runtime_governance.gate_decision_ref"},
                output_keys=("budget_envelope_ref", "halt_thresholds", "resource_floor"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_runtime_recovery",
                name="Plan runtime recovery",
                action_type="agentic_control.incident_recovery.plan",
                depends_on=("bound_runtime_budget",),
                input_bindings={
                    "runtime_boundary_ref": "define_runtime_boundary.runtime_boundary_ref",
                    "budget_envelope_ref": "bound_runtime_budget.budget_envelope_ref",
                },
                output_keys=("incident_recovery_plan_ref", "containment_actions", "verification_steps"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_runtime_telemetry",
                name="Plan runtime telemetry",
                action_type="agentic_control.telemetry_triage.plan",
                depends_on=("bound_runtime_budget", "plan_runtime_recovery"),
                input_bindings={
                    "runtime_boundary_ref": "define_runtime_boundary.runtime_boundary_ref",
                    "incident_recovery_plan_ref": "plan_runtime_recovery.incident_recovery_plan_ref",
                    "budget_envelope_ref": "bound_runtime_budget.budget_envelope_ref",
                },
                output_keys=(
                    "telemetry_triage_plan_ref",
                    "monitored_surfaces",
                    "threshold_contracts",
                    "remediation_order",
                ),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_runtime_verification",
                name="Plan runtime verification",
                action_type="agentic_control.verification.plan",
                depends_on=("plan_runtime_telemetry",),
                input_bindings={
                    "telemetry_triage_plan_ref": "plan_runtime_telemetry.telemetry_triage_plan_ref",
                    "incident_recovery_plan_ref": "plan_runtime_recovery.incident_recovery_plan_ref",
                },
                output_keys=("runtime_verification_plan_ref", "required_gates", "closure_rule"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_runtime_interrogation",
                name="Plan runtime interrogation",
                action_type="agentic_control.interrogation.plan",
                depends_on=("plan_runtime_verification",),
                input_bindings={"verification_plan_ref": "plan_runtime_verification.runtime_verification_plan_ref"},
                output_keys=("runtime_interrogation_plan_ref", "unknowns", "evidence_requests"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="refine_runtime_gaps",
                name="Refine runtime gaps",
                action_type="agentic_control.self_audit.refine",
                depends_on=("plan_runtime_interrogation",),
                input_bindings={
                    "telemetry_triage_plan_ref": "plan_runtime_telemetry.telemetry_triage_plan_ref",
                    "incident_recovery_plan_ref": "plan_runtime_recovery.incident_recovery_plan_ref",
                    "verification_plan_ref": "plan_runtime_verification.runtime_verification_plan_ref",
                    "interrogation_plan_ref": "plan_runtime_interrogation.runtime_interrogation_plan_ref",
                },
                output_keys=("runtime_refinement_plan_ref", "gap_closure_order", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_runtime_memory_admission",
                name="Plan runtime memory admission",
                action_type="agentic_control.memory_admission.plan",
                depends_on=("refine_runtime_gaps",),
                input_bindings={"refinement_plan_ref": "refine_runtime_gaps.runtime_refinement_plan_ref"},
                output_keys=("memory_admission_plan_ref", "redaction_plan_ref", "forget_path_ref"),
                provider_class_required="agentic_control_plane",
            ),
        ),
        provider_requirements=("agentic_control_plane",),
        description=(
            "Composes read-only runtime governance by linking runtime boundary, "
            "ranked health signals, governance gate, resource budget, incident "
            "recovery planning, telemetry triage, verification, interrogation, "
            "refinement, and memory-admission planning before write-capable "
            "autonomous operations execute."
        ),
        confidence=0.25,
        metadata={
            **_NO_NEW_AUTHORITY,
            "risk_floor": "medium",
            "runtime_governor": True,
            "runtime_surfaces": (
                "runtime_boundary_ref",
                "incident_recovery_plan_ref",
                "telemetry_triage_plan_ref",
                "threshold_contracts",
                "remediation_order",
            ),
        },
    )


def _agentic_control_release_governor_skill() -> SkillDescriptor:
    skill_id = "agentic_control.release_governor.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Agentic release governor",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_READ,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="agentic_control"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="define_release_boundary",
                name="Define release boundary",
                action_type="agentic_control.mission.define",
                output_keys=("mission_contract_ref", "release_boundary_ref", "halt_conditions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="rank_release_constraints",
                name="Rank release constraints",
                action_type="agentic_control.priority.rank",
                depends_on=("define_release_boundary",),
                input_bindings={"mission_contract_ref": "define_release_boundary.mission_contract_ref"},
                output_keys=("release_constraint_order_ref", "dependency_blockers", "risk_weights"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="evaluate_release_governance",
                name="Evaluate release governance",
                action_type="agentic_control.governance_gate.evaluate",
                depends_on=("rank_release_constraints",),
                input_bindings={"priority_order_ref": "rank_release_constraints.release_constraint_order_ref"},
                output_keys=("gate_decision_ref", "proof_state", "blocked_actions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="bound_release_budget",
                name="Bound release budget",
                action_type="agentic_control.resource_budget.bound",
                depends_on=("evaluate_release_governance",),
                input_bindings={"gate_decision_ref": "evaluate_release_governance.gate_decision_ref"},
                output_keys=("budget_envelope_ref", "halt_thresholds", "resource_floor"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_release_handoff_boundary",
                name="Plan release handoff boundary",
                action_type="agentic_control.release_handoff.plan",
                depends_on=("bound_release_budget",),
                input_bindings={
                    "release_boundary_ref": "define_release_boundary.release_boundary_ref",
                    "gate_decision_ref": "evaluate_release_governance.gate_decision_ref",
                    "budget_envelope_ref": "bound_release_budget.budget_envelope_ref",
                },
                output_keys=("release_handoff_plan_ref", "commit_boundary", "ci_gate_plan", "rollback_path"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_release_verification",
                name="Plan release verification",
                action_type="agentic_control.verification.plan",
                depends_on=("plan_release_handoff_boundary",),
                input_bindings={
                    "release_handoff_plan_ref": (
                        "plan_release_handoff_boundary.release_handoff_plan_ref"
                    )
                },
                output_keys=("release_verification_plan_ref", "required_gates", "closure_rule"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_release_interrogation",
                name="Plan release interrogation",
                action_type="agentic_control.interrogation.plan",
                depends_on=("plan_release_verification",),
                input_bindings={"verification_plan_ref": "plan_release_verification.release_verification_plan_ref"},
                output_keys=("release_interrogation_plan_ref", "unknowns", "evidence_requests"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="refine_release_gaps",
                name="Refine release gaps",
                action_type="agentic_control.self_audit.refine",
                depends_on=("plan_release_interrogation",),
                input_bindings={
                    "release_handoff_plan_ref": (
                        "plan_release_handoff_boundary.release_handoff_plan_ref"
                    ),
                    "verification_plan_ref": "plan_release_verification.release_verification_plan_ref",
                    "interrogation_plan_ref": "plan_release_interrogation.release_interrogation_plan_ref",
                },
                output_keys=("release_refinement_plan_ref", "gap_closure_order", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_release_memory_admission",
                name="Plan release memory admission",
                action_type="agentic_control.memory_admission.plan",
                depends_on=("refine_release_gaps",),
                input_bindings={"refinement_plan_ref": "refine_release_gaps.release_refinement_plan_ref"},
                output_keys=("memory_admission_plan_ref", "redaction_plan_ref", "forget_path_ref"),
                provider_class_required="agentic_control_plane",
            ),
        ),
        provider_requirements=("agentic_control_plane",),
        description=(
            "Composes read-only release governance by linking release boundary, "
            "constraint ranking, governance gate, resource budget, release-handoff "
            "planning, CI gates, rollback path, verification, interrogation, "
            "refinement, and memory-admission planning before evidence ledger "
            "closure or write-capable release actions."
        ),
        confidence=0.25,
        metadata={
            **_NO_NEW_AUTHORITY,
            "risk_floor": "medium",
            "release_governor": True,
            "release_surfaces": (
                "release_boundary_ref",
                "release_handoff_plan_ref",
                "commit_boundary",
                "ci_gate_plan",
                "rollback_path",
            ),
        },
    )


def _agentic_control_autonomous_operations_skill() -> SkillDescriptor:
    skill_id = "agentic_control.autonomous_operations.v1"
    return SkillDescriptor(
        skill_id=skill_id,
        name="Agentic control autonomous operations",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_WRITE,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=_policy_and_capability_preconditions(domain="agentic_control"),
        postconditions=_verification_postcondition(skill_id=skill_id),
        steps=(
            SkillStep(
                step_id="define_mission",
                name="Define bounded mission",
                action_type="agentic_control.mission.define",
                output_keys=("mission_contract_ref", "mission_contract_hash", "halt_conditions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="rank_work",
                name="Rank autonomous work",
                action_type="agentic_control.priority.rank",
                depends_on=("define_mission",),
                input_bindings={"mission_contract_ref": "define_mission.mission_contract_ref"},
                output_keys=("priority_order_ref", "dependency_blockers", "risk_weights"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="evaluate_governance_gate",
                name="Evaluate governance gate",
                action_type="agentic_control.governance_gate.evaluate",
                depends_on=("rank_work",),
                input_bindings={"priority_order_ref": "rank_work.priority_order_ref"},
                output_keys=("gate_decision_ref", "proof_state", "blocked_actions"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="bound_resource_budget",
                name="Bound resource budget",
                action_type="agentic_control.resource_budget.bound",
                depends_on=("evaluate_governance_gate",),
                input_bindings={"gate_decision_ref": "evaluate_governance_gate.gate_decision_ref"},
                output_keys=("budget_envelope_ref", "halt_thresholds", "resource_floor"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="analyze_math_algorithm",
                name="Analyze math and algorithm",
                action_type="agentic_control.math_algorithm.analyze",
                depends_on=("bound_resource_budget",),
                input_bindings={"budget_envelope_ref": "bound_resource_budget.budget_envelope_ref"},
                output_keys=("algorithm_analysis_ref", "complexity_bound", "failure_modes"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="build_threat_model",
                name="Build security threat model",
                action_type="agentic_control.security_threat_model.build",
                depends_on=("analyze_math_algorithm",),
                input_bindings={"algorithm_analysis_ref": "analyze_math_algorithm.algorithm_analysis_ref"},
                output_keys=("threat_model_ref", "mitigation_refs", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="coordinate_swarm",
                name="Coordinate agent swarm",
                action_type="agentic_control.swarm.coordinate",
                depends_on=("build_threat_model",),
                input_bindings={"threat_model_ref": "build_threat_model.threat_model_ref"},
                output_keys=("swarm_plan_ref", "role_assignment_hash", "consensus_rule"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_product_management",
                name="Plan product management",
                action_type="agentic_control.product_management.plan",
                depends_on=("coordinate_swarm",),
                input_bindings={"swarm_plan_ref": "coordinate_swarm.swarm_plan_ref"},
                output_keys=("product_plan_ref", "success_metrics", "handoff_risks"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_verification",
                name="Plan verification gates",
                action_type="agentic_control.verification.plan",
                depends_on=("plan_product_management",),
                input_bindings={"product_plan_ref": "plan_product_management.product_plan_ref"},
                output_keys=("verification_plan_ref", "required_gates", "closure_rule"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_interrogation",
                name="Plan evidence interrogation",
                action_type="agentic_control.interrogation.plan",
                depends_on=("plan_verification",),
                input_bindings={"verification_plan_ref": "plan_verification.verification_plan_ref"},
                output_keys=("interrogation_plan_ref", "unknowns", "evidence_requests"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="refine_weakness_gaps",
                name="Refine weakness and gaps",
                action_type="agentic_control.self_audit.refine",
                depends_on=("plan_interrogation",),
                input_bindings={
                    "verification_plan_ref": "plan_verification.verification_plan_ref",
                    "interrogation_plan_ref": "plan_interrogation.interrogation_plan_ref",
                },
                output_keys=("refinement_plan_ref", "gap_closure_order", "residual_risk"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_memory_admission",
                name="Plan memory admission",
                action_type="agentic_control.memory_admission.plan",
                depends_on=("refine_weakness_gaps",),
                input_bindings={"refinement_plan_ref": "refine_weakness_gaps.refinement_plan_ref"},
                output_keys=("memory_admission_plan_ref", "redaction_plan_ref", "forget_path_ref"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_incident_recovery",
                name="Plan incident recovery",
                action_type="agentic_control.incident_recovery.plan",
                depends_on=("refine_weakness_gaps", "plan_memory_admission"),
                input_bindings={
                    "refinement_plan_ref": "refine_weakness_gaps.refinement_plan_ref",
                    "memory_admission_plan_ref": "plan_memory_admission.memory_admission_plan_ref",
                },
                output_keys=("incident_recovery_plan_ref", "containment_actions", "verification_steps"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_telemetry_triage",
                name="Plan telemetry triage",
                action_type="agentic_control.telemetry_triage.plan",
                depends_on=("plan_verification", "refine_weakness_gaps", "plan_incident_recovery"),
                input_bindings={
                    "verification_plan_ref": "plan_verification.verification_plan_ref",
                    "refinement_plan_ref": "refine_weakness_gaps.refinement_plan_ref",
                    "incident_recovery_plan_ref": "plan_incident_recovery.incident_recovery_plan_ref",
                },
                output_keys=(
                    "telemetry_triage_plan_ref",
                    "monitored_surfaces",
                    "threshold_contracts",
                    "remediation_order",
                ),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_code_change",
                name="Plan code change boundary",
                action_type="agentic_control.code_change.plan",
                depends_on=("plan_verification", "plan_telemetry_triage"),
                input_bindings={
                    "verification_plan_ref": "plan_verification.verification_plan_ref",
                    "telemetry_triage_plan_ref": "plan_telemetry_triage.telemetry_triage_plan_ref",
                },
                output_keys=("code_change_plan_ref", "change_boundary", "test_contract", "rollback_plan"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="plan_release_handoff",
                name="Plan release handoff",
                action_type="agentic_control.release_handoff.plan",
                depends_on=("plan_code_change",),
                input_bindings={"code_change_plan_ref": "plan_code_change.code_change_plan_ref"},
                output_keys=("release_handoff_plan_ref", "commit_boundary", "ci_gate_plan", "rollback_path"),
                provider_class_required="agentic_control_plane",
            ),
            SkillStep(
                step_id="append_evidence",
                name="Append evidence ledger",
                action_type="agentic_control.evidence.append",
                depends_on=("plan_release_handoff",),
                input_bindings={
                    "verification_plan_ref": "plan_verification.verification_plan_ref",
                    "interrogation_plan_ref": "plan_interrogation.interrogation_plan_ref",
                    "refinement_plan_ref": "refine_weakness_gaps.refinement_plan_ref",
                    "memory_admission_plan_ref": "plan_memory_admission.memory_admission_plan_ref",
                    "incident_recovery_plan_ref": "plan_incident_recovery.incident_recovery_plan_ref",
                    "telemetry_triage_plan_ref": "plan_telemetry_triage.telemetry_triage_plan_ref",
                    "code_change_plan_ref": "plan_code_change.code_change_plan_ref",
                    "release_handoff_plan_ref": "plan_release_handoff.release_handoff_plan_ref",
                },
                output_keys=("ledger_record_id", "ledger_record_hash", "lineage_ref"),
                provider_class_required="agentic_control_plane",
            ),
        ),
        provider_requirements=("agentic_control_plane",),
        description=(
            "Composes mission control, prioritization, governance gating, resource "
            "bounds, algorithm review, threat modeling, swarm coordination, product "
            "planning, verification planning, evidence interrogation, weakness "
            "refinement, memory-admission planning, incident-recovery planning, "
            "telemetry-triage planning, code-change planning, release-handoff "
            "planning, and evidence ledger closure."
        ),
        confidence=0.25,
        metadata={**_NO_NEW_AUTHORITY, "risk_floor": "high", "approval_expected": True},
    )
