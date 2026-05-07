"""Tests for the general-agent capability roadmap.

Purpose: keep the capability roadmap aligned with governed skill and worker
admission rules.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: docs/56_general_agent_capability_roadmap.md.
Invariants:
  - Teachable skills and build-required capabilities remain separate classes.
  - Build-required capabilities require registry, worker, receipt, and verification closure.
  - Production claims remain deployment-witness bound.
"""

from __future__ import annotations

from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent
_ROADMAP_PATH = _ROOT / "docs" / "56_general_agent_capability_roadmap.md"


def test_roadmap_preserves_two_capability_classes() -> None:
    roadmap_text = _ROADMAP_PATH.read_text(encoding="utf-8")

    assert "| Teachable skills |" in roadmap_text
    assert "| Build-required capabilities |" in roadmap_text
    assert "Skills may encode prompts, runbooks, examples, policies, and domain knowledge" in roadmap_text
    assert "Build-required capabilities must enter through the governed capability registry before use" in roadmap_text
    assert "but may not create execution authority" in roadmap_text


def test_build_required_capabilities_are_bound_to_effect_closure() -> None:
    roadmap_text = _ROADMAP_PATH.read_text(encoding="utf-8")

    assert "A typed capability registry entry" in roadmap_text
    assert "A worker or connector implementation with bounded authority" in roadmap_text
    assert "A policy and approval contract" in roadmap_text
    assert "A receipt schema" in roadmap_text
    assert "Tests for success, boundary conditions, violations, rollback, and receipt integrity" in roadmap_text


def test_roadmap_names_highest_priority_worker_families() -> None:
    roadmap_text = _ROADMAP_PATH.read_text(encoding="utf-8")

    assert "Sandboxed computer control" in roadmap_text
    assert "Browser automation" in roadmap_text
    assert "PDF, Office, and structured documents" in roadmap_text
    assert "Automatic governed memory" in roadmap_text
    assert "Public deployment witness" in roadmap_text
    assert "Deployment witness publication" in roadmap_text


def test_roadmap_tracks_repository_closure_without_production_overclaim() -> None:
    roadmap_text = _ROADMAP_PATH.read_text(encoding="utf-8")

    assert "## Implementation Status" in roadmap_text
    assert "fabric admission is not the same as public production readiness" in roadmap_text
    assert "`deployment` capability capsule governs witness collection and publish-with-approval" in roadmap_text
    assert "Publish signed deployment witness and HTTPS public health endpoint" in roadmap_text


def test_roadmap_avoids_forbidden_general_intelligence_phrase() -> None:
    roadmap_text = _ROADMAP_PATH.read_text(encoding="utf-8").lower()

    assert "artificial intelligence" not in roadmap_text
    assert "symbolic intelligence" in roadmap_text
    assert "symbolic reasoning second" in roadmap_text
