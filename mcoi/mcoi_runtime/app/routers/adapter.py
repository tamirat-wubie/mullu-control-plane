"""Agent Adapter Protocol — bring-your-own-agent governance endpoints.

Any external agent (Claude Code, OpenAI, scripts, tools) can register,
heartbeat, request permission for actions, and submit results through
these governed endpoints. Every action-request flows through the full
guard chain (auth → rate-limit → budget → policy).

This is the adoption gateway: the thinnest possible interface for
governing any external agent without requiring it to understand the
platform's internal architecture.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


# ── Pydantic request/response models ──────────────────────────────────


class AgentRegisterRequest(BaseModel):
    agent_name: str
    capabilities: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentHeartbeatRequest(BaseModel):
    agent_id: str
    status: str = "healthy"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ActionRequest(BaseModel):
    agent_id: str
    action_type: str
    target: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = ""
    budget_id: str = ""


class ActionResultRequest(BaseModel):
    agent_id: str
    action_id: str
    outcome: str  # "success", "failure", "partial"
    result: dict[str, Any] = Field(default_factory=dict)


# ── In-memory agent registry ─────────────────────────────────────────


class _AdapterRegistry:
    """Lightweight registry for external agents using the adapter protocol."""

    def __init__(self) -> None:
        self._agents: dict[str, dict[str, Any]] = {}
        self._actions: dict[str, dict[str, Any]] = {}
        self._action_counter = 0

    def register(self, agent_name: str, capabilities: list[str], metadata: dict[str, Any]) -> dict[str, Any]:
        agent_id = f"agent-{sha256(f'{agent_name}:{datetime.now(timezone.utc).isoformat()}'.encode()).hexdigest()[:12]}"
        entry = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "capabilities": tuple(capabilities),
            "metadata": dict(metadata),
            "status": "registered",
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        }
        self._agents[agent_id] = entry
        return entry

    def heartbeat(self, agent_id: str, status: str, metadata: dict[str, Any]) -> dict[str, Any] | None:
        agent = self._agents.get(agent_id)
        if agent is None:
            return None
        agent["status"] = status
        agent["last_heartbeat"] = datetime.now(timezone.utc).isoformat()
        agent["metadata"].update(metadata)
        return agent

    def get(self, agent_id: str) -> dict[str, Any] | None:
        return self._agents.get(agent_id)

    def create_action(self, agent_id: str, action_type: str, target: str, parameters: dict[str, Any]) -> dict[str, Any]:
        self._action_counter += 1
        action_id = f"act-{self._action_counter:06d}"
        action = {
            "action_id": action_id,
            "agent_id": agent_id,
            "action_type": action_type,
            "target": target,
            "parameters": dict(parameters),
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._actions[action_id] = action
        return action

    def resolve_action(self, action_id: str, outcome: str, result: dict[str, Any]) -> dict[str, Any] | None:
        action = self._actions.get(action_id)
        if action is None:
            return None
        action["status"] = outcome
        action["result"] = result
        action["resolved_at"] = datetime.now(timezone.utc).isoformat()
        return action

    def summary(self) -> dict[str, Any]:
        return {
            "registered_agents": len(self._agents),
            "total_actions": len(self._actions),
            "pending_actions": sum(1 for a in self._actions.values() if a["status"] == "pending"),
        }


# Module-level registry (populated by server.py via deps)
_registry = _AdapterRegistry()


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post("/api/v1/agent/register")
def register_agent(req: AgentRegisterRequest):
    """Register an external agent for governed execution."""
    deps.metrics.inc("requests_governed")
    entry = _registry.register(req.agent_name, req.capabilities, req.metadata)
    deps.audit_trail.record(
        action="agent.adapter.register",
        actor_id=entry["agent_id"],
        tenant_id="",
        target=req.agent_name,
        outcome="success",
        detail={"capabilities": req.capabilities},
    )
    return {
        "agent_id": entry["agent_id"],
        "agent_name": entry["agent_name"],
        "status": entry["status"],
        "registered_at": entry["registered_at"],
        "governed": True,
    }


@router.post("/api/v1/agent/heartbeat")
def agent_heartbeat(req: AgentHeartbeatRequest):
    """Agent heartbeat — extends lease and updates status."""
    deps.metrics.inc("requests_governed")
    agent = _registry.heartbeat(req.agent_id, req.status, req.metadata)
    if agent is None:
        raise HTTPException(404, detail={
            "error": "agent not found",
            "error_code": "agent_not_found",
            "governed": True,
        })
    return {
        "agent_id": agent["agent_id"],
        "status": agent["status"],
        "last_heartbeat": agent["last_heartbeat"],
        "governed": True,
    }


@router.post("/api/v1/agent/action-request")
def request_action(req: ActionRequest):
    """Request permission to perform an action. Goes through full guard chain."""
    deps.metrics.inc("requests_governed")

    # Verify agent exists
    agent = _registry.get(req.agent_id)
    if agent is None:
        raise HTTPException(404, detail={
            "error": "agent not found",
            "error_code": "agent_not_found",
            "governed": True,
        })

    # Run through guard chain
    guard_ctx = {
        "tenant_id": req.tenant_id,
        "budget_id": req.budget_id,
        "action_type": req.action_type,
        "target": req.target,
        "agent_id": req.agent_id,
    }
    guard_result = deps.guard_chain.evaluate(guard_ctx)

    if not guard_result.allowed:
        deps.audit_trail.record(
            action="agent.adapter.action_request",
            actor_id=req.agent_id,
            tenant_id=req.tenant_id,
            target=req.target,
            outcome="denied",
            detail={
                "action_type": req.action_type,
                "reason": guard_result.reason,
                "guard": guard_result.guard_name,
            },
        )
        return {
            "decision": "deny",
            "reason": guard_result.reason,
            "guard": guard_result.guard_name,
            "governed": True,
        }

    # Action allowed — create tracking record
    action = _registry.create_action(req.agent_id, req.action_type, req.target, req.parameters)
    deps.audit_trail.record(
        action="agent.adapter.action_request",
        actor_id=req.agent_id,
        tenant_id=req.tenant_id,
        target=req.target,
        outcome="allowed",
        detail={"action_type": req.action_type, "action_id": action["action_id"]},
    )
    return {
        "decision": "allow",
        "action_id": action["action_id"],
        "governed": True,
    }


@router.post("/api/v1/agent/action-result")
def submit_action_result(req: ActionResultRequest):
    """Submit the outcome of a governed action."""
    deps.metrics.inc("requests_governed")
    action = _registry.resolve_action(req.action_id, req.outcome, req.result)
    if action is None:
        raise HTTPException(404, detail={
            "error": "action not found",
            "error_code": "action_not_found",
            "governed": True,
        })
    deps.audit_trail.record(
        action="agent.adapter.action_result",
        actor_id=req.agent_id,
        tenant_id="",
        target=req.action_id,
        outcome=req.outcome,
        detail={"result_keys": list(req.result.keys())},
    )
    return {
        "action_id": req.action_id,
        "outcome": req.outcome,
        "governed": True,
    }


@router.post("/api/v1/agent/checkpoint")
def agent_checkpoint(req: dict[str, Any]):
    """Save coordination checkpoint for an external agent."""
    deps.metrics.inc("requests_governed")
    checkpoint_id = req.get("checkpoint_id", "")
    if not checkpoint_id:
        raise HTTPException(400, detail={
            "error": "checkpoint_id is required",
            "error_code": "missing_checkpoint_id",
            "governed": True,
        })
    checkpoint = deps.coordination_engine.save_checkpoint(
        checkpoint_id,
        lease_duration_seconds=req.get("lease_duration_seconds", 3600),
    )
    return {
        "checkpoint_id": checkpoint.checkpoint_id,
        "lease_expires_at": checkpoint.lease_expires_at,
        "governed": True,
    }


@router.post("/api/v1/agent/restore")
def agent_restore(req: dict[str, Any]):
    """Restore coordination state for an external agent."""
    from mcoi_runtime.persistence.errors import PersistenceError
    deps.metrics.inc("requests_governed")
    checkpoint_id = req.get("checkpoint_id", "")
    if not checkpoint_id:
        raise HTTPException(400, detail={
            "error": "checkpoint_id is required",
            "error_code": "missing_checkpoint_id",
            "governed": True,
        })
    try:
        outcome = deps.coordination_engine.restore_checkpoint(checkpoint_id)
    except PersistenceError:
        raise HTTPException(404, detail={
            "error": f"checkpoint not found: {checkpoint_id}",
            "error_code": "checkpoint_not_found",
            "governed": True,
        })
    return {
        "checkpoint_id": outcome.checkpoint_id,
        "status": outcome.status.value,
        "reason": outcome.reason,
        "governed": True,
    }


@router.get("/api/v1/agent/adapter/summary")
def adapter_summary():
    """Summary of the agent adapter protocol state."""
    deps.metrics.inc("requests_governed")
    return {**_registry.summary(), "governed": True}
