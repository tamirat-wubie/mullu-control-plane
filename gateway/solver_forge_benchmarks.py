"""Gateway solver-forge reference benchmarks.

Purpose: A worked, runnable benchmark that exercises the Solver Forge loop
    end-to-end on REAL (if small) computation. The duplicate-invoice benchmark
    embeds a labeled fixture and three genuine detectors, computes real
    precision/recall/F1, and lets the composer compare them under evidence. It
    is the template adapter owners copy when wiring a real evaluator, and the
    proof that the governed loop selects a winner correctly.
Governance scope: experimentation only. Running a benchmark composes
    candidates, scores them against a fixed fixture, records every result to a
    candidate ledger, and returns a comparison report. It NEVER promotes,
    installs, certifies, or deploys anything.
Dependencies: gateway.problem_signature, gateway.candidate_ledger,
    gateway.candidate_composer, gateway.method_registry.
Invariants:
  - The evaluator is deterministic: identical fixture + capsule -> identical
    scores. No randomness, no wall-clock dependence in scoring.
  - The primary success metric is F1, not recall. A high-recall/low-precision
    detector must NOT win — the loop refuses recall-only optimization.
  - Scores are measured on the fixture, not declared. The detectors really run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from gateway.candidate_composer import (
    CandidateComparisonReport,
    CandidateEvaluation,
    CandidatePipeline,
)
from gateway.candidate_ledger import CandidateLedger, CandidateScore
from gateway.method_registry import MethodRegistry, default_registry
from gateway.problem_signature import (
    ProblemEvidenceRequirement,
    ProblemMetric,
    ProblemSignature,
)


# --------------------------------------------------------------------------- #
# Labeled fixture: synthetic invoices with known duplicate clusters.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class InvoiceRecord:
    id: str
    vendor: str
    number: str
    amount: float
    issued: str  # ISO date YYYY-MM-DD


INVOICE_FIXTURE: tuple[InvoiceRecord, ...] = (
    # Acme: 001/002 exact dup, 003 formatting variation of the same invoice.
    InvoiceRecord("001", "Acme Corp", "A-100", 1200.00, "2026-01-05"),
    InvoiceRecord("002", "Acme Corp", "A-100", 1200.00, "2026-01-05"),
    InvoiceRecord("003", "acme corp.", "A100", 1200.00, "2026-01-12"),
    # Acme: two genuinely distinct invoices (same-vendor traps for overflag).
    InvoiceRecord("014", "Acme Corp", "A-201", 500.00, "2026-05-01"),
    InvoiceRecord("015", "Acme Corp", "A-202", 750.00, "2026-05-02"),
    # Globex: 004/011 exact dup; 005/012 distinct same-vendor invoices.
    InvoiceRecord("004", "Globex LLC", "G-55", 900.00, "2026-02-01"),
    InvoiceRecord("011", "Globex LLC", "G-55", 900.00, "2026-02-01"),
    InvoiceRecord("005", "Globex LLC", "G-56", 450.00, "2026-02-03"),
    InvoiceRecord("012", "Globex LLC", "G-57", 300.00, "2026-02-10"),
    # Initech: 006/007 near dup (vendor-suffix variation, date off by one).
    InvoiceRecord("006", "Initech", "I-7", 3000.00, "2026-03-10"),
    InvoiceRecord("007", "Initech Inc", "I-7", 3000.00, "2026-03-11"),
    # Hooli: 009/010 exact dup.
    InvoiceRecord("009", "Hooli", "H-9", 780.00, "2026-04-02"),
    InvoiceRecord("010", "Hooli", "H-9", 780.00, "2026-04-02"),
    # Umbrella: singleton.
    InvoiceRecord("008", "Umbrella Co", "U-22", 150.00, "2026-03-15"),
)

# Ground-truth duplicate clusters. Pairs within a cluster are true duplicates.
_TRUE_CLUSTERS: tuple[tuple[str, ...], ...] = (
    ("001", "002", "003"),
    ("004", "011"),
    ("006", "007"),
    ("009", "010"),
)


def _true_pairs() -> frozenset[frozenset[str]]:
    pairs: set[frozenset[str]] = set()
    for cluster in _TRUE_CLUSTERS:
        for i in range(len(cluster)):
            for j in range(i + 1, len(cluster)):
                pairs.add(frozenset((cluster[i], cluster[j])))
    return frozenset(pairs)


# --------------------------------------------------------------------------- #
# Normalization helpers + three genuine detectors.
# --------------------------------------------------------------------------- #

_VENDOR_SUFFIXES = {"inc", "llc", "co", "corp", "ltd", "gmbh", "plc", "sa"}


def _norm_vendor(vendor: str) -> str:
    tokens = re.split(r"[^a-z0-9]+", vendor.lower())
    return "".join(t for t in tokens if t and t not in _VENDOR_SUFFIXES)


def _norm_number(number: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "", number).upper()


def _parse_date(value: str) -> date:
    year, month, day = (int(part) for part in value.split("-"))
    return date(year, month, day)


def _amount_close(a: float, b: float, tol: float = 0.005) -> bool:
    return abs(a - b) <= tol * max(abs(a), abs(b), 1.0)


def _date_within(a: str, b: str, days: int) -> bool:
    return abs((_parse_date(a) - _parse_date(b)).days) <= days


def _all_pairs(records: tuple[InvoiceRecord, ...]):
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            yield records[i], records[j]


def detect_exact(records: tuple[InvoiceRecord, ...]) -> frozenset[frozenset[str]]:
    """rule_based baseline: identical (vendor, number, amount). High precision."""
    pairs: set[frozenset[str]] = set()
    for a, b in _all_pairs(records):
        if a.vendor == b.vendor and a.number == b.number and a.amount == b.amount:
            pairs.add(frozenset((a.id, b.id)))
    return frozenset(pairs)


def detect_graph(records: tuple[InvoiceRecord, ...]) -> frozenset[frozenset[str]]:
    """graph_match: normalized vendor + amount proximity + (number or date)."""
    pairs: set[frozenset[str]] = set()
    for a, b in _all_pairs(records):
        if _norm_vendor(a.vendor) != _norm_vendor(b.vendor):
            continue
        if not _amount_close(a.amount, b.amount):
            continue
        if _norm_number(a.number) == _norm_number(b.number) or _date_within(
            a.issued, b.issued, 7
        ):
            pairs.add(frozenset((a.id, b.id)))
    return frozenset(pairs)


def detect_overflag(records: tuple[InvoiceRecord, ...]) -> frozenset[frozenset[str]]:
    """statistical_anomaly trap: any same-vendor pair. High recall, low precision."""
    pairs: set[frozenset[str]] = set()
    for a, b in _all_pairs(records):
        if _norm_vendor(a.vendor) == _norm_vendor(b.vendor):
            pairs.add(frozenset((a.id, b.id)))
    return frozenset(pairs)


# capsule_id -> (detector, declared cost). The cost is a fixed, honest stand-in
# for compute; it does not affect winner selection (the composer compares the
# primary metric only).
_DETECTORS = {
    "capsule:rule_based.exact_field_match.v1": (detect_exact, 1.0),
    "capsule:graph_match.vendor_amount_proximity.v1": (detect_graph, 3.0),
    "capsule:statistical.same_vendor_overflag.v1": (detect_overflag, 2.0),
}

_METRIC_DIRECTIONS = {
    "f1_score": "maximize",
    "precision": "maximize",
    "recall": "maximize",
    "false_positive_rate": "minimize",
}

# Minimum F1 to count as a successful run. Set low so all three detectors
# "pass" the floor and the winner is decided by baseline_delta, not the floor —
# this is what puts the baseline-delta gate (not the threshold) under test.
_F1_FLOOR = 0.4


def _score(predicted: frozenset[frozenset[str]], n_records: int) -> dict[str, float]:
    truth = _true_pairs()
    tp = len(predicted & truth)
    fp = len(predicted - truth)
    fn = len(truth - predicted)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    total_pairs = n_records * (n_records - 1) // 2
    non_dup_pairs = total_pairs - len(truth)
    fpr = fp / non_dup_pairs if non_dup_pairs else 0.0
    return {
        "f1_score": round(f1, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "false_positive_rate": round(fpr, 4),
    }


def reference_evaluator(
    signature: ProblemSignature,
    pipeline: CandidatePipeline,
    seed: str,
) -> CandidateEvaluation:
    """Deterministic evaluator for the duplicate-invoice benchmark.

    Maps the pipeline's (single) capsule to a detector, runs it on the fixture,
    and returns measured scores. Unknown capsules return `skipped` rather than
    fabricating a score.
    """
    capsule_id = pipeline.capsule_ids[0] if pipeline.capsule_ids else ""
    entry = _DETECTORS.get(capsule_id)
    if entry is None:
        return CandidateEvaluation(
            outcome="skipped",
            scores=(),
            notes=f"no_reference_detector_for:{capsule_id}",
        )
    detector, cost = entry
    predicted = detector(INVOICE_FIXTURE)
    metrics = _score(predicted, len(INVOICE_FIXTURE))
    scores = tuple(
        CandidateScore(metric_id=key, value=value, direction=_METRIC_DIRECTIONS[key])
        for key, value in metrics.items()
    )
    outcome = "passed" if metrics["f1_score"] >= _F1_FLOOR else "failed"
    return CandidateEvaluation(
        outcome=outcome,
        scores=scores,
        evidence_refs=(f"duplicate_pairs_receipt:{len(predicted)}",),
        cost_units=cost,
        duration_seconds=0.0,
        notes=(
            f"predicted={len(predicted)} pairs; "
            f"f1={metrics['f1_score']} precision={metrics['precision']} "
            f"recall={metrics['recall']}"
        ),
    )


# --------------------------------------------------------------------------- #
# Benchmark signature + catalog.
# --------------------------------------------------------------------------- #

DUPLICATE_INVOICE_SIGNATURE = ProblemSignature(
    problem_id="invoice_duplicate_detection.v1",
    domain="document_verification",
    goal="detect duplicate invoices before payment",
    inputs=("invoice_records",),
    constraints=("no payment decision without vendor match",),
    risk="medium",
    metrics=(
        ProblemMetric(
            metric_id="f1_score",
            metric_kind="success",
            direction="maximize",
            threshold=_F1_FLOOR,
            description="harmonic mean of precision and recall (primary)",
        ),
        ProblemMetric(metric_id="precision", metric_kind="success", direction="maximize"),
        ProblemMetric(metric_id="recall", metric_kind="success", direction="maximize"),
        ProblemMetric(
            metric_id="false_positive_rate",
            metric_kind="failure",
            direction="minimize",
        ),
    ),
    required_evidence=(
        ProblemEvidenceRequirement(
            requirement_id="matched-pairs",
            evidence_type="duplicate_pairs_receipt",
            required=True,
        ),
    ),
    budget_units=100.0,
    timeout_seconds=5.0,
    allowed_method_families=("rule_based", "graph_match", "statistical_anomaly"),
    baseline_method_family="rule_based",
)


# --------------------------------------------------------------------------- #
# Second benchmark: single-worker task scheduling with deadlines.
# A different domain (engineering_puzzle) that exercises the scheduler capsules.
# The primary metric is on-time rate, so a scheduler that optimizes the wrong
# thing (clear the big tasks first) is recorded but refused as a winner.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class SchedulingTask:
    id: str
    duration: float
    deadline: float
    deps: tuple[str, ...] = ()


SCHEDULING_FIXTURE: tuple[SchedulingTask, ...] = (
    SchedulingTask("T1", 2.0, 3.0),
    SchedulingTask("T2", 1.0, 2.0),
    SchedulingTask("T3", 3.0, 12.0, ("T1",)),
    SchedulingTask("T4", 2.0, 6.0),
    SchedulingTask("T5", 1.0, 5.0, ("T2",)),
    SchedulingTask("T6", 4.0, 20.0),
)

_TASK_INDEX = {task.id: i for i, task in enumerate(SCHEDULING_FIXTURE)}


def _simulate(tasks: tuple[SchedulingTask, ...], pick_key):
    """Single worker, sequential, no preemption; respects dependencies."""
    completed: dict[str, float] = {}
    remaining = list(tasks)
    clock = 0.0
    order: list[str] = []
    while remaining:
        ready = [t for t in remaining if all(d in completed for d in t.deps)]
        if not ready:  # malformed dependency graph; stop deterministically
            break
        nxt = min(ready, key=pick_key)
        clock += nxt.duration
        completed[nxt.id] = clock
        order.append(nxt.id)
        remaining.remove(nxt)
    return completed, tuple(order)


def _key_in_order(task: SchedulingTask):  # naive baseline: original task order
    return _TASK_INDEX[task.id]


def _key_earliest_deadline(task: SchedulingTask):  # earliest-deadline-first
    return (task.deadline, _TASK_INDEX[task.id])


def _key_longest_first(task: SchedulingTask):  # "clear the big rocks first" anti-pattern
    return (-task.duration, _TASK_INDEX[task.id])


def _schedule_metrics(completed: dict[str, float]) -> dict[str, float]:
    by_id = {t.id: t for t in SCHEDULING_FIXTURE}
    on_time = sum(1 for tid, done in completed.items() if done <= by_id[tid].deadline)
    n = len(SCHEDULING_FIXTURE)
    return {
        "on_time_rate": round(on_time / n, 4) if n else 0.0,
        "deadline_miss_count": float(n - on_time),
        "total_completion_time": round(sum(completed.values()), 4),
    }


# capsule_id -> (priority strategy, declared cost)
_SCHEDULERS = {
    "capsule:search_planner.bfs_deadline.v1": (_key_in_order, 1.0),
    "capsule:constraint_solver.scheduling.v1": (_key_earliest_deadline, 3.0),
    "capsule:optimization_solver.lp_relax.v1": (_key_longest_first, 2.0),
}

_SCHEDULE_DIRECTIONS = {
    "on_time_rate": "maximize",
    "deadline_miss_count": "minimize",
    "total_completion_time": "minimize",
}

_ON_TIME_FLOOR = 0.25


def scheduling_evaluator(
    signature: ProblemSignature,
    pipeline: CandidatePipeline,
    seed: str,
) -> CandidateEvaluation:
    """Deterministic evaluator for the task-scheduling benchmark. Maps the
    pipeline's capsule to a scheduling strategy, simulates it on the fixture,
    and measures the on-time rate. Unknown capsules are skipped, not faked."""
    capsule_id = pipeline.capsule_ids[0] if pipeline.capsule_ids else ""
    entry = _SCHEDULERS.get(capsule_id)
    if entry is None:
        return CandidateEvaluation(
            outcome="skipped",
            scores=(),
            notes=f"no_reference_scheduler_for:{capsule_id}",
        )
    pick_key, cost = entry
    completed, order = _simulate(SCHEDULING_FIXTURE, pick_key)
    metrics = _schedule_metrics(completed)
    scores = tuple(
        CandidateScore(metric_id=key, value=value, direction=_SCHEDULE_DIRECTIONS[key])
        for key, value in metrics.items()
    )
    outcome = "passed" if metrics["on_time_rate"] >= _ON_TIME_FLOOR else "failed"
    return CandidateEvaluation(
        outcome=outcome,
        scores=scores,
        evidence_refs=(f"schedule_order_receipt:{'>'.join(order)}",),
        cost_units=cost,
        duration_seconds=0.0,
        notes=(
            f"on_time_rate={metrics['on_time_rate']} "
            f"misses={metrics['deadline_miss_count']} order={'>'.join(order)}"
        ),
    )


SCHEDULING_SIGNATURE = ProblemSignature(
    problem_id="task_scheduling_with_deadlines.v1",
    domain="engineering_puzzle",
    goal="schedule tasks on one worker to meet deadlines",
    inputs=("tasks", "durations", "deadlines", "dependencies"),
    constraints=("respect task dependencies", "single worker, no preemption"),
    risk="medium",
    metrics=(
        ProblemMetric(
            metric_id="on_time_rate",
            metric_kind="success",
            direction="maximize",
            threshold=_ON_TIME_FLOOR,
            description="fraction of tasks finished by their deadline (primary)",
        ),
        ProblemMetric(
            metric_id="deadline_miss_count", metric_kind="failure", direction="minimize"
        ),
        ProblemMetric(
            metric_id="total_completion_time", metric_kind="failure", direction="minimize"
        ),
    ),
    required_evidence=(
        ProblemEvidenceRequirement(
            requirement_id="schedule",
            evidence_type="schedule_order_receipt",
            required=True,
        ),
    ),
    budget_units=100.0,
    timeout_seconds=5.0,
    allowed_method_families=("search_planner", "constraint_solver", "optimization_solver"),
    baseline_method_family="search_planner",
)


@dataclass(frozen=True, slots=True)
class Benchmark:
    benchmark_id: str
    signature: ProblemSignature
    evaluator: object  # EvaluatorCallback
    description: str


BENCHMARKS: dict[str, Benchmark] = {
    DUPLICATE_INVOICE_SIGNATURE.problem_id: Benchmark(
        benchmark_id=DUPLICATE_INVOICE_SIGNATURE.problem_id,
        signature=DUPLICATE_INVOICE_SIGNATURE,
        evaluator=reference_evaluator,
        description=(
            "Invoice duplicate detection over a labeled fixture. Baseline "
            "exact-match vs normalized graph-match vs a same-vendor overflag "
            "trap. Primary metric is F1, so the recall-only trap cannot win."
        ),
    ),
    SCHEDULING_SIGNATURE.problem_id: Benchmark(
        benchmark_id=SCHEDULING_SIGNATURE.problem_id,
        signature=SCHEDULING_SIGNATURE,
        evaluator=scheduling_evaluator,
        description=(
            "Single-worker task scheduling with deadlines and dependencies. "
            "Naive in-order baseline vs earliest-deadline-first vs a "
            "longest-first anti-pattern. Primary metric is on-time rate, so "
            "the anti-pattern is recorded but refused."
        ),
    ),
}


def list_benchmarks() -> tuple[Benchmark, ...]:
    return tuple(BENCHMARKS.values())


def get_benchmark(benchmark_id: str) -> Benchmark:
    if benchmark_id not in BENCHMARKS:
        raise ValueError(f"unknown_benchmark_id:{benchmark_id}")
    return BENCHMARKS[benchmark_id]


def run_benchmark(
    benchmark_id: str,
    *,
    ledger: CandidateLedger | None = None,
    registry: MethodRegistry | None = None,
    adversarial_reviewer=None,
) -> tuple[CandidateComparisonReport, CandidateLedger]:
    """Run one benchmark through the governed composer and return its report.

    Returns the comparison report and the ledger it wrote to. Promotes nothing;
    the report's winners are candidates a human may choose to hand to the
    Capability Forge via solver_forge_bridge — that step is explicit and
    downstream, never automatic.
    """
    benchmark = get_benchmark(benchmark_id)
    ledger = ledger or CandidateLedger()
    registry = registry or default_registry()
    composer = registry.composer_for(
        benchmark.signature, ledger, adversarial_reviewer=adversarial_reviewer
    )
    report = composer.run(benchmark.signature, benchmark.evaluator)
    return report, ledger
