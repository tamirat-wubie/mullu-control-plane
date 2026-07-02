"""Tests for capability closure runner validation.

Purpose: prove capability closure artifacts have schema-backed validation and
fail closed on authority or receipt drift.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_capability_closure_runner and checked example
closure artifacts.
Invariants: validator rejects execution authority overclaims, ref drift, and
closure overclaims.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
_MCOI_ROOT = _ROOT / "mcoi"
for import_root in (_ROOT, _MCOI_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from capability_closure.runner import (  # noqa: E402
    EXAMPLE_ARTIFACT_FILENAMES,
    build_capability_closure_artifacts,
    write_capability_closure_artifacts,
)
from scripts.validate_capability_closure_runner import (  # noqa: E402
    DEFAULT_GENERATED_ARTIFACTS,
    DEFAULT_OUTPUT,
    main,
    parse_args,
    resolve_artifact_paths,
    validate_capability_closure_runner,
    write_capability_closure_runner_validation,
)


def test_capability_closure_runner_examples_validate(tmp_path: Path) -> None:
    validation = validate_capability_closure_runner()
    written = write_capability_closure_runner_validation(validation, tmp_path / "validation.json")
    payload = json.loads(written.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.errors == ()
    assert validation.selected_capability_id == "email.send.with_approval"
    assert validation.selected_debt_id == "email.send.with_approval.approval.missing_governed_approval"
    assert validation.missing_ref_count == 6
    assert validation.status == "AwaitingEvidence"
    assert payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "capability_closure_runner_validation.json"


def test_capability_closure_runner_validator_rejects_authority_overclaim(tmp_path: Path) -> None:
    paths = _write_artifacts(tmp_path)
    plan = json.loads(paths["capability_closure_plan"].read_text(encoding="utf-8"))
    receipt = json.loads(paths["closure_receipt"].read_text(encoding="utf-8"))
    plan["plan_is_not_execution_authority"] = False
    plan["live_execution_enabled"] = True
    receipt["effect_boundary"]["pull_request_created"] = True
    receipt["closure_claim"] = "closed"
    paths["capability_closure_plan"].write_text(json.dumps(plan), encoding="utf-8")
    paths["closure_receipt"].write_text(json.dumps(receipt), encoding="utf-8")

    validation = validate_capability_closure_runner(
        artifact_paths=paths,
        compare_runtime_projection=False,
    )
    serialized = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "plan_is_not_execution_authority must be true" in serialized
    assert "live_execution_enabled must be false" in serialized
    assert "pull_request_created" in serialized
    assert "closure_claim must be not_closed" in serialized


def test_capability_closure_runner_validator_rejects_missing_ref_drift(tmp_path: Path) -> None:
    paths = _write_artifacts(tmp_path)
    refs = json.loads(paths["missing_evidence_refs"].read_text(encoding="utf-8"))
    approval = json.loads(paths["next_approval_action"].read_text(encoding="utf-8"))
    refs["selected_missing_refs"] = ["approval_decision_receipt"]
    refs["selected_missing_ref_count"] = 1
    approval["execution_after_approval_allowed"] = True
    paths["missing_evidence_refs"].write_text(json.dumps(refs), encoding="utf-8")
    paths["next_approval_action"].write_text(json.dumps(approval), encoding="utf-8")

    validation = validate_capability_closure_runner(
        artifact_paths=paths,
        compare_runtime_projection=False,
    )
    serialized = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "selected_missing_refs must match selected debt item" in serialized
    assert "selected_missing_ref_count must match selected refs" in serialized
    assert "execution_after_approval_allowed" in serialized


def test_capability_closure_runner_validator_cli_writes_report(
    tmp_path: Path,
    capsys,
) -> None:
    paths = _write_artifacts(tmp_path)
    output_path = tmp_path / "capability_closure_runner_validation.json"

    exit_code = main(
        [
            "--plan",
            str(paths["capability_closure_plan"]),
            "--missing-refs",
            str(paths["missing_evidence_refs"]),
            "--next-approval",
            str(paths["next_approval_action"]),
            "--receipt",
            str(paths["closure_receipt"]),
            "--output",
            str(output_path),
            "--generated-names",
            "--skip-runtime-compare",
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    stdout_payload = json.loads(captured.out)
    report = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert stdout_payload["ok"] is True
    assert report["ok"] is True
    assert report["selected_capability_id"] == "email.send.with_approval"
    assert report["artifact_paths"]["closure_receipt"] == "closure_receipt.json"


def test_capability_closure_runner_validator_resolves_generated_defaults() -> None:
    args = parse_args(["--generated-names"])
    paths = resolve_artifact_paths(args)
    explicit_args = parse_args(["--generated-names", "--plan", "custom_plan.json"])
    explicit_paths = resolve_artifact_paths(explicit_args)

    assert paths["capability_closure_plan"] == DEFAULT_GENERATED_ARTIFACTS["capability_closure_plan"]
    assert paths["missing_evidence_refs"] == DEFAULT_GENERATED_ARTIFACTS["missing_evidence_refs"]
    assert paths["next_approval_action"] == DEFAULT_GENERATED_ARTIFACTS["next_approval_action"]
    assert paths["closure_receipt"] == DEFAULT_GENERATED_ARTIFACTS["closure_receipt"]
    assert explicit_paths["capability_closure_plan"] == Path("custom_plan.json")
    assert explicit_paths["closure_receipt"] == DEFAULT_GENERATED_ARTIFACTS["closure_receipt"]


def _write_artifacts(tmp_path: Path) -> dict[str, Path]:
    artifacts = build_capability_closure_artifacts()
    return write_capability_closure_artifacts(artifacts, tmp_path)
