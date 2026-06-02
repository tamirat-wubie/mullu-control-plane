"""Tests for the operating substrate integration plan.

Purpose: keep the operating-substrate foundation anchored to existing Mullu
Control Plane governance surfaces.
Governance scope: Foundation Mode, Capability ABI, self-model projection,
world-state projection, UAO, and non-duplication of action authority.
Dependencies: docs/72_operating_substrate_integration_plan.md.
Invariants:
  - The plan must not create a parallel root architecture.
  - The first build unit must bind capability ABI, self-model, and world-state.
  - The plan must keep effect-bearing execution under UAO.
"""

from __future__ import annotations

from pathlib import Path

from scripts.validate_proprietary_boundary import FORBIDDEN_TEXT_PATTERNS


REPO_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = REPO_ROOT / "docs" / "72_operating_substrate_integration_plan.md"


def _plan_text() -> str:
    return PLAN_PATH.read_text(encoding="utf-8")


def test_operating_substrate_plan_exists_and_has_governed_header() -> None:
    text = _plan_text()

    assert PLAN_PATH.exists()
    assert "Purpose: map the operating-substrate foundation" in text
    assert "Governance scope: Capability ABI" in text
    assert "Dependencies:" in text
    assert "Invariants:" in text


def test_operating_substrate_plan_reuses_existing_authority_path() -> None:
    text = _plan_text()

    assert "not a new root system" in text
    assert "Do not add a separate `MulluOS` package" in text
    assert "Universal Action Orchestration" in text
    assert "mcoi/mcoi_runtime/core/universal_action_kernel.py" in text


def test_operating_substrate_plan_names_first_build_unit() -> None:
    text = _plan_text()

    assert "Capability ABI coverage" in text
    assert "self-model projection" in text
    assert "world-state projection binding" in text
    assert "operator read model" in text


def test_operating_substrate_plan_preserves_foundation_mode_boundaries() -> None:
    text = _plan_text()

    assert "Foundation Mode blocks deployment" in text
    assert "claim production readiness" in text
    assert "mutate DNS, legal records, customer state, payment state, or deployment state" in text
    assert "AwaitingEvidence" in text


def test_operating_substrate_plan_avoids_forbidden_and_duplicate_framing() -> None:
    plan_text = _plan_text()
    text = plan_text.lower()

    for forbidden_pattern in FORBIDDEN_TEXT_PATTERNS:
        assert forbidden_pattern.lower() not in text
    assert "mulluos :=" not in text
    assert "separate `mulluos` package" in text
    assert "parallel operating substrate package" in text
