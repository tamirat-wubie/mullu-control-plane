"""Governed swarm deployment documentation tests.

Purpose: keep the feature-flagged governed swarm activation contract visible to operators.
Governance scope: deployment docs, env example, and control-plane route activation.
Dependencies: README, DEPLOYMENT guides, governed swarm env example, and staging activation runbook.
Invariants: docs must name the enable flag, audit store, runtime path, release pin, staging witness, and disabled-by-default boundary.
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
    assert "v0.1.0-governed-swarm" in text


def test_deployment_docs_reference_governed_swarm_feature_flag_boundary() -> None:
    deployment = _read("DEPLOYMENT.md")
    production = _read("docs/PRODUCTION_DEPLOYMENT.md")
    readme = _read("README.md")

    for text in (deployment, production, readme):
        assert "MULLU_GOVERNED_SWARM_ENABLED" in text
        assert "MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH" in text
        assert "MULLU_GOVERNED_SWARM_RUNTIME_PATH" in text
        assert "v0.1.0-governed-swarm" in text
    assert "disabled by default" in deployment
    assert "disabled by default" in production
    assert "/api/v1/swarm/invoice-runs" in production


def test_staging_activation_runbook_binds_witness_and_rollback() -> None:
    text = _read("docs/governed-swarm-staging-activation-runbook.md")

    assert "v0.1.0-governed-swarm" in text
    assert "MULLU_GOVERNED_SWARM_ENABLED=true" in text
    assert "MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH" in text
    assert "/api/v1/swarm/invoice-runs" in text
    assert "scripts/collect_governed_swarm_staging_activation_witness.py" in text
    assert ".github/workflows/governed-swarm-staging-witness.yml" in text
    assert "self-hosted" in text
    assert "scripts/preflight_governed_swarm_staging_runner.py" in text
    assert "scripts/validate_governed_swarm_staging_runner_preflight.py" in text
    assert "governed_swarm_staging_runner_preflight.json" in text
    assert "scripts/validate_governed_swarm_staging_evidence_bundle.py" in text
    assert "governed_swarm_staging_evidence_bundle.json" in text
    assert "scripts/validate_governed_swarm_promotion_readiness.py" in text
    assert "governed_swarm_promotion_readiness.json" in text
    assert "governed-swarm-route-preflight.json" in text
    assert "schemas/governed_swarm_staging_activation_witness.schema.json" in text
    assert "schemas/governed_swarm_staging_evidence_bundle.schema.json" in text
    assert "schemas/governed_swarm_promotion_readiness.schema.json" in text
    assert "MULLU_GOVERNED_SWARM_ENABLED=false" in text


def test_production_docs_block_governed_swarm_production_overclaim() -> None:
    text = _read("docs/PRODUCTION_DEPLOYMENT.md")

    assert "Pilot promotion requires a SolvedVerified governed swarm staging evidence bundle" in text
    assert "Production promotion is not granted by the staging promotion report" in text
    assert "scripts/validate_governed_swarm_promotion_readiness.py" in text
    assert "governed_swarm_promotion_readiness.json" in text
