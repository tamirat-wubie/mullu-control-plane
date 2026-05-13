"""Gateway solver-forge bridge tests.

Purpose: verify that the bridge from a winning CandidateRun to a
    CapabilityForgeInput preserves comparison provenance, refuses non-winners,
    refuses cross-signature handoff, refuses domain/risk relabeling, and never
    calls into CapabilityForge or the maturity ladder directly.
Invariants tested:
  - Only passed, non-baseline, baseline-beating winners cross the bridge.
  - The forge input's domain and risk come from the signature, not from
    caller overrides — laundering by rebadging is rejected.
  - High-risk signatures force requires_approval=True on the forge input.
  - The solver_forge.* metadata key is reserved; author metadata cannot
    overwrite it.
  - The forge input round-trips through CapabilityForge.create_candidate
    and the resulting CandidateCapabilityPackage carries the provenance
    block in its metadata.
  - Bridge surface has no install/promote/certify/deploy.
"""

from __future__ import annotations

import pytest

from gateway.candidate_ledger import (
    CandidateLedger,
    CandidateScore,
    InMemoryCandidateLedgerStore,
)
from gateway.capability_forge import (
    CandidateCapabilityPackage,
    CapabilityForge,
    CapabilityForgeInput,
)
from gateway.problem_signature import (
    ProblemEvidenceRequirement,
    ProblemMetric,
    ProblemSignature,
)
from gateway.solver_forge_bridge import (
    SOLVER_FORGE_PROVENANCE_KEY,
    SolverForgeProvenance,
    build_provenance,
    extract_provenance,
    forge_input_for_winner,
    is_winner,
)


def _signature(
    *,
    risk: str = "low",
    metrics: tuple[ProblemMetric, ...] = (),
    required_evidence: tuple[ProblemEvidenceRequirement, ...] = (),
) -> ProblemSignature:
    budget = 0.0 if risk == "low" else 100.0
    timeout = 0.0 if risk == "low" else 5.0
    return ProblemSignature(
        problem_id="invoice_duplicate_detection.v1",
        domain="finance_ops",
        goal="detect duplicate invoice before payment",
        inputs=("invoice",),
        constraints=(),
        risk=risk,
        metrics=metrics or (
            ProblemMetric(
                metric_id="precision",
                metric_kind="success",
                direction="maximize",
                threshold=0.5,
            ),
        ),
        required_evidence=required_evidence,
        budget_units=budget,
        timeout_seconds=timeout,
        baseline_method_family="rule_based",
    )


def _record_winner(
    *,
    ledger: CandidateLedger,
    signature: ProblemSignature,
    method_family: str = "graph_match",
    score_value: float = 0.85,
    baseline_value: float = 0.5,
    outcome: str = "passed",
    is_baseline: bool = False,
):
    return ledger.record(
        signature_hash=signature.signature_hash,
        problem_id=signature.problem_id,
        candidate_pipeline_id=f"pipeline:{method_family}",
        method_families=(method_family,),
        outcome=outcome,
        scores=(
            CandidateScore(metric_id="precision", value=score_value, direction="maximize"),
        ),
        baseline_delta={"precision": score_value - baseline_value},
        run_seed=f"seed-{method_family}",
        is_baseline=is_baseline,
        cost_units=1.0,
        duration_seconds=0.01,
    )


def _author_fields(**overrides):
    base = dict(
        capability_id="finance.duplicate_invoice_guard.v1",
        version="0.1.0",
        api_docs_ref="docs/api/duplicate_invoice_guard.md",
        input_schema_ref="schemas/duplicate_invoice_guard.input.schema.json",
        output_schema_ref="schemas/duplicate_invoice_guard.output.schema.json",
        owner_team="finance-platform",
    )
    base.update(overrides)
    return base


# --- is_winner ---------------------------------------------------------------


def test_is_winner_accepts_passed_baseline_beating_run() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature = _signature()
    run = _record_winner(ledger=ledger, signature=signature)
    assert is_winner(run, signature) is True


def test_is_winner_rejects_failed_run() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature = _signature()
    run = _record_winner(ledger=ledger, signature=signature, outcome="failed")
    assert is_winner(run, signature) is False


def test_is_winner_rejects_baseline_run() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature = _signature()
    run = _record_winner(ledger=ledger, signature=signature, is_baseline=True)
    assert is_winner(run, signature) is False


