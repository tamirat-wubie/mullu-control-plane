"""Tests for federated control-plane policy distribution.

Purpose: verify signed policy registry distribution and local residency-preserving enforcement.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: federated control-plane core module.
Invariants: signatures are deterministic, sync receipts preserve residency, and enforcement stays local.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mcoi_runtime.core.federated_control_plane import (
    FederatedCluster,
    FederatedControlPlane,
    FederatedPolicyBundle,
)


def _policy_bundle() -> FederatedPolicyBundle:
    return FederatedPolicyBundle.create(
        policy_id="regulated-agent-policy",
        version="v1",
        artifact_payload={"rules": [{"id": "deny-external-tool", "action": "deny"}]},
        signing_key_id="mullu-root-2026",
    )


def test_policy_bundle_signature_is_deterministic() -> None:
    first = _policy_bundle()
    second = _policy_bundle()

    assert first == second
    assert first.artifact_hash.startswith("sha256:")
    assert first.signature.startswith("sha256:")
    assert first.policy_id == "regulated-agent-policy"
    assert first.version == "v1"


def test_signed_policy_sync_preserves_residency_boundary() -> None:
    control_plane = FederatedControlPlane()
    control_plane.register_cluster(
        FederatedCluster(
            cluster_id="cluster-us-east",
            region="us-east",
            residency_region="us",
            allowed_policy_ids=("regulated-agent-policy",),
        )
    )
    control_plane.publish_policy(_policy_bundle())

    receipt = control_plane.sync_policy(
        cluster_id="cluster-us-east",
        policy_id="regulated-agent-policy",
        version="v1",
    ).to_dict()

    assert receipt["accepted"] is True
    assert receipt["tenant_data_replicated"] is False
    assert receipt["reason_codes"] == ["signed_policy_accepted", "tenant_data_not_replicated"]
    assert receipt["receipt_hash"].startswith("sha256:")


def test_local_enforcement_allows_matching_residency_after_sync() -> None:
    control_plane = FederatedControlPlane()
    control_plane.register_cluster(
        FederatedCluster(
            cluster_id="cluster-eu",
            region="eu-central",
            residency_region="eu",
            allowed_policy_ids=("regulated-agent-policy",),
        )
    )
    control_plane.publish_policy(_policy_bundle())
    control_plane.sync_policy(cluster_id="cluster-eu", policy_id="regulated-agent-policy", version="v1")

    receipt = control_plane.enforce_local(
        cluster_id="cluster-eu",
        tenant_id="tenant-eu-1",
        tenant_region="eu",
        policy_id="regulated-agent-policy",
        version="v1",
    ).to_dict()

    assert receipt["verdict"] == "allow"
    assert receipt["local_enforcement"] is True
    assert receipt["central_data_transfer"] is False
    assert receipt["reason_codes"] == ["local_policy_enforced", "residency_boundary_preserved"]
    assert receipt["receipt_hash"].startswith("sha256:")


def test_local_enforcement_denies_region_mismatch() -> None:
    control_plane = FederatedControlPlane()
    control_plane.register_cluster(
        FederatedCluster(
            cluster_id="cluster-us",
            region="us-west",
            residency_region="us",
            allowed_policy_ids=("regulated-agent-policy",),
        )
    )
    control_plane.publish_policy(_policy_bundle())
    control_plane.sync_policy(cluster_id="cluster-us", policy_id="regulated-agent-policy", version="v1")

    receipt = control_plane.enforce_local(
        cluster_id="cluster-us",
        tenant_id="tenant-eu-1",
        tenant_region="eu",
        policy_id="regulated-agent-policy",
        version="v1",
    ).to_dict()

    assert receipt["verdict"] == "deny"
    assert receipt["local_enforcement"] is True
    assert receipt["central_data_transfer"] is False
    assert receipt["reason_codes"] == ["tenant_region_mismatch"]


def test_policy_sync_denies_policy_not_allowed_for_cluster() -> None:
    control_plane = FederatedControlPlane()
    control_plane.register_cluster(
        FederatedCluster(
            cluster_id="cluster-public",
            region="us-public",
            residency_region="us",
            allowed_policy_ids=("public-policy",),
        )
    )
    control_plane.publish_policy(_policy_bundle())

    receipt = control_plane.sync_policy(
        cluster_id="cluster-public",
        policy_id="regulated-agent-policy",
        version="v1",
    ).to_dict()

    assert receipt["accepted"] is False
    assert receipt["tenant_data_replicated"] is False
    assert receipt["reason_codes"] == ["policy_not_allowed_for_cluster"]


def test_federated_control_plane_rejects_non_local_cluster() -> None:
    with pytest.raises(ValueError, match="federated clusters must enforce locally"):
        FederatedCluster(
            cluster_id="cluster-centralized",
            region="global",
            residency_region="us",
            allowed_policy_ids=("regulated-agent-policy",),
            enforcement_local=False,
        )


def test_federation_summary_route_exposes_read_only_witness() -> None:
    from mcoi_runtime.app.server import app

    client = TestClient(app)
    response = client.get("/api/v1/federation/summary")
    data = response.json()

    assert response.status_code == 200
    assert data["governed"] is True
    assert data["read_only"] is True
    assert data["summary"]["tenant_data_replication"] is False
    assert data["witness"]["sync_receipt"]["accepted"] is True
    assert data["witness"]["enforcement_receipt"]["central_data_transfer"] is False
