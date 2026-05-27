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
}
_CAPABILITY_PRECONDITION_DESCRIPTIONS = {
    "financial": "financial capability family is admitted in the governed registry",
    "document": "document capability family is admitted in the governed registry",
    "software_dev": "software_dev capability family is admitted in the governed registry",
    "deployment": "deployment capability family is admitted in the governed registry",
    "browser": "browser, document, and voice capability families are admitted in the governed registry",
    "enterprise": "enterprise and creative capability families are admitted in the governed registry",
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
