"""Tests for governed swarm promotion readiness validation.

Purpose: keep governed swarm pilot promotion dependent on terminal staging evidence.
Governance scope: staging evidence bundle closure, pilot readiness, production
overclaim prevention, and strict CLI blocking.
Dependencies: governed swarm promotion readiness schema, example report, and validator script.
Invariants: production is blocked by this gate; pilot readiness requires solved staging evidence.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from scripts.validate_governed_swarm_promotion_readiness import (
    build_governed_swarm_promotion_readiness_payload,
    main,
    validate_governed_swarm_promotion_readiness_file,
    validate_governed_swarm_promotion_readiness_payload,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_READINESS_PATH = ROOT / "docs" / "governed-swarm-promotion-readiness-example.json"
STAGING_BUNDLE_PATH = ROOT / "docs" / "governed-swarm-staging-evidence-bundle-example.json"


def test_example_governed_swarm_promotion_readiness_passes() -> None:
    errors = validate_governed_swarm_promotion_readiness_file(EXAMPLE_READINESS_PATH)

    assert errors == []
    assert EXAMPLE_READINESS_PATH.exists()
    assert EXAMPLE_READINESS_PATH.name == "governed-swarm-promotion-readiness-example.json"


def test_pilot_promotion_readiness_from_solved_staging_bundle_passes() -> None:
    readiness = build_governed_swarm_promotion_readiness_payload(
        _load(STAGING_BUNDLE_PATH),
        staging_evidence_bundle_ref="docs/governed-swarm-staging-evidence-bundle-example.json",
        target_environment="pilot",
        checked_at="2026-05-17T08:25:00Z",
    )

    errors = validate_governed_swarm_promotion_readiness_payload(readiness)

    assert errors == []
    assert readiness["ready"] is True
    assert readiness["readiness_level"] == "pilot-ready"


def test_promotion_readiness_blocks_unsolved_staging_bundle() -> None:
    bundle = _load(STAGING_BUNDLE_PATH)
    bundle["outcome"] = "AwaitingEvidence"
    bundle["errors"] = ["missing activation proof"]

    readiness = build_governed_swarm_promotion_readiness_payload(
        bundle,
        staging_evidence_bundle_ref="bundle.json",
        target_environment="pilot",
        checked_at="2026-05-17T08:25:00Z",
    )

    errors = validate_governed_swarm_promotion_readiness_payload(readiness)

    assert errors == []
    assert readiness["ready"] is False
    assert "staging_evidence_solved" in readiness["blockers"]
    assert "staging_evidence_bundle_valid" not in readiness["blockers"]


def test_promotion_readiness_blocks_production_overclaim() -> None:
    readiness = build_governed_swarm_promotion_readiness_payload(
        _load(STAGING_BUNDLE_PATH),
        staging_evidence_bundle_ref="bundle.json",
        target_environment="production",
        checked_at="2026-05-17T08:25:00Z",
    )

    errors = validate_governed_swarm_promotion_readiness_payload(readiness)

    assert errors == []
    assert readiness["ready"] is False
    assert readiness["outcome"] == "GovernanceBlocked"
    assert "production_witness_required" in readiness["blockers"]


def test_governed_swarm_promotion_cli_strict_blocks_production(tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "promotion.json"

    exit_code = main(
        [
            "--staging-evidence-bundle",
            str(STAGING_BUNDLE_PATH),
            "--target-environment",
            "production",
            "--output",
            str(output_path),
            "--strict",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 2
    assert payload["ready"] is False
    assert "production_witness_required" in payload["blockers"]
    assert json.loads(captured.out)["outcome"] == "GovernanceBlocked"


def _load(path: Path) -> dict[str, Any]:
    return deepcopy(json.loads(path.read_text(encoding="utf-8")))
