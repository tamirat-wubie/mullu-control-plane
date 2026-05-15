"""Purpose: pin canonical HTTP and GovernedSession guard-chain order.
Governance scope: executable contract for docs/GOVERNANCE_GUARD_CHAIN.md.
Dependencies: HTTP guard-chain builder and GovernedSession public operations.
Invariants:
  - HTTP guard slots keep their documented order by guard name.
  - Session methods keep their documented check/proof/operation/audit order.
  - Drift in either chain fails as a governance-spec change, not a silent refactor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from mcoi_runtime.app.middleware import build_guard_chain
from mcoi_runtime.core.governed_session import GovernedSession


@dataclass
class _LLMResult:
    succeeded: bool = True
    content: str = "answer"
    model_name: str = "stub-model"
    cost: float = 0.0
    input_tokens: int = 1
    output_tokens: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


class _RecordingLLMBridge:
    def __init__(self, events: list[str]) -> None:
        self._events = events

    def complete(self, *_args: Any, **_kwargs: Any) -> _LLMResult:
        self._events.append("llm_call")
        return _LLMResult()


def _session(events: list[str]) -> GovernedSession:
    session = GovernedSession(
        session_id="session-order",
        identity_id="identity-order",
        tenant_id="tenant-order",
        clock=lambda: "2026-01-01T00:00:00Z",
        llm_bridge=_RecordingLLMBridge(events),
    )
    _patch_session_order_recorders(session, events)
    return session


def _patch_session_order_recorders(session: GovernedSession, events: list[str]) -> None:
    def record(name: str):
        def _recorder(*_args: Any, **_kwargs: Any) -> None:
            events.append(name)

        return _recorder

    session._require_open = record("closed_check")  # type: ignore[method-assign]
    session._check_policy = record("policy")  # type: ignore[method-assign]
    session._check_tenant_gating = record("tenant_gating")  # type: ignore[method-assign]
    session._check_rbac = record("rbac")  # type: ignore[method-assign]
    session._check_rate_limit = record("rate_limit")  # type: ignore[method-assign]
    session._check_content_safety = record("content_safety_input")  # type: ignore[method-assign]
    session._check_budget = record("budget")  # type: ignore[method-assign]
    session._record_audit = record("audit")  # type: ignore[method-assign]

    def certify(*_args: Any, **_kwargs: Any) -> dict[str, str]:
        events.append("proof")
        return {
            "endpoint": "stub",
            "decision": "allowed",
            "proof_receipt_id": "",
            "proof_hash": "",
        }

    session._certify_proof = certify  # type: ignore[method-assign]


def test_http_guard_chain_canonical_order_with_all_slots() -> None:
    chain = build_guard_chain(
        api_key_mgr=object(),
        jwt_authenticator=object(),
        rate_limiter=object(),
        budget_mgr=object(),
        tenant_gating_registry=object(),
        access_runtime=object(),
        content_safety_chain=object(),
        temporal_runtime=object(),
    )

    assert chain.guard_names() == [
        "api_key",
        "jwt",
        "tenant",
        "tenant_gating",
        "rbac",
        "Lambda_input_safety",
        "temporal",
        "rate_limit",
        "budget",
    ]


def test_session_llm_canonical_order(monkeypatch) -> None:
    events: list[str] = []

    def output_safety(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        events.append("content_safety_output")
        return SimpleNamespace(allowed=True, content="answer", reason="")

    monkeypatch.setattr(
        "mcoi_runtime.governance.guards.content_safety.evaluate_output_safety",
        output_safety,
    )

    _session(events).llm("hello")

    assert events == [
        "closed_check",
        "policy",
        "tenant_gating",
        "rbac",
        "rate_limit",
        "content_safety_input",
        "budget",
        "proof",
        "llm_call",
        "content_safety_output",
        "audit",
    ]


def test_session_execute_canonical_order() -> None:
    events: list[str] = []

    _session(events).execute("noop")

    assert events == [
        "closed_check",
        "policy",
        "tenant_gating",
        "rbac",
        "rate_limit",
        "proof",
        "audit",
    ]


def test_session_query_canonical_order() -> None:
    events: list[str] = []

    _session(events).query("documents")

    assert events == [
        "closed_check",
        "policy",
        "rbac",
        "rate_limit",
        "proof",
        "audit",
    ]
