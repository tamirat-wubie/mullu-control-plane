"""Purpose: god-mode wiring — register the catalog of per-module proposals
and bind the engine to the deps container / audit trail at startup.

Governance scope: every god capability ships DORMANT here. None are armed
until an operator records a `RegistrationAgreement` for that specific
capability via the `/api/v1/god-mode/...` HTTP surface (or the registry API).

Dependencies: god_mode contracts/registry/engine, deps container.

Invariants:
  - This module's import has zero side effects on privileged subsystems —
    it only seeds the catalog of proposals.
  - Adding a capability here is the ONLY way the registry knows about it;
    forgetting to register is fail-safe (capability simply doesn't exist).
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.contracts.god_mode import (
    GodCapability,
    GodCapabilityBlastRadius,
)
from mcoi_runtime.core.god_mode_engine import (
    GodModeEngine,
    set_engine,
)
from mcoi_runtime.core.god_mode_registry import (
    GodModeRegistry,
    get_registry,
)


# ---------------------------------------------------------------------------
# Per-module god capability proposals
# ---------------------------------------------------------------------------
# All start DORMANT. Each one needs an explicit operator registration agreement
# (justification ≥ default 50 chars) before it becomes invocable.


_CAPABILITY_PROPOSALS: tuple[GodCapability, ...] = (
    # data
    GodCapability(
        module="data",
        name="purge_tenant_now",
        description=(
            "Delete all data for a tenant immediately, bypassing retention "
            "windows and standard purge approvals."
        ),
        blast_radius=GodCapabilityBlastRadius.CATASTROPHIC,
        bypasses=("retention_window", "purge_approval", "lineage_freeze"),
        default_ttl_seconds=60,
        min_justification_chars=120,
        one_shot=True,
        requires_dual_control=True,
    ),
    GodCapability(
        module="data",
        name="force_unlock_lineage",
        description=(
            "Unlock a frozen lineage chain to permit out-of-band edits. "
            "Receipts on subsequent edits will be flagged with a god-mode "
            "lineage marker."
        ),
        blast_radius=GodCapabilityBlastRadius.PLATFORM,
        bypasses=("lineage_freeze",),
        default_ttl_seconds=120,
    ),
    # rbac
    GodCapability(
        module="rbac",
        name="impersonate_user",
        description=(
            "Act as another identity for a single privileged operation. "
            "Receipt records both the operator and the impersonated identity."
        ),
        blast_radius=GodCapabilityBlastRadius.PLATFORM,
        bypasses=("identity_binding", "actor_attribution"),
        default_ttl_seconds=300,
        requires_session=True,
        one_shot=False,
    ),
    GodCapability(
        module="rbac",
        name="grant_role_bypass_approval",
        description=(
            "Grant a role binding without the standard approval workflow. "
            "Use only for break-glass scenarios; the receipt is the audit "
            "trail of record."
        ),
        blast_radius=GodCapabilityBlastRadius.PLATFORM,
        bypasses=("role_grant_approval",),
        default_ttl_seconds=120,
        min_justification_chars=120,
    ),
    # governance
    GodCapability(
        module="governance",
        name="force_release_blocked",
        description=(
            "Release a governance-blocked execution that would otherwise stay "
            "blocked. Any constraint violation flagged at block time is "
            "carried into the receipt."
        ),
        blast_radius=GodCapabilityBlastRadius.PLATFORM,
        bypasses=("governance_block", "blast_radius_check"),
        default_ttl_seconds=60,
    ),
    GodCapability(
        module="governance",
        name="unfreeze_audit_record",
        description=(
            "Unfreeze a previously frozen audit record so that an amendment "
            "can be appended. The original frozen content is preserved as a "
            "predecessor link in the receipt."
        ),
        blast_radius=GodCapabilityBlastRadius.PLATFORM,
        bypasses=("audit_freeze",),
        default_ttl_seconds=60,
        min_justification_chars=120,
    ),
    # temporal
    GodCapability(
        module="temporal_scheduler",
        name="force_admit",
        description=(
            "Force admission control to accept a job that fails the normal "
            "rate-limit / window / blast-radius checks."
        ),
        blast_radius=GodCapabilityBlastRadius.TENANT,
        bypasses=("admission_control", "rate_limit_window"),
        default_ttl_seconds=30,
    ),
    GodCapability(
        module="temporal_scheduler",
        name="cancel_inflight_with_residue",
        description=(
            "Cancel an inflight scheduled job and accept the residue (partial "
            "side effects) explicitly. Receipt records what was completed."
        ),
        blast_radius=GodCapabilityBlastRadius.TENANT,
        bypasses=("inflight_cancellation_safety",),
        default_ttl_seconds=60,
    ),
    # constructs
    GodCapability(
        module="constructs",
        name="force_promote_construct",
        description=(
            "Promote a construct past governance gates without the normal "
            "phi-agent filter approval."
        ),
        blast_radius=GodCapabilityBlastRadius.PLATFORM,
        bypasses=("phi_agent_filter", "construct_promotion_gate"),
        default_ttl_seconds=120,
    ),
    # policy
    GodCapability(
        module="policy",
        name="override_active_version",
        description=(
            "Force a specific policy version to be active, overriding the "
            "version selection algorithm."
        ),
        blast_radius=GodCapabilityBlastRadius.PLATFORM,
        bypasses=("policy_version_selection",),
        default_ttl_seconds=300,
        min_justification_chars=120,
    ),
    # replay
    GodCapability(
        module="replay",
        name="mutate_recorder",
        description=(
            "Modify the in-process replay recorder buffer. The receipt "
            "captures the exact mutation diff."
        ),
        blast_radius=GodCapabilityBlastRadius.PLATFORM,
        bypasses=("replay_immutability",),
        default_ttl_seconds=120,
    ),
    # secrets
    GodCapability(
        module="secrets",
        name="reveal_redacted_in_audit",
        description=(
            "Reveal redacted secret values in an audit detail payload to a "
            "specific operator for incident response."
        ),
        blast_radius=GodCapabilityBlastRadius.PLATFORM,
        bypasses=("secret_redaction",),
        default_ttl_seconds=60,
        min_justification_chars=200,
    ),
    # mfidel
    GodCapability(
        module="mfidel",
        name="unbox_container",
        description=(
            "Unbox an mfidel container to expose its contents directly. The "
            "receipt records every field surfaced."
        ),
        blast_radius=GodCapabilityBlastRadius.LOCAL,
        bypasses=("mfidel_container_seal",),
        default_ttl_seconds=300,
    ),
    # mil_audit
    GodCapability(
        module="mil_audit",
        name="unfreeze_record",
        description=(
            "Unfreeze a MIL audit record. The receipt is appended as an "
            "amendment marker — the frozen original remains canonical."
        ),
        blast_radius=GodCapabilityBlastRadius.PLATFORM,
        bypasses=("mil_audit_freeze",),
        default_ttl_seconds=60,
        min_justification_chars=120,
    ),
)


def install_default_capabilities(registry: GodModeRegistry | None = None) -> int:
    """Seed the registry with the per-module capability proposals.

    Returns the number of capabilities registered. Idempotent — re-running
    against the same registry does nothing.
    """
    target = registry if registry is not None else get_registry()
    count = 0
    for capability in _CAPABILITY_PROPOSALS:
        if not target.has_capability(*capability.key):
            target.register_capability(capability)
            count += 1
    return count


def install_god_mode(
    deps: Any,
    audit_trail: Any | None = None,
    metrics: Any | None = None,
) -> GodModeEngine:
    """Install god-mode subsystem onto the deps container.

    - Seeds the registry with default capability proposals (DORMANT).
    - Constructs an engine bound to the audit_trail and metrics sinks
      (if provided) and registers it on `deps`.
    - Idempotent: subsequent calls reuse the existing engine.
    """
    install_default_capabilities()
    try:
        existing = deps.get("god_mode_engine")  # type: ignore[attr-defined]
    except Exception:
        existing = None
    if isinstance(existing, GodModeEngine):
        return existing
    if metrics is None and hasattr(deps, "get"):
        try:
            metrics = deps.get("metrics")
        except Exception:
            metrics = None
    engine = GodModeEngine(receipt_sink=audit_trail, metrics_sink=metrics)
    set_engine(engine)
    if hasattr(deps, "set"):
        deps.set("god_mode_engine", engine)
        deps.set("god_mode_registry", get_registry())
    return engine


def default_capability_proposals() -> tuple[GodCapability, ...]:
    """Read-only view of the proposals shipped with the platform."""
    return _CAPABILITY_PROPOSALS


__all__ = [
    "install_default_capabilities",
    "install_god_mode",
    "default_capability_proposals",
]
