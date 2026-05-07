"""Federated control-plane read-model endpoints.

Purpose: expose read-only federation summary and residency receipts.
Governance scope: federated policy distribution read models only.
Dependencies: FastAPI and federated control-plane core.
Invariants: endpoints are read-only, deterministic, and report local-only
enforcement boundaries.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from mcoi_runtime.core.federated_control_plane import (
    FederatedCluster,
    FederatedControlPlane,
    FederatedPolicyBundle,
)


router = APIRouter(tags=["federation"])


def _seed_federation() -> tuple[FederatedControlPlane, dict[str, Any]]:
    control_plane = FederatedControlPlane()
    cluster = control_plane.register_cluster(
        FederatedCluster(
            cluster_id="cluster-us-east",
            region="us-east",
            residency_region="us",
            allowed_policy_ids=("regulated-agent-policy",),
        )
    )
    bundle = control_plane.publish_policy(
        FederatedPolicyBundle.create(
            policy_id="regulated-agent-policy",
            version="v1",
            artifact_payload={"rules": [{"id": "deny-external-tool", "action": "deny"}]},
            signing_key_id="mullu-root-2026",
        )
    )
    sync_receipt = control_plane.sync_policy(
        cluster_id=cluster.cluster_id,
        policy_id=bundle.policy_id,
        version=bundle.version,
    )
    enforcement_receipt = control_plane.enforce_local(
        cluster_id=cluster.cluster_id,
        tenant_id="tenant-us-demo",
        tenant_region=cluster.residency_region,
        policy_id=bundle.policy_id,
        version=bundle.version,
    )
    return control_plane, {
        "policy": bundle.to_dict(),
        "sync_receipt": sync_receipt.to_dict(),
        "enforcement_receipt": enforcement_receipt.to_dict(),
    }


_FEDERATION, _FEDERATION_WITNESS = _seed_federation()


@router.get("/api/v1/federation/summary")
def federation_summary() -> dict[str, Any]:
    """Return a read-only federated control-plane summary."""
    return {
        "summary": _FEDERATION.summary(),
        "witness": _FEDERATION_WITNESS,
        "read_only": True,
        "governed": True,
    }
