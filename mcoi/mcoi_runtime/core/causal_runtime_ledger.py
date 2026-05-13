"""Purpose: append-only causal runtime ledger for governed execution traces.
Governance scope: runtime event lineage, hash-chain verification, cause checks,
and proof-reference binding for tool and workflow execution.
Dependencies: runtime invariant helpers and Python standard library only.
Invariants:
  - Events are append-only and sequence ordered.
  - Every event hash binds the previous event hash.
  - Cause references must point to events already committed in this ledger.
  - Payload hashes are recorded instead of raw sensitive payloads.
  - Clock is injected for deterministic tests and replay.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
from typing import Any, Callable, Mapping

from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text


_GENESIS_HASH = "0" * 64


@dataclass(frozen=True, slots=True)
class CausalLedgerEvent:
    """One immutable runtime event in the causal execution ledger."""

    event_id: str
    sequence: int
    occurred_at: str
    tenant_id: str
    actor_id: str
    surface: str
    action: str
    outcome: str
    correlation_id: str
    cause_event_ids: tuple[str, ...] = ()
    input_hash: str = ""
    output_hash: str = ""
    constraint_refs: tuple[str, ...] = ()
    proof_refs: tuple[str, ...] = ()
    previous_event_hash: str = ""
    event_hash: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "event_id",
            "occurred_at",
            "tenant_id",
            "actor_id",
            "surface",
            "action",
            "outcome",
            "correlation_id",
            "previous_event_hash",
            "event_hash",
        ):
            object.__setattr__(
                self,
                field_name,
                ensure_non_empty_text(field_name, str(getattr(self, field_name))),
            )
        if self.sequence < 1:
            raise RuntimeCoreInvariantError("sequence must be positive")
        object.__setattr__(self, "cause_event_ids", _text_tuple("cause_event_ids", self.cause_event_ids))
        object.__setattr__(self, "constraint_refs", _text_tuple("constraint_refs", self.constraint_refs))
        object.__setattr__(self, "proof_refs", _text_tuple("proof_refs", self.proof_refs))
        if not isinstance(self.metadata, Mapping):
            raise RuntimeCoreInvariantError("metadata must be an object")
        object.__setattr__(self, "metadata", _json_mapping(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready representation."""
        payload = asdict(self)
        payload["cause_event_ids"] = list(self.cause_event_ids)
        payload["constraint_refs"] = list(self.constraint_refs)
        payload["proof_refs"] = list(self.proof_refs)
        payload["metadata"] = _json_mapping(self.metadata)
        return payload


@dataclass(frozen=True, slots=True)
class CausalLedgerVerification:
    """Hash-chain verification result for a causal runtime ledger."""

    verified: bool
    event_count: int
    last_event_hash: str
    reason: str = "verified"
    failed_event_id: str = ""


