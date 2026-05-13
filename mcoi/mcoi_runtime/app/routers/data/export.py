"""Data export endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.data._common import _data_error_detail, deps
from mcoi_runtime.core.data_export import ExportFormat, ExportRequest

router = APIRouter()


class DataExportRequest(BaseModel):
    source: str
    format: str = "json"
    fields: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    limit: int = 10_000


@router.get("/api/v1/export/sources")
def list_export_sources():
    """List available data export sources."""
    deps.metrics.inc("requests_governed")
    return {"sources": deps.data_export.list_sources(), "governed": True}


@router.post("/api/v1/export")
def export_data(req: DataExportRequest):
    """Export data in CSV, JSON, or JSONL format."""
    deps.metrics.inc("requests_governed")
    try:
        fmt = ExportFormat(req.format)
    except ValueError:
        raise HTTPException(400, detail=_data_error_detail("unsupported export format", "unsupported_export_format"))
    try:
        result = deps.data_export.export(ExportRequest(
            source=req.source, format=fmt,
            fields=tuple(req.fields), filters=req.filters, limit=req.limit,
        ))
    except ValueError:
        raise HTTPException(400, detail={"error": "invalid request", "error_code": "validation_error", "governed": True})
    return {
        "export": result.to_dict(),
        "content": result.content,
        "governed": True,
    }
