"""Governed swarm staging witness workflow tests.

Purpose: keep manual staging activation witness collection replayable through GitHub Actions.
Governance scope: workflow dispatch inputs, self-hosted audit-store boundary, collector execution, validator execution, artifact upload.
Dependencies: .github/workflows/governed-swarm-staging-witness.yml.
Invariants: workflow must preserve audit proof, validate the emitted witness, and upload the activation receipt.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "governed-swarm-staging-witness.yml"


def test_governed_swarm_staging_workflow_collects_validated_witness() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow
    assert "staging_url:" in workflow
    assert "control_plane_commit:" in workflow
    assert "runtime_path:" in workflow
    assert "audit_store_path:" in workflow
    assert 'default: "self-hosted"' in workflow
    assert "runs-on: ${{ inputs.runner_label }}" in workflow
    assert "MULLU_GOVERNED_SWARM_RUNTIME_PATH" in workflow
    assert "MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH" in workflow
    assert "Preflight self-hosted staging witness inputs" in workflow
    assert "python scripts/preflight_governed_swarm_staging_runner.py" in workflow
    assert ".change_assurance/governed_swarm_staging_runner_preflight.json" in workflow
    assert "governed-swarm-staging-runner-preflight" in workflow
    assert "python scripts/collect_governed_swarm_staging_activation_witness.py" in workflow
    assert '--audit-store-path "$MULLU_GOVERNED_SWARM_AUDIT_STORE_PATH"' in workflow
    assert "python scripts/validate_governed_swarm_staging_activation_witness.py" in workflow
    assert ".change_assurance/governed_swarm_staging_activation_witness.json" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "governed-swarm-staging-activation-witness" in workflow


def test_governed_swarm_staging_workflow_keeps_optional_run_id_bounded() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "run_id:" in workflow
    assert 'MULLU_GOVERNED_SWARM_RUN_ID: ${{ inputs.run_id }}' in workflow
    assert 'if [ -n "$MULLU_GOVERNED_SWARM_RUN_ID" ]; then' in workflow
    assert '--run-id "$MULLU_GOVERNED_SWARM_RUN_ID"' in workflow
