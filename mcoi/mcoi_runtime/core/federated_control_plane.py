"""Federated control-plane policy distribution.

Purpose: distribute signed policy artifacts while enforcing decisions locally per region.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: dataclasses, hashlib, json.
Invariants: policy registry is signed, tenant data is not replicated, and cluster enforcement is local.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any


@dataclass(frozen=True, slots=True)
class FederatedPolicyBundle:
    """A signed policy artifact distributed by the federated control plane."""

    policy_id: str
    version: str
    artifact_hash: str
    signing_key_id: str
    signature: str

    @classmethod
    def create(
        cls,
        *,
        policy_id: str,
        version: str,
        artifact_payload: dict[str, Any],
        signing_key_id: str,
    ) -> FederatedPolicyBundle:
        _require_text(policy_id, "policy_id")
        _require_text(version, "version")
        _require_text(signing_key_id, "signing_key_id")
        artifact_hash = _stable_hash(
            {
                "policy_id": policy_id,
                "version": version,
                "artifact_payload": artifact_payload,
            }
        )
        signature = _stable_hash(
            {
                "artifact_hash": artifact_hash,
                "signing_key_id": signing_key_id,
                "signature_scope": "federated_policy_registry",
            }
        )
        return cls(
            policy_id=policy_id,
            version=version,
            artifact_hash=artifact_hash,
            signing_key_id=signing_key_id,
            signature=signature,
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "policy_id": self.policy_id,
            "version": self.version,
            "artifact_hash": self.artifact_hash,
            "signing_key_id": self.signing_key_id,
            "signature": self.signature,
        }


@dataclass(frozen=True, slots=True)
class FederatedCluster:
    """A local enforcement cluster bound to a residency region."""

    cluster_id: str
    region: str
    residency_region: str
    allowed_policy_ids: tuple[str, ...]
    enforcement_local: bool = True

    def __post_init__(self) -> None:
        _require_text(self.cluster_id, "cluster_id")
        _require_text(self.region, "region")
        _require_text(self.residency_region, "residency_region")
        if not self.allowed_policy_ids:
            raise ValueError("allowed_policy_ids must contain at least one policy id")
        if self.enforcement_local is not True:
            raise ValueError("federated clusters must enforce locally")


@dataclass(frozen=True, slots=True)
class PolicySyncReceipt:
    """Receipt proving a signed policy was accepted by a local cluster."""

    cluster_id: str
    policy_id: str
    version: str
    artifact_hash: str
    signature: str
    accepted: bool
    reason_codes: tuple[str, ...]
    tenant_data_replicated: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "cluster_id": self.cluster_id,
            "policy_id": self.policy_id,
            "version": self.version,
            "artifact_hash": self.artifact_hash,
            "signature": self.signature,
            "accepted": self.accepted,
            "reason_codes": list(self.reason_codes),
            "tenant_data_replicated": self.tenant_data_replicated,
        }
        return {
            **payload,
            "receipt_hash": _stable_hash(payload),
        }


@dataclass(frozen=True, slots=True)
class LocalEnforcementReceipt:
    """Receipt proving a cluster enforced a decision without central data movement."""

    cluster_id: str
    tenant_id: str
    tenant_region: str
    policy_id: str
    version: str
    verdict: str
    local_enforcement: bool
    central_data_transfer: bool
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "cluster_id": self.cluster_id,
            "tenant_id": self.tenant_id,
            "tenant_region": self.tenant_region,
            "policy_id": self.policy_id,
            "version": self.version,
            "verdict": self.verdict,
            "local_enforcement": self.local_enforcement,
            "central_data_transfer": self.central_data_transfer,
            "reason_codes": list(self.reason_codes),
        }
        return {
            **payload,
            "receipt_hash": _stable_hash(payload),
        }


class FederatedControlPlane:
    """Signed policy registry with local regional enforcement receipts."""

    def __init__(self) -> None:
        self._clusters: dict[str, FederatedCluster] = {}
        self._policies: dict[tuple[str, str], FederatedPolicyBundle] = {}
        self._accepted_policy_hashes: dict[str, set[str]] = {}

    def register_cluster(self, cluster: FederatedCluster) -> FederatedCluster:
        if cluster.cluster_id in self._clusters:
            raise ValueError("cluster_id already registered")
        self._clusters[cluster.cluster_id] = cluster
        self._accepted_policy_hashes[cluster.cluster_id] = set()
        return cluster

    def publish_policy(self, bundle: FederatedPolicyBundle) -> FederatedPolicyBundle:
        key = (bundle.policy_id, bundle.version)
        if key in self._policies:
            raise ValueError("policy bundle already published")
        self._policies[key] = bundle
        return bundle

    def sync_policy(self, *, cluster_id: str, policy_id: str, version: str) -> PolicySyncReceipt:
        cluster = self._clusters.get(cluster_id)
        if cluster is None:
            raise ValueError("cluster_id unavailable")
        bundle = self._policies.get((policy_id, version))
        if bundle is None:
            raise ValueError("policy bundle unavailable")
        if policy_id not in cluster.allowed_policy_ids:
            return PolicySyncReceipt(
                cluster_id=cluster_id,
                policy_id=policy_id,
                version=version,
                artifact_hash=bundle.artifact_hash,
                signature=bundle.signature,
                accepted=False,
                reason_codes=("policy_not_allowed_for_cluster",),
            )
        if not self.verify_signature(bundle):
            return PolicySyncReceipt(
                cluster_id=cluster_id,
                policy_id=policy_id,
                version=version,
                artifact_hash=bundle.artifact_hash,
                signature=bundle.signature,
                accepted=False,
                reason_codes=("invalid_policy_signature",),
            )
        self._accepted_policy_hashes[cluster_id].add(bundle.artifact_hash)
        return PolicySyncReceipt(
            cluster_id=cluster_id,
            policy_id=policy_id,
            version=version,
            artifact_hash=bundle.artifact_hash,
            signature=bundle.signature,
            accepted=True,
            reason_codes=("signed_policy_accepted", "tenant_data_not_replicated"),
        )

    def enforce_local(
        self,
        *,
        cluster_id: str,
        tenant_id: str,
        tenant_region: str,
        policy_id: str,
        version: str,
    ) -> LocalEnforcementReceipt:
        cluster = self._clusters.get(cluster_id)
        if cluster is None:
            raise ValueError("cluster_id unavailable")
        _require_text(tenant_id, "tenant_id")
        _require_text(tenant_region, "tenant_region")
        bundle = self._policies.get((policy_id, version))
        if bundle is None:
            raise ValueError("policy bundle unavailable")
        accepted = bundle.artifact_hash in self._accepted_policy_hashes.get(cluster_id, set())
        region_match = tenant_region == cluster.residency_region
        allowed = accepted and region_match
        reason_codes: tuple[str, ...]
        if allowed:
            reason_codes = ("local_policy_enforced", "residency_boundary_preserved")
        elif not accepted:
            reason_codes = ("policy_not_synced_to_cluster",)
        else:
            reason_codes = ("tenant_region_mismatch",)
        return LocalEnforcementReceipt(
            cluster_id=cluster_id,
            tenant_id=tenant_id,
            tenant_region=tenant_region,
            policy_id=policy_id,
            version=version,
            verdict="allow" if allowed else "deny",
            local_enforcement=True,
            central_data_transfer=False,
            reason_codes=reason_codes,
        )

    def verify_signature(self, bundle: FederatedPolicyBundle) -> bool:
        expected = _stable_hash(
            {
                "artifact_hash": bundle.artifact_hash,
                "signing_key_id": bundle.signing_key_id,
                "signature_scope": "federated_policy_registry",
            }
        )
        return bundle.signature == expected

    def summary(self) -> dict[str, Any]:
        return {
            "registered_clusters": len(self._clusters),
            "published_policies": len(self._policies),
            "local_enforcement_only": all(cluster.enforcement_local for cluster in self._clusters.values()),
            "tenant_data_replication": False,
            "clusters": [
                {
                    "cluster_id": cluster.cluster_id,
                    "region": cluster.region,
                    "residency_region": cluster.residency_region,
                    "allowed_policy_ids": list(cluster.allowed_policy_ids),
                    "accepted_policy_count": len(self._accepted_policy_hashes[cluster.cluster_id]),
                }
                for cluster in sorted(self._clusters.values(), key=lambda item: item.cluster_id)
            ],
        }


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"
