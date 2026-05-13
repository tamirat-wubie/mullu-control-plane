"""Domain index endpoint — lists the six HTTP-exposed domain adapters."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["domains"])


@router.get("/domains", response_model=list[str])
def list_domains() -> list[str]:
    """List the six HTTP-exposed domain adapters."""
    return [
        "software_dev",
        "business_process",
        "scientific_research",
        "manufacturing",
        "healthcare",
        "education",
    ]
