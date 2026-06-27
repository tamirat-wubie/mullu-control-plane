"""Tests for sandbox-to-live promotion path validation.

Purpose: prove capabilities move through a reusable sandbox-to-live path
without live authority in Foundation Mode.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: scripts.validate_sandbox_to_live_promotion, capability passports,
gate template registry, and evidence passports.
Invariants: every capability has one ordered path; pilot, live, approved-live,
and production stages remain blocked until evidence and approval exist.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.app.sandbox_to_live_promotion import (
    STAGE_ORDER,
    SandboxToLivePromotionError,
    build_sandbox_to_live_promotion_paths,
)
from scripts.validate_sandbox_to_live_promotion import (
    DEFAULT_OUTPUT,
    DEFAULT_PROMOTION_PATHS,
    validate_sandbox_to_live_promotion,
    write_sandbox_to_live_promotion_validation,
)


def _default_payload() -> dict[str, object]:
    return json.loads(DEFAULT_PROMOTION_PATHS.read_text(encoding="utf-8"))


def _write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    promotion_path = tmp_path / "sandbox_to_live_promotion.json"
    promotion_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return promotion_path


def _promotion_paths(payload: dict[str, object]) -> list[dict[str, object]]:
    paths = payload["promotion_paths"]
    assert isinstance(paths, list)
    return paths


def _path_by_capability(payload: dict[str, object], capability_id: str) -> dict[str, object]:
    for path in _promotion_paths(payload):
        if path.get("capability_id") == capability_id:
            return path
    raise AssertionError(f"missing promotion path {capability_id}")


def test_sandbox_to_live_promotion_validates_and_writes(tmp_path: Path) -> None:
    validation = validate_sandbox_to_live_promotion()
    output_path = tmp_path / "sandbox-to-live-promotion-validation.json"

    written_path = write_sandbox_to_live_promotion_validation(validation, output_path)
    written_payload = json.loads(written_path.read_text(encoding="utf-8"))

    assert validation.ok is True
    assert validation.promotion_path_count == validation.capability_count
    assert validation.promotion_path_count > 20
    assert validation.blocked_path_count > 0
    assert written_payload["errors"] == []
    assert DEFAULT_OUTPUT.name == "sandbox_to_live_promotion_validation.json"


def test_sandbox_to_live_promotion_uses_canonical_stage_order() -> None:
    payload = build_sandbox_to_live_promotion_paths()
    first_path = _promotion_paths(payload)[0]
    stages = first_path["stages"]
    assert isinstance(stages, list)
    stage_ids = tuple(stage["stage_id"] for stage in stages)
    sequences = tuple(stage["sequence"] for stage in stages)

    assert tuple(payload["stage_order"]) == STAGE_ORDER
    assert stage_ids == STAGE_ORDER
    assert sequences == tuple(range(1, 9))
    assert first_path["stage_count"] == 8
    assert first_path["live_action_enabled"] is False


def test_sandbox_to_live_promotion_blocks_live_stages_in_foundation_mode() -> None:
    payload = build_sandbox_to_live_promotion_paths()
    payment = _path_by_capability(payload, "financial.send_payment")
    stages = {stage["stage_id"]: stage for stage in payment["stages"]}

    assert payment["current_stage"] == "operator_review"
    assert payment["live_action_enabled"] is False
    assert stages["pilot"]["stage_status"] == "blocked"
    assert stages["limited_live"]["stage_status"] == "blocked"
    assert stages["approved_live"]["stage_status"] == "blocked"
    assert stages["production"]["stage_status"] == "blocked"
    assert "operator_pilot_authorization" in stages["pilot"]["missing_controls"]


def test_sandbox_to_live_promotion_keeps_dry_run_before_operator_review() -> None:
    payload = build_sandbox_to_live_promotion_paths()
    email = _path_by_capability(payload, "email.draft")
    stages = {stage["stage_id"]: stage for stage in email["stages"]}

    assert STAGE_ORDER.index("dry_run") < STAGE_ORDER.index("operator_review")
    assert email["current_stage"] in {"local_demo", "dry_run", "operator_review"}
    assert stages["pilot"]["stage_status"] == "blocked"
    assert email["promotion_path_is_not_execution_authority"] is True


def test_sandbox_to_live_promotion_rejects_authority_overclaim(tmp_path: Path) -> None:
    payload = _default_payload()
    payload["promotion_path_set_is_not_execution_authority"] = False
    payload["live_execution_enabled"] = True
    path = _path_by_capability(payload, "email.draft")
    path["promotion_path_is_not_execution_authority"] = False
    path["live_action_enabled"] = True

    validation = validate_sandbox_to_live_promotion(promotion_paths_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "promotion_path_set_is_not_execution_authority must be true" in serialized_errors
    assert "live_execution_enabled must be false" in serialized_errors
    assert "promotion_path_is_not_execution_authority must be true" in serialized_errors
    assert "live_action_enabled must be false" in serialized_errors


def test_sandbox_to_live_promotion_rejects_stage_order_drift(tmp_path: Path) -> None:
    payload = _default_payload()
    path = _promotion_paths(payload)[0]
    stages = path["stages"]
    assert isinstance(stages, list)
    stages[0], stages[1] = stages[1], stages[0]

    validation = validate_sandbox_to_live_promotion(promotion_paths_path=_write_payload(tmp_path, payload))
    serialized_errors = json.dumps(validation.errors, sort_keys=True)

    assert validation.ok is False
    assert "stages must preserve canonical order" in serialized_errors
    assert "example does not match runtime projection" in serialized_errors


def test_sandbox_to_live_promotion_rejects_missing_evidence_packet() -> None:
    passport_set = {
        "passport_set_id": "demo.passports",
        "passports": [
            {
                "capability_id": "demo.read",
                "capability_name": "Demo Read",
                "family": "demo",
                "current_unlock_level": "C2",
                "operator_status": "Live action disabled",
                "certification_status": "certified",
                "next_unlock_step": "add sandbox evidence",
            }
        ],
    }
    gate_registry = {"registry_id": "demo.gates", "templates": [{"gate_id": "gate.uao.admission"}]}
    evidence_set = {"evidence_passport_set_id": "demo.evidence", "evidence_passports": []}

    with pytest.raises(SandboxToLivePromotionError, match="non-empty evidence passports"):
        build_sandbox_to_live_promotion_paths(
            passports=passport_set,
            gate_registry=gate_registry,
            evidence_passports=evidence_set,
        )
