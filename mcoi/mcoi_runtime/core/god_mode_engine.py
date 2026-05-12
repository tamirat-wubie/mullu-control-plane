"""Purpose: god-mode invocation engine — tickets, receipts, and consumption.

Governance scope: turns an `ActivationAgreement` (per-invocation consent) into
a single-use, time-bounded `GodModeTicket`, validates ticket presentation at
the moment of privileged action, and emits a `GodModeReceipt` capturing the
outcome with pre/post state hashes.

Dependencies: god_mode contracts, god_mode_registry.

Invariants:
  - A ticket can be issued only if the capability is ARMED.
  - A ticket is consumable exactly once (unless capability.requires_session).
  - An expired ticket is never consumable.
  - Every consumption produces a `GodModeReceipt`.
  - All state mutations are protected by a single lock.
"""

from __future__ import annotations

import hashlib
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from mcoi_runtime.contracts.god_mode import (
    ActivationAgreement,
    GodCapabilityBlastRadius,
    GodModeReceipt,
    GodModeTicket,
    GodReceiptOutcome,
    GodTicketState,
)
from mcoi_runtime.core.god_mode_registry import (
    GodModeRegistry,
    GodModeRegistryError,
    get_registry,
)


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


def _to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(text: str) -> datetime:
    normalized = text.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _hash_state(state: Any) -> str:
    """Stable digest of an opaque state value — used for pre/post receipts."""
    if state is None:
        digest = hashlib.sha256(b"\x00").digest()
    elif isinstance(state, (bytes, bytearray)):
        digest = hashlib.sha256(bytes(state)).digest()
    else:
        encoded = repr(state).encode("utf-8", errors="replace")
        digest = hashlib.sha256(encoded).digest()
    return "sha256:" + digest.hex()


class GodModeEngineError(RuntimeError):
    """Raised on engine contract violations (expired ticket, double consume, ...)."""


