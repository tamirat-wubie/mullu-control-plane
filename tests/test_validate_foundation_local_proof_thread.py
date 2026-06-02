"""Tests for the Foundation Mode local proof-thread validator.

Purpose: prove the first local proof-thread descriptor remains local-only,
approval-gated, acyclic, and rollback-bound.
Governance scope: Foundation Mode, workflow descriptor topology, and external
effect blocking.
Dependencies: scripts.validate_foundation_local_proof_thread.
Invariants: descriptor validation is read-only and rejects cycles, missing
stages, dangling bindings, and blocked public/external effect terms.
"""

from __future__ import annotations

from copy import deepcopy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_foundation_local_proof_thread import (  # noqa: E402
    DEFAULT_DESCRIPTOR_PATH,
    EXPECTED_WORKFLOW_ID,
    load_json_object,
    validate_descriptor,
    validate_foundation_local_proof_thread,
)


def test_foundation_local_proof_thread_artifacts_pass() -> None:
    assert validate_foundation_local_proof_thread() == []


def test_descriptor_has_expected_identity() -> None:
    descriptor = load_json_object(DEFAULT_DESCRIPTOR_PATH, "descriptor")

    assert descriptor["workflow_id"] == EXPECTED_WORKFLOW_ID
    assert descriptor["name"] == "Foundation Local Proof Thread"
    assert descriptor["stages"][3]["stage_type"] == "approval_gate"
    assert descriptor["stages"][-2]["stage_id"] == "stage_record_rollback_note"


def test_descriptor_rejects_missing_required_stage() -> None:
    descriptor = load_json_object(DEFAULT_DESCRIPTOR_PATH, "descriptor")
    candidate = deepcopy(descriptor)
    candidate["stages"] = [stage for stage in candidate["stages"] if stage["stage_id"] != "stage_local_approval"]

    findings = validate_descriptor(candidate)

    assert findings
    assert any(finding.rule_id == "workflow_stage_order_invalid" for finding in findings)
    assert any(finding.rule_id == "workflow_stage_missing" for finding in findings)


def test_descriptor_rejects_cycle() -> None:
    descriptor = load_json_object(DEFAULT_DESCRIPTOR_PATH, "descriptor")
    candidate = deepcopy(descriptor)
    candidate["stages"][0]["predecessors"] = ["stage_close_receipt"]

    findings = validate_descriptor(candidate)

    assert findings
    assert any(finding.rule_id == "workflow_cycle_detected" for finding in findings)


def test_descriptor_rejects_blocked_external_effect_term() -> None:
    descriptor = load_json_object(DEFAULT_DESCRIPTOR_PATH, "descriptor")
    candidate = deepcopy(descriptor)
    candidate["description"] = "Call https://api.mullusi.com for a live endpoint."

    findings = validate_descriptor(candidate)

    assert findings
    assert any(finding.rule_id == "workflow_forbidden_external_term" for finding in findings)
