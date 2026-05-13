"""Gateway candidate comparison ledger.

Purpose: Append-only record of every candidate pipeline run against a problem
    signature, preserving both winners and losers so that the capability forge
    can learn which method families beat baselines on which problem classes.
Governance scope: candidate-only comparison evidence — the ledger never
    promotes capabilities, never grants authority, and never deletes prior
    records. It is the asset that lets future composer runs avoid relitigating
    known-failing combinations and that lets reviewers audit *why* a candidate
    was selected for forge handoff.
Dependencies: standard-library dataclasses, threading, JSON, pathlib, canonical
    command-spine hashing, and ProblemSignature contracts.
Invariants:
  - The ledger is append-only. Records are never mutated or deleted.
  - Every record stores baseline_delta against the signature's declared baseline
    method family; runs without a baseline are flagged but still recorded.
  - Negative results (failed, regression, timeout, budget_exceeded) are recorded
    with the same shape as winners and are equally first-class evidence.
  - Record identity is derived from (signature_hash, candidate_pipeline_id,
    run_seed) canonical hash; duplicate writes are rejected at the store layer.
  - The ledger surfaces no promotion claim; the forge consumes it but maturity
    gates remain at C0–C7.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from gateway.command_spine import canonical_hash


CANDIDATE_OUTCOMES = (
    "passed",
    "failed",
    "regression",
    "timeout",
    "budget_exceeded",
    "error",
    "skipped",
)
_VALID_OUTCOMES = set(CANDIDATE_OUTCOMES)


@dataclass(frozen=True, slots=True)
class CandidateScore:
    """One measured metric on one candidate run."""

    metric_id: str
    value: float
    unit: str = ""
    direction: str = "maximize"  # mirrors ProblemMetric.direction

    def __post_init__(self) -> None:
        if not self.metric_id.strip():
            raise ValueError("metric_id_required")
        if self.direction not in ("maximize", "minimize"):
            raise ValueError("direction_must_be_maximize_or_minimize")


@dataclass(frozen=True, slots=True)
class CandidateRun:
    """One candidate pipeline executed against one problem signature."""

    record_id: str
    signature_hash: str
    problem_id: str
    candidate_pipeline_id: str
    method_families: tuple[str, ...]
    outcome: str
    scores: tuple[CandidateScore, ...]
    baseline_delta: dict[str, float]
    failure_modes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    cost_units: float
    duration_seconds: float
    run_seed: str
    is_baseline: bool
    recorded_at: str
    record_hash: str = ""
    notes: str = ""
    adversarial_review_findings: tuple[str, ...] = ()
    adversarial_review_evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.outcome not in _VALID_OUTCOMES:
            raise ValueError(f"outcome_must_be_one_of:{','.join(CANDIDATE_OUTCOMES)}")
        if self.cost_units < 0:
            raise ValueError("cost_units_must_be_non_negative")
        if self.duration_seconds < 0:
            raise ValueError("duration_seconds_must_be_non_negative")
        object.__setattr__(self, "method_families", tuple(self.method_families))
        object.__setattr__(self, "scores", tuple(self.scores))
        object.__setattr__(self, "failure_modes", tuple(self.failure_modes))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "baseline_delta", dict(self.baseline_delta))
        object.__setattr__(
            self,
            "adversarial_review_findings",
            tuple(self.adversarial_review_findings),
        )
        object.__setattr__(
            self,
            "adversarial_review_evidence_refs",
            tuple(self.adversarial_review_evidence_refs),
        )
        if not self.record_hash:
            object.__setattr__(self, "record_hash", compute_record_hash(self))


def compute_record_hash(record: CandidateRun) -> str:
    """Canonical hash that identifies a single ledger record."""
    payload = {
        "signature_hash": record.signature_hash,
        "candidate_pipeline_id": record.candidate_pipeline_id,
        "run_seed": record.run_seed,
        "outcome": record.outcome,
        "scores": [asdict(score) for score in record.scores],
        "baseline_delta": record.baseline_delta,
        "method_families": list(record.method_families),
        "is_baseline": record.is_baseline,
        "adversarial_review_findings": list(record.adversarial_review_findings),
    }
    return canonical_hash(payload)


def record_from_mapping(payload: dict[str, Any]) -> CandidateRun:
    scores = tuple(
        CandidateScore(**score) if isinstance(score, dict) else score
        for score in payload.get("scores", ())
    )
    return CandidateRun(
        record_id=payload["record_id"],
        signature_hash=payload["signature_hash"],
        problem_id=payload["problem_id"],
        candidate_pipeline_id=payload["candidate_pipeline_id"],
        method_families=tuple(payload.get("method_families", ())),
        outcome=payload["outcome"],
        scores=scores,
        baseline_delta=dict(payload.get("baseline_delta", {})),
        failure_modes=tuple(payload.get("failure_modes", ())),
        evidence_refs=tuple(payload.get("evidence_refs", ())),
        cost_units=float(payload.get("cost_units", 0.0)),
        duration_seconds=float(payload.get("duration_seconds", 0.0)),
        run_seed=payload["run_seed"],
        is_baseline=bool(payload.get("is_baseline", False)),
        recorded_at=payload["recorded_at"],
        record_hash=payload.get("record_hash", ""),
        notes=payload.get("notes", ""),
        adversarial_review_findings=tuple(payload.get("adversarial_review_findings", ())),
        adversarial_review_evidence_refs=tuple(
            payload.get("adversarial_review_evidence_refs", ())
        ),
    )


class CandidateLedgerStore:
    """Storage contract — append-only across all implementations."""

    def append(self, record: CandidateRun) -> None:
        raise NotImplementedError

    def list_for_signature(self, signature_hash: str) -> tuple[CandidateRun, ...]:
        raise NotImplementedError

    def list_all(self) -> tuple[CandidateRun, ...]:
        raise NotImplementedError

    def has_record(self, record_hash: str) -> bool:
        raise NotImplementedError

    def status(self) -> dict[str, Any]:
        return {"backend": "unknown", "available": False}


class InMemoryCandidateLedgerStore(CandidateLedgerStore):
    """In-memory append-only store for tests and short-lived sessions."""

    def __init__(self) -> None:
        self._records: list[CandidateRun] = []
        self._seen: set[str] = set()
        self._lock = threading.Lock()

    def append(self, record: CandidateRun) -> None:
        with self._lock:
            if record.record_hash in self._seen:
                raise ValueError(f"duplicate_record_hash:{record.record_hash}")
            self._records.append(record)
            self._seen.add(record.record_hash)

    def list_for_signature(self, signature_hash: str) -> tuple[CandidateRun, ...]:
        return tuple(r for r in self._records if r.signature_hash == signature_hash)

    def list_all(self) -> tuple[CandidateRun, ...]:
        return tuple(self._records)

    def has_record(self, record_hash: str) -> bool:
        return record_hash in self._seen

    def status(self) -> dict[str, Any]:
        return {"backend": "memory", "available": True, "records": len(self._records)}


class JsonFileCandidateLedgerStore(CandidateLedgerStore):
    """JSON-file durable append-only store."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if not self._path.exists():
            self._write_payload({"records": []})

    def append(self, record: CandidateRun) -> None:
        with self._lock:
            payload = self._read_payload()
            records = payload.setdefault("records", [])
            if not isinstance(records, list):
                raise ValueError("candidate ledger records root must be an array")
            for existing in records:
                if isinstance(existing, dict) and existing.get("record_hash") == record.record_hash:
                    raise ValueError(f"duplicate_record_hash:{record.record_hash}")
            records.append(asdict(record))
            self._write_payload(payload)

    def list_for_signature(self, signature_hash: str) -> tuple[CandidateRun, ...]:
        return tuple(
            record for record in self.list_all() if record.signature_hash == signature_hash
        )

    def list_all(self) -> tuple[CandidateRun, ...]:
        payload = self._read_payload()
        raw = payload.get("records", [])
        if not isinstance(raw, list):
            raise ValueError("candidate ledger records root must be an array")
        return tuple(record_from_mapping(entry) for entry in raw if isinstance(entry, dict))

    def has_record(self, record_hash: str) -> bool:
        return any(record.record_hash == record_hash for record in self.list_all())

    def status(self) -> dict[str, Any]:
        return {
            "backend": "json",
            "available": True,
            "path": str(self._path),
            "records": len(self.list_all()),
        }

    def _read_payload(self) -> dict[str, Any]:
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write_payload(self, payload: dict[str, Any]) -> None:
        self._path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )


