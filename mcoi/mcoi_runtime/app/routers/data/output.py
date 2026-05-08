"""Structured-output parsing endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from mcoi_runtime.app.routers.data._common import deps

router = APIRouter()


class ParseOutputRequest(BaseModel):
    schema_id: str
    text: str


@router.post("/api/v1/output/parse")
def parse_structured_output(req: ParseOutputRequest):
    """Parse LLM output against a schema."""
    result = deps.structured_output.parse(req.schema_id, req.text)
    return {"schema_id": result.schema_id, "valid": result.valid, "parsed": result.parsed, "errors": list(result.errors)}


@router.get("/api/v1/output/schemas")
def list_output_schemas():
    """List output schemas."""
    return {"schemas": [{"id": s.schema_id, "name": s.name, "fields": s.fields} for s in deps.structured_output.list_schemas()]}
