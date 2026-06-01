"""Purpose: build a read-only SDLC dashboard summary from governed artifacts.
Governance scope: SDLC change, stage, blocker, evidence, receipt, and closure
read-model projection.
Dependencies: Python standard library and canonical SDLC example artifacts.
Invariants:
  - The dashboard builder is read-only and deterministic.
  - Every stage keeps its UAO, causal trace, and receipt references visible.
  - Blockers are explicit records, never implicit status strings.
  - Closure does not mutate or certify artifacts; it only summarizes them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SDLC_EXAMPLE_DIR = WORKSPACE_ROOT / "examples" / "sdlc"
READ_MODEL_VERSION = "sdlc_dashboard.v1"


@dataclass(frozen=True, slots=True)
class SdlcStageSpec:
    """Canonical dashboard binding for one SDLC stage artifact."""

    order: int
    key: str
    label: str
    example_name: str
    id_field: str


STAGE_SPECS: tuple[SdlcStageSpec, ...] = (
    SdlcStageSpec(1, "change_request", "Change request", "change_request_uao_validator.json", "request_id"),
    SdlcStageSpec(2, "requirement", "Requirement", "requirement_uao_validator.json", "requirement_id"),
    SdlcStageSpec(3, "design_decision", "Design decision", "design_uao_validator.json", "design_id"),
    SdlcStageSpec(4, "work_plan", "Work plan", "work_plan_uao_validator.json", "plan_id"),
    SdlcStageSpec(5, "implementation_receipt", "Implementation receipt", "implementation_uao_validator.json", "implementation_id"),
    SdlcStageSpec(6, "transition_receipt", "Transition receipt", "transition_uao_validator.json", "transition_id"),
    SdlcStageSpec(7, "verification_receipt", "Verification receipt", "verification_uao_validator.json", "verification_id"),
    SdlcStageSpec(8, "security_review", "Security review", "security_review_uao_validator.json", "security_review_id"),
    SdlcStageSpec(9, "release_candidate", "Release candidate", "release_candidate_uao_validator.json", "release_id"),
    SdlcStageSpec(10, "deployment_candidate", "Deployment candidate", "deployment_candidate_uao_validator.json", "deployment_id"),
    SdlcStageSpec(11, "closure_receipt", "Closure receipt", "closure_uao_validator.json", "closure_id"),
)
STAGE_SPEC_BY_KEY = {spec.key: spec for spec in STAGE_SPECS}
REQUIRED_GATE_FIELDS = ("uao_ref", "causal_decision_trace_ref", "receipt_ref")


class SdlcDashboardError(ValueError):
    """Raised when an SDLC dashboard input cannot be projected."""


def load_sdlc_dashboard_records(
    example_dir: Path = DEFAULT_SDLC_EXAMPLE_DIR,
) -> dict[str, dict[str, Any]]:
    """Load canonical SDLC records used by the dashboard summary."""

    records: dict[str, dict[str, Any]] = {}
    for spec in STAGE_SPECS:
        artifact_path = example_dir / spec.example_name
        if not artifact_path.exists():
            raise FileNotFoundError(f"missing SDLC dashboard artifact: {artifact_path}")
        if not artifact_path.is_file():
            raise IsADirectoryError(f"SDLC dashboard artifact path is not a file: {artifact_path}")
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SdlcDashboardError(f"SDLC dashboard artifact must be a JSON object: {spec.example_name}")
        records[spec.key] = payload
    return records


def build_sdlc_dashboard_summary(
    records: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the read-only SDLC dashboard summary."""

    loaded_records = load_sdlc_dashboard_records() if records is None else records
    _validate_record_set(loaded_records)
    change = loaded_records["change_request"]
    closure = loaded_records["closure_receipt"]
    stages = [
        _build_stage_summary(
            spec=spec,
            record=loaded_records[spec.key],
            closure=closure,
        )
        for spec in STAGE_SPECS
    ]
    blockers = _unique_blockers(stage["blockers"] for stage in stages)
    evidence_refs = _unique_text(
        ref for stage in stages for ref in stage["evidence_refs"]
    )
    receipt_refs = _unique_text(
        [
            *(stage["receipt_ref"] for stage in stages if stage["receipt_ref"]),
            *_text_list(closure.get("receipts")),
        ]
    )
    uao_refs = _unique_text(
        [
            *(stage["uao_ref"] for stage in stages if stage["uao_ref"]),
            *_text_list(closure.get("uao_refs")),
        ]
    )
    causal_trace_refs = _unique_text(
        [
            *(
                stage["causal_decision_trace_ref"]
                for stage in stages
                if stage["causal_decision_trace_ref"]
            ),
            *_text_list(closure.get("causal_decision_trace_refs")),
        ]
    )
    return {
        "dashboard_id": f"sdlc-dashboard:{change.get('request_id', '')}",
        "read_model_version": READ_MODEL_VERSION,
        "read_only": True,
        "governed": True,
        "change": _change_summary(change),
        "stage_count": len(stages),
        "stages": stages,
        "blocker_count": len(blockers),
        "blockers": blockers,
        "evidence_count": len(evidence_refs),
        "evidence_refs": evidence_refs,
        "receipt_count": len(receipt_refs),
        "receipt_refs": receipt_refs,
        "uao_ref_count": len(uao_refs),
        "uao_refs": uao_refs,
        "causal_decision_trace_ref_count": len(causal_trace_refs),
        "causal_decision_trace_refs": causal_trace_refs,
        "closure": _closure_summary(closure),
    }


