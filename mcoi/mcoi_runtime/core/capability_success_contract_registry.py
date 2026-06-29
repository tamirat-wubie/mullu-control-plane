"""Purpose: compile proof-of-success contracts from governed capability entries.
Governance scope: capability completion claims, false-success blocking,
    contract coverage, and operator read-model projection.
Dependencies: governed capability fabric and capability success contracts.
Invariants:
  - Every loaded capability can receive exactly one success contract.
  - Contract required and forbidden deltas preserve capability effect models.
  - Contract proof obligations preserve capability evidence requirements.
  - High-risk and critical contracts require independent evidence gates.
"""

from __future__ import annotations

from typing import Any, Mapping

from mcoi_runtime.contracts.capability_success_contract import (
    CapabilitySuccessClaimType,
    CapabilitySuccessContract,
    CapabilitySuccessRiskLevel,
    CapabilitySuccessVerdict,
    SuccessAcceptancePredicate,
    SuccessAuthorityContract,
    SuccessExpectedDelta,
    SuccessFreshnessPolicy,
    SuccessInvariantContract,
    SuccessProofLevel,
    SuccessProofObligation,
    SuccessReceiptRequirements,
    SuccessRepairPolicy,
    SuccessVerdictPolicy,
)
from mcoi_runtime.contracts.governed_capability_fabric import CapabilityRegistryEntry

from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text, stable_identifier


_PROOF_LEVEL_ORDER = {
    SuccessProofLevel.P0: 0,
    SuccessProofLevel.P1: 1,
    SuccessProofLevel.P2: 2,
    SuccessProofLevel.P3: 3,
    SuccessProofLevel.P4: 4,
    SuccessProofLevel.P5: 5,
}
_MIN_PROOF_BY_RISK = {
    CapabilitySuccessRiskLevel.LOW: SuccessProofLevel.P2,
    CapabilitySuccessRiskLevel.MEDIUM: SuccessProofLevel.P3,
    CapabilitySuccessRiskLevel.HIGH: SuccessProofLevel.P4,
    CapabilitySuccessRiskLevel.CRITICAL: SuccessProofLevel.P5,
}
_FRESHNESS_BY_RISK = {
    CapabilitySuccessRiskLevel.LOW: 3600,
    CapabilitySuccessRiskLevel.MEDIUM: 900,
    CapabilitySuccessRiskLevel.HIGH: 300,
    CapabilitySuccessRiskLevel.CRITICAL: 60,
}


