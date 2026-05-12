"""Conversation message endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from mcoi_runtime.app.routers.data._common import deps

router = APIRouter()


class ConversationMessageRequest(BaseModel):
    conversation_id: str
    role: str = "user"
    content: str = ""
    tenant_id: str = ""


@router.post("/api/v1/conversation/message")
def add_conversation_message(req: ConversationMessageRequest):
    """Add a message to a conversation."""
    deps.metrics.inc("requests_governed")
    conv = deps.conversation_store.get_or_create(req.conversation_id, tenant_id=req.tenant_id)
    msg = conv.add_message(req.role, req.content)
    return {
        "conversation_id": conv.conversation_id,
        "message_id": msg.message_id,
        "message_count": conv.message_count,
    }


@router.get("/api/v1/conversation/{conversation_id}")
def get_conversation(conversation_id: str):
    """Get conversation history."""
    conv = deps.conversation_store.get(conversation_id)
    if conv is None:
        raise HTTPException(404, detail="conversation not found")
    return {
        "conversation_id": conv.conversation_id,
        "messages": [{"role": m.role, "content": m.content, "id": m.message_id} for m in conv.messages],
        "summary": conv.summary(),
    }


@router.get("/api/v1/conversations")
def list_conversations(tenant_id: str | None = None):
    """List conversations."""
    convs = deps.conversation_store.list_conversations(tenant_id=tenant_id)
    return {
        "conversations": [c.summary() for c in convs],
        "count": len(convs),
    }
