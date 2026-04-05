"""Phase 163 — Channel Marketplace / Partner App Ecosystem."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

CONTRIBUTION_KINDS = (
    "connector_pack",
    "deployment_template",
    "dashboard_kit",
    "regional_overlay",
    "compliance_overlay",
)

CONTRIBUTION_STATUSES = (
    "submitted",
    "approved",
    "rejected",
    "deprecated",
)

APPROVAL_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "connector_pack": ("security_review", "test_coverage"),
    "deployment_template": ("dry_run_validation", "documentation_review"),
    "dashboard_kit": ("ux_review", "data_accuracy_check"),
    "regional_overlay": ("locale_validation", "legal_review"),
    "compliance_overlay": ("framework_accuracy_audit", "legal_review"),
}


@dataclass
class PartnerContribution:
    contribution_id: str
    partner_id: str
    kind: str  # one of CONTRIBUTION_KINDS
    display_name: str
    status: str = "submitted"  # submitted / approved / rejected / deprecated
    quality_score: float = 0.0  # 0-10

    def __post_init__(self) -> None:
        if self.kind not in CONTRIBUTION_KINDS:
            raise ValueError("invalid contribution kind")
        if self.status not in CONTRIBUTION_STATUSES:
            raise ValueError("invalid contribution status")
        if not (0.0 <= self.quality_score <= 10.0):
            raise ValueError("quality_score must be between 0 and 10")


class EcosystemMarketplace:
    """Manages partner contributions lifecycle and quality controls."""

    def __init__(self) -> None:
        self._contributions: dict[str, PartnerContribution] = {}

    # ---- lifecycle ----------------------------------------------------------

    def submit_contribution(self, contrib: PartnerContribution) -> PartnerContribution:
        if contrib.contribution_id in self._contributions:
            raise ValueError("duplicate contribution")
        contrib.status = "submitted"
        self._contributions[contrib.contribution_id] = contrib
        return contrib

    def approve(self, contribution_id: str, quality_score: float) -> PartnerContribution:
        c = self._get(contribution_id)
        if c.status != "submitted":
            raise ValueError("contribution must be submitted before approval")
        if not (0.0 <= quality_score <= 10.0):
            raise ValueError("quality_score must be between 0 and 10")
        c.status = "approved"
        c.quality_score = quality_score
        return c

    def reject(self, contribution_id: str, reason: str = "") -> PartnerContribution:
        c = self._get(contribution_id)
        if c.status != "submitted":
            raise ValueError("contribution must be submitted before rejection")
        c.status = "rejected"
        return c

    def deprecate(self, contribution_id: str) -> PartnerContribution:
        c = self._get(contribution_id)
        if c.status != "approved":
            raise ValueError("contribution must be approved before deprecation")
        c.status = "deprecated"
        return c

    # ---- queries ------------------------------------------------------------

    def list_approved(self) -> list[PartnerContribution]:
        return [c for c in self._contributions.values() if c.status == "approved"]

    def by_kind(self, kind: str) -> list[PartnerContribution]:
        return [c for c in self._contributions.values() if c.kind == kind]

    def by_partner(self, partner_id: str) -> list[PartnerContribution]:
        return [c for c in self._contributions.values() if c.partner_id == partner_id]

    def quality_threshold_filter(self, min_score: float = 7.0) -> list[PartnerContribution]:
        return [c for c in self.list_approved() if c.quality_score >= min_score]

    def summary(self) -> dict[str, Any]:
        by_status: dict[str, int] = {}
        by_kind: dict[str, int] = {}
        for c in self._contributions.values():
            by_status[c.status] = by_status.get(c.status, 0) + 1
            by_kind[c.kind] = by_kind.get(c.kind, 0) + 1
        return {
            "total": len(self._contributions),
            "by_status": by_status,
            "by_kind": by_kind,
        }

    # ---- internals ----------------------------------------------------------

    def _get(self, contribution_id: str) -> PartnerContribution:
        try:
            return self._contributions[contribution_id]
        except KeyError:
            raise KeyError("unknown contribution")
