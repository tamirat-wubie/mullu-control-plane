"""Gateway solver-forge bridge.

Purpose: Carry a winning CandidateRun from the comparison ledger into a
    CapabilityForgeInput so the existing CapabilityForge can build a
    candidate-only package that the C0–C7 maturity ladder will then gate.
    The bridge is the single load-bearing seam between the Solver Forge
    (signature + ledger + composer) and the existing Capability Forge
    (package generation + handoff + maturity evidence).
Governance scope: provenance preservation only. The bridge produces a
    CapabilityForgeInput — it does NOT call CapabilityForge.create_candidate,
    NOT mutate the registry, NOT influence maturity. The forge remains the
    package author, the maturity synthesizer remains the readiness author,
    and the governance kernel remains the admission author.
Dependencies: gateway.candidate_ledger, gateway.problem_signature,
    gateway.capability_forge (only the CapabilityForgeInput type), and
    canonical command-spine hashing for the provenance stamp.
Invariants:
  - Only winners cross the bridge. A winner is a CandidateRun with
    outcome=passed, is_baseline=False, and a positive baseline_delta on the
    signature's primary success metric (or negative when the metric direction
    is minimize). Non-winners raise.
  - The winner's signature_hash must equal the supplied signature's hash;
    cross-signature handoffs are refused.
  - The forge input's domain and risk are taken from the signature, never
    from author-supplied overrides. This prevents launder-by-rebadging — a
    capability cannot claim a different problem domain than the one it was
    proven against.
  - Every produced CapabilityForgeInput carries a solver_forge.* provenance
    block in metadata: signature_hash, problem_id, winner record_hash, primary
    metric id + value + baseline_delta, method_families, run_seed, cost,
    duration, recorded_at, provenance_hash. The forge package can persist this
    intact; reviewers can audit the comparison evidence.
  - The bridge has no install/promote/certify/deploy surface. Forge-input
    construction is its only public effect.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from gateway.candidate_ledger import CandidateRun, CandidateScore
from gateway.capability_forge import CapabilityForgeInput
from gateway.command_spine import canonical_hash
from gateway.problem_signature import ProblemMetric, ProblemSignature


SOLVER_FORGE_PROVENANCE_KEY = "solver_forge"


@dataclass(frozen=True, slots=True)
class SolverForgeProvenance:
    """Comparison-evidence provenance stamped into a forge input."""

    signature_hash: str
    problem_id: str
    winner_record_hash: str
    primary_metric_id: str
    primary_metric_value: float
    primary_metric_baseline_delta: float
    primary_metric_direction: str
    method_families: tuple[str, ...]
    run_seed: str
    cost_units: float
    duration_seconds: float
    recorded_at: str
    provenance_hash: str = ""

    def __post_init__(self) -> None:
        if self.primary_metric_direction not in ("maximize", "minimize"):
            raise ValueError("primary_metric_direction_must_be_maximize_or_minimize")
        object.__setattr__(self, "method_families", tuple(self.method_families))
        if not self.provenance_hash:
            object.__setattr__(self, "provenance_hash", _compute_provenance_hash(self))

    def to_metadata_block(self) -> dict[str, Any]:
        return {
            "signature_hash": self.signature_hash,
            "problem_id": self.problem_id,
            "winner_record_hash": self.winner_record_hash,
            "primary_metric_id": self.primary_metric_id,
            "primary_metric_value": self.primary_metric_value,
            "primary_metric_baseline_delta": self.primary_metric_baseline_delta,
            "primary_metric_direction": self.primary_metric_direction,
            "method_families": list(self.method_families),
            "run_seed": self.run_seed,
            "cost_units": self.cost_units,
            "duration_seconds": self.duration_seconds,
            "recorded_at": self.recorded_at,
            "provenance_hash": self.provenance_hash,
        }


def _compute_provenance_hash(provenance: SolverForgeProvenance) -> str:
    payload = {
        "signature_hash": provenance.signature_hash,
        "winner_record_hash": provenance.winner_record_hash,
        "primary_metric_id": provenance.primary_metric_id,
        "primary_metric_value": provenance.primary_metric_value,
        "primary_metric_baseline_delta": provenance.primary_metric_baseline_delta,
        "primary_metric_direction": provenance.primary_metric_direction,
        "method_families": list(provenance.method_families),
        "run_seed": provenance.run_seed,
    }
    return canonical_hash(payload)


def _primary_success_metric(signature: ProblemSignature) -> ProblemMetric:
    success_metrics = signature.success_metrics()
    if not success_metrics:
        raise ValueError("signature_missing_success_metric")
    return success_metrics[0]


def _score_for_metric(scores: tuple[CandidateScore, ...], metric_id: str) -> CandidateScore:
    for score in scores:
        if score.metric_id == metric_id:
            return score
    raise ValueError(f"winner_missing_score_for_metric:{metric_id}")


def _delta_beats_baseline(delta: float, direction: str) -> bool:
    if direction == "maximize":
        return delta > 0
    return delta < 0


def is_winner(winner: CandidateRun, signature: ProblemSignature) -> bool:
    """Return True iff the run is a real winner under the signature."""
    if winner.outcome != "passed":
        return False
    if winner.is_baseline:
        return False
    if winner.signature_hash != signature.signature_hash:
        return False
    primary_metric = _primary_success_metric(signature)
    delta = winner.baseline_delta.get(primary_metric.metric_id)
    if delta is None:
        return False
    return _delta_beats_baseline(delta, primary_metric.direction)


def build_provenance(winner: CandidateRun, signature: ProblemSignature) -> SolverForgeProvenance:
    """Construct a provenance stamp for a winner. Caller is expected to have
    already verified `is_winner(...)`; this raises with a precise reason
    otherwise so failures surface clearly in tests and reviews.
    """
    if winner.outcome != "passed":
        raise ValueError(f"winner_outcome_must_be_passed:{winner.outcome}")
    if winner.is_baseline:
        raise ValueError("baseline_runs_cannot_cross_bridge")
    if winner.signature_hash != signature.signature_hash:
        raise ValueError("winner_signature_hash_must_match_signature")
    primary_metric = _primary_success_metric(signature)
    score = _score_for_metric(winner.scores, primary_metric.metric_id)
    delta = winner.baseline_delta.get(primary_metric.metric_id)
    if delta is None:
        raise ValueError("winner_missing_baseline_delta_for_primary_metric")
    if not _delta_beats_baseline(delta, primary_metric.direction):
        raise ValueError(
            f"winner_does_not_beat_baseline:metric={primary_metric.metric_id}:"
            f"direction={primary_metric.direction}:delta={delta}"
        )
    return SolverForgeProvenance(
        signature_hash=signature.signature_hash,
        problem_id=signature.problem_id,
        winner_record_hash=winner.record_hash,
        primary_metric_id=primary_metric.metric_id,
        primary_metric_value=score.value,
        primary_metric_baseline_delta=delta,
        primary_metric_direction=primary_metric.direction,
        method_families=winner.method_families,
        run_seed=winner.run_seed,
        cost_units=winner.cost_units,
        duration_seconds=winner.duration_seconds,
        recorded_at=winner.recorded_at,
    )


def forge_input_for_winner(
    *,
    winner: CandidateRun,
    signature: ProblemSignature,
    capability_id: str,
    version: str,
    api_docs_ref: str,
    input_schema_ref: str,
    output_schema_ref: str,
    owner_team: str,
    side_effects: tuple[str, ...] = (),
    network_allowlist: tuple[str, ...] = (),
    secret_scope: str = "none",
    requires_approval: bool = False,
    extra_metadata: dict[str, Any] | None = None,
) -> CapabilityForgeInput:
    """Construct a CapabilityForgeInput from a winning ledger record.

    Author-supplied fields (capability_id, version, schema refs, owner_team,
    side effects, network/secret declarations) are required because the
    comparison ledger does not — and must not — invent them. Domain and risk
    are taken from the signature, not from any caller-supplied override; this
    is what prevents a capability from being relabeled into a domain it was
    not proven against.

    Raises ValueError if the supplied run is not a real winner under the
    signature, if domain/risk are obviously inconsistent, or if author
    metadata collides with the reserved solver_forge.* provenance key.
    """
    if not capability_id.strip():
        raise ValueError("capability_id_required")
    if not version.strip():
        raise ValueError("version_required")
    if not api_docs_ref.strip():
        raise ValueError("api_docs_ref_required")
    if not input_schema_ref.strip():
        raise ValueError("input_schema_ref_required")
    if not output_schema_ref.strip():
        raise ValueError("output_schema_ref_required")
    if not owner_team.strip():
        raise ValueError("owner_team_required")
    if extra_metadata and SOLVER_FORGE_PROVENANCE_KEY in extra_metadata:
        raise ValueError(
            f"extra_metadata_must_not_define_reserved_key:{SOLVER_FORGE_PROVENANCE_KEY}"
        )

    provenance = build_provenance(winner, signature)

    if signature.risk == "high" and not requires_approval:
        raise ValueError("high_risk_signature_requires_approval_on_forge_input")

    metadata: dict[str, Any] = dict(extra_metadata or {})
    metadata[SOLVER_FORGE_PROVENANCE_KEY] = provenance.to_metadata_block()

    return CapabilityForgeInput(
        capability_id=capability_id.strip(),
        version=version.strip(),
        domain=signature.domain,
        risk=signature.risk,
        side_effects=tuple(side_effects),
        api_docs_ref=api_docs_ref.strip(),
        input_schema_ref=input_schema_ref.strip(),
        output_schema_ref=output_schema_ref.strip(),
        owner_team=owner_team.strip(),
        network_allowlist=tuple(network_allowlist),
        secret_scope=secret_scope,
        requires_approval=requires_approval,
        metadata=metadata,
    )


def extract_provenance(forge_input: CapabilityForgeInput) -> SolverForgeProvenance | None:
    """Return the SolverForgeProvenance stamped onto a forge input, if any.

    Useful for reviewers and the certification handoff so the comparison
    evidence stays addressable from the package side without re-querying the
    ledger.
    """
    block = forge_input.metadata.get(SOLVER_FORGE_PROVENANCE_KEY)
    if not isinstance(block, dict):
        return None
    return SolverForgeProvenance(
        signature_hash=block["signature_hash"],
        problem_id=block["problem_id"],
        winner_record_hash=block["winner_record_hash"],
        primary_metric_id=block["primary_metric_id"],
        primary_metric_value=float(block["primary_metric_value"]),
        primary_metric_baseline_delta=float(block["primary_metric_baseline_delta"]),
        primary_metric_direction=block["primary_metric_direction"],
        method_families=tuple(block.get("method_families", ())),
        run_seed=block["run_seed"],
        cost_units=float(block.get("cost_units", 0.0)),
        duration_seconds=float(block.get("duration_seconds", 0.0)),
        recorded_at=block["recorded_at"],
        provenance_hash=block.get("provenance_hash", ""),
    )
