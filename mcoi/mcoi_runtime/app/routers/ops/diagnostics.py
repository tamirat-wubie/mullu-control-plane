"""Operational diagnostics: benchmarks, import analysis, proof bridge status."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


@router.post("/api/v1/ops/benchmarks")
def run_benchmarks():
    """Run governance performance benchmarks and return results."""
    from mcoi_runtime.core.governance_bench import run_governance_benchmarks
    suite = run_governance_benchmarks()
    return {"governed": True, **suite.summary()}


_import_analysis_cache: dict[str, Any] | None = None


def _compute_import_analysis() -> dict[str, Any]:
    import os as _os
    from mcoi_runtime.core.import_analyzer import ImportAnalyzer
    import mcoi_runtime
    runtime_dir = _os.path.dirname(_os.path.dirname(mcoi_runtime.__file__))
    mcoi_dir = _os.path.join(runtime_dir, "mcoi_runtime")
    analyzer = ImportAnalyzer(root_package="mcoi_runtime")
    result = analyzer.analyze_directory(mcoi_dir)
    return analyzer.dependency_summary(result)


@router.get("/api/v1/ops/imports")
def analyze_imports():
    """Analyze import dependencies and check for cycles.

    Performs a full AST analysis of the mcoi_runtime tree. The source tree is
    immutable for the process lifetime, so the result is computed once and
    cached -- without this, each call re-parsed thousands of files (seconds of
    CPU), making the endpoint a trivial denial-of-service amplifier.
    """
    global _import_analysis_cache
    if _import_analysis_cache is None:
        _import_analysis_cache = _compute_import_analysis()
    return {"governed": True, **_import_analysis_cache}


@router.get("/api/v1/ops/proof-bridge")
def proof_bridge_status():
    """Get proof bridge certification status."""
    bridge = deps.get("proof_bridge")
    if bridge is None:
        return {"governed": True, "status": "not_initialized"}
    return {"governed": True, **bridge.summary()}
