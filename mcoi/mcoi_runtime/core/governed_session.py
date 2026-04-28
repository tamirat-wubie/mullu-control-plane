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
import logging
import os
import threading
from dataclasses import dataclass
from typing import Any, Callable, Mapping

_log = logging.getLogger(__name__)


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
class SessionPolicy:
    """Per-session action limits.

    Constrains what a governed session can do within its lifetime.
    Prevents runaway agents from burning through resources even when
    tenant-level budget is still available.  A value of 0 means unlimited.
    """

    max_llm_calls: int = 0  # 0 = unlimited
    max_operations: int = 0  # Total operations (llm + execute + query)
    max_execute_actions: int = 0  # Execute-only cap
    max_cost: float = 0.0  # Max cumulative cost ($)

    def __post_init__(self) -> None:
        if self.max_llm_calls < 0:
            raise ValueError("max_llm_calls must be >= 0")
        if self.max_operations < 0:
            raise ValueError("max_operations must be >= 0")
        if self.max_execute_actions < 0:
            raise ValueError("max_execute_actions must be >= 0")
        if self.max_cost < 0.0:
            raise ValueError("max_cost must be >= 0.0")


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
        session_policy: SessionPolicy | None = None,
        llm_cache: Any | None = None,
        usage_tracker: Any | None = None,
        decision_log: Any | None = None,
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
        self._policy = session_policy
        self._llm_cache = llm_cache
        self._usage_tracker = usage_tracker
        self._decision_log = decision_log
        self._lock = threading.Lock()
        self._closed = False
        self._operations = 0
        self._llm_calls = 0
        self._execute_actions = 0
        self._total_cost = 0.0
        self._context_messages: list[dict[str, str]] = []
        self._max_context_messages = 50
        self._compaction_count = 0
        self._auto_checkpoint_interval = 0  # 0 = disabled
        self._session_store: Any | None = None

    # ── Context Compaction ──

    def _add_context(self, role: str, content: str) -> None:
        """Add a message to the session context (for multi-turn conversations)."""
        with self._lock:
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
    def execute_actions(self) -> int:
        return self._execute_actions

    @property
    def session_policy(self) -> SessionPolicy | None:
        return self._policy

    @property
    def llm_calls(self) -> int:
        return self._llm_calls

    # ── Φ_gps Integration ──

    def frame_problem(self, **context: Any) -> dict[str, Any]:
        """Run Φ_gps Phase 0 (FRAME) on the session context.

        Returns the problem profile, ignorance map, and recommended phases.
        Cached after first call — re-frames only if context changes.
        """
        try:
            from mcoi_runtime.core.phi_gps import frame_problem
            result = frame_problem(**context)
            self._problem_profile = result
            return result.to_dict()
        except Exception:
            _log.exception("phi_gps frame_problem failed")
            return {"error": "framing unavailable"}

    def distinguish_prompt(self, prompt: str) -> dict[str, Any]:
        """Run Φ_gps Phase 1 (DISTINGUISH) on a prompt.

        Extracts symbols with confidence κ before LLM processing.
        Useful for understanding what the user is asking about.
        """
        try:
            from mcoi_runtime.core.phi_gps import distinguish
            result = distinguish(prompt)
            return result.to_dict()
        except Exception:
            _log.exception("phi_gps distinguish failed")
            return {"symbols": [], "error": "distinction unavailable"}

    def select_strategy(self, **context: Any) -> list[dict[str, Any]]:
        """Select solving strategies based on problem profile.

        Requires frame_problem() to have been called first.
        """
        try:
            from mcoi_runtime.core.phi_gps import select_strategies, frame_problem as fp
            profile_result = getattr(self, "_problem_profile", None)
            if profile_result is None:
                profile_result = fp(**context)
            strategies = select_strategies(profile_result.profile)
            return [{"name": s.name, "score": s.score} for s in strategies]
        except Exception:
            _log.exception("phi_gps select_strategy failed")
            return [{"error": "strategy selection unavailable"}]

    # ── Governance checks ──

    def _require_open(self) -> None:
        with self._lock:
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
        result = self._rate_limiter.check(
            self._tenant_id, endpoint, identity_id=self._identity_id,
        )
        if not result.allowed:
            raise RuntimeError("rate limited")

    def _check_budget(self) -> None:
        if self._budget_mgr is None:
            return
        report = self._budget_mgr.report(self._tenant_id)
        if report.exhausted:
            raise RuntimeError("budget exhausted")

    def _check_policy(self, operation: str) -> None:
        """Enforce per-session action limits."""
        if self._policy is None:
            return
        p = self._policy
        if p.max_operations > 0 and self._operations >= p.max_operations:
            raise RuntimeError("session operation limit reached")
        if operation == "llm" and p.max_llm_calls > 0 and self._llm_calls >= p.max_llm_calls:
            raise RuntimeError("session LLM call limit reached")
        if operation == "execute" and p.max_execute_actions > 0 and self._execute_actions >= p.max_execute_actions:
            raise RuntimeError("session execute action limit reached")
        if p.max_cost > 0.0 and self._total_cost >= p.max_cost:
            raise RuntimeError("session cost limit reached")

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

    def _certify_proof(
        self,
        endpoint: str,
        decision: str,
        guard_results: list[dict[str, Any]] | None = None,
    ) -> dict[str, str]:
        if self._proof_bridge is None:
            return {
                "endpoint": endpoint,
                "decision": decision,
                "proof_receipt_id": "",
                "proof_hash": "",
            }
        try:
            proof = self._proof_bridge.certify_governance_decision(
                tenant_id=self._tenant_id,
                endpoint=endpoint,
                guard_results=guard_results or [],
                decision=decision,
                actor_id=self._identity_id,
            )
            return {
                "endpoint": endpoint,
                "decision": decision,
                "proof_receipt_id": proof.capsule.receipt.receipt_id,
                "proof_hash": proof.receipt_hash,
            }
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

        Full pipeline: policy → RBAC → content safety → budget → LLM call → PII redaction → audit → proof.
        """
        self._require_open()
        self._check_policy("llm")
        self._check_tenant_gating()
        self._check_rbac("llm", "POST")
        self._check_rate_limit("session/llm")
        self._check_content_safety(prompt)
        self._check_budget()

        if self._llm_bridge is None:
            raise RuntimeError("no LLM bridge configured")

        request_proof = self._certify_proof("session/llm", "allowed")
        cache_policy_context = {
            "policy_version": str(kwargs.get("policy_version", "session-governance:v1")),
            "endpoint": "session/llm",
            "decision": "allowed",
        }

        # Check LLM cache before calling provider
        cache_hit = False
        if self._llm_cache is not None:
            cache_result = self._llm_cache.get(
                self._tenant_id,
                "default",
                "default",
                prompt,
                policy_context=cache_policy_context,
            )
            if cache_result.hit:
                result = cache_result.response
                cache_hit = True

        if not cache_hit:
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

            # Cache successful responses
            if self._llm_cache is not None and result.succeeded:
                self._llm_cache.put(
                    self._tenant_id, "default", "default", prompt,
                    result,
                    cost=result.cost,
                    policy_context=cache_policy_context,
                )

        from dataclasses import fields, is_dataclass, replace
        result_field_names = {
            field.name for field in fields(result)
        } if is_dataclass(result) else set()

        # Lambda_output_safety on response
        if result.succeeded and result.content:
            from mcoi_runtime.governance.guards.content_safety import evaluate_output_safety

            output_safety = evaluate_output_safety(
                result.content,
                chain=self._content_safety,
                pii_scanner=self._pii_scanner,
            )
            if not output_safety.allowed:
                replacement = {"content": "", "error": output_safety.reason}
                if "finished" in result_field_names:
                    replacement["finished"] = False
                if "succeeded" in result_field_names:
                    replacement["succeeded"] = False
                result = replace(result, **replacement)
            elif output_safety.content != result.content:
                result = replace(result, content=output_safety.content)

        result_metadata = dict(getattr(result, "metadata", {}) or {})
        result_metadata["request_envelope_proof"] = request_proof
        if "metadata" in result_field_names:
            result = replace(result, metadata=result_metadata)
        else:
            try:
                setattr(result, "metadata", result_metadata)
            except (AttributeError, TypeError):
                pass

        with self._lock:
            self._operations += 1
            self._llm_calls += 1
            if result.succeeded:
                self._total_cost += result.cost

        # Record to usage tracker
        if self._usage_tracker is not None and result.succeeded:
            self._usage_tracker.record_llm(
                self._tenant_id,
                tokens_in=result.input_tokens,
                tokens_out=result.output_tokens,
                cost=result.cost,
            )

        outcome = "success" if result.succeeded else "error"
        self._record_audit(
            action="session.llm",
            target="llm.complete",
            outcome=outcome,
            detail={
                "model": result.model_name, "cost": result.cost,
                "tokens": result.input_tokens + result.output_tokens,
                "cache_hit": cache_hit,
            },
        )

        self._maybe_checkpoint()
        return result

    def execute(self, action_type: str, **bindings: Any) -> dict[str, Any]:
        """Governed action execution (shell, tool, etc).

        Pipeline: policy → RBAC → tenant gating → dispatch → audit → proof.

        When a GovernedDispatcher is available, routes through the full
        governed execution pipeline. Otherwise returns governed metadata.
        """
        self._require_open()
        self._check_policy("execute")
        self._check_tenant_gating()
        self._check_rbac("execute", "POST")
        self._check_rate_limit("session/execute")
        request_proof = self._certify_proof("session/execute", "allowed")

        result_detail: dict[str, Any] = {
            "action_type": action_type,
            "bindings": dict(bindings),
            "request_envelope_proof": request_proof,
        }

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

        with self._lock:
            self._operations += 1
            self._execute_actions += 1
        if self._usage_tracker is not None:
            self._usage_tracker.record_skill(self._tenant_id, success=result_detail.get("dispatched", True))
        self._record_audit(
            action="session.execute",
            target=action_type,
            outcome="dispatched",
            detail=result_detail,
        )

        self._maybe_checkpoint()
        return {**result_detail, "governed": True}

    def query(self, resource_type: str, **filters: Any) -> dict[str, Any]:
        """Governed read-only query.

        Pipeline: policy → RBAC → query → audit → proof.
        """
        self._require_open()
        self._check_policy("query")
        self._check_rbac(resource_type, "GET")
        self._check_rate_limit("session/query")
        request_proof = self._certify_proof("session/query", "allowed")

        self._operations += 1
        self._record_audit(
            action="session.query",
            target=resource_type,
            outcome="success",
            detail={"filters": filters},
        )

        self._maybe_checkpoint()
        return {
            "resource_type": resource_type,
            "filters": filters,
            "governed": True,
            "request_envelope_proof": request_proof,
        }

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

    # ── Auto-checkpoint ──

    def enable_auto_checkpoint(self, *, interval: int, store: Any) -> None:
        """Enable auto-checkpoint every N operations.

        Args:
            interval: Checkpoint every N operations (e.g., 5).
            store: SessionStore instance to save checkpoints to.
        """
        self._auto_checkpoint_interval = interval
        self._session_store = store

    def _maybe_checkpoint(self) -> None:
        """Auto-checkpoint if interval reached."""
        if self._auto_checkpoint_interval <= 0 or self._session_store is None:
            return
        if self._operations > 0 and self._operations % self._auto_checkpoint_interval == 0:
            try:
                data = self.checkpoint()
                from mcoi_runtime.persistence.session_store import SessionCheckpoint
                cp = SessionCheckpoint.from_dict(dict(data))
                if cp is not None:
                    self._session_store.save(cp)
            except Exception:
                _log.warning("auto-checkpoint failed for session %s", self._session_id, exc_info=True)

    # ── Session persistence ──

    def checkpoint(self) -> dict[str, Any]:
        """Serialize mutable session state for persistence.

        Returns a dict suitable for passing to SessionStore.save().
        Does NOT close the session — the session remains usable.
        """
        self._require_open()
        from mcoi_runtime.persistence.session_store import SessionCheckpoint
        cp = SessionCheckpoint(
            session_id=self._session_id,
            identity_id=self._identity_id,
            tenant_id=self._tenant_id,
            operations=self._operations,
            llm_calls=self._llm_calls,
            total_cost=self._total_cost,
            context_messages=tuple(self._context_messages),
            compaction_count=self._compaction_count,
            checkpoint_at=self._clock(),
        )
        data = cp.to_dict()
        # Persist policy if set
        if self._policy is not None:
            data["session_policy"] = {
                "max_llm_calls": self._policy.max_llm_calls,
                "max_operations": self._policy.max_operations,
                "max_execute_actions": self._policy.max_execute_actions,
                "max_cost": self._policy.max_cost,
            }
        return data

    def _restore_from_checkpoint(self, data: dict[str, Any]) -> None:
        """Restore mutable state from a checkpoint dict.

        Called by Platform.resume(). Validates identity/tenant match.
        """
        if data.get("session_id") != self._session_id:
            raise ValueError("session_id mismatch")
        if data.get("identity_id") != self._identity_id:
            raise ValueError("identity_id mismatch")
        if data.get("tenant_id") != self._tenant_id:
            raise ValueError("tenant_id mismatch")
        self._operations = max(0, int(data.get("operations", 0)))
        self._llm_calls = max(0, int(data.get("llm_calls", 0)))
        self._total_cost = max(0.0, float(data.get("total_cost", 0.0)))
        self._context_messages = list(data.get("context_messages", []))
        self._compaction_count = max(0, int(data.get("compaction_count", 0)))
        # Restore policy if persisted
        policy_data = data.get("session_policy")
        if policy_data and isinstance(policy_data, dict):
            self._policy = SessionPolicy(
                max_llm_calls=int(policy_data.get("max_llm_calls", 0)),
                max_operations=int(policy_data.get("max_operations", 0)),
                max_execute_actions=int(policy_data.get("max_execute_actions", 0)),
                max_cost=float(policy_data.get("max_cost", 0.0)),
            )

    # ── Session lifecycle ──

    def close(self) -> SessionClosureReport:
        """Close the session and produce an immutable closure report."""
        with self._lock:
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
        llm_cache: Any | None = None,
        usage_tracker: Any | None = None,
        decision_log: Any | None = None,
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
        self._llm_cache = llm_cache
        self._usage_tracker = usage_tracker
        self._decision_log = decision_log
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

        from mcoi_runtime.governance.audit.trail import AuditTrail
        from mcoi_runtime.governance.guards.content_safety import build_default_safety_chain
        from mcoi_runtime.core.pii_scanner import PIIScanner
        from mcoi_runtime.core.proof_bridge import ProofBridge
        from mcoi_runtime.governance.guards.budget import TenantBudgetManager
        from mcoi_runtime.governance.guards.tenant_gating import TenantGatingRegistry
        from mcoi_runtime.persistence.postgres_governance_stores import create_governance_stores

        db_backend = os.environ.get("MULLU_DB_BACKEND", "memory")
        env = os.environ.get("MULLU_ENV", "local_dev")
        stores = create_governance_stores(backend=db_backend, connection_string=os.environ.get("MULLU_DB_URL", ""))
        allow_unknown_tenants = _env_flag("MULLU_ALLOW_UNKNOWN_TENANTS")
        if allow_unknown_tenants is None:
            allow_unknown_tenants = env in ("local_dev", "test")
        bootstrap_warnings: list[str] = []

        def _bootstrap_warning(component: str, exc: Exception) -> str:
            return f"{component} bootstrap failed ({type(exc).__name__})"

        # RBAC — load-bearing in pilot/production. See docs/GOVERNANCE_GUARD_CHAIN.md
        # §"Known gaps" entry G4.1. Pre-G4.1, a bootstrap failure here silently
        # turned RBAC into a no-op. Now: in pilot/production we refuse to boot.
        # local_dev/test still permit the optional path for development convenience.
        access_runtime = None
        try:
            from mcoi_runtime.core.event_spine import EventSpineEngine
            from mcoi_runtime.governance.guards.access import AccessRuntimeEngine
            from mcoi_runtime.core.rbac_defaults import seed_default_permissions
            spine = EventSpineEngine(clock=_clock)
            access_runtime = AccessRuntimeEngine(spine)
            seed_default_permissions(access_runtime)
        except Exception as exc:
            access_runtime = None
            bootstrap_warnings.append(_bootstrap_warning("access runtime", exc))

        platform_env = (os.environ.get("MULLU_ENV", "") or "").strip().lower()
        if access_runtime is None and platform_env in ("pilot", "production"):
            # Fail-closed boot. Same shape as G6 (stub LLM in production) and
            # G8 (CORS wildcard in production). Operating without RBAC in a
            # production-grade environment is "appearance of governance without
            # enforcement" — exactly the failure mode this spec exists to prevent.
            raise RuntimeError(
                f"RBAC engine (AccessRuntimeEngine) failed to bootstrap in "
                f"{platform_env!r} environment. The guard chain cannot enforce "
                f"access control without it. Investigate the bootstrap warning "
                f"above and either fix the underlying cause or set "
                f"MULLU_ENV=local_dev for development. See "
                f"docs/GOVERNANCE_GUARD_CHAIN.md §'Guard inventory' #5 (RBAC)."
            )

        # Optional: LLM
        llm_bridge = None
        try:
            from mcoi_runtime.app.llm_bootstrap import LLMConfig, bootstrap_llm
            result = bootstrap_llm(clock=_clock, config=LLMConfig.from_env())
            llm_bridge = result.bridge
        except Exception as exc:
            llm_bridge = None
            bootstrap_warnings.append(_bootstrap_warning("llm", exc))

        # Optional: LLM cache
        llm_cache = None
        try:
            from mcoi_runtime.core.llm_cache import LLMResponseCache
            llm_cache = LLMResponseCache()
        except Exception as exc:
            llm_cache = None
            bootstrap_warnings.append(_bootstrap_warning("llm cache", exc))

        # Optional: Tenant usage tracker
        usage_tracker = None
        try:
            from mcoi_runtime.core.tenant_usage_tracker import TenantUsageTracker
            usage_tracker = TenantUsageTracker()
        except Exception as exc:
            usage_tracker = None
            bootstrap_warnings.append(_bootstrap_warning("usage tracker", exc))

        # Optional: Governance decision log
        decision_log = None
        try:
            from mcoi_runtime.governance.audit.decision_log import GovernanceDecisionLog
            decision_log = GovernanceDecisionLog(clock=_clock)
        except Exception as exc:
            decision_log = None
            bootstrap_warnings.append(_bootstrap_warning("decision log", exc))

        # Optional: Cross-session memory
        cross_session_memory = None
        try:
            from mcoi_runtime.core.cross_session_memory import CrossSessionMemory
            cross_session_memory = CrossSessionMemory(clock=_clock)
        except Exception as exc:
            cross_session_memory = None
            bootstrap_warnings.append(_bootstrap_warning("cross-session memory", exc))

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
            llm_cache=llm_cache,
            usage_tracker=usage_tracker,
            decision_log=decision_log,
            bootstrap_warnings=tuple(bootstrap_warnings),
            bootstrap_components={
                "access_runtime": access_runtime is not None,
                "llm_bridge": llm_bridge is not None,
                "tenant_gating": True,
                "proof_bridge": True,
                "llm_cache": llm_cache is not None,
                "usage_tracker": usage_tracker is not None,
                "decision_log": decision_log is not None,
                "cross_session_memory": cross_session_memory is not None,
            },
        )

    def connect(
        self,
        *,
        identity_id: str,
        tenant_id: str,
        session_policy: SessionPolicy | None = None,
    ) -> GovernedSession:
        """Open a governed session for an identity + tenant.

        Validates tenant gating and identity status before creating session.
        Optionally applies per-session action limits via SessionPolicy.
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
            session_policy=session_policy,
            llm_cache=self._llm_cache,
            usage_tracker=self._usage_tracker,
            decision_log=self._decision_log,
        )

    def resume(
        self,
        *,
        session_id: str,
        identity_id: str,
        tenant_id: str,
        checkpoint_data: dict[str, Any],
    ) -> GovernedSession:
        """Resume a previously checkpointed session.

        Creates a new GovernedSession with live subsystems, then restores
        mutable state from the checkpoint.  Validates that session_id,
        identity_id, and tenant_id match the checkpoint.
        """
        self._session_count += 1
        session = GovernedSession(
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
            llm_cache=self._llm_cache,
            usage_tracker=self._usage_tracker,
            decision_log=self._decision_log,
        )
        session._restore_from_checkpoint(checkpoint_data)

        self._record_platform_audit(
            identity_id=identity_id,
            tenant_id=tenant_id,
            target=session_id,
            outcome="resumed",
            detail={"operations": checkpoint_data.get("operations", 0)},
        )

        return session

    @property
    def session_count(self) -> int:
        return self._session_count

    @property
    def bootstrap_warnings(self) -> tuple[str, ...]:
        return self._bootstrap_warnings

    @property
    def bootstrap_components(self) -> dict[str, bool]:
        return dict(self._bootstrap_components)

    @property
    def proof_bridge(self) -> Any | None:
        """Public accessor for the platform's ProofBridge.

        Exposed so external entry-point surfaces (e.g., the gateway
        webhook layer) can emit transition receipts at their own trust
        boundary, closing the gap documented in
        docs/MAF_RECEIPT_COVERAGE.md §"Routes NOT covered".
        """
        return self._proof_bridge
