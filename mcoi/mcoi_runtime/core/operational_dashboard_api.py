"""Framework-neutral API for read-only operational dashboard projections.

Purpose: expose operational dashboard state and the simple home summary through
JSON-compatible envelopes for apps, gateways, and local UI adapters.
Governance scope: projection boundary only; this module does not build memory
truth, approve execution, mutate notes, or bypass dashboard invariants.
Dependencies: dataclasses, typing, operational dashboard projections, and
runtime invariant helpers.
Invariants: all responses are governed envelopes, invalid providers fail
closed, and no dashboard API response grants execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.operational_dashboard_intelligence import OperationalDashboardState

DashboardStateProvider = Callable[[], OperationalDashboardState]


@dataclass(frozen=True)
class OperationalDashboardEnvelope:
    """JSON-compatible operational dashboard response envelope."""

    governed: bool
    ok: bool
    status: str
    payload: Mapping[str, Any]
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible response."""

        return {
            "governed": self.governed,
            "ok": self.ok,
            "status": self.status,
            "payload": dict(self.payload),
            "error": self.error,
        }


class OperationalDashboardRuntime:
    """Runtime facade for read-only dashboard projections."""

    def __init__(self, state_provider: DashboardStateProvider) -> None:
        self._state_provider = state_provider

    @classmethod
    def from_state(cls, state: OperationalDashboardState) -> "OperationalDashboardRuntime":
        """Create a runtime facade over one immutable dashboard state."""

        return cls(lambda: state)

    def state(self) -> OperationalDashboardEnvelope:
        """Return the full read-only dashboard state."""

        try:
            state = self._load_state()
            return _ok("ready", {"dashboard": state.to_dict()})
        except (RuntimeCoreInvariantError, TypeError, ValueError) as exc:
            return _rejected(exc)

    def simple_home(self) -> OperationalDashboardEnvelope:
        """Return the compact simple dashboard home projection."""

        try:
            state = self._load_state()
            home = state.simple_home_summary.to_dict() if state.simple_home_summary else None
            return _ok("ready" if home else "empty", {"home": home})
        except (RuntimeCoreInvariantError, TypeError, ValueError) as exc:
            return _rejected(exc)

    def sdlc_receipts(self) -> OperationalDashboardEnvelope:
        """Return read-only SDLC validation receipt summaries."""

        try:
            state = self._load_state()
            receipts = [summary.to_dict() for summary in state.sdlc_receipt_summaries]
            return _ok(
                "ready" if receipts else "empty",
                {
                    "sdlc_receipts": receipts,
                    "passed_receipt_refs": list(state.sdlc_passed_receipt_refs),
                    "failed_receipt_refs": list(state.sdlc_failed_receipt_refs),
                },
            )
        except (RuntimeCoreInvariantError, TypeError, ValueError) as exc:
            return _rejected(exc)

    def _load_state(self) -> OperationalDashboardState:
        state = self._state_provider()
        if not isinstance(state, OperationalDashboardState):
            raise RuntimeCoreInvariantError("dashboard state provider must return OperationalDashboardState")
        if state.execution_allowed:
            raise RuntimeCoreInvariantError("dashboard API cannot expose executable state")
        return state


def _ok(status: str, payload: Mapping[str, Any]) -> OperationalDashboardEnvelope:
    return OperationalDashboardEnvelope(governed=True, ok=True, status=status, payload=payload)


def _rejected(exc: Exception) -> OperationalDashboardEnvelope:
    return OperationalDashboardEnvelope(governed=True, ok=False, status="rejected", payload={}, error=str(exc))
