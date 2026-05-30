"""Conversation message endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from mcoi_runtime.app.routers.data._common import deps
from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope, scoped_listing_tenant

router = APIRouter()


class ConversationMessageRequest(BaseModel):
    conversation_id: str
    role: str = "user"
    content: str = ""
    tenant_id: str = ""


@router.post("/api/v1/conversation/message")
def add_conversation_message(req: ConversationMessageRequest, request: Request):
    """Add a message to a conversation."""
    deps.metrics.inc("requests_governed")
    enforce_tenant_scope(request, req.tenant_id)
    conv = deps.conversation_store.get_or_create(req.conversation_id, tenant_id=req.tenant_id)
    # Guard against appending to another tenant's existing conversation (the id
    # is the store key, so a reused id could resolve to a different tenant).
    enforce_tenant_scope(request, getattr(conv, "tenant_id", ""))
    msg = conv.add_message(req.role, req.content)
    return {
        "conversation_id": conv.conversation_id,
        "message_id": msg.message_id,
        "message_count": conv.message_count,
    }


@router.get("/api/v1/conversation/{conversation_id}")
def get_conversation(conversation_id: str, request: Request):
    """Get conversation history."""
    conv = deps.conversation_store.get(conversation_id)
    if conv is None:
        raise HTTPException(404, detail="conversation not found")
    enforce_tenant_scope(request, getattr(conv, "tenant_id", ""))
    return {
        "conversation_id": conv.conversation_id,
        "messages": [{"role": m.role, "content": m.content, "id": m.message_id} for m in conv.messages],
        "summary": conv.summary(),
    }


@router.get("/api/v1/conversations")
def list_conversations(request: Request, tenant_id: str | None = None):
    """List conversations."""
    convs = deps.conversation_store.list_conversations(tenant_id=scoped_listing_tenant(request, tenant_id))
    return {
        "conversations": [c.summary() for c in convs],
        "count": len(convs),
    }