def _validate_record_set(records: Mapping[str, Mapping[str, Any]]) -> None:
    missing = [spec.key for spec in STAGE_SPECS if spec.key not in records]
    if missing:
        raise SdlcDashboardError(f"missing SDLC dashboard record(s): {', '.join(missing)}")
    non_objects = [
        spec.key for spec in STAGE_SPECS if not isinstance(records[spec.key], Mapping)
    ]
    if non_objects:
        raise SdlcDashboardError(f"SDLC dashboard record(s) must be objects: {', '.join(non_objects)}")


def _change_summary(change: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "request_id": _text(change.get("request_id")),
        "tenant_id": _text(change.get("tenant_id")),
        "actor_id": _text(change.get("actor_id")),
        "title": _text(change.get("title")),
        "summary": _text(change.get("summary")),
        "change_type": _text(change.get("change_type")),
        "risk_hint": _text(change.get("risk_hint")),
        "target_surfaces": _text_list(change.get("target_surfaces")),
        "created_at": _text(change.get("created_at")),
    }


def _build_stage_summary(
    *,
    spec: SdlcStageSpec,
    record: Mapping[str, Any],
    closure: Mapping[str, Any],
) -> dict[str, Any]:
    blockers = _stage_blockers(spec.key, record)
    status = _stage_status(spec.key, record, blockers)
    receipt_ref = _text(record.get("receipt_ref"))
    closure_receipts = set(_text_list(closure.get("receipts")))
    return {
        "stage_order": spec.order,
        "stage_key": spec.key,
        "stage_label": spec.label,
        "artifact_id": _text(record.get(spec.id_field)),
        "artifact_ref": f"examples/sdlc/{spec.example_name}",
        "status": status,
        "summary": _stage_summary_text(spec.key, record),
        "blockers": blockers,
        "blocker_count": len(blockers),
        "evidence_refs": _stage_evidence_refs(spec.key, record),
        "receipt_ref": receipt_ref,
        "uao_ref": _text(record.get("uao_ref")),
        "causal_decision_trace_ref": _text(record.get("causal_decision_trace_ref")),
        "closed_by": _text(closure.get("closure_id")) if receipt_ref in closure_receipts else "",
    }


def _stage_status(
    stage_key: str,
    record: Mapping[str, Any],
    blockers: list[dict[str, str]],
) -> str:
    if stage_key == "closure_receipt":
        return _text(record.get("terminal_state")) or "unknown"
    if blockers:
        return "blocked"
    if any(not _text(record.get(field_name)) for field_name in REQUIRED_GATE_FIELDS):
        return "blocked"
    if stage_key == "transition_receipt" and record.get("decision") != "allowed":
        return "blocked"
    if stage_key == "verification_receipt" and int(record.get("tests_failed", 0)) != 0:
        return "blocked"
    if stage_key == "security_review" and record.get("release_blocked") is True:
        return "blocked"
    return "passed"


def _stage_summary_text(stage_key: str, record: Mapping[str, Any]) -> str:
    if stage_key == "change_request":
        return _text(record.get("title"))
    if stage_key == "requirement":
        return _text(record.get("problem_statement"))
    if stage_key == "design_decision":
        return _text(record.get("architecture_summary"))
    if stage_key == "work_plan":
        return f"{len(_mapping_list(record.get('steps')))} ordered work step(s)"
    if stage_key == "implementation_receipt":
        return f"{len(_mapping_list(record.get('changed_files')))} changed file(s)"
    if stage_key == "transition_receipt":
        return f"{_text(record.get('from_state'))} -> {_text(record.get('to_state'))}: {_text(record.get('decision'))}"
    if stage_key == "verification_receipt":
        return f"{record.get('tests_passed', 0)} check(s) passed, {record.get('tests_failed', 0)} failed"
    if stage_key == "security_review":
        return f"residual risk: {_text(record.get('residual_risk'))}"
    if stage_key == "release_candidate":
        return f"{_text(record.get('version'))}: {_text(record.get('deployment_status'))}"
    if stage_key == "deployment_candidate":
        witness = record.get("deployment_witness")
        witness_status = witness.get("status") if isinstance(witness, Mapping) else ""
        return f"{_text(record.get('environment'))}: {_text(witness_status)}"
    if stage_key == "closure_receipt":
        return f"{_text(record.get('terminal_state'))}: {_text(record.get('outcome'))}"
    return stage_key


