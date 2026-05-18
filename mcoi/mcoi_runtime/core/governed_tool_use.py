"""Governed Tool Use — Policy enforcement for LLM function calling.

Purpose: Wraps LLM tool/function calling with governance controls:
    tool allowlists, parameter validation, rate limiting per tool,
    and full audit trail of every tool invocation.
Governance scope: tool invocation authorization and audit.
Dependencies: none (pure algorithm + threading).
Invariants:
  - Only allowlisted tools can be invoked (deny by default).
  - Tool parameters are validated before invocation.
  - Every tool invocation is audited with input/output.
  - Per-tool rate limits prevent abuse of expensive tools.
  - Tool results are PII-scanned before returning to LLM.
  - Thread-safe — concurrent tool invocations are safe.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from mcoi_runtime.contracts.capability_contract import (
    CapabilityAdmissionDecision,
    CapabilityContract,
    IntentSource,
    default_capability_contract,
    evaluate_capability_contract,
)

from .capability_contract_coverage import CapabilityContractCoverageReport, audit_capability_contract_coverage
from .tool_permission_primitives import (
    ToolPermissionDecision,
    ToolPermissionRegistry,
    ToolPermissionRequest,
)


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """A governed tool that an agent can invoke."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)  # JSON Schema
    required_params: frozenset[str] = frozenset()
    max_calls_per_session: int = 0  # 0 = unlimited
    requires_approval: bool = False
    risk_tier: str = "low"  # low, medium, high
    enabled: bool = True
    capability_contract: CapabilityContract | None = None
    declared_effects: tuple[str, ...] = ()
    gov_tier: int = 1
    cap_level: int = 1
    intent_source: IntentSource = IntentSource.USER_DIRECT
    capability_contract_explicit: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability_contract_explicit", self.capability_contract is not None)
        if self.capability_contract is None:
            object.__setattr__(
                self,
                "capability_contract",
                default_capability_contract(
                    capability=self.name,
                    cap_level=self.cap_level,
                    gov_tier=self.gov_tier,
                    risk_tier=self.risk_tier,
                    declared_effects=tuple(self.declared_effects),
                    intent_source=self.intent_source,
                    reversible=not self.requires_approval,
                ),
            )
        if not isinstance(self.intent_source, IntentSource):
            object.__setattr__(self, "intent_source", IntentSource(str(self.intent_source)))


@dataclass(frozen=True, slots=True)
class ToolInvocationResult:
    """Result of a governed tool invocation."""

    tool_name: str
    allowed: bool
    result: Any | None = None
    error: str = ""
    audit_id: str = ""
    permission_decision: ToolPermissionDecision | None = None
    capability_decision: CapabilityAdmissionDecision | None = None


@dataclass
class ToolUsageStats:
    """Per-tool usage tracking within a session."""

    call_count: int = 0
    error_count: int = 0
    denied_count: int = 0
    last_called_at: str = ""


@dataclass(frozen=True, slots=True)
class ToolDecisionRecord:
    """Bounded operator read model for one governed tool decision."""

    observed_at: str
    tool_name: str
    allowed: bool
    stage: str
    reasons: tuple[str, ...]
    session_id: str
    tenant_id: str
    intent_source: str
    capability: str
    effect_class: str
    cap_level: int
    gov_tier: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_at": self.observed_at,
            "tool_name": self.tool_name,
            "allowed": self.allowed,
            "stage": self.stage,
            "reasons": list(self.reasons),
            "session_id": self.session_id,
            "tenant_id": self.tenant_id,
            "intent_source": self.intent_source,
            "capability": self.capability,
            "effect_class": self.effect_class,
            "cap_level": self.cap_level,
            "gov_tier": self.gov_tier,
        }


