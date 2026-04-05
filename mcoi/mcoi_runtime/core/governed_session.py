"""GovernedSession Harness — Unified governance entry point.

Purpose: Binds identity + tenant + budget + audit + safety + proof into a
    single runtime context. Every operation through a GovernedSession
    automatically flows through the full governance pipeline.
Governance scope: session lifecycle and operation dispatch.
Dependencies: Composes existing engines — does not add new governance logic.
Invariants:
  - Every operation is identity-bound, tenant-scoped, and audited.
  - Closed sessions reject all operations.
  - Budget exhaustion blocks LLM calls.
  - Content safety blocks prompt injection.
  - PII is redacted from LLM responses.
  - Proof receipts are generated for every decision.
  - Session closure produces an immutable report.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


def _classify_session_dispatch_exception(exc: Exception) -> str:
    """Return a bounded dispatch error for session-level execution."""
    exc_type = type(exc).__name__
    if isinstance(exc, TimeoutError):
        return f"session dispatch timeout ({exc_type})"
    return f"session dispatch error ({exc_type})"


def _build_session_dispatch_request(
    *,
    session_id: str,
    operation_index: int,
    action_type: str,
    bindings: Mapping[str, Any],
):
    """Build a canonical dispatch request for supported governed session actions."""
    from mcoi_runtime.core.dispatcher import DispatchRequest

    if action_type != "shell_command":
        raise ValueError("unsupported governed session action")

    argv = bindings.get("argv")
    if not isinstance(argv, (list, tuple)) or not argv:
        raise ValueError("shell_command requires non-empty argv")
    if not all(isinstance(item, str) and item.strip() for item in argv):
        raise ValueError("shell_command argv items must be non-empty strings")

    template: dict[str, Any] = {
        "template_id": f"{session_id}-{operation_index}-{action_type}",
        "action_type": action_type,
        "command_argv": list(argv),
    }

    cwd = bindings.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        template["cwd"] = cwd

    environment = bindings.get("environment")
    if isinstance(environment, Mapping) and all(
        isinstance(key, str)
        and key.strip()
        and isinstance(value, str)
        for key, value in environment.items()
    ):
        template["environment"] = dict(environment)

    timeout_seconds = bindings.get("timeout_seconds")
    if isinstance(timeout_seconds, (int, float)) and not isinstance(timeout_seconds, bool):
        template["timeout_seconds"] = float(timeout_seconds)

    return DispatchRequest(
        goal_id=f"session-{session_id}-{operation_index}",
        route=action_type,
        template=template,
        bindings={},
    )


@dataclass(frozen=True, slots=True)
class SessionClosureReport:
    """Immutable report generated when a GovernedSession is closed."""

    session_id: str
    identity_id: str
    tenant_id: str
    operations: int
    llm_calls: int
    audit_entries: int
    proof_receipts: int
    total_cost: float
    closed_at: str


class GovernedSession:
    """Unified governance harness.

    Every operation (LLM, execute, query) flows through the full pipeline:
    RBAC → content safety → budget → operation → PII redaction → audit → proof.

    Usage:
        platform = Platform.from_env()
        session = platform.connect(identity_id="user1", tenant_id="t1")
        result = session.llm("What is 2+2?")
        report = session.close()
    """

    def __init__(
        self,
        *,
        session_id: str,
        identity_id: str,
        tenant_id: str,
        clock: Callable[[], str],
        # Governance engines (all optional for testability)
        access_runtime: Any | None = None,
        content_safety_chain: Any | None = None,
        pii_scanner: Any | None = None,
        budget_mgr: Any | None = None,
        llm_bridge: Any | None = None,
        audit_trail: Any | None = None,
        proof_bridge: Any | None = None,
        tenant_gating: Any | None = None,
        governed_dispatcher: Any | None = None,
        rate_limiter: Any | None = None,
    ) -> None:
        self._session_id = session_id
        self._identity_id = identity_id
        self._tenant_id = tenant_id
        self._clock = clock
        self._access_runtime = access_runtime
        self._content_safety = content_safety_chain
        self._pii_scanner = pii_scanner
        self._budget_mgr = budget_mgr
        self._llm_bridge = llm_bridge
        self._audit_trail = audit_trail
        self._proof_bridge = proof_bridge
        self._tenant_gating = tenant_gating
        self._governed_dispatcher = governed_dispatcher
        self._rate_limiter = rate_limiter
        self._closed = False
        self._operations = 0
        self._llm_calls = 0
        self._total_cost = 0.0
        self._context_messages: list[dict[str, str]] = []
        self._max_context_messages = 50
        self._compaction_count = 0

    # ── Context Compaction ──

    def _add_context(self, role: str, content: str) -> None:
        """Add a message to the session context (for multi-turn conversations)."""
        self._context_messages.append({"role": role, "content": content})
        # Auto-compact when approaching limit
        if len(self._context_messages) > self._max_context_messages:
            self._compact_context()

    def _compact_context(self) -> None:
        """Compact older context by summarizing into a single system message.

        Preserves the last 10 messages verbatim; summarizes everything older.
        Governance state (audit, proof) is NOT compacted — only LLM context.
        """
        if len(self._context_messages) <= 10:
            return

        # Keep last 10 messages, summarize the rest
        old_messages = self._context_messages[:-10]
        recent_messages = self._context_messages[-10:]

        summary_parts = []
        for msg in old_messages:
            role = msg["role"]
            content = msg["content"][:200]  # Truncate each to 200 chars for summary
            summary_parts.append(f"[{role}]: {content}")

        summary = "Previous conversation summary:\n" + "\n".join(summary_parts)
        self._context_messages = [
            {"role": "system", "content": summary},
            *recent_messages,
        ]
        self._compaction_count += 1

    @property
    def context_message_count(self) -> int:
        return len(self._context_messages)

    @property
    def compaction_count(self) -> int:
        return self._compaction_count

    # ── Properties ──

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def identity_id(self) -> str:
        return self._identity_id

    @property
    def tenant_id(self) -> str:
        return self._tenant_id

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def operations(self) -> int:
        return self._operations

    @property
    def llm_calls(self) -> int:
        return self._llm_calls

    # ── Governance checks ──

    def _require_open(self) -> None:
        if self._closed:
            raise RuntimeError("session is closed")

    def _check_tenant_gating(self) -> None:
        if self._tenant_gating is not None:
            reason = None
            if hasattr(self._tenant_gating, "denial_reason"):
                reason = self._tenant_gating.denial_reason(self._tenant_id)
            elif not self._tenant_gating.is_allowed(self._tenant_id):
                reason = "tenant access denied"
            if reason is not None:
                raise PermissionError(reason)

    def _check_rbac(self, resource_type: str, action: str) -> None:
        if self._access_runtime is None:
            return
        from mcoi_runtime.contracts.access_runtime import AccessDecision
        req_id = f"session-{self._session_id}-{self._operations}"
        try:
            evaluation = self._access_runtime.evaluate_access(
                req_id, self._identity_id,
                resource_type=resource_type, action=action,
                scope_ref_id=self._tenant_id,
            )
            if evaluation.decision == AccessDecision.DENIED:
                raise PermissionError("access denied")
            if evaluation.decision == AccessDecision.REQUIRES_APPROVAL:
                raise PermissionError("approval required")
        except PermissionError:
            raise
        except Exception:
            raise PermissionError("access evaluation failed")

    def _check_content_safety(self, content: str) -> None:
        if self._content_safety is None or not content:
            return
        result = self._content_safety.evaluate(content)
        if result.verdict.value == "blocked":
            raise ValueError("content blocked")

    def _check_rate_limit(self, endpoint: str) -> None:
        if self._rate_limiter is None:
            return
        result = self._rate_limiter.check(self._tenant_id, endpoint)
        if not result.allowed:
            raise RuntimeError(
                f"rate limited: retry after {result.retry_after_seconds}s"
            )

    def _check_budget(self) -> None:
        if self._budget_mgr is None:
            return
        report = self._budget_mgr.report(self._tenant_id)
        if report.exhausted:
            raise RuntimeError("budget exhausted")

    def _redact_pii(self, text: str) -> str:
        if self._pii_scanner is None or not text:
            return text
        result = self._pii_scanner.scan(text)
        return result.redacted_text if result.pii_detected else text

    def _record_audit(self, action: str, target: str, outcome: str, detail: dict[str, Any] | None = None) -> None:
        if self._audit_trail is None:
            return
        self._audit_trail.record(
            action=action,
            actor_id=self._identity_id,
            tenant_id=self._tenant_id,
            target=target,
            outcome=outcome,
            detail=detail or {},
        )

    def _certify_proof(self, endpoint: str, decision: str, guard_results: list[dict[str, Any]] | None = None) -> None:
        if self._proof_bridge is None:
            return
        try:
            self._proof_bridge.certify_governance_decision(
                tenant_id=self._tenant_id,
                endpoint=endpoint,
                guard_results=guard_results or [],
                decision=decision,
                actor_id=self._identity_id,
            )
        except Exception as exc:
            self._record_audit(
                action="session.proof",
                target=endpoint,
                outcome="error",
                detail={"error": f"proof certification failed ({type(exc).__name__})"},
            )
            raise RuntimeError("proof certification failed")

    # ── Core operations ──

    def llm(self, prompt: str, **kwargs: Any) -> Any:
        """Governed LLM completion.

        Full pipeline: RBAC → content safety → budget → LLM call → PII redaction → audit → proof.
        """
        self._require_open()
        self._check_tenant_gating()
        self._check_rbac("llm", "POST")
        self._check_rate_limit("session/llm")
        self._check_content_safety(prompt)
        self._check_budget()

        if self._llm_bridge is None:
            raise RuntimeError("no LLM bridge configured")

        self._certify_proof("session/llm", "allowed")

        # Track context for multi-turn conversations
        self._add_context("user", prompt)

        result = self._llm_bridge.complete(
            prompt,
            tenant_id=self._tenant_id,
            budget_id=f"tenant-{self._tenant_id}",
            **kwargs,
        )

        # Track response in context
        if result.succeeded and result.content:
            self._add_context("assistant", result.content)

        # PII redaction on response
        if result.succeeded and result.content:
            redacted = self._redact_pii(result.content)
            if redacted != result.content:
                from dataclasses import replace
                result = replace(result, content=redacted)

        self._operations += 1
        self._llm_calls += 1
        if result.succeeded:
            self._total_cost += result.cost

        outcome = "success" if result.succeeded else "error"
        self._record_audit(
            action="session.llm",
            target="llm.complete",
            outcome=outcome,
            detail={"model": result.model_name, "cost": result.cost, "tokens": result.input_tokens + result.output_tokens},
        )

        return result

    def execute(self, action_type: str, **bindings: Any) -> dict[str, Any]:
        """Governed action execution (shell, tool, etc).

        Pipeline: RBAC → tenant gating → dispatch → audit → proof.

        When a GovernedDispatcher is available, routes through the full
        governed execution pipeline. Otherwise returns governed metadata.
        """
        self._require_open()
        self._check_tenant_gating()
        self._check_rbac("execute", "POST")
        self._check_rate_limit("session/execute")
        self._certify_proof("session/execute", "allowed")

        result_detail: dict[str, Any] = {"action_type": action_type, "bindings": dict(bindings)}

        # Route through GovernedDispatcher if available
        if self._governed_dispatcher is not None:
            try:
                from mcoi_runtime.core.governed_dispatcher import GovernedDispatchContext
                context = GovernedDispatchContext(
                    actor_id=self._identity_id,
                    intent_id=f"session-{self._session_id}-{self._operations}",
                    request=_build_session_dispatch_request(
                        session_id=self._session_id,
                        operation_index=self._operations,
                        action_type=action_type,
                        bindings=bindings,
                    ),
                    mode="reality",
                    budget_remaining=0.0,
                    current_load=0.0,
                )
                dispatch_result = self._governed_dispatcher.governed_dispatch(context)
                result_detail["dispatched"] = True
                result_detail["blocked"] = dispatch_result.blocked
                if dispatch_result.blocked:
                    result_detail["block_reason"] = dispatch_result.block_reason
            except ImportError:
                result_detail["dispatched"] = False
            except Exception as exc:
                result_detail["dispatched"] = False
                result_detail["dispatch_error"] = _classify_session_dispatch_exception(exc)

        self._operations += 1
        self._record_audit(
            action="session.execute",
            target=action_type,
            outcome="dispatched",
            detail=result_detail,
        )

        return {**result_detail, "governed": True}

    def query(self, resource_type: str, **filters: Any) -> dict[str, Any]:
        """Governed read-only query.

        Pipeline: RBAC → query → audit → proof.
        """
        self._require_open()
        self._check_rbac(resource_type, "GET")
        self._check_rate_limit("session/query")
        self._certify_proof("session/query", "allowed")

        self._operations += 1
        self._record_audit(
            action="session.query",
            target=resource_type,
            outcome="success",
            detail={"filters": filters},
        )

        return {"resource_type": resource_type, "filters": filters, "governed": True}

    # ── Identity & access ──

    def has_permission(self, resource: str, action: str) -> bool:
        """Check if this session's identity has a specific permission."""
        if self._access_runtime is None:
            return True
        from mcoi_runtime.contracts.access_runtime import AccessDecision
        req_id = f"check-{self._session_id}-{resource}-{action}"
        try:
            evaluation = self._access_runtime.evaluate_access(
                req_id, self._identity_id,
                resource_type=resource, action=action,
                scope_ref_id=self._tenant_id,
            )
            return evaluation.decision == AccessDecision.ALLOWED
        except Exception as exc:
            self._record_audit(
                action="session.has_permission",
                target=resource,
                outcome="error",
                detail={
                    "action": action,
                    "error": f"access evaluation failed ({type(exc).__name__})",
                },
            )
            return False

    # ── Session lifecycle ──

    def close(self) -> SessionClosureReport:
        """Close the session and produce an immutable closure report."""
        if self._closed:
            raise RuntimeError("session already closed")

        self._closed = True
        closed_at = self._clock()

        audit_count = self._audit_trail.entry_count if self._audit_trail else 0
        proof_count = self._proof_bridge.receipt_count if self._proof_bridge else 0

        self._record_audit(
            action="session.close",
            target=self._session_id,
            outcome="success",
            detail={"operations": self._operations, "llm_calls": self._llm_calls, "total_cost": self._total_cost},
        )

        return SessionClosureReport(
            session_id=self._session_id,
            identity_id=self._identity_id,
            tenant_id=self._tenant_id,
            operations=self._operations,
            llm_calls=self._llm_calls,
            audit_entries=audit_count,
            proof_receipts=proof_count,
            total_cost=self._total_cost,
            closed_at=closed_at,
        )


