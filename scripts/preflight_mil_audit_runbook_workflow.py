#!/usr/bin/env python3
"""Preflight MIL audit runbook workflow readiness.

Purpose: execute the MIL audit runbook promotion gates against explicit local stores.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: MIL audit checklist validator, MIL audit store, trace store, replay store, runbook store.
Invariants:
  - Checklist validation runs before workflow checks.
  - MIL audit record loading is explicit and bounded.
  - Replay projection remains observation-only.
  - Trace and replay persistence precede runbook admission.
  - Durable runbook readback must preserve source verification provenance.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MCOI_ROOT = REPO_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from mcoi_runtime.contracts.learning import LearningAdmissionDecision, LearningAdmissionStatus  # noqa: E402
from mcoi_runtime.contracts.policy import DecisionReason  # noqa: E402
from mcoi_runtime.contracts.replay import ReplayMode  # noqa: E402
from mcoi_runtime.core.invariants import stable_identifier  # noqa: E402
from mcoi_runtime.core.persisted_replay import PersistedReplayValidator  # noqa: E402
from mcoi_runtime.core.replay_engine import ReplayContext, ReplayVerdict  # noqa: E402
from mcoi_runtime.core.runbook import RunbookLibrary  # noqa: E402
from mcoi_runtime.persistence.mil_audit_store import MILAuditStore  # noqa: E402
from mcoi_runtime.persistence.replay_store import ReplayStore  # noqa: E402
from mcoi_runtime.persistence.runbook_store import RunbookStore  # noqa: E402
from mcoi_runtime.persistence.trace_store import TraceStore  # noqa: E402
from scripts.validate_mil_audit_runbook_operator_checklist import (  # noqa: E402
    DEFAULT_CHECKLIST,
    validate_mil_audit_runbook_operator_checklist,
)

DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "mil_audit_runbook_workflow_preflight.json"


@dataclass(frozen=True, slots=True)
class MILAuditRunbookPreflightStep:
    """One MIL audit runbook preflight step."""

    name: str
    passed: bool
    detail: str

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-ready step."""
        return asdict(self)