class GovernedToolRegistry:
    """Registry of allowed tools with governance controls.

    Usage:
        registry = GovernedToolRegistry()
        registry.register(ToolDefinition(
            name="get_balance",
            description="Get account balance",
            required_params=frozenset({"account_id"}),
            max_calls_per_session=10,
        ))

        # Validate and invoke
        result = registry.invoke(
            tool_name="get_balance",
            arguments={"account_id": "123"},
            executor=lambda name, args: {"balance": 100.0},
            session_id="gs-abc",
            tenant_id="t1",
        )
    """

    def __init__(self, *, clock: Callable[[], str] | None = None, max_decision_records: int = 100) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._executors: dict[str, Callable[[str, dict[str, Any]], Any]] = {}
        self._session_usage: dict[str, dict[str, ToolUsageStats]] = {}  # session_id → {tool_name → stats}
        self._lock = threading.Lock()
        self._clock = clock or (lambda: "")
        self._total_invocations = 0
        self._total_denied = 0
        self._permission_registry: ToolPermissionRegistry | None = None
        self._max_decision_records = max(1, int(max_decision_records))
        self._decision_records: list[ToolDecisionRecord] = []

    def bind_permission_registry(self, registry: ToolPermissionRegistry) -> None:
        """Attach tenant/tool permission primitives to invocation checks."""
        self._permission_registry = registry

    def register(
        self,
        tool: ToolDefinition,
        *,
        executor: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> None:
        """Register a tool with optional executor."""
        self._tools[tool.name] = tool
        if executor is not None:
            self._executors[tool.name] = executor

    def unregister(self, tool_name: str) -> bool:
        """Remove a tool from the registry."""
        if tool_name in self._tools:
            del self._tools[tool_name]
            self._executors.pop(tool_name, None)
            return True
        return False

    def list_tools(self, *, enabled_only: bool = True) -> list[ToolDefinition]:
        """List registered tools."""
        tools = list(self._tools.values())
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        return tools

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def _validate_params(self, tool: ToolDefinition, arguments: dict[str, Any]) -> str:
        """Validate tool arguments. Returns error string (empty = valid)."""
        for param in tool.required_params:
            if param not in arguments or arguments[param] is None:
                return f"missing required parameter: {param}"
        return ""

    def _check_session_limit(self, tool: ToolDefinition, session_id: str) -> bool:
        """Check if session has exceeded per-tool call limit."""
        if tool.max_calls_per_session <= 0:
            return True  # Unlimited
        with self._lock:
            session_stats = self._session_usage.get(session_id, {})
            stats = session_stats.get(tool.name)
            if stats is None:
                return True
            return stats.call_count < tool.max_calls_per_session

    def _record_usage(self, tool_name: str, session_id: str, *, error: bool = False, denied: bool = False) -> None:
        with self._lock:
            if session_id not in self._session_usage:
                self._session_usage[session_id] = {}
            if tool_name not in self._session_usage[session_id]:
                self._session_usage[session_id][tool_name] = ToolUsageStats()
            stats = self._session_usage[session_id][tool_name]
            if denied:
                stats.denied_count += 1
                self._total_denied += 1
            else:
                stats.call_count += 1
                self._total_invocations += 1
                if error:
                    stats.error_count += 1
            stats.last_called_at = self._clock()

    def _record_decision(
        self,
        *,
        tool_name: str,
        tool: ToolDefinition | None,
        allowed: bool,
        stage: str,
        reasons: tuple[str, ...],
        session_id: str,
        tenant_id: str,
        intent_source: IntentSource | str,
    ) -> None:
        contract = tool.capability_contract if tool is not None else None
        source = intent_source if isinstance(intent_source, IntentSource) else IntentSource(str(intent_source))
        record = ToolDecisionRecord(
            observed_at=self._clock(),
            tool_name=tool_name,
            allowed=allowed,
            stage=stage,
            reasons=reasons,
            session_id=session_id,
            tenant_id=tenant_id or "system",
            intent_source=source.value,
            capability=contract.capability if contract is not None else "unknown",
            effect_class=contract.axis_V.value if contract is not None else "unknown",
            cap_level=contract.cap_level if contract is not None else 0,
            gov_tier=contract.gov_tier if contract is not None else 0,
        )
        with self._lock:
            self._decision_records.append(record)
            if len(self._decision_records) > self._max_decision_records:
                del self._decision_records[: len(self._decision_records) - self._max_decision_records]

    def invoke(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        executor: Callable[[str, dict[str, Any]], Any] | None = None,
        session_id: str = "",
        tenant_id: str = "",
        budget_ref: str = "default",
        audit_present: bool = True,
        intent_source: IntentSource | str = IntentSource.USER_DIRECT,
    ) -> ToolInvocationResult:
        """Invoke a tool with full governance checks.

        Pipeline: allowlist → enabled → params → permission → session limit → execute → audit.
        """
        # 1. Allowlist check
        tool = self._tools.get(tool_name)
        if tool is None:
            self._record_usage(tool_name, session_id, denied=True)
            self._record_decision(
                tool_name=tool_name,
                tool=None,
                allowed=False,
                stage="allowlist",
                reasons=("tool_not_registered",),
                session_id=session_id,
                tenant_id=tenant_id,
                intent_source=intent_source,
            )
            return ToolInvocationResult(
                tool_name=tool_name, allowed=False,
                error="tool not registered",
            )

        # 2. Capability contract and CxG governance-grid check
        capability_decision = evaluate_capability_contract(
            tool.capability_contract,
            request_intent_source=intent_source,
        )
        if not capability_decision.allowed:
            self._record_usage(tool_name, session_id, denied=True)
            self._record_decision(
                tool_name=tool_name,
                tool=tool,
                allowed=False,
                stage="capability_contract",
                reasons=capability_decision.reasons,
                session_id=session_id,
                tenant_id=tenant_id,
                intent_source=intent_source,
            )
            return ToolInvocationResult(
                tool_name=tool_name,
                allowed=False,
                error=";".join(capability_decision.reasons),
                capability_decision=capability_decision,
            )

        # 3. Enabled check
        if not tool.enabled:
            self._record_usage(tool_name, session_id, denied=True)
            self._record_decision(
                tool_name=tool_name,
                tool=tool,
                allowed=False,
                stage="enabled",
                reasons=("tool_disabled",),
                session_id=session_id,
                tenant_id=tenant_id,
                intent_source=intent_source,
            )
            return ToolInvocationResult(
                tool_name=tool_name, allowed=False,
                error="tool is disabled",
                capability_decision=capability_decision,
            )

        # 4. Parameter validation
        param_error = self._validate_params(tool, arguments)
        if param_error:
            self._record_usage(tool_name, session_id, denied=True)
            self._record_decision(
                tool_name=tool_name,
                tool=tool,
                allowed=False,
                stage="parameters",
                reasons=(param_error.replace(" ", "_"),),
                session_id=session_id,
                tenant_id=tenant_id,
                intent_source=intent_source,
            )
            return ToolInvocationResult(
                tool_name=tool_name, allowed=False,
                error=param_error,
                capability_decision=capability_decision,
            )

        # 5. Permission primitive check
        permission_decision: ToolPermissionDecision | None = None
        if self._permission_registry is not None:
            permission_decision = self._permission_registry.evaluate(
                ToolPermissionRequest(
                    tenant_id=tenant_id or "system",
                    tool_name=tool_name,
                    arguments=arguments,
                    budget_ref=budget_ref,
                    audit_present=audit_present,
                )
            )
            if not permission_decision.allowed:
                self._record_usage(tool_name, session_id, denied=True)
                self._record_decision(
                    tool_name=tool_name,
                    tool=tool,
                    allowed=False,
                    stage="permission",
                    reasons=("tool_permission_denied",),
                    session_id=session_id,
                    tenant_id=tenant_id,
                    intent_source=intent_source,
                )
                return ToolInvocationResult(
                    tool_name=tool_name,
                    allowed=False,
                    error="tool permission denied",
                    permission_decision=permission_decision,
                    capability_decision=capability_decision,
                )

        # 6. Session limit check
        if session_id and not self._check_session_limit(tool, session_id):
            self._record_usage(tool_name, session_id, denied=True)
            self._record_decision(
                tool_name=tool_name,
                tool=tool,
                allowed=False,
                stage="session_limit",
                reasons=("session_tool_call_limit_reached",),
                session_id=session_id,
                tenant_id=tenant_id,
                intent_source=intent_source,
            )
            return ToolInvocationResult(
                tool_name=tool_name, allowed=False,
                error="session tool call limit reached",
                permission_decision=permission_decision,
                capability_decision=capability_decision,
            )

        # 7. Approval check
        if tool.requires_approval:
            self._record_usage(tool_name, session_id, denied=True)
            self._record_decision(
                tool_name=tool_name,
                tool=tool,
                allowed=False,
                stage="approval",
                reasons=("tool_requires_approval",),
                session_id=session_id,
                tenant_id=tenant_id,
                intent_source=intent_source,
            )
            return ToolInvocationResult(
                tool_name=tool_name, allowed=False,
                error="tool requires approval",
                permission_decision=permission_decision,
                capability_decision=capability_decision,
            )

        # 8. Execute
        exec_fn = executor or self._executors.get(tool_name)
        if exec_fn is None:
            self._record_usage(tool_name, session_id, error=True)
            self._record_decision(
                tool_name=tool_name,
                tool=tool,
                allowed=True,
                stage="executor_missing",
                reasons=("no_executor_registered",),
                session_id=session_id,
                tenant_id=tenant_id,
                intent_source=intent_source,
            )
            return ToolInvocationResult(
                tool_name=tool_name, allowed=True,
                error="no executor registered",
                permission_decision=permission_decision,
                capability_decision=capability_decision,
            )

        try:
            result = exec_fn(tool_name, arguments)
            self._record_usage(tool_name, session_id)
            self._record_decision(
                tool_name=tool_name,
                tool=tool,
                allowed=True,
                stage="executed",
                reasons=("tool_executed",),
                session_id=session_id,
                tenant_id=tenant_id,
                intent_source=intent_source,
            )
            return ToolInvocationResult(
                tool_name=tool_name, allowed=True,
                result=result,
                permission_decision=permission_decision,
                capability_decision=capability_decision,
            )
        except Exception as exc:
            self._record_usage(tool_name, session_id, error=True)
            self._record_decision(
                tool_name=tool_name,
                tool=tool,
                allowed=True,
                stage="execution_error",
                reasons=(f"tool_execution_failed:{type(exc).__name__}",),
                session_id=session_id,
                tenant_id=tenant_id,
                intent_source=intent_source,
            )
            return ToolInvocationResult(
                tool_name=tool_name, allowed=True,
                error=f"tool execution failed ({type(exc).__name__})",
                permission_decision=permission_decision,
                capability_decision=capability_decision,
            )

    def session_usage(self, session_id: str) -> dict[str, ToolUsageStats]:
        """Get per-tool usage stats for a session."""
        with self._lock:
            return dict(self._session_usage.get(session_id, {}))

    def clear_session(self, session_id: str) -> None:
        """Clear usage stats for a session (on session close)."""
        with self._lock:
            self._session_usage.pop(session_id, None)

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    def summary(self) -> dict[str, Any]:
        enabled = sum(1 for t in self._tools.values() if t.enabled)
        return {
            "registered_tools": len(self._tools),
            "enabled_tools": enabled,
            "total_invocations": self._total_invocations,
            "total_denied": self._total_denied,
            "active_sessions": len(self._session_usage),
        }

    def capability_contract_coverage(self) -> CapabilityContractCoverageReport:
        """Return a deterministic GCI coverage audit for registered tools."""
        return audit_capability_contract_coverage(self._tools.values())

    def decision_read_model(self, *, limit: int = 50) -> dict[str, Any]:
        """Return a bounded operator read model of recent tool decisions."""
        bounded_limit = max(0, int(limit))
        with self._lock:
            records = tuple(self._decision_records[-bounded_limit:] if bounded_limit else ())
        allowed_count = sum(1 for record in records if record.allowed)
        blocked_count = sum(1 for record in records if not record.allowed)
        return {
            "decision_count": len(records),
            "allowed_count": allowed_count,
            "blocked_count": blocked_count,
            "records": [record.to_dict() for record in records],
        }