class GodModeEngine:
    """Issues and consumes god-mode tickets.

    The engine never executes the privileged operation itself — callers wrap
    their privileged code in `consume(ticket_id, ...)` (or the `invoke`
    context manager) to get a receipt. The engine is the trust anchor for
    *whether* the call is permitted.
    """

    # Default rate-limit window: at most 5 tickets per actor+capability
    # in any 300-second sliding window.
    DEFAULT_RATE_LIMIT_TICKETS = 5
    DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 300

    def __init__(
        self,
        *,
        registry: GodModeRegistry | None = None,
        receipt_sink: Any = None,
        metrics_sink: Any = None,
        rate_limit_tickets: int | None = None,
        rate_limit_window_seconds: int | None = None,
    ) -> None:
        self._lock = threading.RLock()
        self._registry = registry if registry is not None else get_registry()
        self._receipt_sink = receipt_sink
        self._metrics_sink = metrics_sink
        self._rate_limit_tickets = (
            rate_limit_tickets
            if rate_limit_tickets is not None
            else self.DEFAULT_RATE_LIMIT_TICKETS
        )
        self._rate_limit_window_seconds = (
            rate_limit_window_seconds
            if rate_limit_window_seconds is not None
            else self.DEFAULT_RATE_LIMIT_WINDOW_SECONDS
        )
        self._tickets: dict[str, GodModeTicket] = {}
        self._activation_agreements: dict[str, ActivationAgreement] = {}
        self._receipts: dict[str, GodModeReceipt] = {}
        # ticket_id → ordered list of receipt_ids for session-scoped capabilities
        self._ticket_receipts: dict[str, list[str]] = {}
        # Sliding-window log for rate limiting: (actor, module, name) → list[issued_at_dt]
        self._issue_log: dict[tuple[str, str, str], list[datetime]] = {}

    # ------------------------------------------------------------------
    # Ticket issuance
    # ------------------------------------------------------------------

    def issue_ticket(
        self,
        *,
        actor_id: str,
        module: str,
        name: str,
        justification: str,
        target: dict[str, str] | None = None,
        ttl_seconds: int | None = None,
        tenant_id: str = "",
    ) -> tuple[GodModeTicket, ActivationAgreement]:
        """Record the activation agreement and mint a ticket.

        ``tenant_id`` (optional) binds the ticket to a tenant. When set, every
        consume() call must pass ``expected_tenant_id`` matching this value
        or be rejected with a ``cross_tenant`` failure.
        """
        with self._lock:
            try:
                capability = self._registry.get_capability(module, name)
            except GodModeRegistryError as exc:
                self._inc_metric("god_mode_issue_rejected_unknown")
                raise GodModeEngineError(str(exc)) from exc
            state = self._registry.state_of(module, name)
            if state.value != "armed":
                self._inc_metric(f"god_mode_issue_rejected_{state.value}")
                raise GodModeEngineError(
                    f"capability {capability.fqn} is {state.value}; cannot issue ticket"
                )
            self._enforce_rate_limit(actor_id=actor_id, module=module, name=name)
            ttl = ttl_seconds if ttl_seconds is not None else capability.default_ttl_seconds
            now = _utc_now()
            agreement = ActivationAgreement(
                agreement_id=f"god-act-{uuid.uuid4().hex[:16]}",
                capability_module=module,
                capability_name=name,
                actor_id=actor_id,
                justification=justification,
                target=tuple(sorted((target or {}).items())),
                requested_ttl_seconds=ttl,
                recorded_at=_to_iso(now),
                tenant_id=tenant_id,
            )
            ticket = GodModeTicket(
                ticket_id=f"god-tkt-{uuid.uuid4().hex[:16]}",
                agreement_id=agreement.agreement_id,
                capability_module=module,
                capability_name=name,
                actor_id=actor_id,
                issued_at=_to_iso(now),
                expires_at=_to_iso(now + timedelta(seconds=ttl)),
                state=GodTicketState.ISSUED,
                tenant_id=tenant_id,
            )
            self._activation_agreements[agreement.agreement_id] = agreement
            self._tickets[ticket.ticket_id] = ticket
            self._ticket_receipts[ticket.ticket_id] = []
            self._issue_log.setdefault((actor_id, module, name), []).append(now)
            self._inc_metric("god_mode_ticket_issued")
            self._inc_metric(f"god_mode_ticket_issued_{module}_{name}")
            return ticket, agreement

    # ------------------------------------------------------------------
    # Consumption
    # ------------------------------------------------------------------

    def _refresh_expiry(self, ticket: GodModeTicket) -> GodModeTicket:
        """Mark a ticket EXPIRED if its expires_at has passed."""
        if ticket.state != GodTicketState.ISSUED:
            return ticket
        now = _utc_now()
        expires_at = _parse_iso(ticket.expires_at)
        if now >= expires_at:
            updated = GodModeTicket(
                ticket_id=ticket.ticket_id,
                agreement_id=ticket.agreement_id,
                capability_module=ticket.capability_module,
                capability_name=ticket.capability_name,
                actor_id=ticket.actor_id,
                issued_at=ticket.issued_at,
                expires_at=ticket.expires_at,
                state=GodTicketState.EXPIRED,
                tenant_id=ticket.tenant_id,
            )
            self._tickets[ticket.ticket_id] = updated
            return updated
        return ticket

    def get_ticket(self, ticket_id: str) -> GodModeTicket:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                raise GodModeEngineError(f"ticket {ticket_id} not found")
            return self._refresh_expiry(ticket)

    def consume(
        self,
        *,
        ticket_id: str,
        outcome: GodReceiptOutcome,
        pre_state: Any,
        post_state: Any,
        detail: dict[str, str] | None = None,
        failure_reason: str = "",
        expected_tenant_id: str | None = None,
    ) -> GodModeReceipt:
        """Consume a ticket and emit a receipt.

        For one-shot capabilities this transitions the ticket to CONSUMED and
        further consume() calls will fail. For session-scoped capabilities the
        ticket stays ISSUED until expiry; multiple receipts may be emitted.

        ``expected_tenant_id`` (optional): the calling subsystem's tenant
        context. If the ticket was issued with a non-empty ``tenant_id`` and
        ``expected_tenant_id`` does not match, the call is rejected with a
        cross-tenant violation. Pass ``""`` for tenant-agnostic ops.
        """
        with self._lock:
            ticket = self.get_ticket(ticket_id)
            if ticket.state == GodTicketState.EXPIRED:
                raise GodModeEngineError(f"ticket {ticket_id} expired")
            if ticket.state == GodTicketState.CONSUMED:
                raise GodModeEngineError(f"ticket {ticket_id} already consumed")
            if ticket.state == GodTicketState.REVOKED:
                raise GodModeEngineError(f"ticket {ticket_id} revoked")
            if (
                expected_tenant_id is not None
                and ticket.tenant_id
                and ticket.tenant_id != expected_tenant_id
            ):
                self._inc_metric("god_mode_consume_rejected_cross_tenant")
                raise GodModeEngineError(
                    f"ticket {ticket_id} bound to tenant {ticket.tenant_id!r}, "
                    f"caller is acting on tenant {expected_tenant_id!r}"
                )
            capability = self._registry.get_capability(
                ticket.capability_module, ticket.capability_name
            )
            receipt = GodModeReceipt(
                receipt_id=f"god-rcpt-{uuid.uuid4().hex[:16]}",
                ticket_id=ticket.ticket_id,
                agreement_id=ticket.agreement_id,
                capability_module=ticket.capability_module,
                capability_name=ticket.capability_name,
                actor_id=ticket.actor_id,
                outcome=outcome,
                consumed_at=_utc_now_iso(),
                pre_state_hash=_hash_state(pre_state),
                post_state_hash=_hash_state(post_state),
                tenant_id=ticket.tenant_id,
                detail=tuple(sorted((detail or {}).items())),
                failure_reason=failure_reason,
            )
            self._receipts[receipt.receipt_id] = receipt
            self._ticket_receipts[ticket_id].append(receipt.receipt_id)
            self._inc_metric(f"god_mode_consume_{outcome.value}")
            self._inc_metric(
                f"god_mode_consume_{ticket.capability_module}_{ticket.capability_name}_{outcome.value}"
            )
            if capability.one_shot or not capability.requires_session:
                consumed = GodModeTicket(
                    ticket_id=ticket.ticket_id,
                    agreement_id=ticket.agreement_id,
                    capability_module=ticket.capability_module,
                    capability_name=ticket.capability_name,
                    actor_id=ticket.actor_id,
                    issued_at=ticket.issued_at,
                    expires_at=ticket.expires_at,
                    state=GodTicketState.CONSUMED,
                    tenant_id=ticket.tenant_id,
                    consumed_at=receipt.consumed_at,
                )
                self._tickets[ticket_id] = consumed
            self._dispatch_to_sink(receipt, capability_blast=capability.blast_radius)
            return receipt

    def revoke(
        self,
        *,
        ticket_id: str,
        actor_id: str,
        reason: str,
    ) -> GodModeTicket:
        """Forcibly revoke an outstanding ticket."""
        with self._lock:
            ticket = self.get_ticket(ticket_id)
            if ticket.state in (GodTicketState.CONSUMED, GodTicketState.REVOKED):
                raise GodModeEngineError(
                    f"ticket {ticket_id} is {ticket.state.value}; cannot revoke"
                )
            if not reason.strip():
                raise GodModeEngineError("revoke reason required")
            revoked = GodModeTicket(
                ticket_id=ticket.ticket_id,
                agreement_id=ticket.agreement_id,
                capability_module=ticket.capability_module,
                capability_name=ticket.capability_name,
                actor_id=ticket.actor_id,
                issued_at=ticket.issued_at,
                expires_at=ticket.expires_at,
                state=GodTicketState.REVOKED,
                tenant_id=ticket.tenant_id,
                revoked_at=_utc_now_iso(),
                revoked_reason=f"{actor_id}: {reason.strip()}",
            )
            self._tickets[ticket_id] = revoked
            return revoked

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def list_tickets(
        self,
        *,
        actor_id: str | None = None,
        module: str | None = None,
        name: str | None = None,
        tenant_id: str | None = None,
        active_only: bool = False,
    ) -> tuple[GodModeTicket, ...]:
        with self._lock:
            tickets = [self._refresh_expiry(t) for t in self._tickets.values()]
            if actor_id is not None:
                tickets = [t for t in tickets if t.actor_id == actor_id]
            if module is not None:
                tickets = [t for t in tickets if t.capability_module == module]
            if name is not None:
                tickets = [t for t in tickets if t.capability_name == name]
            if tenant_id is not None:
                tickets = [t for t in tickets if t.tenant_id == tenant_id]
            if active_only:
                tickets = [t for t in tickets if t.state == GodTicketState.ISSUED]
            return tuple(sorted(tickets, key=lambda t: t.issued_at))

    def list_receipts(
        self,
        *,
        actor_id: str | None = None,
        module: str | None = None,
        name: str | None = None,
        outcome: GodReceiptOutcome | None = None,
    ) -> tuple[GodModeReceipt, ...]:
        with self._lock:
            receipts = list(self._receipts.values())
            if actor_id is not None:
                receipts = [r for r in receipts if r.actor_id == actor_id]
            if module is not None:
                receipts = [r for r in receipts if r.capability_module == module]
            if name is not None:
                receipts = [r for r in receipts if r.capability_name == name]
            if outcome is not None:
                receipts = [r for r in receipts if r.outcome == outcome]
            return tuple(sorted(receipts, key=lambda r: r.consumed_at))

    def get_activation_agreement(self, agreement_id: str) -> ActivationAgreement:
        with self._lock:
            agreement = self._activation_agreements.get(agreement_id)
            if agreement is None:
                raise GodModeEngineError(f"activation agreement {agreement_id} not found")
            return agreement

    def reset(self) -> None:
        with self._lock:
            self._tickets.clear()
            self._activation_agreements.clear()
            self._receipts.clear()
            self._ticket_receipts.clear()
            self._issue_log.clear()

    # ------------------------------------------------------------------
    # Metrics + rate limit helpers
    # ------------------------------------------------------------------

    def _inc_metric(self, name: str) -> None:
        sink = self._metrics_sink
        if sink is None:
            return
        try:
            inc = getattr(sink, "inc", None)
            if callable(inc):
                inc(name)
        except Exception:
            return

    def _enforce_rate_limit(self, *, actor_id: str, module: str, name: str) -> None:
        """Reject ticket issuance if the (actor, capability) sliding window is full."""
        if self._rate_limit_tickets <= 0:
            return
        now = _utc_now()
        cutoff = now - timedelta(seconds=self._rate_limit_window_seconds)
        key = (actor_id, module, name)
        history = self._issue_log.setdefault(key, [])
        # Drop entries outside the window in-place.
        live = [t for t in history if t > cutoff]
        self._issue_log[key] = live
        if len(live) >= self._rate_limit_tickets:
            self._inc_metric("god_mode_issue_rejected_rate_limited")
            raise GodModeEngineError(
                f"rate limit hit for {actor_id} on {module}.{name}: "
                f"{len(live)} ticket(s) issued in last {self._rate_limit_window_seconds}s"
            )

    def issue_log_for(
        self, *, actor_id: str, module: str, name: str
    ) -> tuple[str, ...]:
        """Read-only view of the rate-limit log entries (ISO timestamps)."""
        with self._lock:
            entries = self._issue_log.get((actor_id, module, name), [])
            return tuple(_to_iso(t) for t in entries)

    # ------------------------------------------------------------------
    # Sink dispatch (audit trail / event spine integration point)
    # ------------------------------------------------------------------

    def _dispatch_to_sink(
        self, receipt: GodModeReceipt, *, capability_blast: GodCapabilityBlastRadius
    ) -> None:
        sink = self._receipt_sink
        if sink is None:
            return
        try:
            handler = getattr(sink, "record_god_mode_receipt", None)
            if callable(handler):
                handler(receipt, blast_radius=capability_blast)
                return
            record = getattr(sink, "record", None)
            if callable(record):
                record(
                    action=f"god_mode.consume.{receipt.capability_module}.{receipt.capability_name}",
                    actor_id=receipt.actor_id,
                    target=receipt.ticket_id,
                    outcome=receipt.outcome.value,
                    detail={
                        "agreement_id": receipt.agreement_id,
                        "blast_radius": capability_blast.value,
                        "receipt_id": receipt.receipt_id,
                        "pre_state_hash": receipt.pre_state_hash,
                        "post_state_hash": receipt.post_state_hash,
                    },
                )
        except Exception:
            # Never let the sink break the privileged-op return path.
            return

    # ------------------------------------------------------------------
    # Convenience context manager
    # ------------------------------------------------------------------

    @contextmanager
    def invoke(
        self,
        *,
        ticket_id: str,
        pre_state: Any,
        detail: dict[str, str] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Context manager wrapping a privileged operation.

        Yields a mutable dict. Set ``state["post"]`` to the post-state value;
        on success a SUCCESS receipt is emitted, on exception a FAILURE
        receipt is emitted with the exception text and the exception is
        re-raised.
        """
        ticket = self.get_ticket(ticket_id)
        if ticket.state != GodTicketState.ISSUED:
            raise GodModeEngineError(
                f"ticket {ticket_id} not invocable (state={ticket.state.value})"
            )
        carrier: dict[str, Any] = {"post": None}
        try:
            yield carrier
        except Exception as exc:
            self.consume(
                ticket_id=ticket_id,
                outcome=GodReceiptOutcome.FAILURE,
                pre_state=pre_state,
                post_state=carrier.get("post"),
                detail=detail,
                failure_reason=f"{type(exc).__name__}: {exc}"[:512],
            )
            raise
        else:
            self.consume(
                ticket_id=ticket_id,
                outcome=GodReceiptOutcome.SUCCESS,
                pre_state=pre_state,
                post_state=carrier.get("post"),
                detail=detail,
            )


_ENGINE: GodModeEngine | None = None


def get_engine() -> GodModeEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = GodModeEngine()
    return _ENGINE


def set_engine(engine: GodModeEngine | None) -> None:
    """Replace the process-wide engine. Test fixture only."""
    global _ENGINE
    _ENGINE = engine


# ---------------------------------------------------------------------------
# Decorator: gate any callable behind a god-mode ticket
# ---------------------------------------------------------------------------


def requires_god_ticket(module: str, name: str):
    """Decorator: require a valid god-mode ticket to invoke the function.

    Usage::

        @requires_god_ticket(module="replay", name="mutate_recorder")
        def _mutate_replay_buffer(*, recorder, frame_id, ticket_id):
            ...

    The decorated function MUST accept ``ticket_id=`` as a keyword argument
    and MAY accept ``expected_tenant_id=`` (string or empty string).

    The decorator validates the ticket against the registry+engine, enforces
    capability+tenant binding, runs the wrapped callable, and consumes the
    ticket with a SUCCESS or FAILURE receipt depending on whether the call
    raised.

    Tenant binding: if the ticket was issued with a non-empty ``tenant_id``,
    the caller MUST pass ``expected_tenant_id=`` (matching that value) or the
    decorator rejects the call as a cross-tenant violation.
    """

    expected_module = module
    expected_name = name

    def decorator(func):
        import functools

        @functools.wraps(func)
        def wrapper(
            *args,
            ticket_id: str | None = None,
            expected_tenant_id: str | None = None,
            **kwargs,
        ):
            if not ticket_id:
                raise GodModeEngineError(
                    f"{expected_module}.{expected_name} requires a god-mode ticket_id"
                )
            engine = get_engine()
            ticket = engine.get_ticket(ticket_id)
            if (
                ticket.capability_module != expected_module
                or ticket.capability_name != expected_name
            ):
                raise GodModeEngineError(
                    f"ticket {ticket_id} is for "
                    f"{ticket.capability_module}.{ticket.capability_name}, "
                    f"not {expected_module}.{expected_name}"
                )
            if ticket.state.value != "issued":
                raise GodModeEngineError(
                    f"ticket {ticket_id} not invocable (state={ticket.state.value})"
                )
            if ticket.tenant_id and expected_tenant_id is None:
                raise GodModeEngineError(
                    f"ticket {ticket_id} is tenant-scoped to {ticket.tenant_id!r}; "
                    "caller must pass expected_tenant_id"
                )
            if (
                expected_tenant_id is not None
                and ticket.tenant_id
                and ticket.tenant_id != expected_tenant_id
            ):
                engine._inc_metric("god_mode_consume_rejected_cross_tenant")  # type: ignore[attr-defined]
                raise GodModeEngineError(
                    f"ticket {ticket_id} bound to tenant {ticket.tenant_id!r}, "
                    f"caller is acting on tenant {expected_tenant_id!r}"
                )
            pre_state = {"args_repr": repr(args)[:512], "kwargs_repr": repr(kwargs)[:512]}
            try:
                result = func(*args, **kwargs)
            except Exception as exc:
                engine.consume(
                    ticket_id=ticket_id,
                    outcome=GodReceiptOutcome.FAILURE,
                    pre_state=pre_state,
                    post_state=None,
                    failure_reason=f"{type(exc).__name__}: {exc}"[:512],
                    expected_tenant_id=expected_tenant_id,
                )
                raise
            engine.consume(
                ticket_id=ticket_id,
                outcome=GodReceiptOutcome.SUCCESS,
                pre_state=pre_state,
                post_state={"result_repr": repr(result)[:512]},
                expected_tenant_id=expected_tenant_id,
            )
            return result

        wrapper.__god_capability__ = (expected_module, expected_name)  # type: ignore[attr-defined]
        return wrapper

    return decorator


__all__ = [
    "GodModeEngine",
    "GodModeEngineError",
    "get_engine",
    "set_engine",
    "requires_god_ticket",
]