@dataclass(frozen=True, slots=True)
class MILAuditRunbookPreflightReport:
    """Full MIL audit runbook workflow preflight report."""

    ready: bool
    checked_at: str
    step_count: int
    steps: tuple[MILAuditRunbookPreflightStep, ...]
    blockers: tuple[str, ...]
    record_id: str
    runbook_id: str
    replay_id: str
    trace_id: str
    runbook_persisted: bool

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready report."""
        return {
            "ready": self.ready,
            "checked_at": self.checked_at,
            "step_count": self.step_count,
            "steps": [step.as_dict() for step in self.steps],
            "blockers": list(self.blockers),
            "record_id": self.record_id,
            "runbook_id": self.runbook_id,
            "replay_id": self.replay_id,
            "trace_id": self.trace_id,
            "runbook_persisted": self.runbook_persisted,
        }


def preflight_mil_audit_runbook_workflow(
    *,
    checklist_path: Path = DEFAULT_CHECKLIST,
    audit_store_path: Path,
    trace_store_path: Path,
    replay_store_path: Path,
    runbook_store_path: Path,
    record_id: str,
    runbook_id: str,
    name: str,
    description: str,
) -> MILAuditRunbookPreflightReport:
    """Run the MIL audit runbook workflow preflight against explicit local stores."""
    steps: list[MILAuditRunbookPreflightStep] = []
    replay_id = ""
    trace_id = ""
    runbook_persisted = False

    checklist_result = validate_mil_audit_runbook_operator_checklist(checklist_path)
    steps.append(
        MILAuditRunbookPreflightStep(
            name="operator checklist validation",
            passed=checklist_result.valid,
            detail=_validation_detail(checklist_result.errors),
        )
    )
    if not checklist_result.valid:
        return _report(
            steps=steps,
            record_id=record_id,
            runbook_id=runbook_id,
            replay_id=replay_id,
            trace_id=trace_id,
            runbook_persisted=runbook_persisted,
        )

    audit_store = MILAuditStore(audit_store_path)
    try:
        record = audit_store.load(record_id)
        load_passed = record.record_id == record_id and record.verification_passed
        load_detail = (
            f"record_id={record.record_id} verification_passed={str(record.verification_passed).lower()}"
            if load_passed
            else "record failed verification witness check"
        )
    except Exception as exc:
        record = None
        load_passed = False
        load_detail = _bounded_detail("record load failed", exc)
    steps.append(MILAuditRunbookPreflightStep("MIL audit record load", load_passed, load_detail))
    if record is None:
        return _report(
            steps=steps,
            record_id=record_id,
            runbook_id=runbook_id,
            replay_id=replay_id,
            trace_id=trace_id,
            runbook_persisted=runbook_persisted,
        )

    try:
        lookup = audit_store.replay_lookup(record_id)
        replay_id = lookup.replay_record.replay_id
        trace_id = lookup.replay_record.trace_id
        replay_passed = (
            lookup.replay_record.mode is ReplayMode.OBSERVATION_ONLY
            and len(lookup.trace_entries) >= 6
            and bool(lookup.replay_record.source_hash)
        )
        replay_detail = (
            f"replay_id={replay_id} mode={lookup.replay_record.mode.value} trace_entries={len(lookup.trace_entries)}"
        )
    except Exception as exc:
        replay_passed = False
        replay_detail = _bounded_detail("replay projection failed", exc)
    steps.append(MILAuditRunbookPreflightStep("observation replay projection", replay_passed, replay_detail))
    if not replay_passed:
        return _report(
            steps=steps,
            record_id=record_id,
            runbook_id=runbook_id,
            replay_id=replay_id,
            trace_id=trace_id,
            runbook_persisted=runbook_persisted,
        )

    trace_store = TraceStore(trace_store_path)
    replay_store = ReplayStore(replay_store_path)
    try:
        bundle = audit_store.persist_replay_bundle(
            record_id,
            trace_store=trace_store,
            replay_store=replay_store,
        )
        replay_id = bundle.replay_id
        trace_id = bundle.replay_record.trace_id
        persistence_passed = len(bundle.trace_ids) >= 6 and bool(replay_store.load(bundle.replay_id))
        persistence_detail = f"replay_id={bundle.replay_id} trace_count={len(bundle.trace_ids)}"
    except Exception as exc:
        bundle = None
        persistence_passed = False
        persistence_detail = _bounded_detail("replay bundle persistence failed", exc)
    steps.append(MILAuditRunbookPreflightStep("trace and replay persistence", persistence_passed, persistence_detail))
    if bundle is None:
        return _report(
            steps=steps,
            record_id=record_id,
            runbook_id=runbook_id,
            replay_id=replay_id,
            trace_id=trace_id,
            runbook_persisted=runbook_persisted,
        )

    try:
        context = ReplayContext(
            state_hash=bundle.replay_record.state_hash,
            environment_digest=bundle.replay_record.environment_digest,
        )
        replay_validation = PersistedReplayValidator(
            replay_store=replay_store,
            trace_store=trace_store,
        ).validate(bundle.replay_id, context)
        validation_passed = replay_validation.validation.verdict is ReplayVerdict.MATCH
        validation_detail = f"verdict={replay_validation.validation.verdict.value} trace_found={replay_validation.trace_found}"
    except Exception as exc:
        context = None
        validation_passed = False
        validation_detail = _bounded_detail("persisted replay validation failed", exc)
    steps.append(MILAuditRunbookPreflightStep("persisted replay validation", validation_passed, validation_detail))
    if context is None:
        return _report(
            steps=steps,
            record_id=record_id,
            runbook_id=runbook_id,
            replay_id=replay_id,
            trace_id=trace_id,
            runbook_persisted=runbook_persisted,
        )

    library = RunbookLibrary(
        replay_validator=PersistedReplayValidator(
            replay_store=replay_store,
            trace_store=trace_store,
        ),
        clock=_utc_now,
    )
    learning = LearningAdmissionDecision(
        admission_id=stable_identifier("mil-audit-runbook-admission", {"record_id": record_id, "runbook_id": runbook_id}),
        knowledge_id=runbook_id,
        status=LearningAdmissionStatus.ADMIT,
        reasons=(DecisionReason("MIL audit replay verified", "mil_audit_replay_verified"),),
        issued_at=_utc_now(),
    )
    admission = library.admit(
        runbook_id=runbook_id,
        name=name,
        description=description,
        template={
            "action_type": "mil_audit_replay",
            "program_id": record.program_id,
            "goal_id": record.goal_id,
        },
        bindings_schema={},
        replay_id=bundle.replay_id,
        execution_id=record.execution_id,
        verification_id=record.record_id,
        execution_succeeded=True,
        verification_passed=record.verification_passed,
        learning_admission=learning,
        context=context,
    )
    admission_passed = admission.entry is not None and admission.entry.provenance.verification_id == record_id
    steps.append(
        MILAuditRunbookPreflightStep(
            name="runbook learning admission",
            passed=admission_passed,
            detail=f"status={admission.status.value} reasons={list(admission.reasons)}",
        )
    )
    if admission.entry is None:
        return _report(
            steps=steps,
            record_id=record_id,
            runbook_id=runbook_id,
            replay_id=replay_id,
            trace_id=trace_id,
            runbook_persisted=runbook_persisted,
        )

    try:
        runbook_store = RunbookStore(runbook_store_path)
        runbook_persisted = runbook_store.save(admission.entry) or runbook_store.load(runbook_id) == admission.entry
        loaded = runbook_store.load(runbook_id)
        listed_ids = runbook_store.list_runbook_ids()
        readback_passed = (
            loaded.runbook_id == runbook_id
            and loaded.provenance.verification_id == record_id
            and runbook_id in listed_ids
        )
        readback_detail = f"runbook_id={loaded.runbook_id} listed={str(runbook_id in listed_ids).lower()}"
    except Exception as exc:
        readback_passed = False
        readback_detail = _bounded_detail("runbook persistence readback failed", exc)
    steps.append(MILAuditRunbookPreflightStep("durable runbook readback", readback_passed, readback_detail))
    return _report(
        steps=steps,
        record_id=record_id,
        runbook_id=runbook_id,
        replay_id=replay_id,
        trace_id=trace_id,
        runbook_persisted=runbook_persisted,
    )


def write_mil_audit_runbook_preflight_report(
    report: MILAuditRunbookPreflightReport,
    output_path: Path,
) -> Path:
    """Write one deterministic MIL audit runbook preflight report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def _report(
    *,
    steps: list[MILAuditRunbookPreflightStep],
    record_id: str,
    runbook_id: str,
    replay_id: str,
    trace_id: str,
    runbook_persisted: bool,
) -> MILAuditRunbookPreflightReport:
    blockers = tuple(step.name for step in steps if not step.passed)
    return MILAuditRunbookPreflightReport(
        ready=not blockers,
        checked_at=_utc_now(),
        step_count=len(steps),
        steps=tuple(steps),
        blockers=blockers,
        record_id=record_id,
        runbook_id=runbook_id,
        replay_id=replay_id,
        trace_id=trace_id,
        runbook_persisted=runbook_persisted,
    )