class Platform:
    """Entry point for the governed platform.

    Wraps all governance subsystems into a programmable interface.
    Creates GovernedSessions bound to identity + tenant.

    Usage:
        platform = Platform.from_env()
        session = platform.connect(identity_id="user1", tenant_id="t1")
    """

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        access_runtime: Any | None = None,
        content_safety_chain: Any | None = None,
        pii_scanner: Any | None = None,
        budget_mgr: Any | None = None,
        llm_bridge: Any | None = None,
        audit_trail: Any | None = None,
        proof_bridge: Any | None = None,
        tenant_gating: Any | None = None,
        governed_dispatcher: Any | None = None,
        rate_limiter: Any | None = None,
        bootstrap_warnings: tuple[str, ...] = (),
        bootstrap_components: dict[str, bool] | None = None,
    ) -> None:
        self._clock = clock
        self._access_runtime = access_runtime
        self._content_safety = content_safety_chain
        self._pii_scanner = pii_scanner
        self._budget_mgr = budget_mgr
        self._llm_bridge = llm_bridge
        self._audit_trail = audit_trail
        self._proof_bridge = proof_bridge
        self._tenant_gating = tenant_gating
        self._governed_dispatcher = governed_dispatcher
        self._rate_limiter = rate_limiter
        self._bootstrap_warnings = tuple(bootstrap_warnings)
        self._bootstrap_components = dict(bootstrap_components or {})
        self._session_count = 0

    def _record_platform_audit(
        self,
        *,
        identity_id: str,
        tenant_id: str,
        target: str,
        outcome: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        if self._audit_trail is None:
            return
        self._audit_trail.record(
            action="platform.connect",
            actor_id=identity_id,
            tenant_id=tenant_id,
            target=target,
            outcome=outcome,
            detail=detail or {},
        )

    def _resolve_identity_for_connect(self, identity_id: str, tenant_id: str) -> Any | None:
        if self._access_runtime is None:
            return None

        from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

        try:
            if hasattr(self._access_runtime, "get_identity"):
                return self._access_runtime.get_identity(identity_id)
            identities = getattr(self._access_runtime, "_identities", None)
            if isinstance(identities, dict):
                return identities.get(identity_id)
        except RuntimeCoreInvariantError:
            return None
        except Exception as exc:
            self._record_platform_audit(
                identity_id=identity_id,
                tenant_id=tenant_id,
                target="identity",
                outcome="error",
                detail={"error": f"identity resolution failed ({type(exc).__name__})"},
            )
            raise PermissionError("identity resolution failed")
        return None

    @classmethod
    def from_server(cls) -> Platform:
        """Create Platform from server.py globals (HTTP context).

        Uses importlib to avoid static import cycle with server.py.
        """
        import importlib
        server = importlib.import_module("mcoi_runtime.app.server")
        return cls(
            clock=server._clock,
            access_runtime=server.access_runtime,
            content_safety_chain=server.content_safety_chain,
            pii_scanner=server.pii_scanner,
            budget_mgr=server.tenant_budget_mgr,
            llm_bridge=server.llm_bootstrap_result.bridge,
            audit_trail=server.audit_trail,
            proof_bridge=server.proof_bridge,
            tenant_gating=server._tenant_gating,
            bootstrap_warnings=tuple(
                warning
                for warning in (getattr(server, "_field_encryption_bootstrap", {}).get("warning", ""),)
                if warning
            ),
            bootstrap_components={
                "access_runtime": server.access_runtime is not None,
                "llm_bridge": server.llm_bootstrap_result.bridge is not None,
                "tenant_gating": server._tenant_gating is not None,
                "proof_bridge": server.proof_bridge is not None,
                "field_encryption": bool(
                    getattr(server, "_field_encryption_bootstrap", {}).get("enabled", False)
                ),
            },
        )

    @classmethod
    def from_env(cls) -> Platform:
        """Create standalone Platform from environment (CLI/SDK context).

        Bootstraps minimal governance subsystems without starting FastAPI.
        """
        import os
        from datetime import datetime, timezone

        def _clock() -> str:
            return datetime.now(timezone.utc).isoformat()

        def _env_flag(name: str) -> bool | None:
            raw = os.environ.get(name)
            if raw is None:
                return None
            normalized = raw.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
            raise ValueError("value must be a boolean flag")

        from mcoi_runtime.core.audit_trail import AuditTrail
        from mcoi_runtime.core.content_safety import build_default_safety_chain
        from mcoi_runtime.core.pii_scanner import PIIScanner
        from mcoi_runtime.core.proof_bridge import ProofBridge
        from mcoi_runtime.core.tenant_budget import TenantBudgetManager
        from mcoi_runtime.core.tenant_gating import TenantGatingRegistry
        from mcoi_runtime.persistence.postgres_governance_stores import create_governance_stores

        db_backend = os.environ.get("MULLU_DB_BACKEND", "memory")
        env = os.environ.get("MULLU_ENV", "local_dev")
        stores = create_governance_stores(backend=db_backend, connection_string=os.environ.get("MULLU_DB_URL", ""))
        allow_unknown_tenants = _env_flag("MULLU_ALLOW_UNKNOWN_TENANTS")
        if allow_unknown_tenants is None:
            allow_unknown_tenants = env in ("local_dev", "test")
        bootstrap_warnings: list[str] = []

        # Optional: RBAC
        access_runtime = None
        try:
            from mcoi_runtime.core.event_spine import EventSpineEngine
            from mcoi_runtime.core.access_runtime import AccessRuntimeEngine
            from mcoi_runtime.core.rbac_defaults import seed_default_permissions
            spine = EventSpineEngine(clock=_clock)
            access_runtime = AccessRuntimeEngine(spine)
            seed_default_permissions(access_runtime)
        except Exception as exc:
            access_runtime = None
            bootstrap_warnings.append(
                f"access runtime bootstrap failed ({type(exc).__name__})"
            )

        # Optional: LLM
        llm_bridge = None
        try:
            from mcoi_runtime.app.llm_bootstrap import LLMConfig, bootstrap_llm
            result = bootstrap_llm(clock=_clock, config=LLMConfig.from_env())
            llm_bridge = result.bridge
        except Exception as exc:
            llm_bridge = None
            bootstrap_warnings.append(
                f"llm bootstrap failed ({type(exc).__name__})"
            )

        return cls(
            clock=_clock,
            access_runtime=access_runtime,
            content_safety_chain=build_default_safety_chain(),
            pii_scanner=PIIScanner(),
            budget_mgr=TenantBudgetManager(clock=_clock, store=stores["budget"]),
            llm_bridge=llm_bridge,
            audit_trail=AuditTrail(clock=_clock, store=stores["audit"]),
            proof_bridge=ProofBridge(clock=_clock),
            tenant_gating=TenantGatingRegistry(
                clock=_clock,
                store=stores["tenant_gating"],
                allow_unknown_tenants=allow_unknown_tenants,
            ),
            bootstrap_warnings=tuple(bootstrap_warnings),
            bootstrap_components={
                "access_runtime": access_runtime is not None,
                "llm_bridge": llm_bridge is not None,
                "tenant_gating": True,
                "proof_bridge": True,
            },
        )

    def connect(
        self,
        *,
        identity_id: str,
        tenant_id: str,
    ) -> GovernedSession:
        """Open a governed session for an identity + tenant.

        Validates tenant gating and identity status before creating session.
        """
        # Validate tenant is not suspended/terminated
        if self._tenant_gating is not None:
            reason = None
            if hasattr(self._tenant_gating, "denial_reason"):
                reason = self._tenant_gating.denial_reason(tenant_id)
            elif not self._tenant_gating.is_allowed(tenant_id):
                reason = "tenant access denied"
            if reason is not None:
                raise PermissionError(reason)

        # Validate identity exists and is enabled (if RBAC is available)
        if self._access_runtime is not None:
            identity = self._resolve_identity_for_connect(identity_id, tenant_id)
            if identity is None:
                self._record_platform_audit(
                    identity_id=identity_id,
                    tenant_id=tenant_id,
                    target="identity",
                    outcome="denied",
                    detail={"error": "identity not registered"},
                )
                raise PermissionError("identity not registered")
            identity_tenant_id = getattr(identity, "tenant_id", "")
            if isinstance(identity_tenant_id, str) and identity_tenant_id and identity_tenant_id != tenant_id:
                self._record_platform_audit(
                    identity_id=identity_id,
                    tenant_id=tenant_id,
                    target="identity",
                    outcome="denied",
                    detail={"error": "identity tenant mismatch"},
                )
                raise PermissionError("identity tenant mismatch")
            if getattr(identity, "enabled", False) is not True:
                self._record_platform_audit(
                    identity_id=identity_id,
                    tenant_id=tenant_id,
                    target="identity",
                    outcome="denied",
                    detail={"error": "identity disabled"},
                )
                raise PermissionError("identity disabled")

        self._session_count += 1
        session_id = f"gs-{hashlib.sha256(f'{identity_id}:{tenant_id}:{self._session_count}'.encode()).hexdigest()[:12]}"

        return GovernedSession(
            session_id=session_id,
            identity_id=identity_id,
            tenant_id=tenant_id,
            clock=self._clock,
            access_runtime=self._access_runtime,
            content_safety_chain=self._content_safety,
            pii_scanner=self._pii_scanner,
            budget_mgr=self._budget_mgr,
            llm_bridge=self._llm_bridge,
            audit_trail=self._audit_trail,
            proof_bridge=self._proof_bridge,
            tenant_gating=self._tenant_gating,
            governed_dispatcher=self._governed_dispatcher,
            rate_limiter=self._rate_limiter,
        )

    @property
    def session_count(self) -> int:
        return self._session_count

    @property
    def bootstrap_warnings(self) -> tuple[str, ...]:
        return self._bootstrap_warnings

    @property
    def bootstrap_components(self) -> dict[str, bool]:
        return dict(self._bootstrap_components)
