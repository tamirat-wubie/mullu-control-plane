"""Phase 210A — Conversation-Aware Workflow.

Purpose: Bridges conversation memory with agent workflows.
    A chat message can trigger a governed workflow — the conversation
    context becomes the workflow input, and results flow back as
    assistant messages.
Governance scope: chat-to-workflow bridging only.
Dependencies: conversation_memory, agent_workflow, traced_workflow.
Invariants:
  - Workflow results are added to conversation as assistant messages.
  - Conversation context is passed to the workflow payload.
  - Failed workflows produce error messages in the conversation.
  - Each chat-workflow has an associated replay trace.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from mcoi_runtime.core.agent_protocol import AgentCapability
from mcoi_runtime.core.conversation_memory import Conversation, ConversationStore
from mcoi_runtime.core.agent_workflow import WorkflowResult
from mcoi_runtime.core.traced_workflow import TracedWorkflowEngine
from mcoi_runtime.core.execution_replay import ReplayTrace


@dataclass(frozen=True, slots=True)
class ChatWorkflowResult:
    """Result of a conversation-triggered workflow."""

    conversation_id: str
    workflow_id: str
    task_id: str
    agent_id: str
    status: str
    response_content: str
    trace_id: str | None
    message_count: int
    cost: float


class ChatWorkflowEngine:
    """Bridges conversations with governed agent workflows."""

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        conversation_store: ConversationStore,
        traced_workflow: TracedWorkflowEngine,
        cost_record_fn: Callable[[str, str, float, int], None] | None = None,
    ) -> None:
        self._clock = clock
        self._conv_store = conversation_store
        self._traced = traced_workflow
        self._cost_fn = cost_record_fn
        self._counter = 0
        self._history: list[ChatWorkflowResult] = []

    def execute(
        self,
        *,
        conversation_id: str,
        message: str,
        tenant_id: str = "",
        capability: AgentCapability = AgentCapability.LLM_COMPLETION,
        system_prompt: str = "",
        budget_id: str = "default",
    ) -> ChatWorkflowResult:
        """Execute a chat-triggered workflow.

        1. Get/create conversation
        2. Add user message
        3. Build workflow payload from conversation context
        4. Execute traced workflow
        5. Add result as assistant message
        6. Return unified result
        """
        self._counter += 1
        task_id = f"chat-wf-{self._counter}"

        conv = self._conv_store.get_or_create(conversation_id, tenant_id=tenant_id)

        # Add system prompt on first message
        if system_prompt and conv.message_count == 0:
            conv.add_system(system_prompt)

        # Add user message
        conv.add_user(message)

        # Build payload with conversation context
        payload = {
            "prompt": message,
            "conversation_context": conv.to_chat_messages()[-10:],  # Last 10 messages
            "conversation_id": conversation_id,
            "message_count": conv.message_count,
        }

        # Execute traced workflow
        wf_result, trace = self._traced.execute(
            task_id=task_id,
            description=message,
            capability=capability,
            payload=payload,
            tenant_id=tenant_id,
            budget_id=budget_id,
        )

        # Extract response
        response = ""
        cost = 0.0
        if wf_result.status == "completed" and wf_result.output:
            response = wf_result.output.get("content", str(wf_result.output))
            cost = wf_result.output.get("cost", 0.0)
            conv.add_assistant(response)
        else:
            error_msg = f"[Workflow failed: {wf_result.error}]"
            conv.add_assistant(error_msg)
            response = error_msg

        # Record cost
        if self._cost_fn and cost > 0:
            tokens = wf_result.output.get("tokens", 0)
            model = wf_result.output.get("model", "unknown")
            self._cost_fn(tenant_id, model, cost, tokens)

        result = ChatWorkflowResult(
            conversation_id=conversation_id,
            workflow_id=wf_result.workflow_id,
            task_id=task_id,
            agent_id=wf_result.agent_id,
            status=wf_result.status,
            response_content=response,
            trace_id=trace.trace_id if trace else None,
            message_count=conv.message_count,
            cost=cost,
        )
        self._history.append(result)
        return result

    def history(self, limit: int = 50) -> list[ChatWorkflowResult]:
        return self._history[-limit:]

    @property
    def total_executions(self) -> int:
        return len(self._history)

    def summary(self) -> dict[str, Any]:
        completed = sum(1 for r in self._history if r.status == "completed")
        total_cost = sum(r.cost for r in self._history)
        return {
            "total": self.total_executions,
            "completed": completed,
            "failed": self.total_executions - completed,
            "total_cost": round(total_cost, 6),
        }
