"""Purpose: command intent admission gate for governed capability fabric.
Governance scope: resolve typed command intents against installed capability
    registry entries before any effectful execution can occur.
Dependencies: governed capability registry, fabric contracts, runtime invariants.
Invariants:
  - No typed intent name resolves without an installed capability.
  - Accepted decisions carry owner and evidence obligations from the registry entry.
  - Rejected decisions are explicit and side-effect free.
"""

from __future__ import annotations

from typing import Any, Callable

from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityRegistryEntry,
    CommandCapabilityAdmissionDecision,
    CommandCapabilityAdmissionStatus,
)

from .capability_unlock_ladder import (
    capability_unlock_admission_profile,
    capability_unlock_profile_errors,
)
from .governed_capability_registry import GovernedCapabilityRegistry
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text


class CommandCapabilityAdmissionGate:
    """Resolve typed command intents through an installed governed capability registry."""

    def __init__(self, *, registry: GovernedCapabilityRegistry, clock: Callable[[], str]) -> None:
        if not isinstance(registry, GovernedCapabilityRegistry):
            raise RuntimeCoreInvariantError("registry must be a GovernedCapabilityRegistry")
        self._registry = registry
        self._clock = clock

    @property
    def registry(self) -> GovernedCapabilityRegistry:
        """Return the governed registry that owns capability admission authority."""
        return self._registry

    def admit(self, *, command_id: str, intent_name: str) -> CommandCapabilityAdmissionDecision:
        """Return an explicit admission decision for one command intent."""
        command_id = ensure_non_empty_text("command_id", command_id)
        intent_name = ensure_non_empty_text("intent_name", intent_name)
        now = self._clock()
        try:
            capability = self._registry.get_capability(intent_name)
        except RuntimeCoreInvariantError:
            return CommandCapabilityAdmissionDecision(
                command_id=command_id,
                intent_name=intent_name,
                status=CommandCapabilityAdmissionStatus.REJECTED,
                capability_id="",
                domain="",
                owner_team="",
                evidence_required=(),
                reason="no installed capability for typed intent",
                decided_at=now,
                rejection_codes=("capability_not_installed",),
            )
        profile_errors = capability_unlock_profile_errors(capability)
        if profile_errors:
            return CommandCapabilityAdmissionDecision(
                command_id=command_id,
                intent_name=intent_name,
                status=CommandCapabilityAdmissionStatus.REJECTED,
                capability_id=capability.capability_id,
                domain=capability.domain,
                owner_team=capability.obligation_model.owner_team,
                evidence_required=(),
                reason="capability unlock profile invalid",
                decided_at=now,
                rejection_codes=profile_errors,
            )
        unlock_profile = capability_unlock_admission_profile(capability)
        return CommandCapabilityAdmissionDecision(
            command_id=command_id,
            intent_name=intent_name,
            status=CommandCapabilityAdmissionStatus.ACCEPTED,
            capability_id=capability.capability_id,
            domain=capability.domain,
            owner_team=capability.obligation_model.owner_team,
            evidence_required=capability.evidence_model.required_evidence,
            reason="typed intent resolved to installed governed capability",
            decided_at=now,
            unlock_ladder_id=unlock_profile.ladder_id if unlock_profile else "",
            unlock_level_id=unlock_profile.level_id if unlock_profile else "",
            unlock_level=unlock_profile.level if unlock_profile else None,
            gate_template_ids=unlock_profile.gate_template_ids if unlock_profile else (),
            requires_operator_approval=unlock_profile.requires_operator_approval if unlock_profile else False,
            requires_receipt=unlock_profile.requires_receipt if unlock_profile else False,
            requires_rollback=unlock_profile.requires_rollback if unlock_profile else False,
            requires_live_witness=unlock_profile.requires_live_witness if unlock_profile else False,
        )

    def capability_for_intent(self, intent_name: str) -> CapabilityRegistryEntry:
        """Return the installed capability contract for an admitted typed intent."""
        intent_name = ensure_non_empty_text("intent_name", intent_name)
        return self._registry.get_capability(intent_name)

    def read_model(self) -> dict[str, Any]:
        """Return the operator read model for the underlying governed registry."""
        return self._registry.read_model()
