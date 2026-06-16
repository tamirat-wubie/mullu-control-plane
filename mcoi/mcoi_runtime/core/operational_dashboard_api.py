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
from mcoi_runtime.core.operational_dashboard_client import (
    build_normal_user_dashboard_client_view,
    render_normal_user_dashboard_html,
    render_normal_user_dashboard_shell,
)
from mcoi_runtime.core.operational_dashboard_intelligence import OperationalDashboardState

DashboardStateProvider = Callable[[], OperationalDashboardState]


NORMAL_USER_DASHBOARD_CLIENT_CONTRACT: dict[str, object] = {
    "contract_ref": "operational_dashboard.normal_user_dashboard.v1",
    "visibility_level": "normal_user",
    "route": {
        "method": "GET",
        "path": "/api/v1/dashboard/simple",
        "payload_key": "dashboard",
    },
    "page_route": {
        "method": "GET",
        "path": "/api/v1/dashboard/simple/page",
        "content_type": "text/html",
    },
    "purpose": "Expose the Level 1 dashboard shell for normal users.",
    "visible_payload_fields": (
        "visibility_level",
        "audit_details_visible",
        "receipts_visible",
        "proof_details_hidden",
        "home",
        "simple_action_summaries",
        "simple_workflow_summaries",
        "simple_start_guide",
        "simple_ready_action_refs",
        "simple_review_action_refs",
        "simple_blocked_action_refs",
        "simple_ready_workflow_refs",
        "simple_review_workflow_refs",
        "simple_blocked_workflow_refs",
        "execution_allowed",
    ),
    "hidden_fields": (
        "auditor_details",
        "blocked_reasons",
        "boundary_witness_ref",
        "checks",
        "decision_ref",
        "operator_details",
        "proof_stamp_ref",
        "raw_decision",
        "review_reasons",
    ),
    "hidden_ref_prefixes": ("gate-decision-", "proof-", "witness-"),
    "invariants": (
        "normal user payloads hide proof and witness references",
        "normal user payloads use dashboard-local opaque refs",
        "normal user payloads do not expose raw checks or decisions",
        "normal user payloads never grant execution authority",
        "operator and auditor details remain on explicit audit/operator routes",
    ),
}


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

    def simple_state(self) -> OperationalDashboardEnvelope:
        """Return the normal-user dashboard projection with audit details hidden."""

        try:
            state = self._load_state()
            simple_dashboard = _normal_user_dashboard_payload(state)
            return _ok("ready" if simple_dashboard["home"] else "empty", {"dashboard": simple_dashboard})
        except (RuntimeCoreInvariantError, TypeError, ValueError) as exc:
            return _rejected(exc)

    def simple_state_contract(self) -> OperationalDashboardEnvelope:
        """Return the stable normal-user dashboard client contract."""

        return _ok("listed", {"contract": _normal_user_dashboard_client_contract()})

    def simple_client_view(self) -> OperationalDashboardEnvelope:
        """Return the UI-ready normal-user dashboard client view."""

        try:
            state = self._load_state()
            simple_dashboard = _normal_user_dashboard_payload(state)
            if simple_dashboard["home"] is None:
                return _ok("empty", {"client_view": None})
            client_view = build_normal_user_dashboard_client_view(
                simple_dashboard,
                contract=_normal_user_dashboard_client_contract(),
            )
            return _ok("ready", {"client_view": client_view.to_dict()})
        except (RuntimeCoreInvariantError, TypeError, ValueError) as exc:
            return _rejected(exc)

    def simple_client_page(self) -> OperationalDashboardEnvelope:
        """Return the read-only HTML page for the normal-user dashboard."""

        try:
            state = self._load_state()
            simple_dashboard = _normal_user_dashboard_payload(state)
            if simple_dashboard["home"] is None:
                return _ok("empty", {"html": _empty_normal_user_dashboard_html()})
            client_view = build_normal_user_dashboard_client_view(
                simple_dashboard,
                contract=_normal_user_dashboard_client_contract(),
            )
            return _ok("ready", {"html": render_normal_user_dashboard_html(client_view)})
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


def _normal_user_dashboard_payload(state: OperationalDashboardState) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "visibility_level": "normal_user",
        "audit_details_visible": False,
        "receipts_visible": False,
        "proof_details_hidden": True,
        "home": state.simple_home_summary.to_dict() if state.simple_home_summary else None,
        "simple_action_summaries": [summary.to_dict() for summary in state.simple_action_summaries],
        "simple_workflow_summaries": [summary.to_dict() for summary in state.simple_workflow_summaries],
        "simple_start_guide": state.simple_start_guide.to_dict() if state.simple_start_guide else None,
        "simple_ready_action_refs": list(state.simple_ready_action_refs),
        "simple_review_action_refs": list(state.simple_review_action_refs),
        "simple_blocked_action_refs": list(state.simple_blocked_action_refs),
        "simple_ready_workflow_refs": list(state.simple_ready_workflow_refs),
        "simple_review_workflow_refs": list(state.simple_review_workflow_refs),
        "simple_blocked_workflow_refs": list(state.simple_blocked_workflow_refs),
        "execution_allowed": False,
    }
    _reject_normal_user_dashboard_leaks(payload)
    return payload


def _normal_user_dashboard_client_contract() -> dict[str, object]:
    return {
        key: list(value) if isinstance(value, tuple) else dict(value) if isinstance(value, Mapping) else value
        for key, value in NORMAL_USER_DASHBOARD_CLIENT_CONTRACT.items()
    }


def _empty_normal_user_dashboard_html() -> str:
    return render_normal_user_dashboard_shell(
        document_title="Mullu Dashboard - Empty",
        body_lines=(
            "    <h1>Ready</h1>",
            "    <p>No dashboard items are waiting.</p>",
        ),
        evidence_label="No evidence yet",
    )


def _reject_normal_user_dashboard_leaks(value: Any) -> None:
    if isinstance(value, Mapping):
        forbidden_keys = {
            "auditor_details",
            "blocked_reasons",
            "boundary_witness_ref",
            "checks",
            "decision_ref",
            "operator_details",
            "proof_stamp_ref",
            "raw_decision",
            "review_reasons",
        }
        leaked_keys = sorted(str(key) for key in value if key in forbidden_keys)
        if leaked_keys:
            raise RuntimeCoreInvariantError(
                f"normal user dashboard cannot expose internal fields: {', '.join(leaked_keys)}"
            )
        for nested_value in value.values():
            _reject_normal_user_dashboard_leaks(nested_value)
        return
    if isinstance(value, list | tuple):
        for nested_value in value:
            _reject_normal_user_dashboard_leaks(nested_value)
        return
    if isinstance(value, str) and value.startswith(("gate-decision-", "proof-", "witness-")):
        raise RuntimeCoreInvariantError("normal user dashboard cannot expose internal governance refs")
