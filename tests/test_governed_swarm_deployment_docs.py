"""Governed swarm deployment documentation tests.

Purpose: keep the feature-flagged governed swarm activation contract visible to operators.
Governance scope: deployment docs, env example, and control-plane route activation.
Dependencies: README, DEPLOYMENT guides, and governed swarm env example.
Invariants: docs must name the enable flag, audit store, runtime path, and disabled-by-default boundary.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_governed_swarm_env_example_lists_required_activation_contract() -> None:
    text = _read("examples/governed_swarm_control_plane.env.example")

    assert "MULLU_GOVERNED_SWARM_ENABLED=true" in text
    assert "MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH=" in text
    assert "MULLU_GOVERNED_SWARM_RUNTIME_PATH=" in text
    assert "mcoi_runtime/swarm" in text
    assert "audit store required when enabled" in text


def test_deployment_docs_reference_governed_swarm_feature_flag_boundary() -> None:
    deployment = _read("DEPLOYMENT.md")
    production = _read("docs/PRODUCTION_DEPLOYMENT.md")
    readme = _read("README.md")

    for text in (deployment, production, readme):
        assert "MULLU_GOVERNED_SWARM_ENABLED" in text
        assert "MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH" in text
        assert "MULLU_GOVERNED_SWARM_RUNTIME_PATH" in text
    assert "disabled by default" in deployment
    assert "disabled by default" in production
    assert "/api/v1/swarm/invoice-runs" in production
