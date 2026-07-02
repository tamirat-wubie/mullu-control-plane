"""Capability promotion ladder.

Purpose: define the canonical L0-L9 capability promotion ladder and derive a
passport-visible level from governed capability pack entries.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: governed capability fabric contracts.
Invariants:
  - Promotion levels are read-model classifications, not execution authority.
  - Live connector and repository mutation levels require evidence gates.
  - Approval-bound levels expose approval obligations explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityRegistryEntry,
    GovernedCapabilityRecord,
)


CAPABILITY_PROMOTION_LADDER_ID = "mullu.capability_promotion_ladder.v1"


@dataclass(frozen=True, slots=True)
class PromotionLevel:
    """One non-authoritative capability promotion level."""

    level: int
    name: str
    summary: str
    required_gates: tuple[str, ...]
    required_evidence: tuple[str, ...]
    requires_operator_approval: bool
    requires_receipt: bool
    requires_rollback: bool
    requires_live_witness: bool

    @property
    def level_id(self) -> str:
        """Return the stable L-level identifier."""

        return f"L{self.level}"


def default_capability_promotion_ladder() -> tuple[PromotionLevel, ...]:
    """Return the canonical L0-L9 capability promotion ladder."""

    return (
        PromotionLevel(
            0,
            "read-only",
            "Inspect repository or local evidence without mutation.",
            ("gate.evidence.intake",),
            ("source_ref",),
            False,
            False,
            False,
            False,
        ),
        PromotionLevel(
            1,
            "draft-only",
            "Prepare drafts without publishing, sending, or writing live state.",
            ("gate.evidence.intake", "gate.receipt.append"),
            ("draft_receipt",),
            False,
            True,
            False,
            False,
        ),
        PromotionLevel(
            2,
            "proposal-only",
            "Prepare proposals, plans, read models, and proof packets without mutation.",
            ("gate.evidence.intake", "gate.evidence.verification", "gate.receipt.append"),
            ("proposal_receipt", "verification_ref"),
            False,
            True,
            False,
            False,
        ),
        PromotionLevel(
            3,
            "sandbox-write",
            "Write only inside a controlled local sandbox or generated artifact boundary.",
            ("gate.evidence.intake", "gate.workspace.write", "gate.receipt.append", "gate.rollback.required"),
            ("sandbox_receipt", "rollback_plan"),
            True,
            True,
            True,
            False,
        ),
        PromotionLevel(
            4,
            "test-run",
            "Run bounded local tests or quality gates with receipts and rollback proof.",
            ("gate.evidence.intake", "gate.evidence.verification", "gate.receipt.append", "gate.rollback.required"),
            ("test_receipt", "rollback_plan"),
            True,
            True,
            True,
            False,
        ),
        PromotionLevel(
            5,
            "pr-preview",
            "Prepare pull request preview evidence without branch push or PR creation.",
            ("gate.evidence.intake", "gate.evidence.verification", "gate.receipt.append", "gate.operator.review"),
            ("pr_preview_packet", "rollback_plan"),
            True,
            True,
            True,
            False,
        ),
        PromotionLevel(
            6,
            "pr-create-with-approval",
            "Create a pull request only after explicit approval and repository effect receipts.",
            ("gate.approval.required", "gate.evidence.verification", "gate.receipt.append", "gate.rollback.required"),
            ("approval_decision_receipt", "pr_creation_receipt", "rollback_plan"),
            True,
            True,
            True,
            False,
        ),
        PromotionLevel(
            7,
            "merge-request-with-approval",
            "Request merge only after approval, CI evidence, and rollback or recovery proof.",
            ("gate.approval.required", "gate.evidence.verification", "gate.receipt.append", "gate.rollback.required"),
            ("approval_decision_receipt", "ci_receipt", "merge_request_receipt", "rollback_plan"),
            True,
            True,
            True,
            False,
        ),
        PromotionLevel(
            8,
            "live-connector-read",
            "Read through a live credentialed connector with lease and live evidence.",
            ("gate.connector.lease", "gate.evidence.verification", "gate.receipt.append"),
            ("connector_lease_receipt", "live_read_receipt"),
            True,
            True,
            False,
            True,
        ),
        PromotionLevel(
            9,
            "live-connector-write",
            "Write through a live connector only with approval, receipts, and recovery proof.",
            ("gate.connector.lease", "gate.approval.required", "gate.evidence.verification", "gate.receipt.append", "gate.rollback.required"),
            ("approval_decision_receipt", "live_write_receipt", "recovery_receipt"),
            True,
            True,
            True,
            True,
        ),
    )


def promotion_level_for_entry(
    entry: CapabilityRegistryEntry,
    governed: GovernedCapabilityRecord,
) -> PromotionLevel:
    """Derive the canonical promotion level for a governed capability entry."""

    if not isinstance(entry, CapabilityRegistryEntry):
        raise ValueError("entry_must_be_capability_registry_entry")
    if not isinstance(governed, GovernedCapabilityRecord):
        raise ValueError("governed_must_be_governed_capability_record")

    levels = {level.level: level for level in default_capability_promotion_ladder()}
    capability_id = entry.capability_id.lower()
    domain = entry.domain.lower()
    effects = _joined_effects(entry)
    connector_like = _connector_like(entry, governed)

    if _is_merge_request(capability_id, effects):
        return levels[7]
    if _is_draft(capability_id, effects):
        return levels[1]
    if _is_pr_preview(capability_id, effects):
        return levels[5]
    if _is_pr_creation(capability_id, effects):
        return levels[6]
    if _is_test_run(capability_id, effects):
        return levels[4]
    if connector_like and governed.world_mutating:
        return levels[9]
    if connector_like and governed.read_only:
        return levels[8]
    if _is_proposal(capability_id, effects):
        return levels[2]
    if _is_sandbox_write(domain, effects, governed):
        return levels[3]
    if governed.read_only:
        return levels[0]
    if governed.world_mutating:
        return levels[3]
    return levels[2]


def promotion_level_projection(
    entry: CapabilityRegistryEntry,
    governed: GovernedCapabilityRecord,
) -> dict[str, Any]:
    """Return a JSON-ready promotion level projection for a passport."""

    level = promotion_level_for_entry(entry, governed)
    return {
        "promotion_ladder_id": CAPABILITY_PROMOTION_LADDER_ID,
        "current_promotion_level": level.level_id,
        "promotion_level_number": level.level,
        "promotion_level_name": level.name,
        "promotion_level_summary": level.summary,
        "promotion_required_gates": list(level.required_gates),
        "promotion_required_evidence": list(level.required_evidence),
        "promotion_requires_operator_approval": level.requires_operator_approval,
        "promotion_requires_receipt": level.requires_receipt,
        "promotion_requires_rollback": level.requires_rollback,
        "promotion_requires_live_witness": level.requires_live_witness,
        "promotion_level_is_not_execution_authority": True,
    }


def validate_capability_promotion_ladder(
    levels: tuple[PromotionLevel, ...] | None = None,
) -> tuple[str, ...]:
    """Return validation errors for a promotion ladder."""

    effective_levels = levels or default_capability_promotion_ladder()
    errors: list[str] = []
    observed = tuple(level.level for level in effective_levels)
    if observed != tuple(range(10)):
        errors.append("promotion_levels_must_be_consecutive_L0_through_L9")
    for level in effective_levels:
        if not level.required_gates:
            errors.append(f"{level.level_id}:required_gates_missing")
        if level.level >= 1 and not level.requires_receipt:
            errors.append(f"{level.level_id}:receipt_required_after_read_only")
        if level.level in {3, 4, 5, 6, 7, 9} and not level.requires_rollback:
            errors.append(f"{level.level_id}:rollback_required_for_effect_boundary")
        if level.level in {3, 4, 5, 6, 7, 8, 9} and not level.requires_operator_approval:
            errors.append(f"{level.level_id}:approval_required_for_effect_boundary")
        if level.level in {8, 9} and not level.requires_live_witness:
            errors.append(f"{level.level_id}:live_witness_required_for_connector_boundary")
    return tuple(errors)


def _joined_effects(entry: CapabilityRegistryEntry) -> str:
    return " ".join(
        (
            entry.capability_id,
            entry.domain,
            *entry.effect_model.expected_effects,
            *entry.effect_model.forbidden_effects,
        )
    ).lower()


def _connector_like(entry: CapabilityRegistryEntry, governed: GovernedCapabilityRecord) -> bool:
    domain = entry.domain.lower()
    plane = entry.isolation_profile.execution_plane.lower()
    secret_scope = entry.isolation_profile.secret_scope.lower()
    return bool(
        domain in {"communication", "connector", "financial", "messaging", "phone"}
        or governed.allowed_networks
        or "connector" in plane
        or "worker" in plane
        or "oauth" in secret_scope
        or "provider" in secret_scope
    )


def _is_draft(capability_id: str, effects: str) -> bool:
    return "draft" in capability_id or "draft" in effects


def _is_proposal(capability_id: str, effects: str) -> bool:
    markers = ("proposal", "plan", "preview", "readiness", "suggest", "classify", "analyze", "summary")
    return any(marker in capability_id or marker in effects for marker in markers)


def _is_sandbox_write(domain: str, effects: str, governed: GovernedCapabilityRecord) -> bool:
    if not governed.world_mutating:
        return False
    markers = ("workspace", "file", "artifact", "docx", "pdf", "spreadsheet", "patch")
    return domain in {"computer", "document", "software_dev", "creative"} or any(marker in effects for marker in markers)


def _is_test_run(capability_id: str, effects: str) -> bool:
    markers = ("test", "quality_gate", "quality_gates", "change.run")
    return any(marker in capability_id or marker in effects for marker in markers)


def _is_pr_preview(capability_id: str, effects: str) -> bool:
    markers = ("pr_candidate", "review_packet", "branch_candidate", "pr_preview")
    return any(marker in capability_id or marker in effects for marker in markers)


def _is_pr_creation(capability_id: str, effects: str) -> bool:
    markers = ("open_pull_request", "pull_request_opened", "pr_create", "pr_creation")
    return any(marker in capability_id or marker in effects for marker in markers)


def _is_merge_request(capability_id: str, effects: str) -> bool:
    return "merge" in capability_id or "merge" in effects