class CapabilitySuccessContractRegistry:
    """Immutable success-contract index for governed capability claims."""

    def __init__(self, contracts: tuple[CapabilitySuccessContract, ...]) -> None:
        if not contracts:
            raise RuntimeCoreInvariantError("capability success contract registry requires contracts")
        contract_ids = [contract.contract_id for contract in contracts]
        capability_ids = [contract.capability_id for contract in contracts]
        duplicate_contract_ids = _duplicates(contract_ids)
        duplicate_capability_ids = _duplicates(capability_ids)
        if duplicate_contract_ids:
            raise RuntimeCoreInvariantError(f"duplicate contract ids: {duplicate_contract_ids}")
        if duplicate_capability_ids:
            raise RuntimeCoreInvariantError(f"duplicate capability ids: {duplicate_capability_ids}")
        self._contracts_by_capability = {contract.capability_id: contract for contract in contracts}
        self._contract_ids = tuple(sorted(contract_ids))

    @classmethod
    def from_capability_entries(
        cls,
        entries: tuple[CapabilityRegistryEntry, ...],
        *,
        overrides: tuple[CapabilitySuccessContract | Mapping[str, Any], ...] = (),
    ) -> "CapabilitySuccessContractRegistry":
        """Compile a complete registry from capability entries and overrides."""
        if not entries:
            raise RuntimeCoreInvariantError("capability entries are required")
        entry_by_capability: dict[str, CapabilityRegistryEntry] = {}
        for entry in entries:
            if entry.capability_id in entry_by_capability:
                raise RuntimeCoreInvariantError(f"duplicate capability entry: {entry.capability_id}")
            entry_by_capability[entry.capability_id] = entry

        contracts = {
            entry.capability_id: compile_capability_success_contract(entry)
            for entry in entries
        }
        for raw_override in overrides:
            override = (
                raw_override
                if isinstance(raw_override, CapabilitySuccessContract)
                else CapabilitySuccessContract.from_mapping(raw_override)
            )
            if override.capability_id not in entry_by_capability:
                raise RuntimeCoreInvariantError(f"override references unknown capability: {override.capability_id}")
            relation_errors = validate_contract_against_entry(
                override,
                entry_by_capability[override.capability_id],
            )
            if relation_errors:
                raise RuntimeCoreInvariantError(
                    f"override invalid for {override.capability_id}: {relation_errors}"
                )
            contracts[override.capability_id] = override
        return cls(tuple(contracts[capability_id] for capability_id in sorted(contracts)))

    @property
    def contract_count(self) -> int:
        return len(self._contracts_by_capability)

    def get_contract(self, capability_id: str) -> CapabilitySuccessContract:
        capability_id = ensure_non_empty_text("capability_id", capability_id)
        contract = self._contracts_by_capability.get(capability_id)
        if contract is None:
            raise RuntimeCoreInvariantError("Unknown capability_id")
        return contract

    def read_model(self) -> dict[str, Any]:
        """Return deterministic operator projection for success contracts."""
        contracts = tuple(
            self._contracts_by_capability[capability_id].to_json_dict()
            for capability_id in sorted(self._contracts_by_capability)
        )
        risk_counts: dict[str, int] = {}
        proof_counts: dict[str, int] = {}
        high_risk_independent_count = 0
        for contract in self._contracts_by_capability.values():
            risk_counts[contract.risk_level.value] = risk_counts.get(contract.risk_level.value, 0) + 1
            proof_counts[contract.proof_level_required.value] = proof_counts.get(contract.proof_level_required.value, 0) + 1
            if (
                contract.risk_level in {CapabilitySuccessRiskLevel.HIGH, CapabilitySuccessRiskLevel.CRITICAL}
                and contract.independent_evidence_required
            ):
                high_risk_independent_count += 1
        return {
            "contract_count": self.contract_count,
            "contract_ids": self._contract_ids,
            "capability_ids": tuple(sorted(self._contracts_by_capability)),
            "risk_counts": dict(sorted(risk_counts.items())),
            "proof_level_counts": dict(sorted(proof_counts.items())),
            "high_risk_independent_contract_count": high_risk_independent_count,
            "contracts": contracts,
        }


def compile_capability_success_contract(entry: CapabilityRegistryEntry) -> CapabilitySuccessContract:
    """Create a deterministic success contract from one capability entry."""
    risk_level = _risk_level_from_entry(entry)
    proof_level = _MIN_PROOF_BY_RISK[risk_level]
    world_mutating = _world_mutating(entry)
    approval_required = bool(entry.authority_policy.approval_chain)
    freshness_seconds = _FRESHNESS_BY_RISK[risk_level]
    durability_seconds = _durability_window_seconds(risk_level, world_mutating)
    return CapabilitySuccessContract(
        contract_id=_contract_id(entry.capability_id, entry.version),
        capability_id=entry.capability_id,
        domain=entry.domain,
        claim_type=_claim_type(entry),
        risk_level=risk_level,
        proof_level_required=proof_level,
        scope_bindings=("actor_id", "capability_id", "environment_id", "target_object", "time_window"),
        authority=SuccessAuthorityContract(
            required_permissions=_required_permissions(entry),
            block_on_unknown_authority=True,
            human_confirmation_required=approval_required,
        ),
        expected_delta=SuccessExpectedDelta(
            required_changes=entry.effect_model.expected_effects,
            forbidden_changes=entry.effect_model.forbidden_effects,
            optional_changes=(),
        ),
        invariants=SuccessInvariantContract(
            must_remain_true=_default_must_remain_true(entry),
            must_not_happen=entry.effect_model.forbidden_effects,
        ),
        proof_obligations=_default_proof_obligations(
            entry=entry,
            freshness_seconds=freshness_seconds,
        ),
        independent_evidence_required=risk_level in {CapabilitySuccessRiskLevel.HIGH, CapabilitySuccessRiskLevel.CRITICAL}
        or approval_required,
        freshness=SuccessFreshnessPolicy(
            max_age_seconds=freshness_seconds,
            recheck_required=durability_seconds > 0,
            durability_window_seconds=durability_seconds,
        ),
        acceptance_predicate=SuccessAcceptancePredicate(
            all_mandatory_evidence_present=True,
            expected_delta_verified=True,
            forbidden_delta_absent=True,
            invariants_preserved=True,
            causal_trace_valid=True,
            contradictions_absent=True,
            durability_satisfied=True,
        ),
        verdict_policy=SuccessVerdictPolicy(
            allow_partial_success=True,
            allow_pending_success=False,
            block_on_stale_evidence=True,
            block_on_scope_mismatch=True,
            block_on_unknown_authority=True,
        ),
        repair_policy=SuccessRepairPolicy(
            retry_allowed=True,
            rollback_required_on_contamination=world_mutating,
            escalate_on_high_risk=risk_level in {CapabilitySuccessRiskLevel.HIGH, CapabilitySuccessRiskLevel.CRITICAL},
        ),
        receipt_requirements=SuccessReceiptRequirements(
            required_fields=_receipt_required_fields(entry),
            hash_chain_required=entry.evidence_model.terminal_certificate_required,
            residual_gaps_required=True,
        ),
        metadata={
            "compiled_from": "capability_registry_entry",
            "capability_version": entry.version,
            "source_risk_tier": risk_level.value,
        },
    )