class CausalRuntimeLedger:
    """Append-only causal runtime ledger with deterministic hash chaining."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._events: list[CausalLedgerEvent] = []
        self._events_by_id: dict[str, CausalLedgerEvent] = {}

    @property
    def event_count(self) -> int:
        """Return committed event count."""
        return len(self._events)

    @property
    def last_event_hash(self) -> str:
        """Return the current ledger head hash."""
        if not self._events:
            return _GENESIS_HASH
        return self._events[-1].event_hash

    def append(
        self,
        *,
        tenant_id: str,
        actor_id: str,
        surface: str,
        action: str,
        outcome: str,
        correlation_id: str,
        cause_event_ids: tuple[str, ...] = (),
        input_hash: str = "",
        output_hash: str = "",
        constraint_refs: tuple[str, ...] = (),
        proof_refs: tuple[str, ...] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> CausalLedgerEvent:
        """Append one event after validating causal references."""
        self.validate_causes(cause_event_ids)
        sequence = len(self._events) + 1
        occurred_at = ensure_non_empty_text("occurred_at", self._clock())
        previous_event_hash = self.last_event_hash
        event_id = _event_id(
            sequence=sequence,
            occurred_at=occurred_at,
            tenant_id=tenant_id,
            actor_id=actor_id,
            surface=surface,
            action=action,
            outcome=outcome,
            correlation_id=correlation_id,
            previous_event_hash=previous_event_hash,
        )
        if event_id in self._events_by_id:
            raise RuntimeCoreInvariantError("event_id already exists")
        event_payload = {
            "event_id": event_id,
            "sequence": sequence,
            "occurred_at": occurred_at,
            "tenant_id": tenant_id,
            "actor_id": actor_id,
            "surface": surface,
            "action": action,
            "outcome": outcome,
            "correlation_id": correlation_id,
            "cause_event_ids": cause_event_ids,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "constraint_refs": constraint_refs,
            "proof_refs": proof_refs,
            "previous_event_hash": previous_event_hash,
            "metadata": _json_mapping(metadata or {}),
        }
        event_hash = _hash_payload(event_payload)
        event = CausalLedgerEvent(event_hash=event_hash, **event_payload)
        self._events.append(event)
        self._events_by_id[event.event_id] = event
        return event

    def validate_causes(self, cause_event_ids: tuple[str, ...]) -> None:
        """Raise when any cause reference is absent or duplicated."""
        normalized = _text_tuple("cause_event_ids", cause_event_ids)
        if len(set(normalized)) != len(normalized):
            raise RuntimeCoreInvariantError("cause_event_ids must be unique")
        missing = [event_id for event_id in normalized if event_id not in self._events_by_id]
        if missing:
            raise RuntimeCoreInvariantError("cause event not found")

    def get_event(self, event_id: str) -> CausalLedgerEvent | None:
        """Return a committed event by id."""
        ensure_non_empty_text("event_id", event_id)
        return self._events_by_id.get(event_id)

    def list_events(
        self,
        *,
        correlation_id: str = "",
        surface: str = "",
        limit: int = 100,
    ) -> tuple[CausalLedgerEvent, ...]:
        """Return bounded events in append order."""
        bounded_limit = max(1, min(int(limit), 1000))
        events = tuple(self._events)
        if correlation_id:
            events = tuple(event for event in events if event.correlation_id == correlation_id)
        if surface:
            events = tuple(event for event in events if event.surface == surface)
        return events[:bounded_limit]

    def verify_chain(self) -> CausalLedgerVerification:
        """Recompute event hashes and previous-hash links."""
        previous_hash = _GENESIS_HASH
        for expected_sequence, event in enumerate(self._events, start=1):
            if event.sequence != expected_sequence:
                return CausalLedgerVerification(
                    verified=False,
                    event_count=len(self._events),
                    last_event_hash=self.last_event_hash,
                    reason="sequence_mismatch",
                    failed_event_id=event.event_id,
                )
            if event.previous_event_hash != previous_hash:
                return CausalLedgerVerification(
                    verified=False,
                    event_count=len(self._events),
                    last_event_hash=self.last_event_hash,
                    reason="previous_hash_mismatch",
                    failed_event_id=event.event_id,
                )
            recomputed = _hash_payload(_event_hash_payload(event))
            if recomputed != event.event_hash:
                return CausalLedgerVerification(
                    verified=False,
                    event_count=len(self._events),
                    last_event_hash=self.last_event_hash,
                    reason="event_hash_mismatch",
                    failed_event_id=event.event_id,
                )
            previous_hash = event.event_hash
        return CausalLedgerVerification(
            verified=True,
            event_count=len(self._events),
            last_event_hash=self.last_event_hash,
        )


def hash_runtime_payload(payload: Any) -> str:
    """Return a stable sha256 hash for runtime payload evidence."""
    return _hash_payload(_json_value(payload))


def _event_id(
    *,
    sequence: int,
    occurred_at: str,
    tenant_id: str,
    actor_id: str,
    surface: str,
    action: str,
    outcome: str,
    correlation_id: str,
    previous_event_hash: str,
) -> str:
    payload = {
        "sequence": sequence,
        "occurred_at": occurred_at,
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "surface": surface,
        "action": action,
        "outcome": outcome,
        "correlation_id": correlation_id,
        "previous_event_hash": previous_event_hash,
    }
    return f"causal-event-{_hash_payload(payload)[:16]}"


def _event_hash_payload(event: CausalLedgerEvent) -> dict[str, Any]:
    return {
        "event_id": event.event_id,
        "sequence": event.sequence,
        "occurred_at": event.occurred_at,
        "tenant_id": event.tenant_id,
        "actor_id": event.actor_id,
        "surface": event.surface,
        "action": event.action,
        "outcome": event.outcome,
        "correlation_id": event.correlation_id,
        "cause_event_ids": event.cause_event_ids,
        "input_hash": event.input_hash,
        "output_hash": event.output_hash,
        "constraint_refs": event.constraint_refs,
        "proof_refs": event.proof_refs,
        "previous_event_hash": event.previous_event_hash,
        "metadata": _json_mapping(event.metadata),
    }


def _hash_payload(payload: Any) -> str:
    encoded = json.dumps(_json_value(payload), sort_keys=True, separators=(",", ":"), default=str)
    return sha256(encoded.encode("utf-8")).hexdigest()


def _text_tuple(field_name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        raise RuntimeCoreInvariantError(f"{field_name} must be a tuple")
    normalized: list[str] = []
    for value in values:
        normalized.append(ensure_non_empty_text(field_name, str(value)))
    return tuple(normalized)


def _json_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return dict(_json_value(dict(value)))


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
