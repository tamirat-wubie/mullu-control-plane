"""Tests for governed swarm production readiness validation.

Purpose: keep governed swarm production claims dependent on pilot readiness,
published deployment witness evidence, and public health declaration evidence.
Governance scope: production promotion, public witness closure, health
declaration, and strict CLI blocking.
Dependencies: governed swarm production readiness schema, example reports, and validator script.
Invariants: production readiness requires public proof; staging/pilot readiness alone is insufficient.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from scripts.validate_governed_swarm_production_readiness import (
    build_governed_swarm_production_readiness_payload,
    main,
    validate_governed_swarm_production_readiness_file,
    validate_governed_swarm_production_readiness_payload,
)


ROOT = Path(__file__).resolve().parents[1]
PILOT_READINESS_PATH = ROOT / "docs" / "governed-swarm-promotion-readiness-example.json"
DEPLOYMENT_WITNESS_PATH = ROOT / "docs" / "governed-swarm-production-deployment-witness-example.json"
PUBLIC_HEALTH_DECLARATION_PATH = (
    ROOT / "docs" / "governed-swarm-public-production-health-declaration-example.json"
)
EXAMPLE_READINESS_PATH = ROOT / "docs" / "governed-swarm-production-readiness-example.json"


def test_example_governed_swarm_production_readiness_passes() -> None:
    errors = validate_governed_swarm_production_readiness_file(EXAMPLE_READINESS_PATH)

    assert errors == []
    assert EXAMPLE_READINESS_PATH.exists()
    assert EXAMPLE_READINESS_PATH.name == "governed-swarm-production-readiness-example.json"


def test_production_readiness_from_public_evidence_passes() -> None:
    readiness = build_governed_swarm_production_readiness_payload(
        _load(PILOT_READINESS_PATH),
        _load(DEPLOYMENT_WITNESS_PATH),
        _load(PUBLIC_HEALTH_DECLARATION_PATH),
        pilot_promotion_readiness_ref="docs/governed-swarm-promotion-readiness-example.json",
        deployment_witness_ref="docs/governed-swarm-production-deployment-witness-example.json",
        public_health_declaration_ref=(
            "docs/governed-swarm-public-production-health-declaration-example.json"
        ),
        checked_at="2026-05-17T09:05:00Z",
    )

    errors = validate_governed_swarm_production_readiness_payload(readiness)

    assert errors == []
    assert readiness["ready"] is True
    assert readiness["readiness_level"] == "production-ready"
    assert readiness["public_health_endpoint"] == "https://api.mullusi.com/health"


def test_production_readiness_blocks_pilot_only_readiness_gap() -> None:
    pilot_readiness = _load(PILOT_READINESS_PATH)
    pilot_readiness["ready"] = False
    pilot_readiness["readiness_level"] = "promotion-blocked"
    pilot_readiness["blockers"] = ["staging_evidence_solved"]

    readiness = build_governed_swarm_production_readiness_payload(
        pilot_readiness,
        _load(DEPLOYMENT_WITNESS_PATH),
        _load(PUBLIC_HEALTH_DECLARATION_PATH),
        pilot_promotion_readiness_ref="pilot.json",
        deployment_witness_ref="deployment.json",
        public_health_declaration_ref="health.json",
        checked_at="2026-05-17T09:05:00Z",
    )

    errors = validate_governed_swarm_production_readiness_payload(readiness)

    assert errors == []
    assert readiness["ready"] is False
    assert "pilot_readiness_ready" in readiness["blockers"]
    assert readiness["outcome"] == "GovernanceBlocked"


def test_production_readiness_blocks_unpublished_deployment_witness() -> None:
    witness = _load(DEPLOYMENT_WITNESS_PATH)
    witness["deployment_claim"] = "not-published"
    witness["errors"] = ["proof verification endpoint did not close all checks"]

    readiness = build_governed_swarm_production_readiness_payload(
        _load(PILOT_READINESS_PATH),
        witness,
        _load(PUBLIC_HEALTH_DECLARATION_PATH),
        pilot_promotion_readiness_ref="pilot.json",
        deployment_witness_ref="deployment.json",
        public_health_declaration_ref="health.json",
        checked_at="2026-05-17T09:05:00Z",
    )

    errors = validate_governed_swarm_production_readiness_payload(readiness)

    assert errors == []
    assert readiness["ready"] is False
    assert "deployment_witness_published" in readiness["blockers"]
    assert "deployment_health_passing" in readiness["blockers"]


def test_production_readiness_blocks_public_health_mismatch() -> None:
    declaration = _load(PUBLIC_HEALTH_DECLARATION_PATH)
    declaration["public_health_endpoint"] = "https://other.example/health"

    readiness = build_governed_swarm_production_readiness_payload(
        _load(PILOT_READINESS_PATH),
        _load(DEPLOYMENT_WITNESS_PATH),
        declaration,
        pilot_promotion_readiness_ref="pilot.json",
        deployment_witness_ref="deployment.json",
        public_health_declaration_ref="health.json",
        checked_at="2026-05-17T09:05:00Z",
    )

    errors = validate_governed_swarm_production_readiness_payload(readiness)

    assert errors == []
    assert readiness["ready"] is False
    assert "public_health_endpoint_match" in readiness["blockers"]
    assert "public_health_declaration_valid" not in readiness["blockers"]


def test_governed_swarm_production_cli_strict_blocks_missing_public_health(tmp_path: Path) -> None:
    declaration = _load(PUBLIC_HEALTH_DECLARATION_PATH)
    declaration["updated"] = False
    declaration["dry_run"] = True
    declaration_path = tmp_path / "public-health.json"
    output_path = tmp_path / "production-readiness.json"
    declaration_path.write_text(json.dumps(declaration), encoding="utf-8")

    exit_code = main(
        [
            "--pilot-readiness",
            str(PILOT_READINESS_PATH),
            "--deployment-witness",
            str(DEPLOYMENT_WITNESS_PATH),
            "--public-health-declaration",
            str(declaration_path),
            "--output",
            str(output_path),
            "--strict",
            "--json",
        ]
    )
    payload = json.loads(output_path.read_text(encoding="utf-8"))

    assert exit_code == 2
    assert payload["ready"] is False
    assert "public_health_declaration_applied" in payload["blockers"]


def _load(path: Path) -> dict[str, Any]:
    return deepcopy(json.loads(path.read_text(encoding="utf-8")))
