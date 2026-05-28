"""Tests for governed swarm staging evidence bundle validation.

Purpose: ensure staging activation evidence cannot close from mismatched preflight
and witness artifacts.
Governance scope: deployed commit, runtime path, audit store, URL binding, runner
readiness, and activation outcome.
Dependencies: staging evidence bundle schema, example artifacts, and validator script.
Invariants: terminal bundle proof requires both source artifacts to validate and all
cross-artifact checks to pass.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from scripts.validate_governed_swarm_staging_evidence_bundle import (
    build_staging_evidence_bundle_payload,
    validate_staging_evidence_bundle_file,
    validate_staging_evidence_bundle_payload,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_BUNDLE_PATH = ROOT / "docs" / "governed-swarm-staging-evidence-bundle-example.json"
RUNNER_PREFLIGHT_PATH = ROOT / "docs" / "governed-swarm-staging-runner-preflight-example.json"
ACTIVATION_WITNESS_PATH = ROOT / "docs" / "governed-swarm-staging-activation-witness-example.json"


def test_example_governed_swarm_staging_evidence_bundle_passes() -> None:
    errors = validate_staging_evidence_bundle_file(EXAMPLE_BUNDLE_PATH)

    assert errors == []
    assert EXAMPLE_BUNDLE_PATH.exists()
    assert EXAMPLE_BUNDLE_PATH.name == "governed-swarm-staging-evidence-bundle-example.json"


def test_build_governed_swarm_staging_evidence_bundle_from_examples_passes() -> None:
    bundle = build_staging_evidence_bundle_payload(
        _load(RUNNER_PREFLIGHT_PATH),
        _load(ACTIVATION_WITNESS_PATH),
        runner_preflight_ref="docs/governed-swarm-staging-runner-preflight-example.json",
        activation_witness_ref="docs/governed-swarm-staging-activation-witness-example.json",
        validated_at="2026-05-17T08:20:00Z",
    )

    errors = validate_staging_evidence_bundle_payload(bundle)

    assert errors == []
    assert bundle["outcome"] == "SolvedVerified"
    assert all(check["passed"] is True for check in bundle["cross_checks"])
    assert bundle["extension_health"]["governed_swarm"]["state"] == "mounted"


def test_staging_evidence_bundle_rejects_commit_mismatch() -> None:
    runner = _load(RUNNER_PREFLIGHT_PATH)
    witness = _load(ACTIVATION_WITNESS_PATH)
    witness["control_plane_commit"] = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    witness["runtime_commit"] = witness["control_plane_commit"]

    bundle = build_staging_evidence_bundle_payload(
        runner,
        witness,
        runner_preflight_ref="runner.json",
        activation_witness_ref="witness.json",
        validated_at="2026-05-17T08:20:00Z",
    )

    errors = validate_staging_evidence_bundle_payload(bundle)

    assert len(errors) == 0
    assert bundle["outcome"] == "AwaitingEvidence"
    assert "control_plane_commit_match" in bundle["errors"][0]


def test_staging_evidence_bundle_rejects_runtime_path_mismatch() -> None:
    runner = _load(RUNNER_PREFLIGHT_PATH)
    witness = _load(ACTIVATION_WITNESS_PATH)
    witness["runtime_path"] = "/opt/mullu/other-governed-swarm/mcoi"
    witness["feature_flags"]["MULLU_GOVERNED_SWARM_RUNTIME_PATH"] = "/opt/mullu/other-governed-swarm/mcoi"

    bundle = build_staging_evidence_bundle_payload(
        runner,
        witness,
        runner_preflight_ref="runner.json",
        activation_witness_ref="witness.json",
        validated_at="2026-05-17T08:20:00Z",
    )

    errors = validate_staging_evidence_bundle_payload(bundle)

    assert len(errors) == 0
    assert bundle["outcome"] == "AwaitingEvidence"
    assert any("runtime_path_match" in error for error in bundle["errors"])


def test_staging_evidence_bundle_blocks_invalid_solved_bundle() -> None:
    bundle = _load(EXAMPLE_BUNDLE_PATH)
    bundle["cross_checks"][0]["passed"] = False

    errors = validate_staging_evidence_bundle_payload(bundle)

    assert len(errors) == 1
    assert "$.outcome cannot be SolvedVerified" in errors[0]
    assert "runner_preflight_valid" in errors[0]


def test_staging_evidence_bundle_blocks_unmounted_extension_health() -> None:
    runner = _load(RUNNER_PREFLIGHT_PATH)
    witness = _load(ACTIVATION_WITNESS_PATH)
    witness["extension_health"]["governed_swarm"]["mounted"] = False
    witness["extension_health"]["governed_swarm"]["state"] = "enabled_unmounted"

    bundle = build_staging_evidence_bundle_payload(
        runner,
        witness,
        runner_preflight_ref="runner.json",
        activation_witness_ref="witness.json",
        validated_at="2026-05-17T08:20:00Z",
    )

    errors = validate_staging_evidence_bundle_payload(bundle)

    assert errors == []
    assert bundle["outcome"] == "AwaitingEvidence"
    assert any("extension_health_bound" in error for error in bundle["errors"])


def _load(path: Path) -> dict[str, Any]:
    return deepcopy(json.loads(path.read_text(encoding="utf-8")))
