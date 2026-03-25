"""Phase 127A — Pilot Target List and Scoring."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from mcoi_runtime.pilot.customer_profile import PilotCustomerProfile, evaluate_fit

@dataclass
class ScoredTarget:
    profile: PilotCustomerProfile
    fit_score: int
    fit_level: str  # "strong", "moderate", "weak"
    rank: int = 0
    designation: str = ""  # "primary", "backup", "deferred"

class TargetListBuilder:
    """Builds and ranks a pilot target list."""

    def __init__(self):
        self._targets: list[ScoredTarget] = []

    def add_candidate(self, profile: PilotCustomerProfile) -> ScoredTarget:
        evaluation = evaluate_fit(profile)
        target = ScoredTarget(
            profile=profile,
            fit_score=evaluation["score"],
            fit_level=evaluation["fit"],
        )
        self._targets.append(target)
        return target

    def rank_and_designate(self) -> list[ScoredTarget]:
        sorted_targets = sorted(self._targets, key=lambda t: t.fit_score, reverse=True)
        for i, t in enumerate(sorted_targets):
            object.__setattr__(t, "rank", i + 1)
            if i == 0:
                object.__setattr__(t, "designation", "primary")
            elif i <= 2:
                object.__setattr__(t, "designation", "backup")
            else:
                object.__setattr__(t, "designation", "deferred")
        self._targets = sorted_targets
        return sorted_targets

    @property
    def primary(self) -> ScoredTarget | None:
        for t in self._targets:
            if t.designation == "primary":
                return t
        return None

    @property
    def backups(self) -> tuple[ScoredTarget, ...]:
        return tuple(t for t in self._targets if t.designation == "backup")

    @property
    def all_targets(self) -> tuple[ScoredTarget, ...]:
        return tuple(self._targets)

    def summary(self) -> dict[str, Any]:
        return {
            "total_candidates": len(self._targets),
            "primary": self.primary.profile.organization_name if self.primary else None,
            "backups": [t.profile.organization_name for t in self.backups],
            "scores": [(t.profile.organization_name, t.fit_score, t.designation) for t in self._targets],
        }
