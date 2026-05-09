"""Conversion helpers between substrate constructs and HTTP payloads."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException

from mcoi_runtime.app.routers.constructs._models import ConstructPayload
from mcoi_runtime.substrate.constructs import ConstructBase


def _construct_to_payload(c: ConstructBase, tenant_id: str) -> ConstructPayload:
    fields: dict[str, Any] = {}
    for k, v in c.__dict__.items():
        if k in {"id", "tier", "type", "invariants", "metadata", "created_at"}:
            continue
        if isinstance(v, UUID):
            fields[k] = str(v)
        elif isinstance(v, tuple):
            fields[k] = list(v)
        else:
            fields[k] = v
    return ConstructPayload(
        id=str(c.id),
        type=c.type.value,
        tier=c.tier.value,
        invariants=list(c.invariants),
        metadata=dict(c.metadata),
        created_at=c.created_at.isoformat() if c.created_at else None,
        fields=fields,
        tenant_id=tenant_id,
    )


def _resolve_uuid(s: str | None, name: str) -> UUID | None:
    if s is None:
        return None
    try:
        return UUID(s)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_uuid", "field": name, "value": s},
        )
