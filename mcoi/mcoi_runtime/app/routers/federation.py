"""Federated control-plane endpoints.

Purpose: expose federation summary and governed regional policy-sync controls.
Governance scope: federated policy distribution read models and admin-gated
regional policy metadata sync.
Dependencies: FastAPI and federated control-plane core.
Invariants: policy sync moves metadata only, operator controls require admin
authority, and all enforcement receipts remain local-only.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.musia_auth import require_admin
from mcoi_runtime.core.federated_control_plane import (
    FederatedCluster,
    FederatedControlPlane,
    FederatedPolicyBundle,
)


router = APIRouter(tags=["federation"])
_TENANT_DATA_KEYS = frozenset({"tenant_id", "tenant_data", "customer_data", "personal_data", "pii"})


class RegisterFederatedClusterRequest(BaseModel):
    cluster_id: str
    region: str
    residency_region: str
    allowed_policy_ids: list[str] = Field(default_factory=list)
    enforcement_local: bool = True


class PublishFederatedPolicyRequest(BaseModel):
    policy_id: str
    version: str
    artifact_payload: dict[str, Any] = Field(default_factory=dict)
    signing_key_id: str


class SyncFederatedPolicyRequest(BaseModel):
    cluster_id: str
    policy_id: str
    version: str


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


def _cluster_to_dict(cluster: FederatedCluster) -> dict[str, Any]:
    return {
        "cluster_id": cluster.cluster_id,
        "region": cluster.region,
        "residency_region": cluster.residency_region,
        "allowed_policy_ids": list(cluster.allowed_policy_ids),
        "enforcement_local": cluster.enforcement_local,
    }


def _reject_tenant_data_fields(payload: Any) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).strip().lower() in _TENANT_DATA_KEYS:
                raise ValueError("policy sync payload must not include tenant data")
            _reject_tenant_data_fields(value)
    elif isinstance(payload, list):
        for item in payload:
            _reject_tenant_data_fields(item)


@router.get("/api/v1/federation/summary")
def federation_summary() -> dict[str, Any]:
    """Return a read-only federated control-plane summary."""
    return {
        "summary": _FEDERATION.summary(),
        "witness": _FEDERATION_WITNESS,
        "read_only": True,
        "governed": True,
    }


@router.post("/api/v1/federation/clusters")
def register_federated_cluster(
    req: RegisterFederatedClusterRequest,
    _: str = Depends(require_admin),
) -> dict[str, Any]:
    """Register a regional cluster for metadata-only policy sync."""
    deps.metrics.inc("requests_governed")
    try:
        cluster = _FEDERATION.register_cluster(
            FederatedCluster(
                cluster_id=req.cluster_id,
                region=req.region,
                residency_region=req.residency_region,
                allowed_policy_ids=tuple(req.allowed_policy_ids),
                enforcement_local=req.enforcement_local,
            )
        )
    except ValueError as exc:
        raise HTTPException(400, detail={
            "error": "federated cluster registration failed",
            "error_code": "federated_cluster_registration_failed",
            "governed": True,
        }) from exc
    deps.audit_trail.record(
        action="federation.cluster.register",
        actor_id="api",
        tenant_id="federation",
        target=cluster.cluster_id,
        outcome="success",
        detail={"region": cluster.region, "residency_region": cluster.residency_region},
    )
    return {"cluster": _cluster_to_dict(cluster), "governed": True}


@router.post("/api/v1/federation/policies")
def publish_federated_policy(
    req: PublishFederatedPolicyRequest,
    _: str = Depends(require_admin),
) -> dict[str, Any]:
    """Publish signed policy metadata for regional sync."""
    deps.metrics.inc("requests_governed")
    try:
        _reject_tenant_data_fields(req.artifact_payload)
        bundle = _FEDERATION.publish_policy(
            FederatedPolicyBundle.create(
                policy_id=req.policy_id,
                version=req.version,
                artifact_payload=req.artifact_payload,
                signing_key_id=req.signing_key_id,
            )
        )
    except ValueError as exc:
        raise HTTPException(400, detail={
            "error": "federated policy publication failed",
            "error_code": "federated_policy_publication_failed",
            "governed": True,
        }) from exc
    deps.audit_trail.record(
        action="federation.policy.publish",
        actor_id="api",
        tenant_id="federation",
        target=f"{bundle.policy_id}:{bundle.version}",
        outcome="success",
        detail={"artifact_hash": bundle.artifact_hash, "signing_key_id": bundle.signing_key_id},
    )
    return {"policy": bundle.to_dict(), "tenant_data_replicated": False, "governed": True}


@router.post("/api/v1/federation/policy-sync")
def sync_federated_policy(
    req: SyncFederatedPolicyRequest,
    _: str = Depends(require_admin),
) -> dict[str, Any]:
    """Sync signed policy metadata to a registered regional cluster."""
    deps.metrics.inc("requests_governed")
    try:
        receipt = _FEDERATION.sync_policy(
            cluster_id=req.cluster_id,
            policy_id=req.policy_id,
            version=req.version,
        )
    except ValueError as exc:
        raise HTTPException(400, detail={
            "error": "federated policy sync failed",
            "error_code": "federated_policy_sync_failed",
            "governed": True,
        }) from exc
    receipt_payload = receipt.to_dict()
    deps.audit_trail.record(
        action="federation.policy.sync",
        actor_id="api",
        tenant_id="federation",
        target=f"{req.cluster_id}:{req.policy_id}:{req.version}",
        outcome="success" if receipt.accepted else "denied",
        detail={
            "accepted": receipt.accepted,
            "reason_codes": list(receipt.reason_codes),
            "tenant_data_replicated": receipt.tenant_data_replicated,
        },
    )
    return {"sync_receipt": receipt_payload, "governed": True}
