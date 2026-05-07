"""Gateway federated control-plane tests.

Purpose: verify signed policy federation, regional sync denials, local-only
    enforcement receipts, and public summary schema behavior.
Governance scope: federation, tenant locality, policy signature acceptance,
    regional enforcement, and manifest-ready public contracts.
Dependencies: gateway.federated_control and federated control schema.
Invariants:
  - Policy metadata can sync only to allowed regional clusters.
  - Tenant data never transfers through the central federation registry.
  - Enforcement denies unsynced policies and tenant region mismatches locally.
  - Snapshot output is schema-valid and hash-bearing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from gateway.federated_control import (
    FederatedControlPlane,
    FederatedControlSnapshot,
    FederatedSyncStatus,
    FederatedVerdict,
    RegionalCluster,
    SignedPolicyBundle,
    federated_control_snapshot_to_json_dict,
)
from gateway.server import create_gateway_app


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "federated_control_snapshot.schema.json"


def test_signed_policy_syncs_to_allowed_region_without_data_transfer() -> None:
    plane = _plane_with_policy_and_cluster()

    decision = plane.sync_policy(cluster_id="cluster-us-east", policy_id="policy-payment-approval", version="1.0.0")
    receipt = plane.enforce(
        tenant_id="tenant-a",
        tenant_region="us-east-1",
        cluster_id="cluster-us-east",
        policy_id="policy-payment-approval",
        policy_version="1.0.0",
    )

    assert decision.status is FederatedSyncStatus.SYNCED
    assert decision.reason == "policy_synced"
    assert decision.central_data_transfer is False
    assert receipt.verdict is FederatedVerdict.ALLOW
    assert receipt.reason_codes == ("local_enforcement",)
    assert receipt.central_data_transfer is False


def test_policy_not_allowed_for_cluster_is_denied() -> None:
    plane = FederatedControlPlane()
    plane.register_policy_bundle(_bundle(allowed_regions=("eu-west-1",)))
    plane.register_cluster(_cluster(region="us-east-1"))

    decision = plane.sync_policy(cluster_id="cluster-us-east", policy_id="policy-payment-approval", version="1.0.0")
    snapshot = plane.snapshot()

    assert decision.status is FederatedSyncStatus.DENIED
    assert decision.reason == "policy_not_allowed_for_cluster"
    assert decision.central_data_transfer is False
    assert snapshot.accepted_policy_count == 0
    assert snapshot.central_data_transfer is False


def test_invalid_signature_is_denied_before_local_acceptance() -> None:
    plane = FederatedControlPlane()
    plane.register_policy_bundle(_bundle(signature="invalid"))
    plane.register_cluster(_cluster())

    decision = plane.sync_policy(cluster_id="cluster-us-east", policy_id="policy-payment-approval", version="1.0.0")

    assert decision.status is FederatedSyncStatus.DENIED
    assert decision.reason == "invalid_policy_signature"
    assert decision.decision_hash


def test_local_enforcement_denies_unsynced_policy() -> None:
    plane = _plane_with_policy_and_cluster()

    receipt = plane.enforce(
        tenant_id="tenant-a",
        tenant_region="us-east-1",
        cluster_id="cluster-us-east",
        policy_id="policy-payment-approval",
        policy_version="1.0.0",
    )

    assert receipt.verdict is FederatedVerdict.DENY
    assert receipt.reason_codes == ("policy_not_synced_to_cluster",)
    assert receipt.central_data_transfer is False
    assert receipt.receipt_hash


def test_tenant_region_mismatch_denies_locally() -> None:
    plane = _plane_with_policy_and_cluster()
    plane.sync_policy(cluster_id="cluster-us-east", policy_id="policy-payment-approval", version="1.0.0")

    receipt = plane.enforce(
        tenant_id="tenant-a",
        tenant_region="eu-west-1",
        cluster_id="cluster-us-east",
        policy_id="policy-payment-approval",
        policy_version="1.0.0",
    )

    assert receipt.verdict is FederatedVerdict.DENY
    assert receipt.reason_codes == ("tenant_region_mismatch",)
    assert receipt.metadata["cluster_region"] == "us-east-1"
    assert receipt.central_data_transfer is False


def test_unknown_cluster_or_policy_are_hard_errors() -> None:
    plane = _plane_with_policy_and_cluster()

    with pytest.raises(ValueError, match="unknown_cluster"):
        plane.sync_policy(cluster_id="missing-cluster", policy_id="policy-payment-approval", version="1.0.0")

    with pytest.raises(ValueError, match="unknown_policy_bundle"):
        plane.sync_policy(cluster_id="cluster-us-east", policy_id="missing-policy", version="1.0.0")

    with pytest.raises(ValueError, match="unknown_policy_bundle"):
        plane.enforce(
            tenant_id="tenant-a",
            tenant_region="us-east-1",
            cluster_id="cluster-us-east",
            policy_id="missing-policy",
            policy_version="1.0.0",
        )


def test_federated_control_snapshot_schema_exposes_locality_contract() -> None:
    plane = _plane_with_policy_and_cluster()
    sync_decision = plane.sync_policy(cluster_id="cluster-us-east", policy_id="policy-payment-approval", version="1.0.0")
    receipt = plane.enforce(
        tenant_id="tenant-a",
        tenant_region="us-east-1",
        cluster_id="cluster-us-east",
        policy_id="policy-payment-approval",
        policy_version="1.0.0",
    )
    snapshot = plane.snapshot()
    payload = federated_control_snapshot_to_json_dict(snapshot)
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    Draft202012Validator(schema).validate(payload)
    assert set(schema["required"]).issubset(payload)
    assert schema["$id"] == "urn:mullusi:schema:federated-control-snapshot:1"
    assert payload["central_data_transfer"] is False
    assert payload["sync_decisions"][0]["decision_id"] == sync_decision.decision_id
    assert payload["enforcement_receipts"][0]["receipt_id"] == receipt.receipt_id
    assert snapshot.snapshot_hash


def test_federation_summary_endpoint_returns_schema_valid_read_model() -> None:
    app = create_gateway_app(platform=_StubPlatform())
    plane = app.state.federated_control_plane
    plane.register_policy_bundle(_bundle())
    plane.register_cluster(_cluster())
    plane.sync_policy(cluster_id="cluster-us-east", policy_id="policy-payment-approval", version="1.0.0")

    response = TestClient(app).get("/api/v1/federation/summary")
    payload = response.json()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert response.status_code == 200
    Draft202012Validator(schema).validate(payload)
    assert payload["cluster_count"] == 1
    assert payload["accepted_policy_count"] == 1
    assert payload["central_data_transfer"] is False
    assert payload["sync_decisions"][0]["reason"] == "policy_synced"


def test_snapshot_rejects_inconsistent_federation_witnesses() -> None:
    plane = _plane_with_policy_and_cluster()
    snapshot = plane.snapshot()

    with pytest.raises(ValueError, match="cluster_count_mismatch"):
        FederatedControlSnapshot(
            snapshot_id="bad-cluster-count",
            policy_bundles=snapshot.policy_bundles,
            clusters=snapshot.clusters,
            sync_decisions=snapshot.sync_decisions,
            enforcement_receipts=snapshot.enforcement_receipts,
            cluster_count=0,
            accepted_policy_count=snapshot.accepted_policy_count,
            local_enforcement_receipt_count=snapshot.local_enforcement_receipt_count,
            central_data_transfer=False,
        )

    with pytest.raises(ValueError, match="central_data_transfer_must_be_false"):
        FederatedControlSnapshot(
            snapshot_id="bad-transfer-flag",
            policy_bundles=snapshot.policy_bundles,
            clusters=snapshot.clusters,
            sync_decisions=snapshot.sync_decisions,
            enforcement_receipts=snapshot.enforcement_receipts,
            cluster_count=snapshot.cluster_count,
            accepted_policy_count=snapshot.accepted_policy_count,
            local_enforcement_receipt_count=snapshot.local_enforcement_receipt_count,
            central_data_transfer=True,
        )


def _plane_with_policy_and_cluster() -> FederatedControlPlane:
    plane = FederatedControlPlane()
    plane.register_policy_bundle(_bundle())
    plane.register_cluster(_cluster())
    return plane


def _bundle(
    *,
    policy_id: str = "policy-payment-approval",
    version: str = "1.0.0",
    artifact_hash: str = "sha256:policy-payment-approval-v1",
    signature: str = "sig:policy-payment-approval-v1",
    allowed_regions: tuple[str, ...] = ("us-east-1",),
) -> SignedPolicyBundle:
    return SignedPolicyBundle(
        policy_id=policy_id,
        version=version,
        artifact_hash=artifact_hash,
        signing_key_id="registry-key-1",
        signature=signature,
        allowed_regions=allowed_regions,
        metadata={"registry_scope": "policy_metadata_only"},
    )


def _cluster(
    *,
    cluster_id: str = "cluster-us-east",
    region: str = "us-east-1",
    allowed_policy_ids: tuple[str, ...] = ("policy-payment-approval",),
) -> RegionalCluster:
    return RegionalCluster(
        cluster_id=cluster_id,
        region=region,
        allowed_policy_ids=allowed_policy_ids,
        metadata={"tenant_data_replication": False},
    )


class _StubPlatform:
    def connect(self, *, identity_id: str, tenant_id: str):
        return _StubSession()


class _StubSession:
    def llm(self, prompt: str, **kwargs):
        return type("Result", (), {"content": "ok", "succeeded": True, "error": "", "cost": 0.0})()

    def close(self) -> None:
        return None
