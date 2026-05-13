"""Schema validation endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from mcoi_runtime.app.routers.data._common import deps

router = APIRouter()


class ValidateRequest(BaseModel):
    schema_id: str
    data: dict[str, Any]


@router.get("/api/v1/schemas")
def list_schemas():
    """List registered validation schemas."""
    return {
        "schemas": [
            {"id": s.schema_id, "name": s.name, "rules": len(s.rules)}
            for s in deps.schema_validator.list_schemas()
        ],
        "summary": deps.schema_validator.summary(),
    }


@router.post("/api/v1/schemas/validate")
def validate_data(req: ValidateRequest):
    """Validate data against a registered schema."""
    result = deps.schema_validator.validate(req.schema_id, req.data)
    return {
        "schema_id": result.schema_id,
        "valid": result.valid,
        "errors": [
            {"field": e.field, "rule": e.rule_type, "message": e.message}
            for e in result.errors
        ],
    }
