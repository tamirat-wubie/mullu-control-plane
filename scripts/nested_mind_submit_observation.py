"""Purpose: operator CLI for nested-mind record_observation proposal submission.
Governance scope: dry-run by default; live submit requires explicit operator flag.
Dependencies: nested-mind observation contracts, submitter bootstrap, local JSON files.
Invariants:
  - Default execution is dry-run and performs no network call.
  - Live submission requires --submit and all environment gates.
  - Optional --store writes only typed plan/report/witness evidence.
  - Output is a submission report JSON object only; bearer tokens are never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
MCOI_PATH = REPO_ROOT / "mcoi"
if str(MCOI_PATH) not in sys.path:
    sys.path.insert(0, str(MCOI_PATH))

from mcoi_runtime.app.nested_mind_integration import (  # noqa: E402
    NESTED_MIND_OBSERVATION_SUBMIT_ENABLED_ENV,
    mount_nested_mind_observation_submitter_from_env,
)
from mcoi_runtime.app._integration_paths import env_flag  # noqa: E402
from mcoi_runtime.contracts import (  # noqa: E402
    NestedMindObservationProposalPlan,
    NestedMindObservationProposalPlanStatus,
    NestedMindObservationSubmissionReport,
    NestedMindObservationSubmissionStatus,
    NestedMindProposalEvidence,
)
from mcoi_runtime.core.invariants import stable_identifier  # noqa: E402
from mcoi_runtime.persistence import NestedMindEvidenceStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Submit a nested-mind record_observation plan.")
    parser.add_argument("--plan", required=True, help="Path to NestedMindObservationProposalPlan JSON")
    parser.add_argument("--evidence", required=True, help="Path to NestedMindProposalEvidence JSON")
    parser.add_argument("--store", help="Optional append-only nested-mind evidence JSONL store")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Validate and print a dry-run report")
    mode.add_argument("--submit", action="store_true", help="Submit when environment gates are enabled")
    args = parser.parse_args(argv)

    plan = _load_plan(Path(args.plan))
    evidence = _load_evidence(Path(args.evidence))
    _validate_evidence_binding(plan, evidence)
    now = _utc_now()

    if not args.submit:
        report = _dry_run_report(plan, now)
        print(report.to_json())
        return 0

    if not env_flag(os.environ.get(NESTED_MIND_OBSERVATION_SUBMIT_ENABLED_ENV)):
        raise RuntimeError(f"{NESTED_MIND_OBSERVATION_SUBMIT_ENABLED_ENV} must be true for --submit")

    bootstrap = mount_nested_mind_observation_submitter_from_env(
        runtime_env=os.environ,
        clock=_utc_now,
    )
    if bootstrap.submitter is None:
        raise RuntimeError("nested-mind observation submitter was not mounted")
    outcome = bootstrap.submitter.submit_observation_plan_with_witness(plan, submit_enabled=True)
    report = outcome.report
    if args.store:
        _record_submit_evidence(Path(args.store), plan, report, outcome.commit_witness)
    print(report.to_json())
    return 0


def _load_json(path: Path) -> Mapping[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RuntimeError(f"failed to read {path}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"failed to parse JSON from {path}") from exc
    if not isinstance(raw, Mapping):
        raise RuntimeError(f"{path} must contain a JSON object")
    return raw


def _load_plan(path: Path) -> NestedMindObservationProposalPlan:
    raw = _load_json(path)
    return NestedMindObservationProposalPlan(
        plan_id=str(raw.get("plan_id", "")),
        proposal_evidence_id=str(raw.get("proposal_evidence_id", "")),
        mind_id=str(raw.get("mind_id", "")),
        method=str(raw.get("method", "")),
        target_route=str(raw.get("target_route", "")),
        proposal_payload=raw.get("proposal_payload") if isinstance(raw.get("proposal_payload"), Mapping) else {},
        payload_hash=str(raw.get("payload_hash", "")),
        mullu_receipt_hash=str(raw.get("mullu_receipt_hash", "")),
        authority_receipt_hash=str(raw.get("authority_receipt_hash", "")),
        status=NestedMindObservationProposalPlanStatus(str(raw.get("status", ""))),
        planned_at=str(raw.get("planned_at", "")),
        blockers=tuple(str(item) for item in raw.get("blockers", ()) or ()),
        metadata=raw.get("metadata") if isinstance(raw.get("metadata"), Mapping) else {},
    )


def _load_evidence(path: Path) -> NestedMindProposalEvidence:
    raw = _load_json(path)
    return NestedMindProposalEvidence(
        evidence_id=str(raw.get("evidence_id", "")),
        mind_id=str(raw.get("mind_id", "")),
        evidence_hash=str(raw.get("evidence_hash", "")),
        mullu_receipt_hash=str(raw.get("mullu_receipt_hash", "")),
        authority_receipt_hash=str(raw.get("authority_receipt_hash", "")),
        metadata=raw.get("metadata") if isinstance(raw.get("metadata"), Mapping) else {},
    )


def _validate_evidence_binding(
    plan: NestedMindObservationProposalPlan,
    evidence: NestedMindProposalEvidence,
) -> None:
    if plan.proposal_evidence_id != evidence.evidence_id:
        raise RuntimeError("plan proposal_evidence_id does not match evidence_id")
    if plan.mind_id != evidence.mind_id:
        raise RuntimeError("plan mind_id does not match evidence mind_id")
    if plan.mullu_receipt_hash != evidence.mullu_receipt_hash:
        raise RuntimeError("plan mullu_receipt_hash does not match evidence")
    if plan.authority_receipt_hash != evidence.authority_receipt_hash:
        raise RuntimeError("plan authority_receipt_hash does not match evidence")


def _dry_run_report(plan: NestedMindObservationProposalPlan, submitted_at: str) -> NestedMindObservationSubmissionReport:
    return NestedMindObservationSubmissionReport(
        report_id=stable_identifier(
            "nested-mind-observation-submission-dry-run",
            {"plan_id": plan.plan_id, "submitted_at": submitted_at},
        ),
        plan_id=plan.plan_id,
        mind_id=plan.mind_id,
        proposal_evidence_id=plan.proposal_evidence_id,
        payload_hash=plan.payload_hash,
        connector_result_id=None,
        connector_response_digest=None,
        response_envelope_hash=None,
        commit_witness_id=None,
        status=NestedMindObservationSubmissionStatus.DISABLED,
        submitted_at=submitted_at,
        blockers=("dry_run_no_network_call",),
    )


def _record_submit_evidence(
    store_path: Path,
    plan: NestedMindObservationProposalPlan,
    report: NestedMindObservationSubmissionReport,
    commit_witness: object | None,
) -> None:
    store = NestedMindEvidenceStore(store_path)
    store.record_plan(plan)
    store.record_submission_report(report)
    if report.status is NestedMindObservationSubmissionStatus.ACCEPTED:
        if commit_witness is None:
            raise RuntimeError("accepted submission cannot be stored without a commit witness")
        store.record_commit_witness(commit_witness)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
