"""Semantic search endpoints."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from mcoi_runtime.app.routers.data._common import deps

router = APIRouter()


class SemanticSearchRequest(BaseModel):
    query: str
    limit: int = 10


@router.post("/api/v1/search")
def semantic_search_endpoint(req: SemanticSearchRequest):
    """Semantic search across indexed documents."""
    results = deps.semantic_search.search(req.query, limit=req.limit)
    return {
        "results": [{"doc_id": r.doc_id, "score": r.score, "matched": list(r.matched_terms)} for r in results],
        "count": len(results),
    }


@router.get("/api/v1/search/stats")
def search_stats():
    """Semantic search index statistics."""
    return deps.semantic_search.summary()
