"""Phase 212B — Tool-Augmented Agent Workflows.

Purpose: Agents that can invoke tools during workflow execution.
    The LLM decides which tools to call, the runtime executes them,
    and results flow back for the next step.
Governance scope: tool-augmented execution only.
Dependencies: tool_use, agent_workflow.
Invariants:
  - Tool calls are governed (validated, logged).
  - Maximum tool calls per workflow is bounded.
  - Tool results are included in the workflow output.
  - Failed tool calls don't crash the workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from mcoi_runtime.core.tool_use import ToolRegistry, ToolResult


@dataclass(frozen=True, slots=True)
class ToolCallRecord:
    """Record of a tool call within a workflow."""

    tool_id: str
    arguments: dict[str, Any]
    result: ToolResult
    step_index: int


@dataclass(frozen=True, slots=True)
class ToolAugmentedResult:
    """Result of a tool-augmented workflow step."""

    content: str
    tool_calls: tuple[ToolCallRecord, ...]
    total_tool_calls: int
    all_succeeded: bool


class ToolAugmentedAgent:
    """Agent that can invoke tools during LLM-driven workflows.

    Flow:
    1. LLM generates response (may include tool-use requests)
    2. Agent parses tool requests from LLM output
    3. Invokes tools via ToolRegistry
    4. Collects results and produces final output
    """

    def __init__(
        self,
        *,
        tool_registry: ToolRegistry,
        llm_fn: Callable[[str], Any] | None = None,
        max_tool_calls: int = 10,
    ) -> None:
        self._tools = tool_registry
        self._llm_fn = llm_fn
        self._max_tool_calls = max_tool_calls
        self._history: list[ToolAugmentedResult] = []

    def execute_with_tools(
        self,
        prompt: str,
        *,
        tool_ids: list[str] | None = None,
        tenant_id: str = "",
    ) -> ToolAugmentedResult:
        """Execute a prompt with tool augmentation.

        If tool_ids is provided, only those tools are available.
        Otherwise, all registered tools are available.
        """
        # Get available tools
        available = self._tools.list_tools()
        if tool_ids is not None:
            available = [t for t in available if t.tool_id in tool_ids]

        # Build tool-augmented prompt
        tool_descriptions = "\n".join(
            f"- {t.tool_id}: {t.description}" for t in available
        )
        augmented_prompt = (
            f"{prompt}\n\n"
            f"Available tools:\n{tool_descriptions}\n\n"
            f"To use a tool, respond with TOOL_CALL: tool_id(arg1=val1, arg2=val2)"
        )

        # Get LLM response
        if self._llm_fn:
            llm_result = self._llm_fn(augmented_prompt)
            content = getattr(llm_result, "content", str(llm_result))
        else:
            content = f"[stub: processed '{prompt[:50]}' with {len(available)} tools available]"

        # Parse and execute tool calls from response
        tool_calls: list[ToolCallRecord] = []
        lines = content.split("\n")
        step_idx = 0

        for line in lines:
            if line.strip().startswith("TOOL_CALL:") and step_idx < self._max_tool_calls:
                parsed = self._parse_tool_call(line)
                if parsed:
                    tool_id, args = parsed
                    result = self._tools.invoke(tool_id, args, tenant_id=tenant_id)
                    tool_calls.append(ToolCallRecord(
                        tool_id=tool_id, arguments=args,
                        result=result, step_index=step_idx,
                    ))
                    step_idx += 1

        all_ok = all(tc.result.succeeded for tc in tool_calls) if tool_calls else True

        result = ToolAugmentedResult(
            content=content,
            tool_calls=tuple(tool_calls),
            total_tool_calls=len(tool_calls),
            all_succeeded=all_ok,
        )
        self._history.append(result)
        return result

    def _parse_tool_call(self, line: str) -> tuple[str, dict[str, Any]] | None:
        """Parse a TOOL_CALL line. Returns (tool_id, arguments) or None."""
        try:
            call_str = line.strip().replace("TOOL_CALL:", "").strip()
            if "(" not in call_str:
                return None
            tool_id = call_str[:call_str.index("(")].strip()
            args_str = call_str[call_str.index("(") + 1:call_str.rindex(")")].strip()
            args: dict[str, Any] = {}
            if args_str:
                for pair in args_str.split(","):
                    if "=" in pair:
                        key, val = pair.split("=", 1)
                        args[key.strip()] = val.strip().strip("'\"")
            return tool_id, args
        except Exception:
            return None

    @property
    def history_count(self) -> int:
        return len(self._history)

    def summary(self) -> dict[str, Any]:
        total_tool_calls = sum(r.total_tool_calls for r in self._history)
        return {
            "executions": self.history_count,
            "total_tool_calls": total_tool_calls,
            "available_tools": self._tools.tool_count,
        }
