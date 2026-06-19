"""Phi-GPS solver advisory surface backed by InceptaDive reports.

Purpose: expose a compact execution-free InceptaDive advisory summary that Phi-GPS
solver routing can attach to compiled problem records.
Governance scope: advisory routing metadata only; no proof closure or action
approval.
Dependencies: Phi-GPS contracts and phi_inceptadive_bridge.
Invariants: advisory summaries preserve report lineage and always set
execution_approval=false.
"""

from __future__ import annotations

from mcoi_runtime.core.phi_gps import CompiledProblem, SolverMode
from mcoi_runtime.core.phi_inceptadive_bridge import (
    PhiInceptaDiveReport,
    build_compiled_problem_dive_report,
)


def build_phi_inceptadive_solver_advisory(compiled: CompiledProblem) -> dict[str, object]:
    """Return a compact solver-routing advisory for a compiled Phi-GPS problem."""

    report = build_compiled_problem_dive_report(compiled)
    return phi_inceptadive_report_summary(report)


def phi_inceptadive_report_summary(report: PhiInceptaDiveReport) -> dict[str, object]:
    """Return a compact non-executing summary for solver and route read models."""

    return {
        "inceptadive_report_id": report.report_id,
        "problem_id": report.problem_id,
        "proof_gap_count": len(report.proof_gaps),
        "hidden_assumption_count": len(report.hidden_assumptions),
        "fracture_count": report.fracture_count,
        "promotion_candidate_count": report.promotion_candidate_count,
        "requires_repair": report.requires_repair,
        "suggested_solver_modes": [mode.value if isinstance(mode, SolverMode) else str(mode) for mode in report.suggested_solver_modes],
        "lineage": list(report.lineage),
        "execution_approval": False,
    }
