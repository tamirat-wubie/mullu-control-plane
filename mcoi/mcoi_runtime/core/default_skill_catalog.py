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