def _validation_detail(errors: tuple[str, ...]) -> str:
    return "valid=true" if not errors else f"errors={list(errors)}"


def _bounded_detail(summary: str, exc: Exception) -> str:
    return f"{summary} ({type(exc).__name__})"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse MIL audit runbook preflight CLI arguments."""
    parser = argparse.ArgumentParser(description="Preflight MIL audit runbook workflow readiness.")
    parser.add_argument("--checklist", default=str(DEFAULT_CHECKLIST))
    parser.add_argument("--audit-store", required=True)
    parser.add_argument("--trace-store", required=True)
    parser.add_argument("--replay-store", required=True)
    parser.add_argument("--runbook-store", required=True)
    parser.add_argument("--record-id", required=True)
    parser.add_argument("--runbook-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for MIL audit runbook workflow preflight."""
    args = parse_args(argv)
    report = preflight_mil_audit_runbook_workflow(
        checklist_path=Path(args.checklist),
        audit_store_path=Path(args.audit_store),
        trace_store_path=Path(args.trace_store),
        replay_store_path=Path(args.replay_store),
        runbook_store_path=Path(args.runbook_store),
        record_id=args.record_id,
        runbook_id=args.runbook_id,
        name=args.name,
        description=args.description,
    )
    write_mil_audit_runbook_preflight_report(report, Path(args.output))
    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    elif report.ready:
        print("MIL AUDIT RUNBOOK WORKFLOW PREFLIGHT READY")
    else:
        print(f"MIL AUDIT RUNBOOK WORKFLOW PREFLIGHT BLOCKED blockers={list(report.blockers)}")
    return 0 if report.ready or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