def validate_contract_against_entry(
    contract: CapabilitySuccessContract,
    entry: CapabilityRegistryEntry,
    *,
    minimum_proof_by_risk: Mapping[str, str | SuccessProofLevel] | None = None,
) -> tuple[str, ...]:
    """Return relation errors between a success contract and capability entry."""
    errors: list[str] = []
    if contract.capability_id != entry.capability_id:
        errors.append("contract capability_id does not match entry")
    if contract.domain != entry.domain:
        errors.append("contract domain does not match entry")
    risk_level = _risk_level_from_entry(entry)
    if contract.risk_level != risk_level:
        errors.append("contract risk_level does not match entry risk tier")
    expected_effects = set(entry.effect_model.expected_effects)
    if not expected_effects.issubset(set(contract.expected_delta.required_changes)):
        errors.append("contract required_changes omit expected capability effects")
    forbidden_effects = set(entry.effect_model.forbidden_effects)
    if not forbidden_effects.issubset(set(contract.expected_delta.forbidden_changes)):
        errors.append("contract forbidden_changes omit forbidden capability effects")
    mandatory_evidence = set(entry.evidence_model.required_evidence)
    if not mandatory_evidence.issubset(set(contract.mandatory_evidence_fields)):
        errors.append("contract mandatory proof obligations omit capability required evidence")
    if not contract.acceptance_predicate.requires_all_success_gates:
        errors.append("contract acceptance predicate leaves a success gate optional")
    if contract.verdict_policy.allow_pending_success:
        errors.append("contract permits pending state to be called success")
    if not contract.verdict_policy.block_on_stale_evidence:
        errors.append("contract does not block stale evidence")
    if not contract.verdict_policy.block_on_scope_mismatch:
        errors.append("contract does not block scope mismatch")
    if not contract.authority.block_on_unknown_authority:
        errors.append("contract does not block unknown authority")
    if risk_level in {CapabilitySuccessRiskLevel.HIGH, CapabilitySuccessRiskLevel.CRITICAL}:
        if not contract.independent_evidence_required:
            errors.append("high-risk contract does not require independent evidence")
        if not contract.repair_policy.escalate_on_high_risk:
            errors.append("high-risk contract does not escalate high-risk ambiguity")
    if entry.evidence_model.terminal_certificate_required and not contract.receipt_requirements.hash_chain_required:
        errors.append("terminal-certificate capability contract does not require hash chain")
    min_map = minimum_proof_by_risk or {risk.value: level for risk, level in _MIN_PROOF_BY_RISK.items()}
    configured_min = min_map.get(risk_level.value)
    if configured_min is not None:
        min_level = configured_min if isinstance(configured_min, SuccessProofLevel) else SuccessProofLevel(str(configured_min))
        if _PROOF_LEVEL_ORDER[contract.proof_level_required] < _PROOF_LEVEL_ORDER[min_level]:
            errors.append("contract proof level is below risk policy")
    return tuple(errors)


def _risk_level_from_entry(entry: CapabilityRegistryEntry) -> CapabilitySuccessRiskLevel:
    raw = str(entry.metadata.get("risk_tier") or entry.extensions.get("risk_tier") or "medium").strip().lower()
    if raw == "max":
        raw = "critical"
    return CapabilitySuccessRiskLevel(raw)


