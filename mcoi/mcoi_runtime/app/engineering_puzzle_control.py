"""Purpose: control-surface adapter for engineering puzzle kernel workflows.
Governance scope: JSON-like request validation, contract construction, and
JSON-safe response envelopes for governed arrangement search.
Dependencies: engineering puzzle contracts, integration facade, event spine.
Invariants:
  - Incoming payloads are validated into contract objects before execution.
  - Missing required nested objects fail closed with explicit ValueError.
  - Responses expose verdict, puzzle, judgment, and event lineage explicitly.
  - This module does not register HTTP routes or mutate global server state.
"""

from __future__ import annotations

from typing import Any, Mapping

from mcoi_runtime.contracts.engineering_puzzle import (
    CandidateArrangement,
    EngineeringPuzzle,
    ObserverNode,
    VerificationWitness,
)
from mcoi_runtime.core.engineering_puzzle_integration import EngineeringPuzzleIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine


def _require_mapping(payload: Mapping[str, Any], field_name: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return payload


def _required(payload: Mapping[str, Any], field_name: str) -> Any:
    if field_name not in payload:
        raise ValueError(f"{field_name} is required")
    return payload[field_name]


def _optional_tuple(payload: Mapping[str, Any], field_name: str) -> tuple[Any, ...]:
    value = payload.get(field_name, ())
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    raise ValueError(f"{field_name} must be a sequence")


def _optional_mapping(
    payload: Mapping[str, Any],
    field_name: str,
) -> Mapping[str, Any]:
    value = payload.get(field_name, {})
    if value is None:
        return {}
    return _require_mapping(value, field_name)


def _optional_bool(
    payload: Mapping[str, Any],
    field_name: str,
    default: bool,
) -> bool:
    value = payload.get(field_name, default)
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _optional_float(
    payload: Mapping[str, Any],
    field_name: str,
    default: float,
) -> float:
    value = payload.get(field_name, default)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number")
    return float(value)


def build_observer_node(payload: Mapping[str, Any]) -> ObserverNode:
    """Build an observer node from a JSON-like mapping."""

    payload = _require_mapping(payload, "observer")
    return ObserverNode(
        observer_id=_required(payload, "observer_id"),
        invariants=_optional_tuple(payload, "invariants"),
        rules=_optional_tuple(payload, "rules"),
        assumptions=_optional_tuple(payload, "assumptions"),
        known_unknowns=_optional_tuple(payload, "known_unknowns"),
        risk_margins=_optional_tuple(payload, "risk_margins"),
        fragile_points=_optional_tuple(payload, "fragile_points"),
        interfaces=_optional_tuple(payload, "interfaces"),
        history_refs=_optional_tuple(payload, "history_refs"),
    )


def build_verification_witness(
    payload: Mapping[str, Any] | None,
) -> VerificationWitness | None:
    """Build a dual verification witness when supplied."""

    if payload is None:
        return None
    payload = _require_mapping(payload, "witness")
    return VerificationWitness(
        witness_id=_required(payload, "witness_id"),
        model_evidence=_optional_tuple(payload, "model_evidence"),
        observation_evidence=_optional_tuple(payload, "observation_evidence"),
        prediction=_required(payload, "prediction"),
        observation=_required(payload, "observation"),
        mismatch_margin=_optional_float(payload, "mismatch_margin", 0.0),
        threshold=_optional_float(payload, "threshold", 0.0),
        passed=_optional_bool(payload, "passed", False),
    )


def build_engineering_puzzle(payload: Mapping[str, Any]) -> EngineeringPuzzle:
    """Build an engineering puzzle episode from a JSON-like mapping."""

    payload = _require_mapping(payload, "puzzle")
    return EngineeringPuzzle(
        invariants=_optional_tuple(payload, "invariants"),
        rules=_optional_tuple(payload, "rules"),
        state=_optional_mapping(payload, "state"),
        interfaces=_optional_tuple(payload, "interfaces"),
        history=_optional_tuple(payload, "history"),
        goal=_required(payload, "goal"),
        episode_model_hash=_required(payload, "episode_model_hash"),
        observer=build_observer_node(_required(payload, "observer")),
        witness=build_verification_witness(payload.get("witness")),
    )


def build_candidate_arrangement(payload: Mapping[str, Any]) -> CandidateArrangement:
    """Build a candidate arrangement from a JSON-like mapping."""

    payload = _require_mapping(payload, "candidate")
    return CandidateArrangement(
        candidate_id=_required(payload, "candidate_id"),
        state_delta=_optional_mapping(payload, "state_delta"),
        filter_results=_required(payload, "filter_results"),
        confidence=_optional_float(payload, "confidence", 0.0),
        authority_ref=payload.get("authority_ref", ""),
        governance_certified=_optional_bool(payload, "governance_certified", False),
        rollback_plan=_required(payload, "rollback_plan"),
        verification_plan=_required(payload, "verification_plan"),
        assumptions=_optional_tuple(payload, "assumptions"),
        unknowns=_optional_tuple(payload, "unknowns"),
        rejected_alternatives=_optional_tuple(payload, "rejected_alternatives"),
        fragile=_optional_bool(payload, "fragile", False),
        witness=build_verification_witness(payload.get("witness")),
    )


class EngineeringPuzzleControlSurface:
    """JSON-like control surface for engineering puzzle workflows."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        self._integration = EngineeringPuzzleIntegration(event_spine)

    def decide_goal_delta(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Run goal-delta governance from a request payload."""

        payload = _require_mapping(payload, "payload")
        result = self._integration.decide_goal_delta(
            build_engineering_puzzle(_required(payload, "puzzle")),
            _required(payload, "proposed_goal"),
            satisfaction_predicate_equivalent=_optional_bool(
                payload,
                "satisfaction_predicate_equivalent",
                False,
            ),
            new_episode_model_hash=payload.get("new_episode_model_hash", ""),
            fork_event_id=payload.get("fork_event_id", ""),
        )
        return {
            "kind": result["decision"].kind.value,
            "active_puzzle": result["active_puzzle"].to_json_dict(),
            "closed_puzzle": (
                None
                if result["closed_puzzle"] is None
                else result["closed_puzzle"].to_json_dict()
            ),
            "judgment": result["judgment"].to_json_dict(),
            "event": result["event"].to_json_dict(),
            "governed": True,
        }

    def judge_candidate(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Run candidate governance from a request payload."""

        payload = _require_mapping(payload, "payload")
        result = self._integration.judge_candidate(
            build_engineering_puzzle(_required(payload, "puzzle")),
            build_candidate_arrangement(_required(payload, "candidate")),
            confidence_floor=_optional_float(payload, "confidence_floor", 0.0),
        )
        return {
            "puzzle": result["puzzle"].to_json_dict(),
            "judgment": result["judgment"].to_json_dict(),
            "event": result["event"].to_json_dict(),
            "governed": True,
        }
