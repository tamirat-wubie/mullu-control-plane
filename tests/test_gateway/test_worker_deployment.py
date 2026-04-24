"""Gateway worker deployment tests.

Tests: Docker Compose and Kubernetes manifests expose the command worker and
    deferred command-spine environment.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent


def test_compose_declares_gateway_worker_service():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "gateway-worker:" in compose
    assert 'command: ["python", "-m", "gateway.worker"]' in compose
    assert "MULLU_COMMAND_LEDGER_BACKEND: postgresql" in compose
    assert "MULLU_TENANT_IDENTITY_BACKEND: postgresql" in compose
    assert 'MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY: "true"' in compose
    assert 'MULLU_COMMAND_ANCHOR_KEY_ID: "compose-local"' in compose
    assert "MULLU_COMMAND_ANCHOR_SECRET:" in compose
    assert 'MULLU_GATEWAY_DEFER_APPROVED_EXECUTION: "true"' in compose
    assert 'MULLU_GATEWAY_WORKER_ID: "gateway-worker-1"' in compose


def test_kubernetes_declares_gateway_worker_deployment():
    manifest = (ROOT / "k8s" / "mullu-api.yaml").read_text(encoding="utf-8")

    assert "name: mullu-gateway-worker" in manifest
    assert 'command: ["python", "-m", "gateway.worker"]' in manifest
    assert 'MULLU_COMMAND_LEDGER_BACKEND: "postgresql"' in manifest
    assert 'MULLU_TENANT_IDENTITY_BACKEND: "postgresql"' in manifest
    assert 'MULLU_REQUIRE_PERSISTENT_TENANT_IDENTITY: "true"' in manifest
    assert 'MULLU_COMMAND_ANCHOR_KEY_ID: "k8s-command-anchor"' in manifest
    assert "MULLU_COMMAND_ANCHOR_SECRET:" in manifest
    assert 'MULLU_GATEWAY_DEFER_APPROVED_EXECUTION: "true"' in manifest
    assert "name: mullu-gateway-worker-pdb" in manifest
