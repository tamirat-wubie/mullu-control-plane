"""Phi-GPS solver advisory surface backed by InceptaDive reports.

Purpose: expose a compact execution-free InceptaDive advisory summary that Phi-GPS
solver routing can attach to compiled problem records.
Governance scope: advisory routing metadata only; no proof closure or action
approval.
Dependencies: Phi-GPS contracts, phi_inceptadive_bridge, and deterministic
identifier generation.
Invariants: advisory summaries preserve lineage cardinality through public refs
and always set execution_approval=false.
"""

from __future__ import annotations

from typing import Sequence

from mcoi_runtime.core.invariants import stable_identifier
from mcoi_runtime.core.phi_gps import CompiledProblem, SolverMode
from mcoi_runtime.core.phi_inceptadive_bridge import (
    PhiInceptaDiveReport,
    build_compiled_problem_dive_report,
)

_PUBLIC_PROBLEM_PREFIX = "phi_inceptadive_problem_"
_PUBLIC_LINEAGE_PREFIX = "phi_inceptadive_lineage_"


def build_phi_inceptadive_solver_advisory(compiled: CompiledProblem) -> dict[str, object]:
    """Return a compact solver-routing advisory for a compiled Phi-GPS problem."""

    report = build_compiled_problem_dive_report(compiled)
    return phi_inceptadive_report_summary(report)


def phi_inceptadive_report_summary(report: PhiInceptaDiveReport) -> dict[str, object]:
    """Return a compact non-executing summary for solver and route read models."""

    return {
        "inceptadive_report_id": report.report_id,
        "problem_id": _public_ref(_PUBLIC_PROBLEM_PREFIX, "phi-inceptadive-problem", report.problem_id),
        "problem_identifier_exposed": False,
        "proof_gap_count": len(report.proof_gaps),
        "hidden_assumption_count": len(report.hidden_assumptions),
        "fracture_count": report.fracture_count,
        "promotion_candidate_count": report.promotion_candidate_count,
        "requires_repair": report.requires_repair,
        "suggested_solver_modes": [mode.value if isinstance(mode, SolverMode) else str(mode) for mode in report.suggested_solver_modes],
        "lineage": list(_public_refs(_PUBLIC_LINEAGE_PREFIX, "phi-inceptadive-lineage", report.lineage)),
        "lineage_ref_count": len(report.lineage),
        "lineage_identifiers_exposed": False,
        "execution_approval": False,
    }


def _public_refs(prefix: str, namespace: str, values: Sequence[str]) -> tuple[str, ...]:
    return tuple(_public_ref(prefix, namespace, value) for value in values if str(value).strip())


def _public_ref(prefix: str, namespace: str, value: str) -> str:
    normalized = " ".join(str(value or "").strip().split())
    if normalized.startswith(prefix):
        return normalized
    return prefix + stable_identifier(namespace, {"value": normalized})
