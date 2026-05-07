"""Gateway economic intelligence foundation.

Purpose: rank admitted operational actions by explicit utility terms.
Governance scope: utility scoring, blocked-route evidence, policy preservation,
    and operator-facing economic routing snapshots.
Dependencies: dataclasses, decimal, enum, typing, and command-spine hashing.
Invariants:
  - The engine chooses only among actions admitted by policy and authority.
  - A cheaper route cannot bypass control, tenant, evidence, or risk gates.
  - Utility terms are explicit, non-negative, and hash-bound.
  - Economic decisions are advisory routing records, not execution authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from typing import Any

from gateway.command_spine import canonical_hash


class EconomicVerdict(StrEnum):
    SELECT = "select"
    DENY = "deny"
    REVIEW = "review"


class EconomicRiskTier(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_RISK_MULTIPLIER = {
    EconomicRiskTier.LOW: Decimal("1.00"),
    EconomicRiskTier.MEDIUM: Decimal("1.50"),
    EconomicRiskTier.HIGH: Decimal("2.50"),
    EconomicRiskTier.CRITICAL: Decimal("4.00"),
}


@dataclass(frozen=True, slots=True)
class UtilityWeights:
    value_weight: Decimal = Decimal("1.00")
    model_cost_weight: Decimal = Decimal("1.00")
    tool_cost_weight: Decimal = Decimal("1.00")
    latency_cost_weight: Decimal = Decimal("1.00")
    risk_cost_weight: Decimal = Decimal("1.00")
    human_review_cost_weight: Decimal = Decimal("1.00")
    failure_compensation_cost_weight: Decimal = Decimal("1.00")

    def __post_init__(self) -> None:
        for name in self.__dataclass_fields__:
            object.__setattr__(self, name, _money(getattr(self, name), name))

    def to_json_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class EconomicActionCandidate:
    candidate_id: str
    tenant_id: str
    action_ref: str
    capability_ref: str
    policy_verdict: str
    authority_verdict: str
    budget_verdict: str
    evidence_refs: tuple[str, ...]
    expected_value_usd: Decimal
    model_cost_usd: Decimal
    tool_cost_usd: Decimal
    latency_cost_usd: Decimal
    risk_cost_usd: Decimal
    human_review_cost_usd: Decimal
    failure_compensation_cost_usd: Decimal
    risk_tier: EconomicRiskTier
    control_admitted: bool
    candidate_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("candidate_id", "tenant_id", "action_ref", "capability_ref"):
            _require_text(getattr(self, name), name)
        for name in ("policy_verdict", "authority_verdict", "budget_verdict"):
            verdict = str(getattr(self, name)).strip()
            if verdict not in {"allow", "deny", "review"}:
                raise ValueError(f"{name}_invalid")
            object.__setattr__(self, name, verdict)
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs"))
        for name in (
            "expected_value_usd",
            "model_cost_usd",
            "tool_cost_usd",
            "latency_cost_usd",
            "risk_cost_usd",
            "human_review_cost_usd",
            "failure_compensation_cost_usd",
        ):
            object.__setattr__(self, name, _money(getattr(self, name), name))
        if not isinstance(self.risk_tier, EconomicRiskTier):
            raise ValueError("risk_tier_invalid")
        if not isinstance(self.control_admitted, bool):
            raise ValueError("control_admitted_boolean_required")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class EconomicRoutingDecision:
    decision_id: str
    tenant_id: str
    verdict: EconomicVerdict
    selected_candidate_id: str | None
    selected_action_ref: str | None
    reason: str
    utility_score: Decimal
    blocked_candidate_ids: tuple[str, ...]
    blocked_reasons: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    decision_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("decision_id", "tenant_id", "reason"):
            _require_text(getattr(self, name), name)
        if not isinstance(self.verdict, EconomicVerdict):
            raise ValueError("economic_verdict_invalid")
        if self.verdict is EconomicVerdict.SELECT:
            _require_text(self.selected_candidate_id or "", "selected_candidate_id")
            _require_text(self.selected_action_ref or "", "selected_action_ref")
        if self.verdict is not EconomicVerdict.SELECT and self.selected_candidate_id is not None:
            raise ValueError("non_select_decision_cannot_select_candidate")
        object.__setattr__(self, "utility_score", _signed_money(self.utility_score, "utility_score"))
        object.__setattr__(self, "blocked_candidate_ids", _normalize_text_tuple(self.blocked_candidate_ids, "blocked_candidate_ids", allow_empty=True))
        object.__setattr__(self, "blocked_reasons", _normalize_text_tuple(self.blocked_reasons, "blocked_reasons", allow_empty=True))
        object.__setattr__(self, "evidence_refs", _normalize_text_tuple(self.evidence_refs, "evidence_refs", allow_empty=True))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class EconomicIntelligenceSnapshot:
    snapshot_id: str
    candidates: tuple[EconomicActionCandidate, ...]
    decisions: tuple[EconomicRoutingDecision, ...]
    selected_count: int
    review_count: int
    denied_count: int
    blocked_candidate_count: int
    policy_override_allowed: bool
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        _require_text(self.snapshot_id, "snapshot_id")
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "decisions", tuple(self.decisions))
        for name in ("selected_count", "review_count", "denied_count", "blocked_candidate_count"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name}_non_negative")
        if self.policy_override_allowed is not False:
            raise ValueError("policy_override_must_not_be_allowed")
        actual_selected = sum(1 for decision in self.decisions if decision.verdict is EconomicVerdict.SELECT)
        actual_review = sum(1 for decision in self.decisions if decision.verdict is EconomicVerdict.REVIEW)
        actual_denied = sum(1 for decision in self.decisions if decision.verdict is EconomicVerdict.DENY)
        actual_blocked = len({candidate_id for decision in self.decisions for candidate_id in decision.blocked_candidate_ids})
        if self.selected_count != actual_selected:
            raise ValueError("selected_count_mismatch")
        if self.review_count != actual_review:
            raise ValueError("review_count_mismatch")
        if self.denied_count != actual_denied:
            raise ValueError("denied_count_mismatch")
        if self.blocked_candidate_count != actual_blocked:
            raise ValueError("blocked_candidate_count_mismatch")

    def to_json_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


class EconomicIntelligenceEngine:
    def __init__(self, *, snapshot_id: str = "economic-intelligence-snapshot") -> None:
        self._snapshot_id = snapshot_id
        self._candidates: dict[str, EconomicActionCandidate] = {}
        self._decisions: list[EconomicRoutingDecision] = []

    def register_candidate(self, candidate: EconomicActionCandidate) -> EconomicActionCandidate:
        stamped = _stamp_candidate(candidate)
        self._candidates[stamped.candidate_id] = stamped
        return stamped

    def route(
        self,
        *,
        tenant_id: str,
        candidate_ids: tuple[str, ...],
        weights: UtilityWeights | None = None,
        require_positive_utility: bool = True,
    ) -> EconomicRoutingDecision:
        _require_text(tenant_id, "tenant_id")
        weights = weights or UtilityWeights()
        requested_ids = _normalize_text_tuple(candidate_ids, "candidate_ids")
        candidates = tuple(self._candidates.get(candidate_id) for candidate_id in requested_ids)
        missing_ids = tuple(
            candidate_id
            for candidate_id, candidate in zip(requested_ids, candidates, strict=True)
            if candidate is None
        )
        present_candidates = tuple(candidate for candidate in candidates if candidate is not None)
        blocked: list[tuple[str, str]] = [(candidate_id, "candidate_missing") for candidate_id in missing_ids]
        admitted: list[tuple[Decimal, EconomicActionCandidate]] = []
        evidence_refs: set[str] = set()

        for candidate in present_candidates:
            evidence_refs.update(candidate.evidence_refs)
            reason = _blocked_reason(candidate, tenant_id)
            if reason:
                blocked.append((candidate.candidate_id, reason))
                continue
            admitted.append((_utility_score(candidate, weights), candidate))

        if not admitted:
            return self._record_decision(EconomicRoutingDecision(
                "pending", tenant_id, EconomicVerdict.DENY, None, None, "no_admitted_candidate",
                Decimal("0.00"), tuple(candidate_id for candidate_id, _reason in blocked),
                tuple(reason for _candidate_id, reason in blocked), tuple(sorted(evidence_refs)),
                metadata={"policy_override_allowed": False},
            ))

        admitted.sort(key=lambda item: (item[0], item[1].candidate_id), reverse=True)
        best_score, best_candidate = admitted[0]
        if require_positive_utility and best_score <= Decimal("0.00"):
            return self._record_decision(EconomicRoutingDecision(
                "pending", tenant_id, EconomicVerdict.REVIEW, None, None, "positive_utility_not_proven",
                best_score, tuple(candidate_id for candidate_id, _reason in blocked),
                tuple(reason for _candidate_id, reason in blocked), tuple(sorted(evidence_refs)),
                metadata={"best_candidate_id": best_candidate.candidate_id, "policy_override_allowed": False},
            ))

        return self._record_decision(EconomicRoutingDecision(
            "pending", tenant_id, EconomicVerdict.SELECT, best_candidate.candidate_id,
            best_candidate.action_ref, "highest_admitted_utility", best_score,
            tuple(candidate_id for candidate_id, _reason in blocked),
            tuple(reason for _candidate_id, reason in blocked),
            tuple(sorted(evidence_refs.union(best_candidate.evidence_refs))),
            metadata={"policy_override_allowed": False, "admitted_candidate_count": len(admitted), "weights": weights.to_json_dict()},
        ))

    def snapshot(self) -> EconomicIntelligenceSnapshot:
        blocked_ids = {candidate_id for decision in self._decisions for candidate_id in decision.blocked_candidate_ids}
        snapshot = EconomicIntelligenceSnapshot(
            snapshot_id=self._snapshot_id,
            candidates=tuple(sorted(self._candidates.values(), key=lambda item: item.candidate_id)),
            decisions=tuple(self._decisions),
            selected_count=sum(1 for decision in self._decisions if decision.verdict is EconomicVerdict.SELECT),
            review_count=sum(1 for decision in self._decisions if decision.verdict is EconomicVerdict.REVIEW),
            denied_count=sum(1 for decision in self._decisions if decision.verdict is EconomicVerdict.DENY),
            blocked_candidate_count=len(blocked_ids),
            policy_override_allowed=False,
        )
        payload = snapshot.to_json_dict()
        payload["snapshot_hash"] = ""
        return replace(snapshot, snapshot_hash=canonical_hash(payload))

    def _record_decision(self, decision: EconomicRoutingDecision) -> EconomicRoutingDecision:
        payload = decision.to_json_dict()
        payload["decision_hash"] = ""
        decision_hash = canonical_hash(payload)
        stamped = replace(decision, decision_id=f"economic-decision-{decision_hash[:16]}", decision_hash=decision_hash)
        self._decisions.append(stamped)
        return stamped


def economic_intelligence_snapshot_to_json_dict(snapshot: EconomicIntelligenceSnapshot) -> dict[str, Any]:
    return snapshot.to_json_dict()


def _blocked_reason(candidate: EconomicActionCandidate, tenant_id: str) -> str:
    if candidate.tenant_id != tenant_id:
        return "tenant_mismatch"
    if not candidate.control_admitted:
        return "control_not_admitted"
    if candidate.policy_verdict != "allow":
        return "policy_not_allowed"
    if candidate.authority_verdict != "allow":
        return "authority_not_allowed"
    if candidate.budget_verdict != "allow":
        return "budget_not_allowed"
    if candidate.risk_tier is EconomicRiskTier.CRITICAL:
        return "critical_risk_requires_operator_review"
    return ""


def _utility_score(candidate: EconomicActionCandidate, weights: UtilityWeights) -> Decimal:
    risk_cost = candidate.risk_cost_usd * _RISK_MULTIPLIER[candidate.risk_tier]
    return _signed_money(
        candidate.expected_value_usd * weights.value_weight
        - candidate.model_cost_usd * weights.model_cost_weight
        - candidate.tool_cost_usd * weights.tool_cost_weight
        - candidate.latency_cost_usd * weights.latency_cost_weight
        - risk_cost * weights.risk_cost_weight
        - candidate.human_review_cost_usd * weights.human_review_cost_weight
        - candidate.failure_compensation_cost_usd * weights.failure_compensation_cost_weight,
        "utility_score",
    )


def _stamp_candidate(candidate: EconomicActionCandidate) -> EconomicActionCandidate:
    payload = candidate.to_json_dict()
    payload["candidate_hash"] = ""
    return replace(candidate, candidate_hash=canonical_hash(payload))


def _money(value: Decimal | int | float | str, field_name: str) -> Decimal:
    decimal_value = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if decimal_value < Decimal("0.00"):
        raise ValueError(f"{field_name}_non_negative")
    return decimal_value


def _signed_money(value: Decimal | int | float | str, field_name: str) -> Decimal:
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception as exc:
        raise ValueError(f"{field_name}_decimal_required") from exc


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


def _json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return f"{value:.2f}"
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
