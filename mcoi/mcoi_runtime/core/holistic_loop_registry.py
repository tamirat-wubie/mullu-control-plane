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

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from mcoi_runtime.contracts._base import freeze_value, require_datetime_text
from mcoi_runtime.contracts.holistic_loop import (
    LoopManifest,
    LoopMode,
    LoopPhase,
    LoopReadModel,
    LoopState,
    LoopStatus,
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
    observed_evidence_refs: Mapping[str, Sequence[str]] | None = None,
    updated_at: str = DEFAULT_LOOP_UPDATED_AT,
) -> LoopRegistry:
    """Build the default read-only registry for existing governed loops."""

    require_datetime_text(updated_at, "updated_at")
    manifests = _default_manifests()
    evidence_by_loop = observed_evidence_refs or {}
    states = {
        loop_id: _default_open_state(
            loop_id,
            updated_at,
            evidence_refs=tuple(evidence_by_loop.get(loop_id, ())),
        )
        for loop_id in manifests
    }
    return LoopRegistry(manifests=manifests, states=states)


def build_default_loop_read_model(
    *,
    observed_evidence_refs: Mapping[str, Sequence[str]] | None = None,
    generated_at: str = DEFAULT_LOOP_UPDATED_AT,
    limit: int = DEFAULT_READ_MODEL_LIMIT,
) -> LoopReadModel:
    """Build the bounded default read model for existing governed loops."""

    registry = build_default_loop_registry(
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
    evidence_refs: Sequence[str] = (),
) -> LoopState:
    return LoopState(
        loop_id=loop_id,
        status=LoopStatus.OPEN,
        current_step=LoopPhase.OBSERVE,
        mode=LoopMode.DRY_RUN,
        evidence_refs=tuple(evidence_refs),
        updated_at=updated_at,
    )


def _summarize_manifest_state(manifest: LoopManifest, state: LoopState) -> LoopSummary:
    observed = set(state.evidence_refs)
    missing = tuple(evidence for evidence in manifest.required_evidence if evidence not in observed)
    missing_blockers = tuple(f"missing_evidence:{evidence}" for evidence in missing)
    blockers = _stable_unique_tuple((*state.open_blockers, *missing_blockers))
    status = LoopStatus.BLOCKED if blockers else state.status
    if not blockers and status == LoopStatus.OPEN:
        status = LoopStatus.VERIFIED
    return LoopSummary(
        loop_id=manifest.loop_id,
        name=manifest.name,
        purpose=manifest.purpose,
        owner=manifest.owner,
        risk_class=manifest.risk_class,
        status=status,
        mode=state.mode,
        current_step=state.current_step,
        required_authority=manifest.required_authority,
        required_evidence=manifest.required_evidence,
        evidence_refs=state.evidence_refs,
        missing_evidence=missing,
        closure_conditions=manifest.closure_conditions,
        open_blockers=blockers,
        rollback_policy=manifest.rollback_policy,
        learning_policy=manifest.learning_policy,
        updated_at=state.updated_at,
    )


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
