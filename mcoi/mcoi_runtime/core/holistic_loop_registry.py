"""Purpose: default registry and bounded read model for governed loop contracts.
Governance scope: non-invasive description of existing Mullu loop surfaces.
Dependencies: holistic loop contracts and shared contract freezing helpers.
Invariants:
  - Registry construction does not import or execute runtime loop behavior.
  - The first registered loops are descriptive read models only.
  - Missing evidence is converted to explicit blockers.
  - Read-model limits are bounded and deterministic.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from mcoi_runtime.contracts._base import freeze_value, require_datetime_text
from mcoi_runtime.contracts.holistic_loop import (
    LoopAuthorityBinding,
    LoopClosureConditionBinding,
    LoopClosureReport,
    LoopEvidenceBinding,
    LoopLearningBinding,
    LoopManifest,
    LoopMode,
    LoopModeBinding,
    LoopPhase,
    LoopReadModel,
    LoopRiskBinding,
    LoopRollbackBinding,
    LoopState,
    LoopStatus,
    LoopStepReceipt,
    LoopSummary,
)


DEFAULT_READ_MODEL_LIMIT = 20
DEFAULT_LOOP_UPDATED_AT = "2026-06-08T00:00:00+00:00"


@dataclass(frozen=True, slots=True)
class LoopRegistry:
    """Immutable registry of loop manifests and current read-only states."""

    manifests: Mapping[str, LoopManifest]
    states: Mapping[str, LoopState] = field(default_factory=dict)

    def __post_init__(self) -> None:
        manifests = dict(self.manifests)
        states = dict(self.states)
        if not manifests:
            raise ValueError("manifests must not be empty")
        for loop_id, manifest in manifests.items():
            if loop_id != manifest.loop_id:
                raise ValueError("manifest key must match loop_id")
        for loop_id, state in states.items():
            if loop_id not in manifests:
                raise ValueError("state must reference a registered loop")
            if state.mode not in manifests[loop_id].allowed_modes:
                raise ValueError("state mode must be allowed by manifest")
            if state.current_step not in manifests[loop_id].canonical_steps:
                raise ValueError("state step must be allowed by manifest")
        object.__setattr__(self, "manifests", freeze_value(manifests))
        object.__setattr__(self, "states", freeze_value(states))

    def list_manifests(self) -> tuple[LoopManifest, ...]:
        """Return registered manifests in deterministic order."""

        return tuple(self.manifests[loop_id] for loop_id in sorted(self.manifests))

    def get_manifest(self, loop_id: str) -> LoopManifest:
        """Return one registered manifest or raise a causal error."""

        try:
            return self.manifests[loop_id]
        except KeyError as exc:
            raise ValueError(f"loop not registered: {loop_id}") from exc

    def get_state(self, loop_id: str) -> LoopState:
        """Return one loop state, synthesizing the default open state if absent."""

        manifest = self.get_manifest(loop_id)
        state = self.states.get(loop_id)
        if state is not None:
            return state
        return _default_open_state(manifest.loop_id, DEFAULT_LOOP_UPDATED_AT)

    def summarize(self, loop_id: str) -> LoopSummary:
        """Return a blocker-aware read-model summary for one loop."""

        manifest = self.get_manifest(loop_id)
        state = self.get_state(loop_id)
        return _summarize_manifest_state(manifest, state)

    def build_read_model(
        self,
        *,
        generated_at: str = DEFAULT_LOOP_UPDATED_AT,
        limit: int = DEFAULT_READ_MODEL_LIMIT,
    ) -> LoopReadModel:
        """Return a bounded read model over registered loops."""

        require_datetime_text(generated_at, "generated_at")
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise ValueError("limit must be a positive integer")
        loop_ids = sorted(self.manifests)
        selected_ids = loop_ids[:limit]
        loops = tuple(self.summarize(loop_id) for loop_id in selected_ids)
        return LoopReadModel(
            generated_at=generated_at,
            loops=loops,
            total_count=len(loop_ids),
            returned_count=len(loops),
            truncated=len(loops) < len(loop_ids),
        )


def build_default_loop_registry(
    *,
    observed_authority_refs: Mapping[str, Sequence[str]] | None = None,
    observed_evidence_refs: Mapping[str, Sequence[str]] | None = None,
    updated_at: str = DEFAULT_LOOP_UPDATED_AT,
) -> LoopRegistry:
    """Build the default read-only registry for existing governed loops."""

    require_datetime_text(updated_at, "updated_at")
    manifests = _default_manifests()
    authority_by_loop = observed_authority_refs or {}
    evidence_by_loop = observed_evidence_refs or {}
    states = {
        loop_id: _default_open_state(
            loop_id,
            updated_at,
            authority_refs=tuple(authority_by_loop.get(loop_id, ())),
            evidence_refs=tuple(evidence_by_loop.get(loop_id, ())),
        )
        for loop_id in manifests
    }
    return LoopRegistry(manifests=manifests, states=states)


def build_default_loop_read_model(
    *,
    observed_authority_refs: Mapping[str, Sequence[str]] | None = None,
    observed_evidence_refs: Mapping[str, Sequence[str]] | None = None,
    generated_at: str = DEFAULT_LOOP_UPDATED_AT,
    limit: int = DEFAULT_READ_MODEL_LIMIT,
) -> LoopReadModel:
    """Build the bounded default read model for existing governed loops."""

    registry = build_default_loop_registry(
        observed_authority_refs=observed_authority_refs,
        observed_evidence_refs=observed_evidence_refs,
        updated_at=generated_at,
    )
    return registry.build_read_model(generated_at=generated_at, limit=limit)


def _default_manifests() -> dict[str, LoopManifest]:
    return {
        manifest.loop_id: manifest
        for manifest in (
            LoopManifest(
                loop_id="deployment_witness_loop",
                name="Deployment Witness Loop",
                purpose=(
                    "Describe endpoint publication, runtime witness, conformance, "
                    "audit, proof, and authority evidence needed for deployment closure."
                ),
                owner="platform_governance",
                risk_class="release_publication",
                allowed_modes=(
                    LoopMode.DRY_RUN,
                    LoopMode.SHADOW,
                    LoopMode.SIMULATION,
                    LoopMode.REPLAY,
                    LoopMode.REAL,
                ),
                required_authority=(
                    "operator_approval_ref",
                    "deployment_publication_authority",
                ),
                required_evidence=(
                    "deployment_witness_published",
                    "runtime_witness_valid",
                    "runtime_conformance_verified",
                    "audit_anchor_verified",
                    "proof_verification_passed",
                    "authority_obligations_clear",
                    "public_endpoint_declared",
                ),
                closure_conditions=(
                    "deployment_witness_state_published",
                    "runtime_responsibility_debt_clear",
                    "authority_responsibility_debt_clear",
                    "public_health_endpoint_matches_declared_gateway",
                    "proof_and_audit_verification_pass",
                ),
                rollback_policy="revert_publication_status_and_restore_last_verified_witness",
                learning_policy="promote deployment blockers into release preflight checks",
                metadata={
                    "existing_surfaces": (
                        "scripts/collect_deployment_witness.py",
                        "scripts/preflight_deployment_witness.py",
                    ),
                    "behavior_rewrite": False,
                },
            ),
            LoopManifest(
                loop_id="runtime_conformance_loop",
                name="Runtime Conformance Loop",
                purpose=(
                    "Describe signed runtime conformance collection and certificate "
                    "validation without changing the conformance endpoint."
                ),
                owner="runtime_governance",
                risk_class="runtime_attestation",
                allowed_modes=(LoopMode.DRY_RUN, LoopMode.SHADOW, LoopMode.REPLAY, LoopMode.REAL),
                required_authority=(
                    "runtime_conformance_issuer",
                    "conformance_secret_handoff_ref",
                ),
                required_evidence=(
                    "certificate_schema_valid",
                    "certificate_signature_verified",
                    "core_canaries_passed",
                    "authority_directory_sync_valid",
                    "proof_coverage_matrix_current",
                    "open_conformance_gaps_bounded",
                ),
                closure_conditions=(
                    "accepted_conformance_status",
                    "gateway_witness_valid",
                    "runtime_witness_valid",
                    "core_canary_set_passed",
                    "known_limitations_and_security_model_aligned",
                ),
                rollback_policy="invalidate_conformance_claim_and_retain_failed_collection",
                learning_policy="convert failed conformance checks into explicit canaries or docs gaps",
                metadata={
                    "existing_surfaces": (
                        "scripts/collect_runtime_conformance.py",
                        "schemas/runtime_conformance_certificate.schema.json",
                    ),
                    "behavior_rewrite": False,
                },
            ),
            LoopManifest(
                loop_id="cognitive_outcome_loop",
                name="Cognitive Outcome Loop",
                purpose=(
                    "Describe observe, decide, act, verify, learn, and audit evidence "
                    "for the bounded cognitive loop and outcome ledger."
                ),
                owner="cognitive_governance",
                risk_class="learning_admission",
                allowed_modes=(LoopMode.DRY_RUN, LoopMode.SHADOW, LoopMode.SIMULATION, LoopMode.REPLAY),
                required_authority=(
                    "governed_dispatch_policy_decision",
                    "learning_admission_decision",
                ),
                required_evidence=(
                    "governed_dispatch_trace",
                    "mechanical_verification_result",
                    "critic_verdict_or_null_critic",
                    "learning_admission_recorded",
                    "episodic_outcome_anchor",
                ),
                closure_conditions=(
                    "hard_constraints_proven_or_blocked",
                    "mechanical_verification_completed",
                    "critic_did_not_upgrade_failed_proof",
                    "learning_admitted_only_from_verified_evidence",
                ),
                rollback_policy="defer_or_reject_learning_admission_without_memory_promotion",
                learning_policy="admit only verified outcomes into episodic memory",
                metadata={
                    "existing_surfaces": (
                        "mcoi_runtime/core/cognitive_loop.py",
                        "docs/design/COGNITIVE_OUTCOME_LEDGER.md",
                    ),
                    "behavior_rewrite": False,
                },
            ),
            LoopManifest(
                loop_id="governed_code_change_loop",
                name="Governed Code-Change Loop",
                purpose=(
                    "Describe lease-bound code-worker execution, SDLC receipt "
                    "requirements, rollback handoff, and terminal closure blockers."
                ),
                owner="sdlc_governance",
                risk_class="repository_mutation",
                allowed_modes=(LoopMode.DRY_RUN, LoopMode.SIMULATION, LoopMode.REPLAY),
                required_authority=(
                    "uao_ref",
                    "code_worker_lease",
                    "sdlc_closure_authority",
                ),
                required_evidence=(
                    "code_worker_receipt",
                    "implementation_receipt",
                    "verification_receipt",
                    "recovery_handoff",
                ),
                closure_conditions=(
                    "worker_receipt_not_terminal_closure",
                    "implementation_receipt_present",
                    "verification_receipt_present",
                    "recovery_handoff_present",
                    "closure_blockers_empty",
                ),
                rollback_policy="restore_workspace_snapshot_or_open_recovery_handoff",
                learning_policy="promote failure diagnosis into tests or SDLC gate evidence",
                metadata={
                    "existing_surfaces": (
                        "mcoi_runtime/core/governed_code_change_loop.py",
                        "tests/test_governed_code_change_loop.py",
                    ),
                    "behavior_rewrite": False,
                },
            ),
        )
    }


def _default_open_state(
    loop_id: str,
    updated_at: str,
    *,
    authority_refs: Sequence[str] = (),
    evidence_refs: Sequence[str] = (),
) -> LoopState:
    return LoopState(
        loop_id=loop_id,
        status=LoopStatus.OPEN,
        current_step=LoopPhase.OBSERVE,
        mode=LoopMode.DRY_RUN,
        authority_refs=tuple(authority_refs),
        evidence_refs=tuple(evidence_refs),
        updated_at=updated_at,
    )


def _summarize_manifest_state(manifest: LoopManifest, state: LoopState) -> LoopSummary:
    observed_authority = set(state.authority_refs)
    observed = set(state.evidence_refs)
    missing_authority = tuple(
        authority for authority in manifest.required_authority if authority not in observed_authority
    )
    authority_blockers = tuple(f"missing_authority:{authority}" for authority in missing_authority)
    missing = tuple(evidence for evidence in manifest.required_evidence if evidence not in observed)
    missing_blockers = tuple(f"missing_evidence:{evidence}" for evidence in missing)
    blockers = _stable_unique_tuple((*state.open_blockers, *authority_blockers, *missing_blockers))
    status = LoopStatus.BLOCKED if blockers else state.status
    if not blockers and status == LoopStatus.OPEN:
        status = LoopStatus.VERIFIED
    return LoopSummary(
        loop_id=manifest.loop_id,
        name=manifest.name,
        purpose=manifest.purpose,
        owner=manifest.owner,
        risk_class=manifest.risk_class,
        risk_binding=_risk_binding_for(manifest.loop_id),
        status=status,
        mode=state.mode,
        mode_binding=_mode_binding_for(manifest.loop_id, state.mode, manifest.allowed_modes),
        current_step=state.current_step,
        required_authority=manifest.required_authority,
        authority_bindings=_authority_bindings_for(manifest.loop_id),
        authority_refs=state.authority_refs,
        missing_authority=missing_authority,
        required_evidence=manifest.required_evidence,
        evidence_bindings=_evidence_bindings_for(manifest.loop_id),
        step_receipts=_step_receipts_for(manifest, state, blockers),
        evidence_refs=state.evidence_refs,
        missing_evidence=missing,
        closure_conditions=manifest.closure_conditions,
        closure_condition_bindings=_closure_condition_bindings_for(manifest.loop_id),
        closure_report=_closure_report_for(manifest, blockers, missing),
        open_blockers=blockers,
        rollback_policy=manifest.rollback_policy,
        rollback_binding=_rollback_binding_for(manifest.loop_id),
        learning_policy=manifest.learning_policy,
        learning_binding=_learning_binding_for(manifest.loop_id),
        updated_at=state.updated_at,
    )


def _step_receipts_for(
    manifest: LoopManifest,
    state: LoopState,
    blockers: Sequence[str],
) -> tuple[LoopStepReceipt, ...]:
    status = LoopStatus.BLOCKED if blockers else LoopStatus.VERIFIED
    receipts: list[LoopStepReceipt] = []
    for step in manifest.canonical_steps:
        decision = _step_decision(step, bool(blockers))
        receipts.append(
            LoopStepReceipt(
                loop_id=manifest.loop_id,
                step=step,
                input_hash=_receipt_hash(manifest.loop_id, step.value, "input"),
                output_hash=_receipt_hash(manifest.loop_id, step.value, "output"),
                decision=decision,
                evidence_refs=state.evidence_refs,
                status=status,
                errors=tuple(blockers),
                timestamp=state.updated_at,
                metadata={
                    "read_only": True,
                    "synthetic_projection": True,
                    "terminal_closure": False,
                    "behavior_rewrite": False,
                },
            )
        )
    return tuple(receipts)


def _step_decision(step: LoopPhase, blocked: bool) -> str:
    if blocked and step in {
        LoopPhase.VERIFY,
        LoopPhase.RECORD_RECEIPT,
        LoopPhase.UPDATE_STATE,
        LoopPhase.LEARN,
        LoopPhase.AUDIT,
    }:
        return "block_until_required_evidence_observed"
    if step is LoopPhase.ACT:
        return "project_existing_behavior_without_execution"
    return f"project_read_model_{step.value}"


def _receipt_hash(loop_id: str, step: str, boundary: str) -> str:
    digest = hashlib.sha256(f"{loop_id}:{step}:{boundary}:read_model_v1".encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _authority_bindings_for(loop_id: str) -> tuple[LoopAuthorityBinding, ...]:
    try:
        return _DEFAULT_AUTHORITY_BINDINGS[loop_id]
    except KeyError as exc:
        raise ValueError(f"loop authority catalog missing: {loop_id}") from exc


def _rollback_binding_for(loop_id: str) -> LoopRollbackBinding:
    try:
        return _DEFAULT_ROLLBACK_BINDINGS[loop_id]
    except KeyError as exc:
        raise ValueError(f"loop rollback catalog missing: {loop_id}") from exc


def _risk_binding_for(loop_id: str) -> LoopRiskBinding:
    try:
        return _DEFAULT_RISK_BINDINGS[loop_id]
    except KeyError as exc:
        raise ValueError(f"loop risk catalog missing: {loop_id}") from exc


def _learning_binding_for(loop_id: str) -> LoopLearningBinding:
    try:
        return _DEFAULT_LEARNING_BINDINGS[loop_id]
    except KeyError as exc:
        raise ValueError(f"loop learning catalog missing: {loop_id}") from exc


def _mode_binding_for(
    loop_id: str,
    projected_mode: LoopMode,
    allowed_modes: Sequence[LoopMode],
) -> LoopModeBinding:
    try:
        defaults = _DEFAULT_MODE_BINDINGS[loop_id]
    except KeyError as exc:
        raise ValueError(f"loop mode catalog missing: {loop_id}") from exc
    return LoopModeBinding(
        projected_mode=projected_mode,
        allowed_modes=tuple(allowed_modes),
        purpose=defaults.purpose,
        separation_refs=defaults.separation_refs,
        real_execution_guard_refs=defaults.real_execution_guard_refs,
        source_refs=defaults.source_refs,
        validator_refs=defaults.validator_refs,
        proof_surface_refs=defaults.proof_surface_refs,
    )


def _closure_condition_bindings_for(loop_id: str) -> tuple[LoopClosureConditionBinding, ...]:
    try:
        return _DEFAULT_CLOSURE_CONDITION_BINDINGS[loop_id]
    except KeyError as exc:
        raise ValueError(f"loop closure condition catalog missing: {loop_id}") from exc


def _closure_report_for(
    manifest: LoopManifest,
    blockers: Sequence[str],
    missing_evidence: Sequence[str],
) -> LoopClosureReport:
    evidence_complete = not missing_evidence
    closure_reason = (
        "read_model_verified_terminal_closure_required"
        if evidence_complete and not blockers
        else "read_model_blocked_by_unresolved_gaps"
    )
    learning_candidates = (manifest.learning_policy,) if blockers else ()
    return LoopClosureReport(
        loop_id=manifest.loop_id,
        closed=False,
        closure_reason=closure_reason,
        evidence_complete=evidence_complete,
        unresolved_gaps=tuple(blockers),
        rollback_available=bool(manifest.rollback_policy),
        learning_candidates=learning_candidates,
        metadata={
            "read_only": True,
            "terminal_closure": False,
            "closure_conditions": manifest.closure_conditions,
        },
    )


def _evidence_bindings_for(loop_id: str) -> tuple[LoopEvidenceBinding, ...]:
    try:
        return _DEFAULT_EVIDENCE_BINDINGS[loop_id]
    except KeyError as exc:
        raise ValueError(f"loop evidence catalog missing: {loop_id}") from exc


def _binding(
    evidence_ref: str,
    purpose: str,
    *,
    source_refs: Sequence[str],
    validator_refs: Sequence[str],
    proof_surface_refs: Sequence[str],
) -> LoopEvidenceBinding:
    return LoopEvidenceBinding(
        evidence_ref=evidence_ref,
        purpose=purpose,
        source_refs=tuple(source_refs),
        validator_refs=tuple(validator_refs),
        proof_surface_refs=tuple(proof_surface_refs),
    )


def _authority_binding(
    authority_ref: str,
    purpose: str,
    *,
    source_refs: Sequence[str],
    validator_refs: Sequence[str],
    proof_surface_refs: Sequence[str],
) -> LoopAuthorityBinding:
    return LoopAuthorityBinding(
        authority_ref=authority_ref,
        purpose=purpose,
        source_refs=tuple(source_refs),
        validator_refs=tuple(validator_refs),
        proof_surface_refs=tuple(proof_surface_refs),
    )


def _rollback_binding(
    rollback_ref: str,
    purpose: str,
    *,
    source_refs: Sequence[str],
    validator_refs: Sequence[str],
    proof_surface_refs: Sequence[str],
) -> LoopRollbackBinding:
    return LoopRollbackBinding(
        rollback_ref=rollback_ref,
        purpose=purpose,
        source_refs=tuple(source_refs),
        validator_refs=tuple(validator_refs),
        proof_surface_refs=tuple(proof_surface_refs),
    )


def _risk_binding(
    risk_ref: str,
    purpose: str,
    *,
    hazard_refs: Sequence[str],
    mitigation_refs: Sequence[str],
    monitor_refs: Sequence[str],
    source_refs: Sequence[str],
    validator_refs: Sequence[str],
    proof_surface_refs: Sequence[str],
) -> LoopRiskBinding:
    return LoopRiskBinding(
        risk_ref=risk_ref,
        purpose=purpose,
        hazard_refs=tuple(hazard_refs),
        mitigation_refs=tuple(mitigation_refs),
        monitor_refs=tuple(monitor_refs),
        source_refs=tuple(source_refs),
        validator_refs=tuple(validator_refs),
        proof_surface_refs=tuple(proof_surface_refs),
    )


def _learning_binding(
    learning_ref: str,
    purpose: str,
    *,
    evidence_input_refs: Sequence[str],
    admission_refs: Sequence[str],
    retention_refs: Sequence[str],
    source_refs: Sequence[str],
    validator_refs: Sequence[str],
    proof_surface_refs: Sequence[str],
) -> LoopLearningBinding:
    return LoopLearningBinding(
        learning_ref=learning_ref,
        purpose=purpose,
        evidence_input_refs=tuple(evidence_input_refs),
        admission_refs=tuple(admission_refs),
        retention_refs=tuple(retention_refs),
        source_refs=tuple(source_refs),
        validator_refs=tuple(validator_refs),
        proof_surface_refs=tuple(proof_surface_refs),
    )


def _mode_binding(
    purpose: str,
    *,
    separation_refs: Sequence[str],
    real_execution_guard_refs: Sequence[str],
    source_refs: Sequence[str],
    validator_refs: Sequence[str],
    proof_surface_refs: Sequence[str],
) -> LoopModeBinding:
    return LoopModeBinding(
        projected_mode=LoopMode.DRY_RUN,
        allowed_modes=(LoopMode.DRY_RUN,),
        purpose=purpose,
        separation_refs=tuple(separation_refs),
        real_execution_guard_refs=tuple(real_execution_guard_refs),
        source_refs=tuple(source_refs),
        validator_refs=tuple(validator_refs),
        proof_surface_refs=tuple(proof_surface_refs),
    )


def _closure_condition_binding(
    closure_ref: str,
    purpose: str,
    *,
    required_evidence_refs: Sequence[str],
    required_authority_refs: Sequence[str],
    source_refs: Sequence[str],
    validator_refs: Sequence[str],
    proof_surface_refs: Sequence[str],
) -> LoopClosureConditionBinding:
    return LoopClosureConditionBinding(
        closure_ref=closure_ref,
        purpose=purpose,
        required_evidence_refs=tuple(required_evidence_refs),
        required_authority_refs=tuple(required_authority_refs),
        source_refs=tuple(source_refs),
        validator_refs=tuple(validator_refs),
        proof_surface_refs=tuple(proof_surface_refs),
    )


_DEPLOYMENT_WITNESS_SOURCES = (
    "scripts/collect_deployment_witness.py",
    "schemas/deployment_witness.schema.json",
)
_DEPLOYMENT_WITNESS_VALIDATORS = (
    "tests/test_collect_deployment_witness.py",
    "tests/test_deployment_witness_schema.py",
)
_RUNTIME_CONFORMANCE_SOURCES = (
    "scripts/collect_runtime_conformance.py",
    "schemas/runtime_conformance_certificate.schema.json",
)
_RUNTIME_CONFORMANCE_VALIDATORS = (
    "tests/test_collect_runtime_conformance.py",
    "tests/test_gateway/test_conformance.py",
)
_COGNITIVE_OUTCOME_SOURCES = (
    "mcoi/mcoi_runtime/core/cognitive_loop.py",
    "mcoi/mcoi_runtime/persistence/cognitive_outcome_ledger.py",
    "schemas/learning_admission.schema.json",
)
_COGNITIVE_OUTCOME_VALIDATORS = (
    "mcoi/tests/test_cognitive_loop.py",
    "mcoi/tests/test_cognitive_outcome_ledger.py",
    "tests/test_cognitive_outcome_ledger_doc_status.py",
)
_GOVERNED_CODE_CHANGE_SOURCES = (
    "mcoi/mcoi_runtime/core/governed_code_change_loop.py",
    "scripts/run_governed_code_change_loop.py",
)
_GOVERNED_CODE_CHANGE_VALIDATORS = (
    "tests/test_governed_code_change_loop.py",
    "tests/test_validate_governed_code_change_loop_receipt.py",
)


_DEFAULT_CLOSURE_CONDITION_BINDINGS: Mapping[str, tuple[LoopClosureConditionBinding, ...]] = {
    "deployment_witness_loop": (
        _closure_condition_binding(
            "deployment_witness_state_published",
            "Require a published deployment witness before publication closure can be described.",
            required_evidence_refs=("deployment_witness_published",),
            required_authority_refs=("deployment_publication_authority",),
            source_refs=(
                "scripts/collect_deployment_witness.py",
                "scripts/preflight_deployment_witness.py",
            ),
            validator_refs=(
                "tests/test_collect_deployment_witness.py",
                "tests/test_preflight_deployment_witness.py",
            ),
            proof_surface_refs=("production_evidence_plane",),
        ),
        _closure_condition_binding(
            "runtime_responsibility_debt_clear",
            "Require runtime witness and conformance evidence before runtime debt is cleared.",
            required_evidence_refs=("runtime_witness_valid", "runtime_conformance_verified"),
            required_authority_refs=("deployment_publication_authority",),
            source_refs=("scripts/preflight_deployment_witness.py",),
            validator_refs=("tests/test_preflight_deployment_witness.py",),
            proof_surface_refs=("gateway_runtime_witness", "runtime_conformance_attestation"),
        ),
        _closure_condition_binding(
            "authority_responsibility_debt_clear",
            "Require operator and publication authority evidence before authority debt is cleared.",
            required_evidence_refs=("authority_obligations_clear",),
            required_authority_refs=("operator_approval_ref", "deployment_publication_authority"),
            source_refs=("scripts/emit_deployment_publication_operator_input_request.py",),
            validator_refs=("tests/test_emit_deployment_publication_operator_input_request.py",),
            proof_surface_refs=("authority_obligation_mesh",),
        ),
        _closure_condition_binding(
            "public_health_endpoint_matches_declared_gateway",
            "Require declared public endpoint evidence to match the publication witness.",
            required_evidence_refs=("public_endpoint_declared", "deployment_witness_published"),
            required_authority_refs=("deployment_publication_authority",),
            source_refs=("schemas/gateway_publication_readiness.schema.json",),
            validator_refs=("tests/test_plan_deployment_publication_closure.py",),
            proof_surface_refs=("production_evidence_plane", "gateway_runtime_witness"),
        ),
        _closure_condition_binding(
            "proof_and_audit_verification_pass",
            "Require proof verification and audit anchor evidence before closure can be considered.",
            required_evidence_refs=("audit_anchor_verified", "proof_verification_passed"),
            required_authority_refs=("operator_approval_ref",),
            source_refs=("scripts/validate_release_status.py",),
            validator_refs=("tests/test_validate_release_status.py",),
            proof_surface_refs=("audit_chain_api", "proof_route_gap_triage"),
        ),
    ),
    "runtime_conformance_loop": (
        _closure_condition_binding(
            "accepted_conformance_status",
            "Require schema, signature, and issuer evidence before conformance status is accepted.",
            required_evidence_refs=("certificate_schema_valid", "certificate_signature_verified"),
            required_authority_refs=("runtime_conformance_issuer",),
            source_refs=("scripts/collect_runtime_conformance.py",),
            validator_refs=("tests/test_collect_runtime_conformance.py",),
            proof_surface_refs=("runtime_conformance_attestation",),
        ),
        _closure_condition_binding(
            "gateway_witness_valid",
            "Require authority-directory and certificate evidence before gateway witness validity is described.",
            required_evidence_refs=("authority_directory_sync_valid", "certificate_signature_verified"),
            required_authority_refs=("conformance_secret_handoff_ref",),
            source_refs=("schemas/runtime_conformance_certificate.schema.json",),
            validator_refs=("tests/test_collect_runtime_conformance_cli.py",),
            proof_surface_refs=("runtime_conformance_attestation",),
        ),
        _closure_condition_binding(
            "runtime_witness_valid",
            "Require core canary and certificate evidence before runtime witness validity is described.",
            required_evidence_refs=("core_canaries_passed", "certificate_schema_valid"),
            required_authority_refs=("runtime_conformance_issuer",),
            source_refs=("scripts/collect_runtime_conformance.py",),
            validator_refs=("tests/test_gateway/test_conformance.py",),
            proof_surface_refs=("runtime_conformance_attestation", "gateway_runtime_witness"),
        ),
        _closure_condition_binding(
            "core_canary_set_passed",
            "Require the runtime canary set to pass before conformance closure can advance.",
            required_evidence_refs=("core_canaries_passed",),
            required_authority_refs=("runtime_conformance_issuer",),
            source_refs=("schemas/runtime_conformance_collection.schema.json",),
            validator_refs=("tests/test_collect_runtime_conformance.py",),
            proof_surface_refs=("runtime_conformance_attestation",),
        ),
        _closure_condition_binding(
            "known_limitations_and_security_model_aligned",
            "Require bounded conformance gaps and proof coverage before limitation alignment is described.",
            required_evidence_refs=("proof_coverage_matrix_current", "open_conformance_gaps_bounded"),
            required_authority_refs=("conformance_secret_handoff_ref",),
            source_refs=("docs/40_proof_coverage_matrix.md",),
            validator_refs=("tests/test_proof_coverage_matrix.py",),
            proof_surface_refs=("proof_route_gap_triage",),
        ),
    ),
    "cognitive_outcome_loop": (
        _closure_condition_binding(
            "hard_constraints_proven_or_blocked",
            "Require governed dispatch and verification evidence before hard constraints can be described as resolved or blocked.",
            required_evidence_refs=("governed_dispatch_trace", "mechanical_verification_result"),
            required_authority_refs=("governed_dispatch_policy_decision",),
            source_refs=("mcoi/mcoi_runtime/core/cognitive_loop.py",),
            validator_refs=("mcoi/tests/test_cognitive_loop.py",),
            proof_surface_refs=("software_outcome_learning",),
        ),
        _closure_condition_binding(
            "mechanical_verification_completed",
            "Require mechanical verification evidence before outcome verification can be described.",
            required_evidence_refs=("mechanical_verification_result",),
            required_authority_refs=("governed_dispatch_policy_decision",),
            source_refs=("mcoi/mcoi_runtime/core/mil_learning_admission.py",),
            validator_refs=("mcoi/tests/test_whqr_mil_learning_admission.py",),
            proof_surface_refs=("software_outcome_learning",),
        ),
        _closure_condition_binding(
            "critic_did_not_upgrade_failed_proof",
            "Require critic verdict evidence before failed proof upgrade prevention can be described.",
            required_evidence_refs=("critic_verdict_or_null_critic",),
            required_authority_refs=("learning_admission_decision",),
            source_refs=("schemas/learning_admission.schema.json",),
            validator_refs=("mcoi/tests/test_learning_loop.py",),
            proof_surface_refs=("software_outcome_learning",),
        ),
        _closure_condition_binding(
            "learning_admitted_only_from_verified_evidence",
            "Require learning admission and episodic outcome anchors before learning closure can be described.",
            required_evidence_refs=("learning_admission_recorded", "episodic_outcome_anchor"),
            required_authority_refs=("learning_admission_decision",),
            source_refs=("mcoi/mcoi_runtime/persistence/cognitive_outcome_ledger.py",),
            validator_refs=("mcoi/tests/test_cognitive_outcome_ledger.py",),
            proof_surface_refs=("software_outcome_learning",),
        ),
    ),
    "governed_code_change_loop": (
        _closure_condition_binding(
            "worker_receipt_not_terminal_closure",
            "Require code-worker receipt evidence while preserving the non-terminal worker boundary.",
            required_evidence_refs=("code_worker_receipt",),
            required_authority_refs=("code_worker_lease",),
            source_refs=("mcoi/mcoi_runtime/core/governed_code_change_loop.py",),
            validator_refs=("tests/test_governed_code_change_loop.py",),
            proof_surface_refs=("software_dev_capability_pack",),
        ),
        _closure_condition_binding(
            "implementation_receipt_present",
            "Require implementation receipt evidence before code-change closure can advance.",
            required_evidence_refs=("implementation_receipt",),
            required_authority_refs=("uao_ref",),
            source_refs=("schemas/sdlc_implementation_receipt.schema.json",),
            validator_refs=("scripts/validate_sdlc_artifact.py",),
            proof_surface_refs=("software_dev_capability_pack",),
        ),
        _closure_condition_binding(
            "verification_receipt_present",
            "Require verification receipt evidence before code-change closure can advance.",
            required_evidence_refs=("verification_receipt",),
            required_authority_refs=("sdlc_closure_authority",),
            source_refs=("schemas/sdlc_verification_receipt.schema.json",),
            validator_refs=("scripts/validate_sdlc_artifact.py",),
            proof_surface_refs=("software_dev_capability_pack",),
        ),
        _closure_condition_binding(
            "recovery_handoff_present",
            "Require recovery handoff evidence before code-change closure can advance.",
            required_evidence_refs=("recovery_handoff",),
            required_authority_refs=("sdlc_closure_authority",),
            source_refs=("schemas/sdlc_recovery_handoff_receipt.schema.json",),
            validator_refs=("scripts/validate_sdlc_artifact.py",),
            proof_surface_refs=("software_dev_capability_pack",),
        ),
        _closure_condition_binding(
            "closure_blockers_empty",
            "Require all governed code-change receipts before empty blockers can be described.",
            required_evidence_refs=(
                "code_worker_receipt",
                "implementation_receipt",
                "verification_receipt",
                "recovery_handoff",
            ),
            required_authority_refs=("uao_ref", "code_worker_lease", "sdlc_closure_authority"),
            source_refs=("scripts/run_governed_code_change_loop.py",),
            validator_refs=("tests/test_validate_governed_code_change_loop_receipt.py",),
            proof_surface_refs=("software_dev_capability_pack",),
        ),
    ),
}


_DEFAULT_MODE_BINDINGS: Mapping[str, LoopModeBinding] = {
    "deployment_witness_loop": _mode_binding(
        "Expose deployment witness dry-run, shadow, simulation, replay, and real-mode boundaries without changing publication state.",
        separation_refs=(
            "dry_run_preflight_without_publication",
            "shadow_observation_without_gateway_mutation",
            "simulation_and_replay_are_non_effect_bearing",
            "real_mode_requires_publication_authority_and_complete_witnesses",
        ),
        real_execution_guard_refs=(
            "operator_approval_ref",
            "deployment_publication_authority",
            "proof_and_audit_verification_pass",
        ),
        source_refs=(
            "scripts/preflight_deployment_witness.py",
            "scripts/collect_deployment_witness.py",
            "scripts/validate_release_status.py",
        ),
        validator_refs=(
            "tests/test_preflight_deployment_witness.py",
            "tests/test_collect_deployment_witness.py",
            "tests/test_validate_release_status.py",
        ),
        proof_surface_refs=("production_evidence_plane", "gateway_runtime_witness"),
    ),
    "runtime_conformance_loop": _mode_binding(
        "Expose runtime conformance dry-run, shadow, replay, and real-mode boundaries without changing conformance issuance.",
        separation_refs=(
            "dry_run_collection_without_certificate_promotion",
            "shadow_validation_without_endpoint_mutation",
            "replay_uses_retained_conformance_collection",
            "real_mode_requires_issuer_and_secret_handoff",
        ),
        real_execution_guard_refs=(
            "runtime_conformance_issuer",
            "conformance_secret_handoff_ref",
            "certificate_signature_verified",
        ),
        source_refs=(
            "scripts/collect_runtime_conformance.py",
            "schemas/runtime_conformance_collection.schema.json",
            "schemas/runtime_conformance_certificate.schema.json",
        ),
        validator_refs=(
            "tests/test_collect_runtime_conformance.py",
            "tests/test_collect_runtime_conformance_cli.py",
            "tests/test_gateway/test_conformance.py",
        ),
        proof_surface_refs=("runtime_conformance_attestation", "proof_route_gap_triage"),
    ),
    "cognitive_outcome_loop": _mode_binding(
        "Expose cognitive dry-run, shadow, simulation, and replay boundaries without admitting memory promotion.",
        separation_refs=(
            "dry_run_dispatch_without_memory_write",
            "shadow_outcome_projection_without_learning_admission",
            "simulation_and_replay_do_not_mutate_episodic_memory",
        ),
        real_execution_guard_refs=(
            "real_mode_not_registered_for_cognitive_outcome_loop",
            "learning_admission_decision_required_before_memory_promotion",
        ),
        source_refs=(
            "mcoi/mcoi_runtime/core/cognitive_loop.py",
            "mcoi/mcoi_runtime/core/mil_learning_admission.py",
            "mcoi/mcoi_runtime/persistence/cognitive_outcome_ledger.py",
        ),
        validator_refs=(
            "mcoi/tests/test_cognitive_loop.py",
            "mcoi/tests/test_learning_loop.py",
            "mcoi/tests/test_cognitive_outcome_ledger.py",
        ),
        proof_surface_refs=("software_outcome_learning",),
    ),
    "governed_code_change_loop": _mode_binding(
        "Expose governed code-change dry-run, simulation, and replay boundaries without granting repository mutation authority.",
        separation_refs=(
            "dry_run_plan_without_workspace_write",
            "simulation_without_worker_lease",
            "replay_uses_retained_worker_receipts",
            "real_mode_not_registered_for_governed_code_change_loop",
        ),
        real_execution_guard_refs=(
            "uao_ref_required_for_effect_bearing_change",
            "code_worker_lease_required_for_workspace_write",
            "sdlc_closure_authority_required_after_verification",
        ),
        source_refs=(
            "mcoi/mcoi_runtime/core/governed_code_change_loop.py",
            "scripts/run_governed_code_change_loop.py",
            "schemas/sdlc_verification_receipt.schema.json",
        ),
        validator_refs=(
            "tests/test_governed_code_change_loop.py",
            "tests/test_validate_governed_code_change_loop_receipt.py",
            "scripts/validate_sdlc_artifact.py",
        ),
        proof_surface_refs=("software_dev_capability_pack",),
    ),
}


_DEFAULT_LEARNING_BINDINGS: Mapping[str, LoopLearningBinding] = {
    "deployment_witness_loop": _learning_binding(
        "promote deployment blockers into release preflight checks",
        "Bind deployment witness blockers to later release preflight and publication readiness checks.",
        evidence_input_refs=(
            "deployment_witness_published",
            "runtime_witness_valid",
            "authority_obligations_clear",
        ),
        admission_refs=(
            "blocker_promoted_only_after_failed_witness_validation",
            "publication_claim_remains_non_terminal_until_reverified",
        ),
        retention_refs=(
            "deployment_publication_closure_validation",
            "gateway_publication_readiness",
        ),
        source_refs=(
            "scripts/preflight_deployment_witness.py",
            "scripts/validate_release_status.py",
            "schemas/deployment_publication_closure_validation.schema.json",
        ),
        validator_refs=(
            "tests/test_preflight_deployment_witness.py",
            "tests/test_validate_release_status.py",
            "tests/test_plan_deployment_publication_closure.py",
        ),
        proof_surface_refs=("production_evidence_plane", "gateway_runtime_witness"),
    ),
    "runtime_conformance_loop": _learning_binding(
        "convert failed conformance checks into explicit canaries or docs gaps",
        "Bind runtime conformance failures to later canary additions or bounded documentation gaps.",
        evidence_input_refs=(
            "certificate_schema_valid",
            "core_canaries_passed",
            "open_conformance_gaps_bounded",
        ),
        admission_refs=(
            "failed_conformance_collection_retained",
            "new_canary_requires_validator_anchor",
        ),
        retention_refs=(
            "runtime_conformance_collection",
            "runtime_conformance_certificate",
        ),
        source_refs=(
            "scripts/collect_runtime_conformance.py",
            "schemas/runtime_conformance_collection.schema.json",
            "schemas/runtime_conformance_certificate.schema.json",
        ),
        validator_refs=(
            "tests/test_collect_runtime_conformance.py",
            "tests/test_collect_runtime_conformance_cli.py",
            "tests/test_gateway/test_conformance.py",
        ),
        proof_surface_refs=("runtime_conformance_attestation", "proof_route_gap_triage"),
    ),
    "cognitive_outcome_loop": _learning_binding(
        "admit only verified outcomes into episodic memory",
        "Bind cognitive outcomes to learning admission and episodic retention proof.",
        evidence_input_refs=(
            "governed_dispatch_trace",
            "mechanical_verification_result",
            "learning_admission_recorded",
            "episodic_outcome_anchor",
        ),
        admission_refs=(
            "mechanical_verification_required",
            "critic_cannot_upgrade_failed_proof",
            "learning_admission_record_required",
        ),
        retention_refs=(
            "episodic_outcome_anchor",
            "cognitive_outcome_ledger",
        ),
        source_refs=(
            "mcoi/mcoi_runtime/core/mil_learning_admission.py",
            "mcoi/mcoi_runtime/persistence/cognitive_outcome_ledger.py",
            "schemas/learning_admission.schema.json",
        ),
        validator_refs=(
            "mcoi/tests/test_learning_loop.py",
            "mcoi/tests/test_whqr_mil_learning_admission.py",
            "mcoi/tests/test_cognitive_outcome_ledger.py",
        ),
        proof_surface_refs=("software_outcome_learning",),
    ),
    "governed_code_change_loop": _learning_binding(
        "promote failure diagnosis into tests or SDLC gate evidence",
        "Bind governed code-change failures to later tests, verification receipts, or SDLC gate evidence.",
        evidence_input_refs=(
            "code_worker_receipt",
            "verification_receipt",
            "recovery_handoff",
        ),
        admission_refs=(
            "diagnosis_requires_worker_or_verification_receipt",
            "new_gate_evidence_requires_sdlc_validator",
        ),
        retention_refs=(
            "sdlc_verification_receipt",
            "sdlc_recovery_handoff_receipt",
        ),
        source_refs=(
            "mcoi/mcoi_runtime/core/governed_code_change_loop.py",
            "schemas/sdlc_verification_receipt.schema.json",
            "schemas/sdlc_recovery_handoff_receipt.schema.json",
        ),
        validator_refs=(
            "tests/test_governed_code_change_loop.py",
            "tests/test_validate_governed_code_change_loop_receipt.py",
            "scripts/validate_sdlc_artifact.py",
        ),
        proof_surface_refs=("software_dev_capability_pack",),
    ),
}


_DEFAULT_RISK_BINDINGS: Mapping[str, LoopRiskBinding] = {
    "deployment_witness_loop": _risk_binding(
        "release_publication",
        "Publication risk covers public endpoint claims, witness freshness, and responsibility debt.",
        hazard_refs=(
            "public_endpoint_overclaim",
            "stale_or_unverified_deployment_witness",
            "authority_responsibility_debt",
        ),
        mitigation_refs=(
            "block_terminal_closure_until_publication_evidence_passes",
            "retain_last_verified_witness_boundary",
            "surface_authority_debt_as_blocker",
        ),
        monitor_refs=(
            "gateway_publication_readiness",
            "deployment_publication_closure_validation",
            "authority_obligation_mesh",
        ),
        source_refs=(
            "schemas/gateway_publication_readiness.schema.json",
            "schemas/deployment_publication_closure_validation.schema.json",
            "gateway/authority_obligation_mesh.py",
        ),
        validator_refs=(
            "tests/test_report_gateway_publication_readiness.py",
            "tests/test_validate_gateway_publication_receipt.py",
            "tests/test_gateway/test_authority_obligation_mesh.py",
        ),
        proof_surface_refs=("production_evidence_plane", "authority_obligation_mesh"),
    ),
    "runtime_conformance_loop": _risk_binding(
        "runtime_attestation",
        "Runtime attestation risk covers unsigned claims, failed canaries, and unbounded gaps.",
        hazard_refs=(
            "unsigned_or_stale_conformance_certificate",
            "core_canary_regression",
            "unclassified_runtime_gap",
        ),
        mitigation_refs=(
            "reject_schema_invalid_certificate",
            "retain_failed_collection_evidence",
            "surface_open_conformance_gaps",
        ),
        monitor_refs=(
            "runtime_conformance_collection",
            "runtime_conformance_certificate",
            "proof_coverage_matrix",
        ),
        source_refs=_RUNTIME_CONFORMANCE_SOURCES,
        validator_refs=_RUNTIME_CONFORMANCE_VALIDATORS,
        proof_surface_refs=("runtime_conformance_attestation", "proof_route_gap_triage"),
    ),
    "cognitive_outcome_loop": _risk_binding(
        "learning_admission",
        "Learning admission risk covers unverified outcome promotion and failed proof upgrades.",
        hazard_refs=(
            "unverified_outcome_memory_promotion",
            "critic_verdict_upgrades_failed_proof",
            "missing_episodic_outcome_anchor",
        ),
        mitigation_refs=(
            "require_mechanical_verification_before_learning",
            "record_learning_admission_decision",
            "defer_learning_when_evidence_is_missing",
        ),
        monitor_refs=(
            "learning_admission_record",
            "cognitive_outcome_ledger",
            "governed_dispatch_trace",
        ),
        source_refs=_COGNITIVE_OUTCOME_SOURCES,
        validator_refs=_COGNITIVE_OUTCOME_VALIDATORS,
        proof_surface_refs=("software_outcome_learning",),
    ),
    "governed_code_change_loop": _risk_binding(
        "repository_mutation",
        "Repository mutation risk covers unorchestrated edits, stale leases, and missing recovery proof.",
        hazard_refs=(
            "unorchestrated_repository_mutation",
            "code_worker_lease_expired",
            "missing_recovery_handoff",
        ),
        mitigation_refs=(
            "require_uao_reference",
            "enforce_code_worker_lease",
            "block_closure_until_recovery_handoff_exists",
        ),
        monitor_refs=(
            "governed_code_change_receipt",
            "sdlc_verification_receipt",
            "sdlc_recovery_handoff_receipt",
        ),
        source_refs=(
            "mcoi/mcoi_runtime/core/governed_code_change_loop.py",
            "schemas/sdlc_verification_receipt.schema.json",
            "schemas/sdlc_recovery_handoff_receipt.schema.json",
        ),
        validator_refs=(
            "tests/test_governed_code_change_loop.py",
            "tests/test_validate_governed_code_change_loop_receipt.py",
            "scripts/validate_sdlc_artifact.py",
        ),
        proof_surface_refs=("software_dev_capability_pack",),
    ),
}


_DEFAULT_ROLLBACK_BINDINGS: Mapping[str, LoopRollbackBinding] = {
    "deployment_witness_loop": _rollback_binding(
        "revert_publication_status_and_restore_last_verified_witness",
        "Rollback deployment publication status and restore the last verified witness boundary.",
        source_refs=(
            "scripts/apply_deployment_publication_status.py",
            "schemas/deployment_publication_closure_plan.schema.json",
            "schemas/deployment_witness.schema.json",
        ),
        validator_refs=(
            "tests/test_apply_deployment_publication_status.py",
            "tests/test_plan_deployment_publication_closure.py",
            "tests/test_collect_deployment_witness.py",
        ),
        proof_surface_refs=("production_evidence_plane", "authority_obligation_mesh"),
    ),
    "runtime_conformance_loop": _rollback_binding(
        "invalidate_conformance_claim_and_retain_failed_collection",
        "Rollback runtime conformance by invalidating the claim while retaining failed collection proof.",
        source_refs=_RUNTIME_CONFORMANCE_SOURCES,
        validator_refs=_RUNTIME_CONFORMANCE_VALIDATORS,
        proof_surface_refs=("runtime_conformance_attestation",),
    ),
    "cognitive_outcome_loop": _rollback_binding(
        "defer_or_reject_learning_admission_without_memory_promotion",
        "Rollback cognitive outcome learning by deferring or rejecting admission without memory promotion.",
        source_refs=(
            "schemas/learning_admission.schema.json",
            "mcoi/mcoi_runtime/core/mil_learning_admission.py",
        ),
        validator_refs=(
            "mcoi/tests/test_learning_loop.py",
            "mcoi/tests/test_whqr_mil_learning_admission.py",
        ),
        proof_surface_refs=("software_outcome_learning",),
    ),
    "governed_code_change_loop": _rollback_binding(
        "restore_workspace_snapshot_or_open_recovery_handoff",
        "Rollback governed code changes by restoring a workspace snapshot or opening recovery handoff.",
        source_refs=(
            "mcoi/mcoi_runtime/core/governed_code_change_loop.py",
            "schemas/sdlc_recovery_handoff_receipt.schema.json",
        ),
        validator_refs=(
            "tests/test_governed_code_change_loop.py",
            "tests/test_validate_governed_code_change_loop_receipt.py",
            "scripts/validate_sdlc_artifact.py",
        ),
        proof_surface_refs=("software_dev_capability_pack",),
    ),
}


_DEFAULT_AUTHORITY_BINDINGS: Mapping[str, tuple[LoopAuthorityBinding, ...]] = {
    "deployment_witness_loop": (
        _authority_binding(
            "operator_approval_ref",
            "Operator approval reference authorizes deployment-publication closure review.",
            source_refs=(
                "schemas/deployment_publication_operator_input_request.schema.json",
                "scripts/emit_deployment_publication_operator_input_request.py",
            ),
            validator_refs=(
                "tests/test_emit_deployment_publication_operator_input_request.py",
                "tests/test_validate_deployment_publication_operator_input_request.py",
            ),
            proof_surface_refs=("production_evidence_plane", "authority_obligation_mesh"),
        ),
        _authority_binding(
            "deployment_publication_authority",
            "Publication authority binds deployment status changes to responsibility debt.",
            source_refs=(
                "gateway/authority_obligation_mesh.py",
                "scripts/apply_deployment_publication_status.py",
            ),
            validator_refs=(
                "tests/test_apply_deployment_publication_status.py",
                "tests/test_gateway/test_authority_obligation_mesh.py",
            ),
            proof_surface_refs=("authority_obligation_mesh", "production_evidence_plane"),
        ),
    ),
    "runtime_conformance_loop": (
        _authority_binding(
            "runtime_conformance_issuer",
            "Runtime conformance issuer authority signs and bounds certificate claims.",
            source_refs=_RUNTIME_CONFORMANCE_SOURCES,
            validator_refs=_RUNTIME_CONFORMANCE_VALIDATORS,
            proof_surface_refs=("runtime_conformance_attestation",),
        ),
        _authority_binding(
            "conformance_secret_handoff_ref",
            "Secret handoff reference prevents unsigned or stale conformance closure.",
            source_refs=(
                "schemas/runtime_conformance_certificate.schema.json",
                "scripts/collect_runtime_conformance.py",
            ),
            validator_refs=(
                "tests/test_collect_runtime_conformance.py",
                "tests/test_gateway/test_conformance.py",
            ),
            proof_surface_refs=("runtime_conformance_attestation", "authority_obligation_mesh"),
        ),
    ),
    "cognitive_outcome_loop": (
        _authority_binding(
            "governed_dispatch_policy_decision",
            "Governed dispatch policy decision authorizes cognitive loop action admission.",
            source_refs=(
                "mcoi/mcoi_runtime/core/cognitive_loop.py",
                "mcoi/mcoi_runtime/core/universal_action_kernel.py",
            ),
            validator_refs=(
                "mcoi/tests/test_cognitive_loop.py",
                "mcoi/tests/test_universal_action_kernel.py",
            ),
            proof_surface_refs=("software_outcome_learning",),
        ),
        _authority_binding(
            "learning_admission_decision",
            "Learning admission decision authorizes promotion from outcome to memory.",
            source_refs=(
                "schemas/learning_admission.schema.json",
                "mcoi/mcoi_runtime/core/mil_learning_admission.py",
            ),
            validator_refs=(
                "mcoi/tests/test_learning_loop.py",
                "mcoi/tests/test_whqr_mil_learning_admission.py",
            ),
            proof_surface_refs=("software_outcome_learning",),
        ),
    ),
    "governed_code_change_loop": (
        _authority_binding(
            "uao_ref",
            "Universal Action Orchestration reference authorizes repository mutation routing.",
            source_refs=(
                "schemas/universal_action_orchestration.schema.json",
                "mcoi/mcoi_runtime/core/universal_action_kernel.py",
            ),
            validator_refs=(
                "tests/test_validate_universal_action_orchestration.py",
                "mcoi/tests/test_universal_action_kernel.py",
            ),
            proof_surface_refs=("software_dev_capability_pack",),
        ),
        _authority_binding(
            "code_worker_lease",
            "Code-worker lease authority bounds worker execution and replay windows.",
            source_refs=(
                "mcoi/mcoi_runtime/swarm/lease_manager.py",
                "schemas/temporal_lease_window_receipt.schema.json",
            ),
            validator_refs=(
                "tests/test_gateway/test_temporal_lease_window.py",
                "tests/test_governed_code_change_loop.py",
            ),
            proof_surface_refs=("software_dev_capability_pack",),
        ),
        _authority_binding(
            "sdlc_closure_authority",
            "SDLC closure authority separates implementation proof from terminal closure.",
            source_refs=(
                "schemas/sdlc_closure_receipt.schema.json",
                "scripts/emit_sdlc_closure_receipt.py",
            ),
            validator_refs=(
                "scripts/validate_sdlc_artifact.py",
                "tests/test_validate_sdlc_release_readiness.py",
            ),
            proof_surface_refs=("software_dev_capability_pack",),
        ),
    ),
}


_DEFAULT_EVIDENCE_BINDINGS: Mapping[str, tuple[LoopEvidenceBinding, ...]] = {
    "deployment_witness_loop": (
        _binding(
            "deployment_witness_published",
            "Deployment witness envelope has been produced and schema validated.",
            source_refs=_DEPLOYMENT_WITNESS_SOURCES,
            validator_refs=_DEPLOYMENT_WITNESS_VALIDATORS,
            proof_surface_refs=("production_evidence_plane",),
        ),
        _binding(
            "runtime_witness_valid",
            "Runtime witness fields in the deployment witness are present and valid.",
            source_refs=(
                "scripts/collect_deployment_witness.py",
                "schemas/runtime_witness.schema.json",
            ),
            validator_refs=("tests/test_collect_deployment_witness.py",),
            proof_surface_refs=("gateway_runtime_witness",),
        ),
        _binding(
            "runtime_conformance_verified",
            "Runtime conformance certificate has passed its collection and schema checks.",
            source_refs=_RUNTIME_CONFORMANCE_SOURCES,
            validator_refs=_RUNTIME_CONFORMANCE_VALIDATORS,
            proof_surface_refs=("runtime_conformance_attestation",),
        ),
        _binding(
            "audit_anchor_verified",
            "Audit anchor verification surface is available for deployment closure proof.",
            source_refs=(
                "gateway/audit_trace_verifier.py",
                "schemas/audit_verification_endpoint.schema.json",
            ),
            validator_refs=("tests/test_gateway/test_audit_trace_verifier.py",),
            proof_surface_refs=("audit_chain_api",),
        ),
        _binding(
            "proof_verification_passed",
            "Proof verification endpoint contract is present for deployment proof checks.",
            source_refs=("schemas/proof_verification_endpoint.schema.json",),
            validator_refs=("tests/test_gateway/test_production_evidence.py",),
            proof_surface_refs=("proof_route_gap_triage", "production_evidence_plane"),
        ),
        _binding(
            "authority_obligations_clear",
            "Authority obligation mesh exposes responsibility debt before closure.",
            source_refs=("gateway/authority_obligation_mesh.py",),
            validator_refs=("tests/test_gateway/test_authority_obligation_mesh.py",),
            proof_surface_refs=("authority_obligation_mesh",),
        ),
        _binding(
            "public_endpoint_declared",
            "Public endpoint declaration is bound to gateway publication readiness evidence.",
            source_refs=(
                "schemas/public_production_health_declaration.schema.json",
                "schemas/gateway_publication_readiness.schema.json",
            ),
            validator_refs=(
                "tests/test_validate_gateway_publication_receipt.py",
                "tests/test_report_gateway_publication_readiness.py",
            ),
            proof_surface_refs=("production_evidence_plane",),
        ),
    ),
    "runtime_conformance_loop": (
        _binding(
            "certificate_schema_valid",
            "Runtime conformance certificate schema validates before a claim is accepted.",
            source_refs=_RUNTIME_CONFORMANCE_SOURCES,
            validator_refs=_RUNTIME_CONFORMANCE_VALIDATORS,
            proof_surface_refs=("runtime_conformance_attestation",),
        ),
        _binding(
            "certificate_signature_verified",
            "Runtime conformance certificate signature verification is represented.",
            source_refs=_RUNTIME_CONFORMANCE_SOURCES,
            validator_refs=_RUNTIME_CONFORMANCE_VALIDATORS,
            proof_surface_refs=("runtime_conformance_attestation",),
        ),
        _binding(
            "core_canaries_passed",
            "Runtime conformance collection records core canary status.",
            source_refs=_RUNTIME_CONFORMANCE_SOURCES,
            validator_refs=_RUNTIME_CONFORMANCE_VALIDATORS,
            proof_surface_refs=("runtime_conformance_attestation",),
        ),
        _binding(
            "authority_directory_sync_valid",
            "Authority directory sync evidence is checked by runtime conformance.",
            source_refs=(
                "scripts/collect_runtime_conformance.py",
                "gateway/authority_obligation_mesh.py",
            ),
            validator_refs=("tests/test_gateway/test_conformance.py",),
            proof_surface_refs=("runtime_conformance_attestation", "authority_obligation_mesh"),
        ),
        _binding(
            "proof_coverage_matrix_current",
            "Proof coverage matrix currency is available as runtime conformance input.",
            source_refs=("scripts/proof_coverage_matrix.py",),
            validator_refs=("tests/test_proof_coverage_matrix.py",),
            proof_surface_refs=("proof_route_gap_triage",),
        ),
        _binding(
            "open_conformance_gaps_bounded",
            "Open conformance gaps are explicit and bounded rather than silently closed.",
            source_refs=_RUNTIME_CONFORMANCE_SOURCES,
            validator_refs=_RUNTIME_CONFORMANCE_VALIDATORS,
            proof_surface_refs=("runtime_conformance_attestation",),
        ),
    ),
    "cognitive_outcome_loop": (
        _binding(
            "governed_dispatch_trace",
            "Cognitive loop dispatch trace is available before learning admission.",
            source_refs=_COGNITIVE_OUTCOME_SOURCES,
            validator_refs=_COGNITIVE_OUTCOME_VALIDATORS,
            proof_surface_refs=("software_outcome_learning",),
        ),
        _binding(
            "mechanical_verification_result",
            "Mechanical verification result is bound to the outcome record.",
            source_refs=_COGNITIVE_OUTCOME_SOURCES,
            validator_refs=_COGNITIVE_OUTCOME_VALIDATORS,
            proof_surface_refs=("software_outcome_learning",),
        ),
        _binding(
            "critic_verdict_or_null_critic",
            "Critic verdict state is explicit and cannot upgrade failed proof silently.",
            source_refs=_COGNITIVE_OUTCOME_SOURCES,
            validator_refs=_COGNITIVE_OUTCOME_VALIDATORS,
            proof_surface_refs=("software_outcome_learning",),
        ),
        _binding(
            "learning_admission_recorded",
            "Learning admission record exists before memory promotion is described.",
            source_refs=(
                "mcoi/mcoi_runtime/core/learning.py",
                "schemas/learning_admission.schema.json",
            ),
            validator_refs=("mcoi/tests/test_learning_loop.py",),
            proof_surface_refs=("software_outcome_learning",),
        ),
        _binding(
            "episodic_outcome_anchor",
            "Outcome ledger anchor is available for replay and later audit.",
            source_refs=("mcoi/mcoi_runtime/persistence/cognitive_outcome_ledger.py",),
            validator_refs=("mcoi/tests/test_cognitive_outcome_ledger.py",),
            proof_surface_refs=("software_outcome_learning",),
        ),
    ),
    "governed_code_change_loop": (
        _binding(
            "code_worker_receipt",
            "Code worker execution receipt is present but not terminal closure.",
            source_refs=_GOVERNED_CODE_CHANGE_SOURCES,
            validator_refs=_GOVERNED_CODE_CHANGE_VALIDATORS,
            proof_surface_refs=("software_dev_capability_pack",),
        ),
        _binding(
            "implementation_receipt",
            "SDLC implementation receipt exists for the repository mutation boundary.",
            source_refs=("schemas/sdlc_implementation_receipt.schema.json",),
            validator_refs=("scripts/validate_sdlc_artifact.py",),
            proof_surface_refs=("software_dev_capability_pack",),
        ),
        _binding(
            "verification_receipt",
            "SDLC verification receipt exists for test and validator evidence.",
            source_refs=("schemas/sdlc_verification_receipt.schema.json",),
            validator_refs=("scripts/validate_sdlc_artifact.py",),
            proof_surface_refs=("software_dev_capability_pack",),
        ),
        _binding(
            "recovery_handoff",
            "Recovery handoff receipt exists for rollback or incident continuation.",
            source_refs=("schemas/sdlc_recovery_handoff_receipt.schema.json",),
            validator_refs=("scripts/validate_sdlc_artifact.py",),
            proof_surface_refs=("software_dev_capability_pack",),
        ),
    ),
}


def _stable_unique_tuple(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return tuple(ordered)


__all__ = [
    "DEFAULT_LOOP_UPDATED_AT",
    "DEFAULT_READ_MODEL_LIMIT",
    "LoopRegistry",
    "build_default_loop_read_model",
    "build_default_loop_registry",
]
