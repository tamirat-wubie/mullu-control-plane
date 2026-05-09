"""Pydantic request models for LLM endpoints."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CompletionRequest(BaseModel):
    prompt: str
    model_name: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024
    temperature: float = 0.0
    tenant_id: str = "system"
    actor_id: str = "anonymous"
    budget_id: str = "default"
    system: str = ""


class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    tenant_id: str = "system"
    actor_id: str = "anonymous"
    budget_id: str = "default"
    model_name: str = "claude-sonnet-4-20250514"
    system_prompt: str = ""


class ChatWorkflowRequest(BaseModel):
    conversation_id: str
    message: str
    tenant_id: str = "system"
    actor_id: str = "anonymous"
    capability: str = "llm.completion"
    system_prompt: str = ""
    budget_id: str = "default"


class AutoCompleteRequest(BaseModel):
    prompt: str
    max_tokens: int = 1024
    max_cost: float = 0.0
    preferred_speed: str = ""
    force_model: str = ""
    tenant_id: str = "system"
    actor_id: str = "anonymous"
    budget_id: str = "default"


class ABTestRequest(BaseModel):
    prompt: str
    model_ids: list[str] = Field(default_factory=list)
    criteria: str = "cost"