def _required_permissions(entry: CapabilityRegistryEntry) -> tuple[str, ...]:
    permissions = [f"role:{role}" for role in entry.authority_policy.required_roles]
    permissions.extend(f"approval:{approver}" for approver in entry.authority_policy.approval_chain)
    return tuple(dict.fromkeys(permissions))


def _world_mutating(entry: CapabilityRegistryEntry) -> bool:
    governed = entry.extensions.get("governed_record", {})
    if isinstance(governed, Mapping) and "world_mutating" in governed:
        return governed["world_mutating"] is True
    return not all(
        any(marker in effect.lower() for marker in ("read", "search", "analysis", "insight", "observe"))
        for effect in entry.effect_model.expected_effects
    )


def _claim_type(entry: CapabilityRegistryEntry) -> CapabilitySuccessClaimType:
    capability_id = entry.capability_id
    if capability_id == "computer.code.patch":
        return CapabilitySuccessClaimType.FILE_WRITE
    if capability_id == "computer.command.run":
        return CapabilitySuccessClaimType.COMMAND_RUN
    if capability_id.startswith("email.send"):
        return CapabilitySuccessClaimType.EMAIL_SEND
    if capability_id.startswith("calendar.") and any(
        marker in capability_id for marker in ("schedule", "reschedule", "invite")
    ):
        return CapabilitySuccessClaimType.CALENDAR_WRITE
    if capability_id.startswith("financial."):
        return CapabilitySuccessClaimType.PAYMENT if "payment" in capability_id else CapabilitySuccessClaimType.CUSTOM
    if capability_id.startswith("deployment."):
        return CapabilitySuccessClaimType.DEPLOYMENT_WITNESS
    if capability_id == "github.open_pull_request":
        return CapabilitySuccessClaimType.GITHUB_PR
    if capability_id.startswith("software_dev."):
        return CapabilitySuccessClaimType.SOFTWARE_CHANGE
    if capability_id.endswith(".evidence.append"):
        return CapabilitySuccessClaimType.EVIDENCE_APPEND
    if not _world_mutating(entry):
        return CapabilitySuccessClaimType.READ_OBSERVATION
    return CapabilitySuccessClaimType.CUSTOM


def _default_must_remain_true(entry: CapabilityRegistryEntry) -> tuple[str, ...]:
    invariants = [
        "scope_identity_preserved",
        "authority_boundary_preserved",
        "credential_scope_not_exceeded",
        "receipt_emitted_before_success_claim",
    ]
    if _world_mutating(entry):
        invariants.append("rollback_or_compensation_boundary_known")
    return tuple(invariants)