def _default_clock() -> str:
    return datetime.now(timezone.utc).isoformat()


class CandidateLedger:
    """Append-only comparison ledger over a CandidateLedgerStore."""

    def __init__(
        self,
        store: CandidateLedgerStore | None = None,
        *,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._store = store or InMemoryCandidateLedgerStore()
        self._clock = clock or _default_clock

    def record(
        self,
        *,
        signature_hash: str,
        problem_id: str,
        candidate_pipeline_id: str,
        method_families: tuple[str, ...],
        outcome: str,
        scores: tuple[CandidateScore, ...],
        baseline_delta: dict[str, float] | None,
        failure_modes: tuple[str, ...] = (),
        evidence_refs: tuple[str, ...] = (),
        cost_units: float = 0.0,
        duration_seconds: float = 0.0,
        run_seed: str = "",
        is_baseline: bool = False,
        notes: str = "",
        adversarial_review_findings: tuple[str, ...] = (),
        adversarial_review_evidence_refs: tuple[str, ...] = (),
    ) -> CandidateRun:
        record_id = f"candrun:{candidate_pipeline_id}:{run_seed or 'noseed'}"
        record = CandidateRun(
            record_id=record_id,
            signature_hash=signature_hash,
            problem_id=problem_id,
            candidate_pipeline_id=candidate_pipeline_id,
            method_families=method_families,
            outcome=outcome,
            scores=scores,
            baseline_delta=baseline_delta or {},
            failure_modes=failure_modes,
            evidence_refs=evidence_refs,
            cost_units=cost_units,
            duration_seconds=duration_seconds,
            run_seed=run_seed,
            is_baseline=is_baseline,
            recorded_at=self._clock(),
            notes=notes,
            adversarial_review_findings=adversarial_review_findings,
            adversarial_review_evidence_refs=adversarial_review_evidence_refs,
        )
        self._store.append(record)
        return record

    def for_signature(self, signature_hash: str) -> tuple[CandidateRun, ...]:
        return self._store.list_for_signature(signature_hash)

    def baseline_for(self, signature_hash: str) -> CandidateRun | None:
        for record in self._store.list_for_signature(signature_hash):
            if record.is_baseline:
                return record
        return None

    def winners_for(
        self,
        signature_hash: str,
        *,
        primary_metric_id: str,
    ) -> tuple[CandidateRun, ...]:
        """Return passed runs whose baseline_delta on the primary metric is
        positive when direction is maximize, negative when minimize, AND that
        carry no adversarial-review findings. A run is only a "winner" if it
        beat a baseline AND survived adversarial review; runs without a
        recorded baseline delta or with non-empty findings are deliberately
        excluded.

        Note: this method cannot detect the case where the *baseline itself*
        has findings — the caller must check baseline integrity separately
        (the composer reports this via baseline_compromised flags on its
        comparison report).
        """
        runs = [
            run
            for run in self._store.list_for_signature(signature_hash)
            if run.outcome == "passed"
            and not run.is_baseline
            and not run.adversarial_review_findings
        ]
        winners: list[CandidateRun] = []
        for run in runs:
            delta = run.baseline_delta.get(primary_metric_id)
            if delta is None:
                continue
            metric_direction = next(
                (score.direction for score in run.scores if score.metric_id == primary_metric_id),
                "maximize",
            )
            if metric_direction == "maximize" and delta > 0:
                winners.append(run)
            elif metric_direction == "minimize" and delta < 0:
                winners.append(run)
        return tuple(winners)

    def negative_results_for(self, signature_hash: str) -> tuple[CandidateRun, ...]:
        return tuple(
            run
            for run in self._store.list_for_signature(signature_hash)
            if run.outcome != "passed"
        )

    def status(self) -> dict[str, Any]:
        return self._store.status()