def _stage_evidence_refs(stage_key: str, record: Mapping[str, Any]) -> list[str]:
    if stage_key == "change_request":
        return _text_list(record.get("evidence_refs"))
    if stage_key == "requirement":
        return _unique_text(
            [*_text_list(record.get("acceptance_tests")), *_text_list(record.get("evidence_required"))]
        )
    if stage_key == "design_decision":
        return _unique_text(
            [
                *_text_list(record.get("schema_changes")),
                *_text_list(record.get("validator_changes")),
                *_text_list(record.get("test_plan")),
            ]
        )
    if stage_key == "work_plan":
        return _unique_text(
            [
                *_text_list(record.get("expected_artifacts")),
                *_text_list(record.get("required_validators")),
                *_text_list(record.get("required_tests")),
            ]
        )
    if stage_key == "implementation_receipt":
        return _unique_text(
            [
                *(item["path"] for item in _mapping_list(record.get("changed_files")) if isinstance(item.get("path"), str)),
                *_text_list(record.get("test_changes")),
                *_text_list(record.get("documentation_changes")),
                *_text_list(record.get("schema_changes")),
                *_text_list(record.get("validator_changes")),
                *_text_list(record.get("rollback_refs")),
            ]
        )
    if stage_key == "transition_receipt":
        return _unique_text(
            [
                *_text_list(record.get("required_evidence_refs")),
                *_text_list(record.get("required_receipt_refs")),
            ]
        )
    if stage_key == "verification_receipt":
        return _unique_text(
            [
                *_text_list(record.get("coverage_refs")),
                *(
                    _text(item.get("output_ref"))
                    for item in _mapping_list(record.get("validator_outputs"))
                    if item.get("output_ref")
                ),
            ]
        )
    if stage_key == "security_review":
        return _unique_text(
            [
                *(
                    _text(item.get("evidence_ref"))
                    for item in _mapping_list(record.get("required_checks"))
                    if item.get("evidence_ref")
                ),
                *_text_list(record.get("security_receipts")),
            ]
        )
    if stage_key == "release_candidate":
        return _unique_text(
            [
                *_text_list(record.get("change_set")),
                _text(record.get("release_receipt")),
                _text(record.get("rollback_plan")),
            ]
        )
    if stage_key == "deployment_candidate":
        return _deployment_evidence_refs(record)
    if stage_key == "closure_receipt":
        return _unique_text(
            [
                *_text_list(record.get("receipts")),
                *_text_list(record.get("uao_refs")),
                *_text_list(record.get("causal_decision_trace_refs")),
            ]
        )
    return []


def _stage_blockers(stage_key: str, record: Mapping[str, Any]) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    for field_name in REQUIRED_GATE_FIELDS:
        if stage_key != "closure_receipt" and not _text(record.get(field_name)):
            blockers.append(_blocker(stage_key, f"missing_{field_name}", "required gate reference is missing"))
    if stage_key == "transition_receipt":
        for item in _mapping_list(record.get("blockers")):
            blockers.append(_blocker(stage_key, _text(item.get("blocker_id")) or "transition_blocker", _text(item.get("reason"))))
        if record.get("decision") != "allowed":
            blockers.append(_blocker(stage_key, "transition_not_allowed", _text(record.get("transition_reason"))))
    elif stage_key == "verification_receipt":
        for item in _mapping_list(record.get("commands")):
            if item.get("status") != "passed":
                blockers.append(_blocker(stage_key, _text(item.get("name")), "validator command did not pass"))
        for failed_check in _text_list(record.get("failed_checks")):
            blockers.append(_blocker(stage_key, failed_check, "failed verification check"))
    elif stage_key == "security_review":
        for item in _mapping_list(record.get("required_checks")):
            if item.get("status") != "passed":
                blockers.append(_blocker(stage_key, _text(item.get("check")), "security check did not pass"))
        for finding in _mapping_list(record.get("findings")):
            if finding.get("status") == "open":
                blockers.append(_blocker(stage_key, _text(finding.get("finding_id")), _text(finding.get("description"))))
        if record.get("release_blocked") is True:
            blockers.append(_blocker(stage_key, "release_blocked", "security review blocks release"))
    elif stage_key == "release_candidate":
        blockers.extend(_release_blockers(record))
    elif stage_key == "deployment_candidate":
        blockers.extend(_deployment_blockers(record))
    elif stage_key == "closure_receipt":
        for item in _mapping_list(record.get("known_remaining_blockers")):
            blockers.append(
                _blocker(
                    stage_key,
                    _text(item.get("blocker_id")),
                    _text(item.get("reason")),
                    status=_text(item.get("status")) or "open",
                )
            )
    return blockers


