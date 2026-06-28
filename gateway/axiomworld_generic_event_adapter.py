"""AxiomWorld generic event adapter.

Purpose: Convert plain domain event payloads into governed AxiomWorld kernel
    calls for observations, claims, action proposals, and safe projections.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.axiomworld_kernel and gateway.world_state.
Invariants:
  - Adapter payloads never mutate world state directly.
  - Every observed symbol receives explicit evidence references.
  - Missing or malformed fields fail with bounded causal error codes.
  - Simulation and public/private projection scopes remain explicit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any, Mapping

from gateway.axiomworld_kernel import (
    AxiomActionProposal,
    AxiomDecision,
    AxiomObservationEvent,
    AxiomProjection,
    AxiomProjectionScope,
    AxiomReversibility,
    AxiomRiskLevel,
    AxiomWorldKernel,
    AxiomWorldReceipt,
)
from gateway.axiomworld_kernel import AxiomClaimProposal
from gateway.world_state import EvidenceRef, ValidityWindow, WorldState


@dataclass(frozen=True, slots=True)
class AxiomWorldGenericEventResult:
    """Adapter result for one generic world-state event."""

    event_id: str
    tenant_id: str
    decision: AxiomDecision
    receipts: tuple[AxiomWorldReceipt, ...]
    projection: AxiomProjection
    materialized_state: WorldState

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-oriented result without leaking private kernel internals."""
        return {
            "event_id": self.event_id,
            "tenant_id": self.tenant_id,
            "decision": self.decision.value,
            "receipts": [_json_ready(asdict(receipt)) for receipt in self.receipts],
            "projection": _json_ready(asdict(self.projection)),
            "materialized_state": _json_ready(asdict(self.materialized_state)),
        }


class AxiomWorldGenericEventAdapter:
    """Consume generic event payloads through an AxiomWorld kernel."""

    def __init__(self, kernel: AxiomWorldKernel | None = None) -> None:
        self._kernel = kernel or AxiomWorldKernel()

    @property
    def kernel(self) -> AxiomWorldKernel:
        """Return the bound kernel for tests and explicit integration."""
        return self._kernel

    def ingest(self, payload: Mapping[str, Any]) -> AxiomWorldGenericEventResult:
        """Normalize and ingest one generic world-state payload.

        Input contract:
          - `event_id`, `tenant_id`, `source`, `observed_at`
          - `evidence`: non-empty list of evidence objects
          - optional `symbol`, `claims`, `actions`, and `projection`
        Output contract:
          - all kernel receipts created during this adapter call
          - observer-scoped projection and materialized state
        Error contract:
          - raises `ValueError` with a bounded code for malformed input
        """
        event_id = _require_text(payload.get("event_id"), "event_id")
        tenant_id = _require_text(payload.get("tenant_id"), "tenant_id")
        source = _require_text(payload.get("source"), "source")
        observed_at = _require_text(payload.get("observed_at"), "observed_at")
        evidence_refs = _evidence_refs(payload.get("evidence"), default_source=source)

        receipt_start = len(self._kernel.receipts())
        symbol_payload = payload.get("symbol")
        if symbol_payload is not None:
            self._kernel.observe_event(
                _observation_event(
                    symbol_payload,
                    tenant_id=tenant_id,
                    source=source,
                    observed_at=observed_at,
                    evidence_refs=evidence_refs,
                )
            )

        for claim_payload in _mapping_items(payload.get("claims"), "claims"):
            self._kernel.propose_claim(
                _claim_proposal(
                    claim_payload,
                    tenant_id=tenant_id,
                    source=source,
                    observed_at=observed_at,
                    default_evidence_refs=evidence_refs,
                )
            )

        for action_payload in _mapping_items(payload.get("actions"), "actions"):
            action = _action_proposal(action_payload, tenant_id=tenant_id)
            self._kernel.propose_action(action)
            if _bool(action_payload.get("simulate"), default=False):
                self._kernel.simulate_action(action.action_id)

        projection_request = _projection_request(payload.get("projection"))
        projection = self._kernel.project(
            observer=projection_request["observer"],
            scope=projection_request["scope"],
            tenant_id=tenant_id,
        )
        state = self._kernel.materialize(tenant_id=tenant_id)
        receipts = self._kernel.receipts()[receipt_start:]
        return AxiomWorldGenericEventResult(
            event_id=event_id,
            tenant_id=tenant_id,
            decision=_summarize_decision(receipts),
            receipts=receipts,
            projection=projection,
            materialized_state=state,
        )


