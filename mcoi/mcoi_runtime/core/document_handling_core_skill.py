"""Purpose: Mullu Govern document-handling core skill descriptor.

Governance scope: document intake, graph extraction, patch planning, validated
artifact transformation, privacy gates, and audit packet closure.
Dependencies: skill contracts only; provider execution remains outside this
candidate descriptor.
Invariants:
  - Source document bytes are immutable and hash-bound before analysis.
  - Document text is untrusted data unless policy promotes it to instruction.
  - Every mutation is represented as a patch with preconditions and postconditions.
  - Fixed-layout, OOXML, markup, plain text, and OCR paths remain mechanism-specific.
  - Privacy, metadata, redaction, and render validation gates fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass

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

DOCUMENT_HANDLING_CORE_SKILL_ID = "document.handling_core.v1"
DOCUMENT_HANDLING_CORE_PROVIDER = "document_worker"
DOCUMENT_HANDLING_CORE_CATALOG_VERSION = "document-handling-core.v1"
DOCUMENT_SYMBOLIC_STATE = "S_doc := <I_doc, L_doc, Sigma_doc, Gamma_doc, H_doc>"
DOCUMENT_STATE_JUDGMENT = "Sigma_doc satisfies L_doc over I_doc"

DOCUMENT_LAYERS = (
    "byte",
    "format",
    "structural",
    "layout",
    "semantic",
    "governance",
    "causal",
)

DOCUMENT_CORE_INVARIANTS = (
    "preserve_original_source_bytes_by_hash",
    "separate_observation_from_inference",
    "separate_semantic_edit_from_layout_edit",
    "represent_every_mutation_as_validated_patch",
    "gate_risky_output_through_privacy_and_exposure_policy",
    "perform_destructive_redaction_not_visual_overlay",
    "render_verify_layout_sensitive_outputs",
    "record_typed_failures_without_silent_recovery",
    "route_format_specific_mechanisms_behind_common_interface",
    "treat_document_text_as_untrusted_until_policy_promotes_it",
)

DOCUMENT_MECHANISM_LADDER = (
    "raw_text_spans",
    "markup_ast",
    "office_open_xml_package",
    "fixed_layout_pdf",
    "scanned_image_ocr",
    "multimodal_layout_graph",
    "corpus_knowledge_graph",
    "governed_agentic_editing",
)

DOCUMENT_OPERATION_SURFACES = (
    "analyze_document",
    "extract_document_graph",
    "edit_document",
    "redact_document",
    "convert_document",
    "compare_documents",
    "synthesize_documents",
    "audit_document",
)

DOCUMENT_VALIDATION_GATES = (
    "input_validity",
    "extraction_validity",
    "target_resolution_validity",
    "patch_validity",
    "semantic_validity",
    "layout_validity",
    "privacy_validity",
    "audit_history_validity",
)

DOCUMENT_FAILURE_MODES = (
    "unsupported_format",
    "ambiguous_target",
    "extraction_coverage_gap",
    "ocr_low_confidence",
    "schema_or_relationship_breakage",
    "layout_clipping_or_overlap",
    "recoverable_redacted_content",
    "metadata_or_hidden_text_leakage",
    "semantic_contradiction_introduced",
    "missing_audit_event",
)

DOCUMENT_FORMAT_MECHANISMS = (
    "txt_line_map_patch",
    "markdown_ast_patch",
    "html_dom_patch",
    "docx_ooxml_patch",
    "pdf_coordinate_patch_or_redaction",
    "image_ocr_coordinate_overlay",
    "corpus_claim_alignment",
)

PROHIBITED_ACTION_TYPES = (
    "agentic_control.code_change.plan",
    "agentic_control.release_handoff.plan",
    "agentic_control.evidence.append",
    "software_dev.change.run",
)


@dataclass(frozen=True)
class DocumentHandlingCoreContract:
    """Machine-readable contract surfaces for the document core skill."""

    symbolic_state: str
    state_judgment: str
    layers: tuple[str, ...]
    invariants: tuple[str, ...]
    mechanism_ladder: tuple[str, ...]
    operation_surfaces: tuple[str, ...]
    validation_gates: tuple[str, ...]
    failure_modes: tuple[str, ...]
    format_mechanisms: tuple[str, ...]


DOCUMENT_HANDLING_CORE_CONTRACT = DocumentHandlingCoreContract(
    symbolic_state=DOCUMENT_SYMBOLIC_STATE,
    state_judgment=DOCUMENT_STATE_JUDGMENT,
    layers=DOCUMENT_LAYERS,
    invariants=DOCUMENT_CORE_INVARIANTS,
    mechanism_ladder=DOCUMENT_MECHANISM_LADDER,
    operation_surfaces=DOCUMENT_OPERATION_SURFACES,
    validation_gates=DOCUMENT_VALIDATION_GATES,
    failure_modes=DOCUMENT_FAILURE_MODES,
    format_mechanisms=DOCUMENT_FORMAT_MECHANISMS,
)


def document_handling_core_skill_descriptor() -> SkillDescriptor:
    """Return the approval-gated candidate descriptor for holistic document work."""

    skill_id = DOCUMENT_HANDLING_CORE_SKILL_ID
    return SkillDescriptor(
        skill_id=skill_id,
        name="Document handling core",
        skill_class=SkillClass.COMPOSITE,
        effect_class=EffectClass.EXTERNAL_WRITE,
        determinism_class=DeterminismClass.INPUT_BOUNDED,
        trust_class=TrustClass.TRUSTED_INTERNAL,
        verification_strength=VerificationStrength.MANDATORY,
        lifecycle=SkillLifecycle.CANDIDATE,
        preconditions=(
            SkillPrecondition(
                condition_id="document.core.policy_allows",
                condition_type=PreconditionType.POLICY_ALLOWS,
                description=(
                    "document workflow policy permits governed handling-core selection"
                ),
            ),
            SkillPrecondition(
                condition_id="document.core.capability_available",
                condition_type=PreconditionType.CAPABILITY_AVAILABLE,
                description=(
                    "document worker capability family is admitted in the governed registry"
                ),
            ),
            SkillPrecondition(
                condition_id="document.core.source_immutable",
                condition_type=PreconditionType.STATE_CHECK,
                description=(
                    "source bytes and source hash are present before extraction or mutation"
                ),
            ),
            SkillPrecondition(
                condition_id="document.core.write_approval_expected",
                condition_type=PreconditionType.POLICY_ALLOWS,
                description=(
                    "write-capable edit, redaction, conversion, or publication requires "
                    "explicit approval"
                ),
            ),
        ),
        postconditions=(
            SkillPostcondition(
                condition_id="document.handling_core.v1.source_hash_preserved",
                condition_type=PostconditionType.FILE_EXISTS,
                description=(
                    "terminal receipt carries the original source hash and derived "
                    "artifact hash"
                ),
            ),
            SkillPostcondition(
                condition_id="document.handling_core.v1.validation_passed",
                condition_type=PostconditionType.VERIFICATION_PASSED,
                description=(
                    "all required extraction, patch, layout, privacy, and audit gates "
                    "have explicit results"
                ),
            ),
            SkillPostcondition(
                condition_id="document.handling_core.v1.audit_history_recorded",
                condition_type=PostconditionType.FILE_EXISTS,
                description=(
                    "causal history records ingest, inference, patch, validation, and "
                    "exposure decisions"
                ),
            ),
        ),
        steps=(
            SkillStep(
                step_id="preserve_source",
                name="Preserve immutable source",
                action_type="document.bytes.preserve",
                output_keys=("source_ref", "source_hash", "observed_size"),
                provider_class_required=DOCUMENT_HANDLING_CORE_PROVIDER,
            ),
            SkillStep(
                step_id="detect_format",
                name="Detect declared and observed format",
                action_type="document.format.detect",
                depends_on=("preserve_source",),
                input_bindings={"source_ref": "preserve_source.source_ref"},
                output_keys=("declared_type", "observed_type", "container_profile"),
                provider_class_required=DOCUMENT_HANDLING_CORE_PROVIDER,
            ),
            SkillStep(
                step_id="extract_graph",
                name="Extract canonical document graph",
                action_type="document.graph.extract",
                depends_on=("detect_format",),
                input_bindings={
                    "source_ref": "preserve_source.source_ref",
                    "observed_type": "detect_format.observed_type",
                },
                output_keys=(
                    "document_graph_ref",
                    "extraction_coverage",
                    "extractor_warnings",
                ),
                provider_class_required=DOCUMENT_HANDLING_CORE_PROVIDER,
            ),
            SkillStep(
                step_id="analyze_governance",
                name="Analyze structure semantics and governance risk",
                action_type="document.governance.analyze",
                depends_on=("extract_graph",),
                input_bindings={"document_graph_ref": "extract_graph.document_graph_ref"},
                output_keys=("analysis_ref", "risk_register_ref", "exposure_policy_ref"),
                provider_class_required=DOCUMENT_HANDLING_CORE_PROVIDER,
            ),
            SkillStep(
                step_id="plan_patch_set",
                name="Plan reversible document patches",
                action_type="document.patch.plan",
                depends_on=("analyze_governance",),
                input_bindings={
                    "document_graph_ref": "extract_graph.document_graph_ref",
                    "risk_register_ref": "analyze_governance.risk_register_ref",
                },
                output_keys=(
                    "patch_plan_ref",
                    "target_resolution_report",
                    "rollback_plan_ref",
                ),
                provider_class_required=DOCUMENT_HANDLING_CORE_PROVIDER,
            ),
            SkillStep(
                step_id="apply_approved_patch",
                name="Apply approved patch set",
                action_type="document.patch.apply.with_approval",
                depends_on=("plan_patch_set",),
                input_bindings={
                    "source_ref": "preserve_source.source_ref",
                    "patch_plan_ref": "plan_patch_set.patch_plan_ref",
                    "rollback_plan_ref": "plan_patch_set.rollback_plan_ref",
                },
                output_keys=("artifact_ref", "artifact_hash", "change_diff_ref"),
                provider_class_required=DOCUMENT_HANDLING_CORE_PROVIDER,
            ),
            SkillStep(
                step_id="validate_artifact",
                name="Validate structure layout privacy and audit closure",
                action_type="document.validation.gate_all",
                depends_on=("apply_approved_patch",),
                input_bindings={
                    "artifact_ref": "apply_approved_patch.artifact_ref",
                    "exposure_policy_ref": "analyze_governance.exposure_policy_ref",
                },
                output_keys=(
                    "validation_report_ref",
                    "privacy_report_ref",
                    "render_report_ref",
                ),
                provider_class_required=DOCUMENT_HANDLING_CORE_PROVIDER,
            ),
            SkillStep(
                step_id="publish_audit_packet",
                name="Publish governed document handling audit packet",
                action_type="document.audit_packet.publish.with_approval",
                depends_on=("validate_artifact",),
                input_bindings={
                    "artifact_hash": "apply_approved_patch.artifact_hash",
                    "validation_report_ref": "validate_artifact.validation_report_ref",
                    "privacy_report_ref": "validate_artifact.privacy_report_ref",
                },
                output_keys=("audit_packet_ref", "terminal_receipt_ref"),
                provider_class_required=DOCUMENT_HANDLING_CORE_PROVIDER,
            ),
        ),
        provider_requirements=(DOCUMENT_HANDLING_CORE_PROVIDER,),
        description=(
            "Preserves source bytes, extracts a canonical document graph, analyzes "
            "structure/semantics/governance risk, plans validated patches, applies "
            "approved transformations, and closes with privacy, render, and audit "
            "evidence."
        ),
        confidence=0.25,
        metadata={
            "catalog_version": DOCUMENT_HANDLING_CORE_CATALOG_VERSION,
            "grants_new_capability_authority": False,
            "approval_expected": True,
            "risk_floor": "high",
            "core_skill": True,
            "symbolic_state": DOCUMENT_SYMBOLIC_STATE,
            "state_judgment": DOCUMENT_STATE_JUDGMENT,
            "document_layers": DOCUMENT_LAYERS,
            "mechanism_ladder": DOCUMENT_MECHANISM_LADDER,
            "validation_gates": DOCUMENT_VALIDATION_GATES,
            "operation_surfaces": DOCUMENT_OPERATION_SURFACES,
            "failure_modes": DOCUMENT_FAILURE_MODES,
        },
    )


def validate_document_handling_core_descriptor(
    descriptor: SkillDescriptor | None = None,
) -> None:
    """Fail closed if the descriptor drifts beyond the governed contract."""

    candidate = descriptor or document_handling_core_skill_descriptor()
    if candidate.skill_id != DOCUMENT_HANDLING_CORE_SKILL_ID:
        msg = "document handling core skill id drift"
        raise ValueError(msg)
    if candidate.lifecycle is not SkillLifecycle.CANDIDATE:
        msg = "document handling core must remain candidate lifecycle"
        raise ValueError(msg)
    if candidate.effect_class is not EffectClass.EXTERNAL_WRITE:
        msg = "document handling core strongest effect must remain external write"
        raise ValueError(msg)
    if candidate.metadata.get("approval_expected") is not True:
        msg = "document handling core write path must require approval"
        raise ValueError(msg)
    if candidate.metadata.get("grants_new_capability_authority") is not False:
        msg = "document handling core must not grant new capability authority"
        raise ValueError(msg)
    if tuple(candidate.provider_requirements) != (DOCUMENT_HANDLING_CORE_PROVIDER,):
        msg = "document handling core provider boundary drift"
        raise ValueError(msg)

    step_ids = tuple(step.step_id for step in candidate.steps)
    for step in candidate.steps:
        if step.action_type in PROHIBITED_ACTION_TYPES:
            msg = (
                "document handling core contains prohibited action type: "
                f"{step.action_type}"
            )
            raise ValueError(msg)
        if step.provider_class_required not in candidate.provider_requirements:
            msg = f"step provider not admitted by descriptor: {step.step_id}"
            raise ValueError(msg)
        for dependency in step.depends_on:
            if dependency not in step_ids:
                msg = f"missing dependency {dependency} for step {step.step_id}"
                raise ValueError(msg)
            if step_ids.index(dependency) >= step_ids.index(step.step_id):
                msg = f"dependency order violation for step {step.step_id}"
                raise ValueError(msg)

    missing_gates = set(DOCUMENT_VALIDATION_GATES) - set(
        candidate.metadata["validation_gates"]
    )
    if missing_gates:
        msg = "document handling core validation gate coverage drift"
        raise ValueError(msg)