def _release_blockers(record: Mapping[str, Any]) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    security_status = record.get("security_status")
    if record.get("tests_passed") is not True:
        blockers.append(_blocker("release_candidate", "tests_not_passing", "release tests are not passing"))
    if isinstance(security_status, Mapping):
        if int(security_status.get("critical_open", 0)) > 0:
            blockers.append(_blocker("release_candidate", "critical_security_open", "critical security finding is open"))
        if int(security_status.get("high_open", 0)) > 0:
            blockers.append(_blocker("release_candidate", "high_security_open", "high security finding is open"))
        if security_status.get("status") == "blocked":
            blockers.append(_blocker("release_candidate", "security_status_blocked", "security status blocks release"))
    if record.get("evidence_bound_claims") is not True:
        blockers.append(_blocker("release_candidate", "evidence_bound_claims_missing", "release claims are not evidence-bound"))
    return blockers


def _deployment_blockers(record: Mapping[str, Any]) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []
    if record.get("rollback_ready") is not True:
        blockers.append(_blocker("deployment_candidate", "rollback_not_ready", "deployment rollback is not ready"))
    if record.get("public_production_claim") is not True:
        return blockers
    required_statuses = {
        "deployment_witness": {"published"},
        "public_health": {"declared", "passing"},
        "runtime_conformance": {"passing"},
        "proof_verify_endpoint": {"reachable", "passing"},
        "audit_verify_endpoint": {"reachable", "passing"},
    }
    for field_name, allowed_statuses in required_statuses.items():
        probe = record.get(field_name)
        status = probe.get("status") if isinstance(probe, Mapping) else None
        if status not in allowed_statuses:
            blockers.append(_blocker("deployment_candidate", field_name, f"{field_name} evidence is not production-ready"))
    return blockers


def _deployment_evidence_refs(record: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for field_name in (
        "health_check",
        "runtime_conformance",
        "deployment_witness",
        "public_health",
        "proof_verify_endpoint",
        "audit_verify_endpoint",
    ):
        probe = record.get(field_name)
        if isinstance(probe, Mapping) and isinstance(probe.get("ref"), str):
            refs.append(probe["ref"])
    if isinstance(record.get("rollback_command"), str):
        refs.append(record["rollback_command"])
    return _unique_text(refs)


def _closure_summary(closure: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "closure_id": _text(closure.get("closure_id")),
        "change_id": _text(closure.get("change_id")),
        "terminal_state": _text(closure.get("terminal_state")),
        "outcome": _text(closure.get("outcome")),
        "closed_at": _text(closure.get("closed_at")),
        "next_action": _text(closure.get("next_action")),
        "receipt_count": len(_text_list(closure.get("receipts"))),
        "known_remaining_blocker_count": len(_mapping_list(closure.get("known_remaining_blockers"))),
        "learning_notes": _text_list(closure.get("learning_notes")),
    }


def _blocker(stage_key: str, blocker_id: str, reason: str, *, status: str = "open") -> dict[str, str]:
    return {
        "stage_key": stage_key,
        "blocker_id": blocker_id or f"{stage_key}_blocker",
        "status": status or "open",
        "reason": reason or "blocked without detail",
    }


def _unique_blockers(blocker_groups: Any) -> list[dict[str, str]]:
    observed: set[tuple[str, str, str, str]] = set()
    blockers: list[dict[str, str]] = []
    for group in blocker_groups:
        for blocker in group:
            if not isinstance(blocker, Mapping):
                continue
            key = (
                _text(blocker.get("stage_key")),
                _text(blocker.get("blocker_id")),
                _text(blocker.get("status")),
                _text(blocker.get("reason")),
            )
            if key in observed:
                continue
            observed.add(key)
            blockers.append(
                {
                    "stage_key": key[0],
                    "blocker_id": key[1],
                    "status": key[2],
                    "reason": key[3],
                }
            )
    return blockers


def _unique_text(values: Any) -> list[str]:
    observed: set[str] = set()
    result: list[str] = []
    for value in values:
        text = _text(value)
        if not text or text in observed:
            continue
        observed.add(text)
        result.append(text)
    return result


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _mapping_list(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, Mapping)]
