"""Phase 162 — Self-Serve Enterprise Expansion / Bundle Upgrade Paths."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

# 162A — Pack-to-Bundle Mapping
PACK_TO_BUNDLE_MAP: dict[str, str] = {
    "regulated_ops": "regulated_financial_bundle",
    "enterprise_service": "service_regulated_bundle",
    "financial_control": "regulated_financial_bundle",
    "factory_quality": "industrial_suite",
    "healthcare": "healthcare_financial_bundle",
    "supply_chain": "industrial_suite",
    "public_sector": "public_sector_bundle",
    "research_lab": "research_lab_bundle",
}

BUNDLE_SAVINGS: dict[str, float] = {
    "regulated_financial_bundle": 1200.0,
    "service_regulated_bundle": 1000.0,
    "industrial_suite": 1500.0,
    "healthcare_financial_bundle": 1100.0,
    "public_sector_bundle": 900.0,
    "research_lab_bundle": 800.0,
}

# 162B — Bundle Upgrade Offer
@dataclass
class BundleUpgradeOffer:
    current_pack: str
    recommended_bundle: str
    monthly_savings: float
    reason: str

def recommend_bundle_upgrade(
    pack: str,
    activation_rate: float,
    satisfaction: float,
    months_active: int,
) -> BundleUpgradeOffer | None:
    if activation_rate < 0.6 or satisfaction < 7 or months_active < 2:
        return None
    bundle = PACK_TO_BUNDLE_MAP.get(pack)
    if not bundle:
        return None
    savings = BUNDLE_SAVINGS.get(bundle, 0.0)
    return BundleUpgradeOffer(
        current_pack=pack,
        recommended_bundle=bundle,
        monthly_savings=savings,
        reason=f"High activation ({activation_rate:.0%}), satisfaction {satisfaction}/10, {months_active}mo tenure",
    )

# 162C — In-Product Expansion Engine
@dataclass
class InProductExpansionEngine:
    _recommended: dict[str, BundleUpgradeOffer] = field(default_factory=dict)
    _accepted: set[str] = field(default_factory=set)
    _declined: set[str] = field(default_factory=set)

    def suggest(self, account_id: str, pack: str, metrics: dict[str, Any]) -> BundleUpgradeOffer | None:
        offer = recommend_bundle_upgrade(
            pack,
            metrics.get("activation_rate", 0.0),
            metrics.get("satisfaction", 0.0),
            metrics.get("months_active", 0),
        )
        if offer:
            self._recommended[account_id] = offer
        return offer

    def accept(self, account_id: str) -> None:
        if account_id in self._recommended:
            self._accepted.add(account_id)
            self._declined.discard(account_id)

    def decline(self, account_id: str) -> None:
        if account_id in self._recommended:
            self._declined.add(account_id)
            self._accepted.discard(account_id)

    @property
    def conversion_rate(self) -> float:
        total = len(self._recommended)
        return len(self._accepted) / total if total else 0.0

    def summary(self) -> dict[str, Any]:
        return {
            "recommended": len(self._recommended),
            "accepted": len(self._accepted),
            "declined": len(self._declined),
            "pending": len(self._recommended) - len(self._accepted) - len(self._declined),
            "conversion_rate": round(self.conversion_rate, 4),
        }

# 162D — Low-Touch Bundle Flow
class LowTouchBundleFlow:
    def qualify_for_bundle(
        self,
        account_id: str,
        pack: str,
        activation: float,
        satisfaction: float,
    ) -> str:
        if pack not in PACK_TO_BUNDLE_MAP:
            return "not_ready"
        if activation >= 0.7 and satisfaction >= 8:
            return "eligible"
        if activation >= 0.5 and satisfaction >= 6:
            return "sales_assist"
        return "not_ready"
