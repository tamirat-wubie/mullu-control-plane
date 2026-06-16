"""Framework-neutral API for simple governed platform actions.

Purpose: expose simple action checks through JSON-compatible envelopes for
dashboards, local services, and HTTP adapters.
Governance scope: API boundary only; SimplePlatform owns the governance SDK
call and MVK remains the action authority.
Dependencies: dataclasses, typing, simple platform facade, and invariant
helpers.
Invariants: invalid requests fail closed with explicit causal context, default
user responses hide proof and witness references, raw audit responses preserve
proof and witness references, and no API handler bypasses the simple platform
facade.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from .invariants import RuntimeCoreInvariantError
from .simple_platform import SimplePlatform, SimpleVisibilityLevel

DOCUMENT_MANIPULATION_WIRING_CLIENT_CONTRACT: dict[str, object] = {
    "contract_ref": "simple_platform.document_manipulation_wiring.v1",
    "purpose": "Expose read-only document manipulation wiring for clients.",
    "routes": (
        {
            "method": "GET",
            "path": "/api/v1/simple/documents/wiring",
            "payload_key": "wiring",
        },
        {
            "method": "GET",
            "path": "/api/v1/simple/documents/wiring/contract",
            "payload_key": "contract",
        },
    ),
    "invariants": (
        "document wiring is read-only",
        "document wiring grants no execution authority",
        "document manipulation remains bounded to docs_update checks",
    ),
}


@dataclass(frozen=True)
class SimplePlatformEnvelope:
    """JSON-compatible simple platform response envelope."""

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


class SimplePlatformRuntime:
    """Runtime facade for plain user action checks."""

    def __init__(self, platform: SimplePlatform | None = None) -> None:
        self.platform = platform or SimplePlatform()

    def check_action(self, request_body: Mapping[str, Any]) -> SimplePlatformEnvelope:
        """Validate and check one plain action request."""

        try:
            check = self.platform.check_action(request_body)
            return SimplePlatformEnvelope(
                governed=True,
                ok=check.ok_to_continue,
                status=check.outcome,
                payload={"check": check.to_dict()},
            )
        except (RuntimeCoreInvariantError, KeyError, TypeError, ValueError) as exc:
            return SimplePlatformEnvelope(
                governed=True,
                ok=False,
                status="rejected",
                payload={},
                error=str(exc),
            )

    def check_action_experience(self, request_body: Mapping[str, Any]) -> SimplePlatformEnvelope:
        """Validate one action and return the visibility-filtered shell."""

        try:
            visibility_level, action_body = _visibility_scoped_request(request_body)
            experience = self.platform.check_action_experience(
                action_body,
                visibility_level=visibility_level,
            )
            return SimplePlatformEnvelope(
                governed=True,
                ok=experience.outcome == "ready",
                status=experience.outcome,
                payload={"experience": experience.to_dict()},
            )
        except (RuntimeCoreInvariantError, KeyError, TypeError, ValueError) as exc:
            return SimplePlatformEnvelope(
                governed=True,
                ok=False,
                status="rejected",
                payload={},
                error=str(exc),
            )

    def check_task_experience(self, request_body: Mapping[str, Any]) -> SimplePlatformEnvelope:
        """Validate one template-backed task and return the visibility-filtered shell."""

        try:
            visibility_level, task_body = _visibility_scoped_request(request_body)
            experience = self.platform.check_task_experience(
                task_body,
                visibility_level=visibility_level,
            )
            return SimplePlatformEnvelope(
                governed=True,
                ok=experience.outcome == "ready",
                status=experience.outcome,
                payload={"experience": experience.to_dict()},
            )
        except (RuntimeCoreInvariantError, KeyError, TypeError, ValueError) as exc:
            return SimplePlatformEnvelope(
                governed=True,
                ok=False,
                status="rejected",
                payload={},
                error=str(exc),
            )

    def check_task(self, request_body: Mapping[str, Any]) -> SimplePlatformEnvelope:
        """Validate and check one template-backed task request."""

        try:
            check = self.platform.check_task(request_body)
            return SimplePlatformEnvelope(
                governed=True,
                ok=check.ok_to_continue,
                status=check.outcome,
                payload={"check": check.to_dict()},
            )
        except (RuntimeCoreInvariantError, KeyError, TypeError, ValueError) as exc:
            return SimplePlatformEnvelope(
                governed=True,
                ok=False,
                status="rejected",
                payload={},
                error=str(exc),
            )

    def check_workflow_experience(self, request_body: Mapping[str, Any]) -> SimplePlatformEnvelope:
        """Validate one workflow and return the visibility-filtered shell."""

        try:
            visibility_level, workflow_body = _visibility_scoped_request(request_body)
            experience = self.platform.check_workflow_experience(
                workflow_body,
                visibility_level=visibility_level,
            )
            return SimplePlatformEnvelope(
                governed=True,
                ok=experience.outcome == "ready",
                status=experience.outcome,
                payload={"workflow": experience.to_dict()},
            )
        except (RuntimeCoreInvariantError, KeyError, TypeError, ValueError) as exc:
            return SimplePlatformEnvelope(
                governed=True,
                ok=False,
                status="rejected",
                payload={},
                error=str(exc),
            )

    def check_workflow(self, request_body: Mapping[str, Any]) -> SimplePlatformEnvelope:
        """Validate and check one template-backed workflow request."""

        try:
            plan = self.platform.check_workflow(request_body)
            return SimplePlatformEnvelope(
                governed=True,
                ok=plan.ok_to_continue,
                status=plan.outcome,
                payload={"workflow": plan.to_dict()},
            )
        except (RuntimeCoreInvariantError, KeyError, TypeError, ValueError) as exc:
            return SimplePlatformEnvelope(
                governed=True,
                ok=False,
                status="rejected",
                payload={},
                error=str(exc),
            )

    def action_menu(self) -> SimplePlatformEnvelope:
        """Return the stable simple action vocabulary."""

        return SimplePlatformEnvelope(
            governed=True,
            ok=True,
            status="listed",
            payload={
                "actions": [
                    {
                        "action": "view",
                        "label": "View",
                        "purpose": "Read an allowed file or artifact.",
                    },
                    {
                        "action": "change",
                        "label": "Change",
                        "purpose": "Modify an allowed local file or artifact.",
                    },
                    {
                        "action": "send",
                        "label": "Send",
                        "purpose": "Prepare an external message or notification for review.",
                    },
                    {
                        "action": "verify",
                        "label": "Verify",
                        "purpose": "Check an allowed artifact before continuing.",
                    },
                ],
                "tasks": [template.to_dict() for template in self.platform.task_templates()],
                "outcomes": [
                    {"outcome": "ready", "label": "Ready"},
                    {"outcome": "needs_review", "label": "Needs approval"},
                    {"outcome": "blocked", "label": "Blocked"},
                ],
                "visibility_levels": [
                    {
                        "visibility_level": "normal_user",
                        "label": "Normal user",
                        "purpose": "Show simple status, risk, approval need, and choices.",
                    },
                    {
                        "visibility_level": "operator",
                        "label": "Operator",
                        "purpose": "Show simple status plus receipt and blocked-reason references.",
                    },
                    {
                        "visibility_level": "auditor_developer",
                        "label": "Auditor/developer",
                        "purpose": "Show proof refs, raw decision, and governance trace fields.",
                    },
                ],
                "workflows": [template.to_dict() for template in self.platform.workflow_templates()],
            },
        )

    def simple_home(self) -> SimplePlatformEnvelope:
        """Return the compact first-screen summary for simple platform users."""

        return SimplePlatformEnvelope(
            governed=True,
            ok=True,
            status="ready",
            payload={"home": self.platform.simple_home().to_dict()},
        )

    def document_manipulation_wiring(self) -> SimplePlatformEnvelope:
        """Return the read-only document manipulation wiring proof."""

        return SimplePlatformEnvelope(
            governed=True,
            ok=True,
            status="listed",
            payload={"wiring": self.platform.document_manipulation_wiring().to_dict()},
        )

    def document_manipulation_wiring_contract(self) -> SimplePlatformEnvelope:
        """Return the client contract for document wiring readback."""

        return SimplePlatformEnvelope(
            governed=True,
            ok=True,
            status="listed",
            payload={"contract": deepcopy(DOCUMENT_MANIPULATION_WIRING_CLIENT_CONTRACT)},
        )

    def start_guide(self) -> SimplePlatformEnvelope:
        """Return the plain onboarding guide for user-facing surfaces."""

        return SimplePlatformEnvelope(
            governed=True,
            ok=True,
            status="listed",
            payload={"guide": self.platform.onboarding_guide().to_dict()},
        )


def _visibility_scoped_request(
    request_body: Mapping[str, Any],
) -> tuple[SimpleVisibilityLevel, dict[str, object]]:
    """Split optional visibility from a simple request without reflection."""

    visibility_value = request_body.get("visibility_level", "normal_user")
    if not isinstance(visibility_value, str):
        raise RuntimeCoreInvariantError("visibility_level must be text")
    action_body = dict(request_body)
    action_body.pop("visibility_level", None)
    return _visibility_level_from_text(visibility_value), action_body


def _visibility_level_from_text(value: str) -> SimpleVisibilityLevel:
    normalized = value.strip().replace("-", "_")
    if normalized in {"normal_user", "operator", "auditor_developer"}:
        return normalized  # type: ignore[return-value]
    raise RuntimeCoreInvariantError(
        "visibility_level must be one of: normal_user, operator, auditor_developer"
    )