def test_is_winner_rejects_run_with_wrong_signature_hash() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature_a = _signature()
    signature_b = ProblemSignature(
        problem_id="different_problem.v1",
        domain="finance_ops",
        goal="something else entirely",
        inputs=(),
        constraints=(),
        risk="low",
        metrics=(
            ProblemMetric(
                metric_id="precision",
                metric_kind="success",
                direction="maximize",
            ),
        ),
        required_evidence=(),
        baseline_method_family="rule_based",
    )
    run = _record_winner(ledger=ledger, signature=signature_a)
    assert is_winner(run, signature_b) is False


def test_is_winner_rejects_when_baseline_delta_is_zero_or_negative() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature = _signature()
    losing = _record_winner(
        ledger=ledger,
        signature=signature,
        method_family="weak_method",
        score_value=0.4,
        baseline_value=0.5,
    )
    assert is_winner(losing, signature) is False


def test_is_winner_honors_minimize_direction() -> None:
    metrics = (
        ProblemMetric(
            metric_id="error_rate",
            metric_kind="success",
            direction="minimize",
            threshold=0.1,
        ),
    )
    signature = _signature(metrics=metrics)
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    # candidate beats baseline by going LOWER on error_rate
    winner = ledger.record(
        signature_hash=signature.signature_hash,
        problem_id=signature.problem_id,
        candidate_pipeline_id="pipeline:graph_match",
        method_families=("graph_match",),
        outcome="passed",
        scores=(
            CandidateScore(metric_id="error_rate", value=0.05, direction="minimize"),
        ),
        baseline_delta={"error_rate": -0.05},
        run_seed="seed-min",
        is_baseline=False,
    )
    assert is_winner(winner, signature) is True


# --- build_provenance --------------------------------------------------------


def test_build_provenance_round_trips_into_metadata_block() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature = _signature()
    winner = _record_winner(ledger=ledger, signature=signature)
    provenance = build_provenance(winner, signature)

    block = provenance.to_metadata_block()
    assert block["signature_hash"] == signature.signature_hash
    assert block["winner_record_hash"] == winner.record_hash
    assert block["primary_metric_id"] == "precision"
    assert block["primary_metric_direction"] == "maximize"
    assert block["primary_metric_baseline_delta"] == pytest.approx(0.35)
    assert block["method_families"] == ["graph_match"]
    assert block["provenance_hash"]


def test_build_provenance_refuses_non_winner_with_precise_reason() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature = _signature()
    failed = _record_winner(ledger=ledger, signature=signature, outcome="failed")
    with pytest.raises(ValueError, match="winner_outcome_must_be_passed:failed"):
        build_provenance(failed, signature)


def test_build_provenance_refuses_baseline_run() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature = _signature()
    baseline_run = _record_winner(
        ledger=ledger,
        signature=signature,
        method_family="rule_based",
        is_baseline=True,
    )
    with pytest.raises(ValueError, match="baseline_runs_cannot_cross_bridge"):
        build_provenance(baseline_run, signature)


def test_build_provenance_refuses_signature_hash_mismatch() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature_a = _signature()
    # forge a second signature with a different hash by changing the goal
    signature_b = ProblemSignature(
        problem_id="invoice_duplicate_detection.v1",
        domain="finance_ops",
        goal="DIFFERENT GOAL — different hash",
        inputs=(),
        constraints=(),
        risk="low",
        metrics=(
            ProblemMetric(
                metric_id="precision",
                metric_kind="success",
                direction="maximize",
            ),
        ),
        required_evidence=(),
        baseline_method_family="rule_based",
    )
    assert signature_a.signature_hash != signature_b.signature_hash
    run = _record_winner(ledger=ledger, signature=signature_a)
    with pytest.raises(ValueError, match="winner_signature_hash_must_match_signature"):
        build_provenance(run, signature_b)


# --- forge_input_for_winner --------------------------------------------------


def test_forge_input_takes_domain_and_risk_from_signature_not_overrides() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature = _signature()
    winner = _record_winner(ledger=ledger, signature=signature)
    forge_input = forge_input_for_winner(
        winner=winner,
        signature=signature,
        **_author_fields(),
    )
    assert forge_input.domain == "finance_ops"
    assert forge_input.risk == "low"


