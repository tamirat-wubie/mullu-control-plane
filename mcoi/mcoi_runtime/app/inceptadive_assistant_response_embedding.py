"""Redacted InceptaDive metadata for assistant response envelopes.

Purpose: attach advisory-only InceptaDive shadow metadata to live assistant
response envelopes without changing response content, conversation state, or
dispatch authority.
Governance scope: assistant response metadata only; no connector dispatch,
memory write authority, execution approval, or governance-verdict replacement.
Dependencies: InceptaDive shadow runtime facade and non-executing hook helpers.
Invariants: raw user input and assistant content are inspected only inside the
bounded shadow runtime and are never returned by this embedder.
"""

from __future__ import annotations

from collections.abc import Sequence

from mcoi_runtime.app.inceptadive_shadow_integration import InceptaDiveShadowRuntime
from mcoi_runtime.core.inceptadive_shadow_hooks import run_workflow_shadow_hook
from mcoi_runtime.core.inceptadive_shadow_types import ShadowSeverity


def build_assistant_response_shadow_advisory(
    runtime: InceptaDiveShadowRuntime,
    *,
    request_id: str,
    user_input: str,
    assistant_content: str,
    route: str,
    tenant_id: str,
    model_name: str,
    succeeded: bool,
    created_at: str,
) -> dict[str, object]:
    """Return redacted shadow metadata for one assistant response envelope.

    Input contract: caller supplies the already-selected shadow runtime and the
    live response boundary facts. Output contract: JSON-compatible metadata
    carrying no execution authority. Error contract: advisory failures are
    converted to a bounded unavailable record so response content remains under
    the normal route contract.
    """

    try:
        outcome = run_workflow_shadow_hook(
            runtime,
            request_id=request_id,
            user_input=user_input,
            workflow_steps=_response_shadow_steps(assistant_content, succeeded=succeeded),
            normal_intent="assistant_response",
            explicit_target=route,
            scope=tenant_id,
            risk_level=_response_shadow_risk(user_input, assistant_content, succeeded=succeeded),
            external_side_effect=False,
            created_at=created_at,
        )
        advisory = outcome.to_dict()
    except Exception as exc:  # noqa: BLE001 - advisory cannot perturb response path
        advisory = {
            "status": "unavailable",
            "error_code": "inceptadive_assistant_response_advisory_unavailable",
            "error_type": type(exc).__name__,
            "governance_required": True,
            "execution_authority": False,
            "raw_request_text_exposed": False,
            "assistant_content_exposed": False,
            "private_memory_exposed": False,
            "created_at": created_at,
        }

    advisory.update(
        {
            "embedding_surface": "assistant_response",
            "route": route,
            "tenant_id": tenant_id or "system",
            "model_name": model_name or "unknown",
            "assistant_content_exposed": False,
            "shadow_memory_write_authority": False,
            "connector_dispatch_authority": False,
            "governance_verdict_replaced": False,
        }
    )
    return advisory


def _response_shadow_steps(assistant_content: str, *, succeeded: bool) -> tuple[str, ...]:
    labels = ["assistant_response.generated" if succeeded else "assistant_response.failed"]
    text = _lower_text(assistant_content)
    for label, terms in (
        ("assistant_response.high_impact_terms_present", ("deploy", "release", "publish", "merge", "launch")),
        ("assistant_response.external_terms_present", ("send", "email", "notify", "post", "message")),
        ("assistant_response.destructive_terms_present", ("delete", "destroy", "purge", "wipe", "drop")),
        ("assistant_response.secret_terms_present", ("secret", "token", "credential", "password")),
    ):
        if _has_any_term(text, terms):
            labels.append(label)
    return tuple(labels)


def _response_shadow_risk(user_input: str, assistant_content: str, *, succeeded: bool) -> ShadowSeverity:
    if not succeeded:
        return ShadowSeverity.MEDIUM
    text = _lower_text(user_input + " " + assistant_content)
    if _has_any_term(text, ("delete", "destroy", "purge", "wipe", "drop", "secret", "token", "production", "prod")):
        return ShadowSeverity.HIGH
    if _has_any_term(text, ("deploy", "release", "publish", "merge", "launch", "send", "email", "payment")):
        return ShadowSeverity.MEDIUM
    return ShadowSeverity.LOW


def _has_any_term(text: str, terms: Sequence[str]) -> bool:
    return any(term in text.split() for term in terms)


def _lower_text(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())