def _observation_event(
    payload: Any,
    *,
    tenant_id: str,
    source: str,
    observed_at: str,
    evidence_refs: tuple[EvidenceRef, ...],
) -> AxiomObservationEvent:
    mapping = _require_mapping(payload, "symbol")
    entity_id = _require_text(mapping.get("entity_id"), "symbol.entity_id")
    entity_type = _require_text(mapping.get("entity_type"), "symbol.entity_type")
    display_name = _require_text(mapping.get("display_name"), "symbol.display_name")
    stable_fingerprint = _require_mapping(
        mapping.get("stable_fingerprint"),
        "symbol.stable_fingerprint",
    )
    return AxiomObservationEvent(
        entity_id=entity_id,
        tenant_id=tenant_id,
        entity_type=entity_type,
        display_name=display_name,
        source=source,
        observed_at=observed_at,
        evidence_refs=evidence_refs,
        stable_fingerprint=dict(stable_fingerprint),
        attributes=dict(_optional_mapping(mapping.get("attributes"), "symbol.attributes")),
        aliases=tuple(_text_items(mapping.get("aliases"), "symbol.aliases")),
        scope=_scope(mapping.get("scope"), default=AxiomProjectionScope.INTERNAL),
        permissions=dict(_optional_mapping(mapping.get("permissions"), "symbol.permissions")),
        validity=_validity(mapping.get("validity"), observed_at),
    )


def _claim_proposal(
    payload: Mapping[str, Any],
    *,
    tenant_id: str,
    source: str,
    observed_at: str,
    default_evidence_refs: tuple[EvidenceRef, ...],
) -> AxiomClaimProposal:
    evidence_value = payload.get("evidence")
    if evidence_value is None:
        evidence_refs = default_evidence_refs
    else:
        evidence_refs = _evidence_refs(evidence_value, default_source=source, allow_empty=True)
    return AxiomClaimProposal(
        claim_id=_require_text(payload.get("claim_id"), "claim.claim_id"),
        tenant_id=tenant_id,
        subject_ref=_require_text(payload.get("subject_ref"), "claim.subject_ref"),
        predicate=_require_text(payload.get("predicate"), "claim.predicate"),
        object_value=_require_text(payload.get("object_value"), "claim.object_value"),
        source=source,
        observed_at=observed_at,
        evidence_refs=evidence_refs,
        scope=_scope(payload.get("scope"), default=AxiomProjectionScope.INTERNAL),
        simulated=_bool(payload.get("simulated"), default=False),
        allowed_for_planning=_bool(payload.get("allowed_for_planning"), default=True),
        allowed_for_execution=_bool(payload.get("allowed_for_execution"), default=False),
        validity=_validity(payload.get("validity"), observed_at),
    )


def _action_proposal(payload: Mapping[str, Any], *, tenant_id: str) -> AxiomActionProposal:
    return AxiomActionProposal(
        action_id=_require_text(payload.get("action_id"), "action.action_id"),
        tenant_id=tenant_id,
        actor=_require_text(payload.get("actor"), "action.actor"),
        intent=_require_text(payload.get("intent"), "action.intent"),
        target_ref=_require_text(payload.get("target_ref"), "action.target_ref"),
        risk_level=_risk(payload.get("risk_level")),
        reversibility=_reversibility(payload.get("reversibility")),
        permissions_required=tuple(
            _text_items(payload.get("permissions_required"), "action.permissions_required")
        ),
        preconditions=tuple(_text_items(payload.get("preconditions"), "action.preconditions")),
        expected_delta=dict(
            _optional_mapping(payload.get("expected_delta"), "action.expected_delta")
        ),
    )