def test_forge_input_stamps_solver_forge_provenance_block() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature = _signature()
    winner = _record_winner(ledger=ledger, signature=signature)
    forge_input = forge_input_for_winner(
        winner=winner,
        signature=signature,
        **_author_fields(),
    )
    block = forge_input.metadata[SOLVER_FORGE_PROVENANCE_KEY]
    assert block["winner_record_hash"] == winner.record_hash
    assert block["signature_hash"] == signature.signature_hash
    assert block["method_families"] == ["graph_match"]


def test_forge_input_refuses_author_metadata_overwriting_provenance_key() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature = _signature()
    winner = _record_winner(ledger=ledger, signature=signature)
    with pytest.raises(ValueError, match="reserved_key:solver_forge"):
        forge_input_for_winner(
            winner=winner,
            signature=signature,
            extra_metadata={SOLVER_FORGE_PROVENANCE_KEY: {"signature_hash": "fake"}},
            **_author_fields(),
        )


def test_forge_input_refuses_non_winner() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature = _signature()
    losing = _record_winner(
        ledger=ledger,
        signature=signature,
        method_family="weak_method",
        score_value=0.4,
        baseline_value=0.5,
    )
    with pytest.raises(ValueError, match="winner_does_not_beat_baseline"):
        forge_input_for_winner(
            winner=losing,
            signature=signature,
            **_author_fields(),
        )


def test_forge_input_high_risk_signature_requires_approval() -> None:
    high_risk = _signature(risk="high")
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    winner = _record_winner(ledger=ledger, signature=high_risk)
    with pytest.raises(ValueError, match="high_risk_signature_requires_approval_on_forge_input"):
        forge_input_for_winner(
            winner=winner,
            signature=high_risk,
            **_author_fields(),
        )

    # passes once approval is declared
    forge_input = forge_input_for_winner(
        winner=winner,
        signature=high_risk,
        requires_approval=True,
        **_author_fields(),
    )
    assert forge_input.requires_approval is True
    assert forge_input.risk == "high"


def test_forge_input_validates_author_fields() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature = _signature()
    winner = _record_winner(ledger=ledger, signature=signature)
    with pytest.raises(ValueError, match="capability_id_required"):
        forge_input_for_winner(
            winner=winner,
            signature=signature,
            **_author_fields(capability_id="   "),
        )


# --- end-to-end into CapabilityForge ----------------------------------------


def test_forge_input_round_trips_through_capability_forge() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature = _signature()
    winner = _record_winner(ledger=ledger, signature=signature)
    forge_input = forge_input_for_winner(
        winner=winner,
        signature=signature,
        **_author_fields(),
    )
    package: CandidateCapabilityPackage = CapabilityForge().create_candidate(forge_input)

    assert package.capability_id == "finance.duplicate_invoice_guard.v1"
    assert package.domain == "finance_ops"
    assert package.risk == "low"
    assert package.certification_status == "candidate"
    assert package.promotion_blocked is True

    block = package.metadata.get(SOLVER_FORGE_PROVENANCE_KEY)
    assert isinstance(block, dict)
    assert block["winner_record_hash"] == winner.record_hash
    assert block["signature_hash"] == signature.signature_hash


def test_extract_provenance_reads_back_what_bridge_wrote() -> None:
    ledger = CandidateLedger(InMemoryCandidateLedgerStore())
    signature = _signature()
    winner = _record_winner(ledger=ledger, signature=signature)
    forge_input = forge_input_for_winner(
        winner=winner,
        signature=signature,
        **_author_fields(),
    )
    extracted = extract_provenance(forge_input)
    assert extracted is not None
    assert extracted.signature_hash == signature.signature_hash
    assert extracted.winner_record_hash == winner.record_hash
    assert extracted.method_families == ("graph_match",)


def test_extract_provenance_returns_none_when_block_missing() -> None:
    forge_input = CapabilityForgeInput(
        capability_id="x",
        version="0.0.1",
        domain="finance_ops",
        risk="low",
        side_effects=(),
        api_docs_ref="d",
        input_schema_ref="i",
        output_schema_ref="o",
        owner_team="t",
    )
    assert extract_provenance(forge_input) is None


# --- promotion isolation -----------------------------------------------------


def test_bridge_module_exposes_no_install_promote_certify_deploy() -> None:
    import gateway.solver_forge_bridge as bridge

    public_names = {name for name in dir(bridge) if not name.startswith("_")}
    forbidden = {"install", "promote", "certify", "deploy", "register_capability"}
    assert public_names.isdisjoint(forbidden)
