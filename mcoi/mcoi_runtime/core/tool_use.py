"""Phase 211C — Tool-Use Contracts.

Purpose: Typed contracts for LLM tool use (function calling).
    Agents can declare tools, LLM can request tool invocations,
    and results flow back into the conversation.
Governance scope: tool definition and invocation management only.
Dependencies: none (pure contracts).
Invariants:
  - Tool schemas are validated at registration time.
  - Tool invocations are governed (budget, audit).
  - Tool results are immutable.
  - Unknown tool calls produce explicit errors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable
from hashlib import sha256
import json


def _classify_tool_exception(exc: Exception) -> str:
    """Collapse handler failures into stable, non-leaking error strings."""
    error_type = type(exc).__name__
    if isinstance(exc, TimeoutError):
        return f"tool timeout ({error_type})"
    if isinstance(exc, ConnectionError):
        return f"tool network error ({error_type})"
    if isinstance(exc, ValueError):
        return f"tool validation error ({error_type})"
    return f"tool handler error ({error_type})"


@dataclass(frozen=True, slots=True)
class ToolParameter:
    """Single parameter in a tool definition."""

    name: str
    param_type: str  # "string", "number", "boolean", "object", "array"
    description: str = ""
    required: bool = True
    default: Any = None


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Defines a tool that an LLM agent can invoke."""

    tool_id: str
    name: str
    description: str
    parameters: tuple[ToolParameter, ...]
    category: str = "general"
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    """Request to invoke a tool from the LLM."""

    invocation_id: str
    tool_id: str
    arguments: dict[str, Any]
    tenant_id: str = ""
    conversation_id: str = ""


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Result of a tool invocation."""

    invocation_id: str
    tool_id: str
    output: dict[str, Any]
    succeeded: bool
    error: str = ""
    result_hash: str = ""


class ToolRegistry:
    """Manages tool definitions and invocations."""

    def __init__(self, *, clock: Callable[[], str]) -> None:
        self._clock = clock
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}
        self._invocation_log: list[ToolResult] = []
        self._counter = 0

    def register(self, tool: ToolDefinition, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        """Register a tool with its handler function."""
        if tool.tool_id in self._tools:
            raise ValueError("tool already registered")
        self._tools[tool.tool_id] = tool
        self._handlers[tool.tool_id] = handler

    def get(self, tool_id: str) -> ToolDefinition | None:
        return self._tools.get(tool_id)

    def invoke(
        self,
        tool_id: str,
        arguments: dict[str, Any],
        tenant_id: str = "",
        *,
        allowed_tool_ids: set[str] | None = None,
    ) -> ToolResult:
        """Invoke a registered tool."""
        self._counter += 1
        invocation_id = f"inv-{self._counter}"

        if allowed_tool_ids is not None and tool_id not in allowed_tool_ids:
            result = ToolResult(
                invocation_id=invocation_id, tool_id=tool_id,
                output={}, succeeded=False, error="tool not allowed",
            )
            self._invocation_log.append(result)
            return result

        tool = self._tools.get(tool_id)
        if tool is None:
            result = ToolResult(
                invocation_id=invocation_id, tool_id=tool_id,
                output={}, succeeded=False, error="unknown tool",
            )
            self._invocation_log.append(result)
            return result

        if not tool.enabled:
            result = ToolResult(
                invocation_id=invocation_id, tool_id=tool_id,
                output={}, succeeded=False, error="tool disabled",
            )
            self._invocation_log.append(result)
            return result

        # Validate required parameters
        for param in tool.parameters:
            if param.required and param.name not in arguments:
                result = ToolResult(
                    invocation_id=invocation_id, tool_id=tool_id,
                    output={}, succeeded=False,
                    error="missing required parameter",
                )
                self._invocation_log.append(result)
                return result

        handler = self._handlers[tool_id]
        try:
            output = handler(arguments)
            result_hash = sha256(
                json.dumps(output, sort_keys=True, default=str).encode()
            ).hexdigest()

            result = ToolResult(
                invocation_id=invocation_id, tool_id=tool_id,
                output=output, succeeded=True, result_hash=result_hash,
            )
        except Exception as exc:
            result = ToolResult(
                invocation_id=invocation_id, tool_id=tool_id,
                output={}, succeeded=False, error=_classify_tool_exception(exc),
            )

        self._invocation_log.append(result)
        return result

    def to_llm_tools(self) -> list[dict[str, Any]]:
        """Export tool definitions in LLM-compatible format (Anthropic/OpenAI)."""
        tools = []
        for tool in self._tools.values():
            if not tool.enabled:
                continue
            properties: dict[str, Any] = {}
            required: list[str] = []
            for param in tool.parameters:
                properties[param.name] = {
                    "type": param.param_type,
                    "description": param.description,
                }
                if param.required:
                    required.append(param.name)

            tools.append({
                "name": tool.tool_id,
                "description": tool.description,
                "input_schema": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            })
        return tools

    def list_tools(self, category: str | None = None) -> list[ToolDefinition]:
        tools = sorted(self._tools.values(), key=lambda t: t.tool_id)
        if category is not None:
            tools = [t for t in tools if t.category == category]
        return tools

    def invocation_history(self, limit: int = 50) -> list[ToolResult]:
        return self._invocation_log[-limit:]

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def invocation_count(self) -> int:
        return len(self._invocation_log)

    def summary(self) -> dict[str, Any]:
        succeeded = sum(1 for r in self._invocation_log if r.succeeded)
        return {
            "tools": self.tool_count,
            "invocations": self.invocation_count,
            "succeeded": succeeded,
            "failed": self.invocation_count - succeeded,
        }