def _evidence_refs(
    value: Any,
    *,
    default_source: str,
    allow_empty: bool = False,
) -> tuple[EvidenceRef, ...]:
    items = _mapping_items(value, "evidence", allow_empty=allow_empty)
    refs = tuple(
        EvidenceRef(
            evidence_id=_require_text(item.get("evidence_id"), "evidence.evidence_id"),
            evidence_type=_require_text(item.get("evidence_type"), "evidence.evidence_type"),
            source=_require_text(item.get("source", default_source), "evidence.source"),
            observed_at=_require_text(item.get("observed_at"), "evidence.observed_at"),
            uri=str(item.get("uri", "")),
            content_hash=str(item.get("content_hash", "")),
            metadata=dict(_optional_mapping(item.get("metadata"), "evidence.metadata")),
        )
        for item in items
    )
    if not refs and not allow_empty:
        raise ValueError("evidence_required")
    return refs


def _projection_request(value: Any) -> dict[str, Any]:
    if value is None:
        return {"observer": "generic_event_adapter", "scope": AxiomProjectionScope.INTERNAL}
    mapping = _require_mapping(value, "projection")
    return {
        "observer": _require_text(
            mapping.get("observer", "generic_event_adapter"),
            "projection.observer",
        ),
        "scope": _scope(mapping.get("scope"), default=AxiomProjectionScope.INTERNAL),
    }


def _summarize_decision(receipts: tuple[AxiomWorldReceipt, ...]) -> AxiomDecision:
    decisions = tuple(receipt.decision for receipt in receipts)
    if AxiomDecision.REJECT in decisions:
        return AxiomDecision.REJECT
    if AxiomDecision.QUARANTINE in decisions:
        return AxiomDecision.QUARANTINE
    if AxiomDecision.REQUIRE_APPROVAL in decisions:
        return AxiomDecision.REQUIRE_APPROVAL
    if AxiomDecision.REQUIRE_EVIDENCE in decisions:
        return AxiomDecision.REQUIRE_EVIDENCE
    if decisions and all(decision == AxiomDecision.SIMULATE_ONLY for decision in decisions):
        return AxiomDecision.SIMULATE_ONLY
    return AxiomDecision.ACCEPT


def _validity(value: Any, observed_at: str) -> ValidityWindow:
    if value is None:
        return ValidityWindow(valid_from=observed_at)
    mapping = _require_mapping(value, "validity")
    return ValidityWindow(
        valid_from=_require_text(
            mapping.get("valid_from", observed_at),
            "validity.valid_from",
        ),
        valid_until=str(mapping.get("valid_until", "")),
        requires_refresh=_bool(mapping.get("requires_refresh"), default=False),
    )


def _scope(value: Any, *, default: AxiomProjectionScope) -> AxiomProjectionScope:
    if value is None or value == "":
        return default
    try:
        return AxiomProjectionScope(str(value))
    except ValueError as exc:
        raise ValueError("projection_scope_invalid") from exc


def _risk(value: Any) -> AxiomRiskLevel:
    try:
        return AxiomRiskLevel(str(value))
    except ValueError as exc:
        raise ValueError("action_risk_level_invalid") from exc


def _reversibility(value: Any) -> AxiomReversibility:
    try:
        return AxiomReversibility(str(value))
    except ValueError as exc:
        raise ValueError("action_reversibility_invalid") from exc


def _mapping_items(
    value: Any,
    field_name: str,
    *,
    allow_empty: bool = True,
) -> tuple[Mapping[str, Any], ...]:
    if value is None:
        if allow_empty:
            return ()
        raise ValueError(f"{field_name}_required")
    if not isinstance(value, list | tuple):
        raise ValueError(f"{field_name}_array_required")
    items: list[Mapping[str, Any]] = []
    for index, item in enumerate(value):
        items.append(_require_mapping(item, f"{field_name}[{index}]"))
    if not items and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return tuple(items)


def _text_items(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list | tuple):
        raise ValueError(f"{field_name}_array_required")
    items = tuple(str(item).strip() for item in value if str(item).strip())
    if len(set(items)) != len(items):
        raise ValueError(f"{field_name}_duplicates_forbidden")
    return items


def _optional_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if value is None:
        return {}
    return _require_mapping(value, field_name)


def _require_mapping(value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name}_object_required")
    return value


def _require_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name}_required")
    return text


def _bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError("boolean_required")
    return value


def _json_ready(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