def _default_proof_obligations(
    *,
    entry: CapabilityRegistryEntry,
    freshness_seconds: int,
) -> tuple[SuccessProofObligation, ...]:
    obligations: list[SuccessProofObligation] = []
    for evidence_field in entry.evidence_model.required_evidence:
        obligations.append(
            SuccessProofObligation(
                obligation_id=f"capability_evidence.{evidence_field}",
                what_must_be_proven=f"Capability evidence field is present and scope-bound: {evidence_field}",
                evidence_fields=(evidence_field,),
                evidence_type="capability_evidence",
                verifier="capability_success_contract_registry",
                freshness_window_seconds=freshness_seconds,
                scope_binding=("capability_id", "environment_id", "target_object", "observed_at"),
                mandatory=True,
                failure_effect=CapabilitySuccessVerdict.BLOCKED_FALSE_SUCCESS,
            )
        )
    obligations.extend(
        (
            SuccessProofObligation(
                obligation_id="expected_delta_observed",
                what_must_be_proven="Observed state contains the capability expected effect.",
                evidence_fields=("observed_delta",),
                evidence_type="state_observation",
                verifier="delta_verifier",
                freshness_window_seconds=freshness_seconds,
                scope_binding=("capability_id", "target_object", "observed_at"),
                mandatory=True,
                failure_effect=CapabilitySuccessVerdict.BLOCKED_FALSE_SUCCESS,
            ),
            SuccessProofObligation(
                obligation_id="forbidden_delta_absent",
                what_must_be_proven="Observed state excludes all forbidden effects.",
                evidence_fields=("forbidden_delta_scan",),
                evidence_type="invariant_scan",
                verifier="invariant_verifier",
                freshness_window_seconds=freshness_seconds,
                scope_binding=("capability_id", "target_object", "observed_at"),
                mandatory=True,
                failure_effect=CapabilitySuccessVerdict.BLOCKED_INVARIANT_DAMAGE,
            ),
            SuccessProofObligation(
                obligation_id="scope_match",
                what_must_be_proven="Evidence belongs to the claimed actor, capability, environment, object, and time.",
                evidence_fields=("scope_hash",),
                evidence_type="scope_binding",
                verifier="scope_verifier",
                freshness_window_seconds=freshness_seconds,
                scope_binding=("actor_id", "capability_id", "environment_id", "target_object", "observed_at"),
                mandatory=True,
                failure_effect=CapabilitySuccessVerdict.BLOCKED_SCOPE_MISMATCH,
            ),
            SuccessProofObligation(
                obligation_id="authority_verified",
                what_must_be_proven="Actor authority and approval requirements match the capability policy.",
                evidence_fields=("authority_verdict",),
                evidence_type="authority_receipt",
                verifier="authority_gate",
                freshness_window_seconds=freshness_seconds,
                scope_binding=("actor_id", "capability_id", "approval_id"),
                mandatory=True,
                failure_effect=CapabilitySuccessVerdict.BLOCKED_AUTHORITY_MISMATCH,
            ),
            SuccessProofObligation(
                obligation_id="causal_trace_valid",
                what_must_be_proven="Action trace causally links the attempt to the observed state delta.",
                evidence_fields=("action_trace_hash",),
                evidence_type="causal_trace",
                verifier="causal_trace_verifier",
                freshness_window_seconds=freshness_seconds,
                scope_binding=("actor_id", "capability_id", "target_object", "trace_id"),
                mandatory=True,
                failure_effect=CapabilitySuccessVerdict.BLOCKED_FALSE_SUCCESS,
            ),
            SuccessProofObligation(
                obligation_id="contradictions_absent",
                what_must_be_proven="No critical observer, trace, or invariant contradiction remains open.",
                evidence_fields=("contradiction_scan",),
                evidence_type="contradiction_scan",
                verifier="contradiction_verifier",
                freshness_window_seconds=freshness_seconds,
                scope_binding=("claim_id", "capability_id", "observed_at"),
                mandatory=True,
                failure_effect=CapabilitySuccessVerdict.BLOCKED_CONTRADICTION,
            ),
        )
    )
    if entry.evidence_model.terminal_certificate_required:
        obligations.append(
            SuccessProofObligation(
                obligation_id="receipt_hash_chain_bound",
                what_must_be_proven="Receipt includes evidence hashes and previous/current receipt hash chain fields.",
                evidence_fields=("previous_receipt_hash", "current_receipt_hash", "evidence_hashes"),
                evidence_type="receipt_integrity",
                verifier="receipt_hash_chain_verifier",
                freshness_window_seconds=freshness_seconds,
                scope_binding=("claim_id", "capability_id", "receipt_id"),
                mandatory=True,
                failure_effect=CapabilitySuccessVerdict.BLOCKED_FALSE_SUCCESS,
            )
        )
    return tuple(obligations)


def _receipt_required_fields(entry: CapabilityRegistryEntry) -> tuple[str, ...]:
    base_fields = [
        "receipt_id",
        "claim.claim_id",
        "claim.capability_id",
        "claim.actor_id",
        "scope.environment_id",
        "scope.target_object",
        "expected_delta.required",
        "expected_delta.forbidden",
        "observed_delta.confirmed",
        "evidence.mandatory_present",
        "evidence.missing",
        "causality.status",
        "invariants.status",
        "contradictions",
        "settled_verdict",
        "residual_gaps",
        "repair_plan",
    ]
    if entry.evidence_model.terminal_certificate_required:
        base_fields.extend(("ledger.previous_receipt_hash", "ledger.current_receipt_hash", "ledger.evidence_hashes"))
    return tuple(base_fields)


def _durability_window_seconds(risk_level: CapabilitySuccessRiskLevel, world_mutating: bool) -> int:
    if risk_level is CapabilitySuccessRiskLevel.CRITICAL:
        return 300
    if risk_level is CapabilitySuccessRiskLevel.HIGH:
        return 120 if world_mutating else 60
    if risk_level is CapabilitySuccessRiskLevel.MEDIUM and world_mutating:
        return 30
    return 0


def _contract_id(capability_id: str, capability_version: str) -> str:
    return stable_identifier(
        "capability-success-contract",
        {
            "capability_id": capability_id,
            "capability_version": capability_version,
        },
    )


def _duplicates(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return tuple(sorted(duplicates))
