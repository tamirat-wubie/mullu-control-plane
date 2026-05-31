"""Tests for the nested-mind observation plan builder CLI.

Purpose: verify offline construction of plan/evidence JSON for the guarded
record_observation submit path.
Governance scope: operator preparation only; no network or write submission.
Dependencies: nested_mind_build_observation_plan.py and observation contracts.
Invariants: generated plan binds to evidence; sensitive fields are rejected.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from mcoi_runtime.contracts import (
    NestedMindObservationProposalPlan,
    NestedMindObservationProposalPlanStatus,
    NestedMindProposalEvidence,
    stable_json_hash,
)

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "nested_mind_build_observation_plan.py"


def _module():
    spec = importlib.util.spec_from_file_location("nested_mind_build_observation_plan", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_builder_creates_bound_plan_and_evidence(tmp_path, capsys) -> None:
    module = _module()
    observation_path = tmp_path / "observation.json"
    plan_path = tmp_path / "plan.json"
    evidence_path = tmp_path / "evidence.json"
    observation = {"observation_id": "obs-1", "source": "operator", "value": {"status": "ok"}}
    observation_path.write_text(json.dumps(observation), encoding="utf-8")

    exit_code = module.main(
        [
            "--mind-id",
            "root",
            "--observation-id",
            "obs-1",
            "--observation",
            str(observation_path),
            "--mullu-receipt-hash",
            "mullu-receipt-hash-1",
            "--authority-receipt-hash",
            "authority-receipt-hash-1",
            "--plan-out",
            str(plan_path),
            "--evidence-out",
            str(evidence_path),
            "--planned-at",
            "2026-05-31T00:00:00+00:00",
        ]
    )
    output = json.loads(capsys.readouterr().out)
    plan = _load_plan_json(plan_path)
    evidence = NestedMindProposalEvidence(**json.loads(evidence_path.read_text(encoding="utf-8")))

    assert exit_code == 0
    assert output["status"] == "planned"
    assert plan.proposal_evidence_id == evidence.evidence_id
    assert plan.target_route == "/minds/root/proposals"
    assert plan.proposal_payload["kind"] == "record_observation"
    assert plan.proposal_payload["metadata"]["observation_hash"] == stable_json_hash(observation)
    assert plan.payload_hash == stable_json_hash(plan.proposal_payload)
    assert evidence.metadata["observation_hash"] == stable_json_hash(observation)


def test_builder_rejects_sensitive_observation_fields(tmp_path) -> None:
    module = _module()
    observation_path = tmp_path / "observation.json"
    observation_path.write_text(json.dumps({"authorization": "Bearer secret"}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="forbidden sensitive field"):
        module.main(
            [
                "--mind-id",
                "root",
                "--observation-id",
                "obs-1",
                "--observation",
                str(observation_path),
                "--mullu-receipt-hash",
                "mullu-receipt-hash-1",
                "--authority-receipt-hash",
                "authority-receipt-hash-1",
                "--plan-out",
                str(tmp_path / "plan.json"),
                "--evidence-out",
                str(tmp_path / "evidence.json"),
                "--planned-at",
                "2026-05-31T00:00:00+00:00",
            ]
        )


def test_builder_rejects_unsafe_observation_id_before_output(tmp_path, capsys) -> None:
    module = _module()
    observation_path = tmp_path / "observation.json"
    observation_path.write_text(json.dumps({"observation_id": "obs-1"}), encoding="utf-8")

    for index, observation_id in enumerate(("../x", "x/y", "x\\y", "x?y", "x#y", "%2e%2e")):
        with pytest.raises(ValueError, match="observation_id"):
            module.main(
                [
                    "--mind-id",
                    "root",
                    "--observation-id",
                    observation_id,
                    "--observation",
                    str(observation_path),
                    "--mullu-receipt-hash",
                    "mullu-receipt-hash-1",
                    "--authority-receipt-hash",
                    "authority-receipt-hash-1",
                    "--plan-out",
                    str(tmp_path / f"unsafe-{index}-plan.json"),
                    "--evidence-out",
                    str(tmp_path / f"unsafe-{index}-evidence.json"),
                    "--planned-at",
                    "2026-05-31T00:00:00+00:00",
                ]
            )

    assert capsys.readouterr().out == ""


def test_builder_rejects_non_finite_observation_json_before_output(tmp_path, capsys) -> None:
    module = _module()
    observation_path = tmp_path / "observation.json"
    observation_path.write_text('{"observation_id": "obs-1", "score": NaN}', encoding="utf-8")

    with pytest.raises(RuntimeError, match="failed to parse strict JSON"):
        module.main(
            [
                "--mind-id",
                "root",
                "--observation-id",
                "obs-1",
                "--observation",
                str(observation_path),
                "--mullu-receipt-hash",
                "mullu-receipt-hash-1",
                "--authority-receipt-hash",
                "authority-receipt-hash-1",
                "--plan-out",
                str(tmp_path / "plan.json"),
                "--evidence-out",
                str(tmp_path / "evidence.json"),
                "--planned-at",
                "2026-05-31T00:00:00+00:00",
            ]
        )
    assert capsys.readouterr().out == ""
    assert not (tmp_path / "plan.json").exists()
    assert not (tmp_path / "evidence.json").exists()


def test_builder_fixed_timestamp_produces_stable_plan_id(tmp_path, capsys) -> None:
    module = _module()
    observation_path = tmp_path / "observation.json"
    observation_path.write_text(json.dumps({"observation_id": "obs-1"}), encoding="utf-8")
    args = [
        "--mind-id",
        "root",
        "--observation-id",
        "obs-1",
        "--observation",
        str(observation_path),
        "--mullu-receipt-hash",
        "mullu-receipt-hash-1",
        "--authority-receipt-hash",
        "authority-receipt-hash-1",
        "--planned-at",
        "2026-05-31T00:00:00+00:00",
    ]

    module.main([*args, "--plan-out", str(tmp_path / "plan-a.json"), "--evidence-out", str(tmp_path / "evidence-a.json")])
    first = json.loads(capsys.readouterr().out)
    module.main([*args, "--plan-out", str(tmp_path / "plan-b.json"), "--evidence-out", str(tmp_path / "evidence-b.json")])
    second = json.loads(capsys.readouterr().out)

    assert first["plan_id"] == second["plan_id"]
    assert first["payload_hash"] == second["payload_hash"]


def _load_plan_json(path: Path) -> NestedMindObservationProposalPlan:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return NestedMindObservationProposalPlan(
        plan_id=raw["plan_id"],
        proposal_evidence_id=raw["proposal_evidence_id"],
        mind_id=raw["mind_id"],
        method=raw["method"],
        target_route=raw["target_route"],
        proposal_payload=raw["proposal_payload"],
        payload_hash=raw["payload_hash"],
        mullu_receipt_hash=raw["mullu_receipt_hash"],
        authority_receipt_hash=raw["authority_receipt_hash"],
        status=NestedMindObservationProposalPlanStatus(raw["status"]),
        planned_at=raw["planned_at"],
        blockers=tuple(raw.get("blockers", ())),
        metadata=raw.get("metadata", {}),
    )
