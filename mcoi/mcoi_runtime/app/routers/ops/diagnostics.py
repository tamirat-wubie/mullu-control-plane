"""Operational diagnostics: benchmarks, import analysis, proof bridge status."""
from __future__ import annotations

from fastapi import APIRouter

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


@router.post("/api/v1/ops/benchmarks")
def run_benchmarks():
    """Run governance performance benchmarks and return results."""
    from mcoi_runtime.core.governance_bench import run_governance_benchmarks
    suite = run_governance_benchmarks()
    return {"governed": True, **suite.summary()}


@router.get("/api/v1/ops/imports")
def analyze_imports():
    """Analyze import dependencies and check for cycles.

    Note: This endpoint performs full AST analysis of all Python files.
    May take 500ms-2s on large codebases. Use sparingly.
    """
    import os as _os
    from mcoi_runtime.core.import_analyzer import ImportAnalyzer
    import mcoi_runtime
    runtime_dir = _os.path.dirname(_os.path.dirname(mcoi_runtime.__file__))
    mcoi_dir = _os.path.join(runtime_dir, "mcoi_runtime")
    analyzer = ImportAnalyzer(root_package="mcoi_runtime")
    result = analyzer.analyze_directory(mcoi_dir)
    summary = analyzer.dependency_summary(result)
    return {"governed": True, **summary}


@router.get("/api/v1/ops/proof-bridge")
def proof_bridge_status():
    """Get proof bridge certification status."""
    bridge = deps.get("proof_bridge")
    if bridge is None:
        return {"governed": True, "status": "not_initialized"}
    return {"governed": True, **bridge.summary()}
