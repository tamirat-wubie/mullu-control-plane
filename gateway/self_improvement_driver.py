"""Gateway self-improvement driver.

Purpose: crawl the whole-system surface index and run the self-auditor,
    diagnose, refiner, enhancer, engineer, and runtime-safe fixer roles as one
    governed, proposal-only cycle. The driver never promotes a capability,
    never mutates the registry, and never edits source; it produces ranked
    gaps, an activation-blocked improvement portfolio, append-only ledger
    evidence, and non-terminal connector-healing receipts that downstream
    gates (evals, change-assurance, terminal closure, learning admission)
    consume before any promotion.
Governance scope: read-only crawl of the proof-coverage witness-integrity
    index, diagnosis/proposal generation, candidate-evidence recording, and
    bounded connector recovery.
Dependencies: gateway.autonomous_capability_upgrade (diagnose/refine/enhance),
    gateway.candidate_ledger (baseline_delta winner gate), and
    gateway.connector_self_healing (runtime-safe fixer); plus command-spine
    canonical hashing for stable identities.
Invariants:
  - The cycle is proposal-only: every report is activation_blocked and
    promotion_blocked, and the portfolio it carries is activation-blocked.
  - Winner selection is the only-winner-on-metric test: a run wins only via
    CandidateLedger.winners_for (positive baseline_delta on the primary metric
    AND no adversarial-review findings).
  - The ledger is append-only and records proposals/negatives as first-class
    evidence; the driver never deletes or mutates records.
  - Adversarial review is symmetric: a compromised baseline (baseline run with
    adversarial findings) disqualifies every winner for that signature.
  - The driver promotes nothing and edits no source; the runtime-safe fixer
    emits non-terminal healing receipts only.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from gateway.autonomous_capability_upgrade import (
    AutonomousCapabilityUpgradeLoop,
    CapabilityHealthSignal,
    CapabilityImprovementPortfolio,
    MATURITY_LEVELS,
)
from gateway.candidate_ledger import CandidateLedger, CandidateRun
from gateway.command_spine import canonical_hash
from gateway.connector_self_healing import (
    ConnectorFailure,
    ConnectorHealingReceipt,
    ConnectorRecoveryPolicy,
    ConnectorSelfHealingEngine,
)


@dataclass(frozen=True, slots=True)
class SurfaceGap:
    """One proof surface ranked by its unanchored witness gap."""

    surface_id: str
    runtime_witness_count: int
    unanchored_witness_count: int
    anchored_witness_count: int
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.surface_id.strip():
            raise ValueError("surface_id_required")
        if self.runtime_witness_count < 0 or self.unanchored_witness_count < 0:
            raise ValueError("witness_counts_non_negative")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class RouteCoverageGap:
    """One HTTP route whose coverage state is below `proven`."""

    surface_id: str
    route: str
    coverage_state: str

    def __post_init__(self) -> None:
        if not self.route.strip():
            raise ValueError("route_required")
        if self.coverage_state not in ("witnessed", "unproven"):
            raise ValueError("route_gap_state_must_be_witnessed_or_unproven")


@dataclass(frozen=True, slots=True)
class SelfImprovementCycleReport:
    """Proposal-only result of one whole-system self-improvement cycle."""

    generated_at: str
    crawled_surface_count: int
    actionable_gap_count: int
    ranked_gaps: tuple[SurfaceGap, ...]
    portfolio: CapabilityImprovementPortfolio | None
    recorded_proposals: tuple[CandidateRun, ...]
    healing_receipts: tuple[ConnectorHealingReceipt, ...]
    route_gaps: tuple[RouteCoverageGap, ...] = ()
    activation_blocked: bool = True
    promotion_blocked: bool = True
    report_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.activation_blocked:
            raise ValueError("cycle_activation_must_be_blocked")
        if not self.promotion_blocked:
            raise ValueError("cycle_promotion_must_be_blocked")
        object.__setattr__(self, "ranked_gaps", tuple(self.ranked_gaps))
        object.__setattr__(self, "recorded_proposals", tuple(self.recorded_proposals))
        object.__setattr__(self, "healing_receipts", tuple(self.healing_receipts))
        object.__setattr__(self, "route_gaps", tuple(self.route_gaps))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        """Return a schema-compatible JSON projection of the cycle report."""
        payload = {
            "generated_at": self.generated_at,
            "crawled_surface_count": self.crawled_surface_count,
            "actionable_gap_count": self.actionable_gap_count,
            "ranked_gaps": [asdict(gap) for gap in self.ranked_gaps],
            "route_gaps": [asdict(gap) for gap in self.route_gaps],
            "portfolio": self.portfolio.to_json_dict() if self.portfolio is not None else None,
            "recorded_proposals": [asdict(run) for run in self.recorded_proposals],
            "healing_receipts": [receipt.to_json_dict() for receipt in self.healing_receipts],
            "activation_blocked": self.activation_blocked,
            "promotion_blocked": self.promotion_blocked,
            "report_hash": self.report_hash,
            "metadata": dict(self.metadata),
        }
        return json.loads(json.dumps(payload, default=str))


def crawl_witness_integrity(matrix_path: str | Path) -> tuple[SurfaceGap, ...]:
    """Self-auditor: crawl the surface index, ranked largest-gap-first.

    Reads the proof-coverage matrix witness-integrity block and returns one
    SurfaceGap per surface, ordered by descending unanchored witness count
    with an alphabetical surface_id tie-break (the established target-selection
    heuristic).
    """
    payload = json.loads(Path(matrix_path).read_text(encoding="utf-8"))
    surfaces = payload.get("witness_integrity", {}).get("surfaces", [])
    if not isinstance(surfaces, list):
        raise ValueError("witness_integrity_surfaces_must_be_array")
    gaps = [_gap_from_surface(surface) for surface in surfaces if isinstance(surface, dict)]
    return tuple(sorted(gaps, key=lambda gap: (-gap.unanchored_witness_count, gap.surface_id)))


_ROUTE_STATE_RANK = {"unproven": 0, "witnessed": 1}


def crawl_route_coverage(matrix_path: str | Path) -> tuple[RouteCoverageGap, ...]:
    """Broaden the crawl to HTTP routes: rank routes below `proven` worst-first.

    Coverage states rank proven > witnessed > unproven, so any non-`proven`
    route is an enhancement target. Ordering is unproven before witnessed, then
    by route path. Returns visibility-only gaps — they do not enter proposals.
    """
    payload = json.loads(Path(matrix_path).read_text(encoding="utf-8"))
    routes = payload.get("route_coverage", {}).get("routes", [])
    if not isinstance(routes, list):
        raise ValueError("route_coverage_routes_must_be_array")
    gaps = [
        RouteCoverageGap(
            surface_id=str(route.get("surface_id", "")),
            route=str(route.get("route", "")),
            coverage_state=str(route.get("coverage_state", "")),
        )
        for route in routes
        if isinstance(route, dict) and route.get("coverage_state") in _ROUTE_STATE_RANK
    ]
    return tuple(sorted(gaps, key=lambda gap: (_ROUTE_STATE_RANK[gap.coverage_state], gap.route)))


def run_cycle(
    matrix_path: str | Path,
    *,
    generated_at: str,
    top_n: int = 5,
    upgrade_loop: AutonomousCapabilityUpgradeLoop | None = None,
    ledger: CandidateLedger | None = None,
    healing_engine: ConnectorSelfHealingEngine | None = None,
    connector_failures: tuple[tuple[ConnectorFailure, ConnectorRecoveryPolicy], ...] = (),
    include_routes: bool = False,
    max_route_gaps: int = 50,
) -> SelfImprovementCycleReport:
    """Run one proposal-only self-improvement cycle over the surface index.

    Stages: self-auditor (crawl/rank) -> diagnose+refine+enhance (portfolio)
    -> engineer evidence (record proposals to the append-only ledger) ->
    runtime-safe fixer (connector healing receipts). When include_routes is
    set, the audit stage also crawls the HTTP route-coverage index and reports
    the worst non-`proven` routes (visibility only — routes do not enter the
    proposal portfolio). Promotes nothing.
    """
    if top_n < 1:
        raise ValueError("top_n_positive")
    if max_route_gaps < 0:
        raise ValueError("max_route_gaps_non_negative")
    loop = upgrade_loop or AutonomousCapabilityUpgradeLoop()
    book = ledger or CandidateLedger()
    fixer = healing_engine or ConnectorSelfHealingEngine()

    ranked = crawl_witness_integrity(matrix_path)
    actionable = tuple(gap for gap in ranked if gap.unanchored_witness_count > 0)[:top_n]

    portfolio: CapabilityImprovementPortfolio | None = None
    recorded: list[CandidateRun] = []
    if actionable:
        signals = tuple(_signal_from_gap(gap, observed_at=generated_at) for gap in actionable)
        portfolio = loop.propose_portfolio(
            signals,
            generated_at=generated_at,
            max_candidates=len(signals),
        )
        for plan in portfolio.plans:
            recorded.append(
                book.record(
                    signature_hash=signature_hash_for(plan.capability_id),
                    problem_id=plan.capability_id,
                    candidate_pipeline_id=plan.candidate.candidate_id,
                    method_families=plan.candidate.change_classes,
                    outcome="skipped",
                    scores=(),
                    baseline_delta=None,
                    evidence_refs=plan.health_signal.evidence_refs,
                    run_seed=plan.candidate.candidate_hash[:16] or "noseed",
                    notes="proposal_awaiting_execution_and_evals",
                )
            )

    receipts = tuple(
        fixer.evaluate(failure, policy) for failure, policy in connector_failures
    )

    route_gaps: tuple[RouteCoverageGap, ...] = ()
    if include_routes:
        route_gaps = crawl_route_coverage(matrix_path)[:max_route_gaps]

    report = SelfImprovementCycleReport(
        generated_at=generated_at,
        crawled_surface_count=len(ranked),
        actionable_gap_count=len(actionable),
        ranked_gaps=actionable,
        portfolio=portfolio,
        recorded_proposals=tuple(recorded),
        healing_receipts=receipts,
        route_gaps=route_gaps,
        metadata={
            "cycle_is_not_execution": True,
            "promotes_capabilities": False,
            "mutates_registry": False,
            "edits_source": False,
            "ledger_backend": book.status().get("backend", "unknown"),
        },
    )
    return _stamp_report(report)


def select_winners(
    ledger: CandidateLedger,
    signature_hash: str,
    *,
    primary_metric_id: str,
) -> tuple[CandidateRun, ...]:
    """Only-winner-on-metric gate with symmetric adversarial review.

    Delegates winner detection to CandidateLedger.winners_for (positive
    baseline_delta on the primary metric AND no adversarial findings) but
    first disqualifies *all* winners when the recorded baseline is itself
    compromised (carries adversarial-review findings).
    """
    baseline = ledger.baseline_for(signature_hash)
    if baseline is not None and baseline.adversarial_review_findings:
        return ()
    return ledger.winners_for(signature_hash, primary_metric_id=primary_metric_id)


def signature_hash_for(capability_id: str) -> str:
    """Stable problem-signature hash for a self-improvement proposal."""
    return canonical_hash({"capability_id": capability_id, "kind": "self_improvement_proposal"})


def _gap_from_surface(surface: dict[str, Any]) -> SurfaceGap:
    runtime = int(surface.get("runtime_witness_count", 0))
    unanchored = int(surface.get("unanchored_witness_count", 0))
    anchored = max(0, runtime - unanchored)
    refs = _surface_evidence_refs(surface)
    return SurfaceGap(
        surface_id=str(surface.get("surface_id", "")),
        runtime_witness_count=runtime,
        unanchored_witness_count=unanchored,
        anchored_witness_count=anchored,
        evidence_refs=refs,
    )


def _surface_evidence_refs(surface: dict[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for entry in surface.get("anchored_witnesses", []):
        if isinstance(entry, dict):
            refs.extend(str(anchor) for anchor in entry.get("anchors", []))
    deduped = tuple(dict.fromkeys(ref for ref in refs if ref.strip()))
    if deduped:
        return deduped[:8]
    return (f"proof_coverage_matrix#{surface.get('surface_id', 'unknown')}",)


def _signal_from_gap(gap: SurfaceGap, *, observed_at: str) -> CapabilityHealthSignal:
    total = gap.runtime_witness_count
    ratio = (gap.anchored_witness_count / total) if total > 0 else 1.0
    ratio = min(max(ratio, 0.0), 1.0)
    maturity_index = round(ratio * (len(MATURITY_LEVELS) - 1))
    return CapabilityHealthSignal(
        capability_id=f"proof_surface.{gap.surface_id}",
        observed_at=observed_at,
        maturity_level=MATURITY_LEVELS[maturity_index],
        success_rate=ratio,
        failure_count=gap.unanchored_witness_count,
        mean_latency_ms=0,
        cost_per_success=0.0,
        open_incidents=0,
        blocker_codes=("unanchored_witnesses",) if gap.unanchored_witness_count else (),
        evidence_refs=gap.evidence_refs,
        metadata={
            "surface_id": gap.surface_id,
            "runtime_witness_count": gap.runtime_witness_count,
            "unanchored_witness_count": gap.unanchored_witness_count,
        },
    )


def _stamp_report(report: SelfImprovementCycleReport) -> SelfImprovementCycleReport:
    payload = asdict(replace(report, report_hash=""))
    return replace(report, report_hash=canonical_hash(payload))
