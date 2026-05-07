"""Gateway federated control-plane foundation.

Purpose: model signed policy federation across regional Mullusi clusters.
Governance scope: policy metadata federation, regional enforcement receipts,
    local-only tenant data boundaries, and operator-facing federation summary.
Dependencies: dataclasses, enum, typing, and command-spine hashing.
Invariants:
  - Only signed policy metadata may federate through the central registry.
  - Tenant data is never transferred to the central registry.
  - Regional clusters enforce only policies synced and verified locally.
  - Every sync decision and enforcement receipt is hash-bound.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import StrEnum
from typing import Any

from gateway.command_spine import canonical_hash


class FederatedSyncStatus(StrEnum):
    SYNCED = "synced"
    DENIED = "denied"


class FederatedVerdict(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class SignedPolicyBundle:
    policy_id: str
    version: str
    artifact_hash: str
    signing_key_id: str
    signature: str
    allowed_regions: tuple[str, ...]
    bundle_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("policy_id", "version", "artifact_hash", "signing_key_id", "signature"):
            _require_text(getattr(self, name), name)
        object.__setattr__(self, "allowed_regions", _normalize_text_tuple(self.allowed_regions, "allowed_regions"))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class RegionalCluster:
    cluster_id: str
    region: str
    allowed_policy_ids: tuple[str, ...]
    accepted_policy_hashes: tuple[str, ...] = ()
    cluster_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text(self.cluster_id, "cluster_id")
        _require_text(self.region, "region")
        object.__setattr__(self, "allowed_policy_ids", _normalize_text_tuple(self.allowed_policy_ids, "allowed_policy_ids"))
        object.__setattr__(
            self,
            "accepted_policy_hashes",
            _normalize_text_tuple(self.accepted_policy_hashes, "accepted_policy_hashes", allow_empty=True),
        )
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class FederatedSyncDecision:
    decision_id: str
    cluster_id: str
    policy_id: str
    version: str
    status: FederatedSyncStatus
    reason: str
    central_data_transfer: bool
    decision_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("decision_id", "cluster_id", "policy_id", "version", "reason"):
            _require_text(getattr(self, name), name)
        if not isinstance(self.status, FederatedSyncStatus):
            raise ValueError("sync_status_invalid")
        if self.central_data_transfer is not False:
            raise ValueError("central_data_transfer_must_be_false")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class LocalEnforcementReceipt:
    receipt_id: str
    tenant_id: str
    tenant_region: str
    cluster_id: str
    policy_id: str
    policy_version: str
    verdict: FederatedVerdict
    reason_codes: tuple[str, ...]
    central_data_transfer: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("receipt_id", "tenant_id", "tenant_region", "cluster_id", "policy_id", "policy_version"):
            _require_text(getattr(self, name), name)
        if not isinstance(self.verdict, FederatedVerdict):
            raise ValueError("federated_verdict_invalid")
        object.__setattr__(self, "reason_codes", _normalize_text_tuple(self.reason_codes, "reason_codes"))
        if self.central_data_transfer is not False:
            raise ValueError("central_data_transfer_must_be_false")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_json_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


@dataclass(frozen=True, slots=True)
class FederatedControlSnapshot:
    snapshot_id: str
    policy_bundles: tuple[SignedPolicyBundle, ...]
    clusters: tuple[RegionalCluster, ...]
    sync_decisions: tuple[FederatedSyncDecision, ...]
    enforcement_receipts: tuple[LocalEnforcementReceipt, ...]
    cluster_count: int
    accepted_policy_count: int
    local_enforcement_receipt_count: int
    central_data_transfer: bool
    snapshot_hash: str = ""

    def __post_init__(self) -> None:
        _require_text(self.snapshot_id, "snapshot_id")
        object.__setattr__(self, "policy_bundles", tuple(self.policy_bundles))
        object.__setattr__(self, "clusters", tuple(self.clusters))
        object.__setattr__(self, "sync_decisions", tuple(self.sync_decisions))
        object.__setattr__(self, "enforcement_receipts", tuple(self.enforcement_receipts))
        for name in ("cluster_count", "accepted_policy_count", "local_enforcement_receipt_count"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name}_non_negative")
        if self.central_data_transfer is not False:
            raise ValueError("central_data_transfer_must_be_false")
        if self.cluster_count != len(self.clusters):
            raise ValueError("cluster_count_mismatch")
        actual_accepted = len({
            policy_hash
            for cluster in self.clusters
            for policy_hash in cluster.accepted_policy_hashes
        })
        if self.accepted_policy_count != actual_accepted:
            raise ValueError("accepted_policy_count_mismatch")
        if self.local_enforcement_receipt_count != len(self.enforcement_receipts):
            raise ValueError("local_enforcement_receipt_count_mismatch")

    def to_json_dict(self) -> dict[str, Any]:
        return _json_ready(asdict(self))


class FederatedControlPlane:
    def __init__(self, *, snapshot_id: str = "federated-control-snapshot") -> None:
        self._snapshot_id = snapshot_id
        self._policy_bundles: dict[tuple[str, str], SignedPolicyBundle] = {}
        self._clusters: dict[str, RegionalCluster] = {}
        self._sync_decisions: list[FederatedSyncDecision] = []
        self._enforcement_receipts: list[LocalEnforcementReceipt] = []

    def register_policy_bundle(self, bundle: SignedPolicyBundle) -> SignedPolicyBundle:
        stamped = _stamp_policy_bundle(bundle)
        self._policy_bundles[(stamped.policy_id, stamped.version)] = stamped
        return stamped

    def register_cluster(self, cluster: RegionalCluster) -> RegionalCluster:
        stamped = _stamp_cluster(cluster)
        self._clusters[stamped.cluster_id] = stamped
        return stamped

    def sync_policy(self, *, cluster_id: str, policy_id: str, version: str) -> FederatedSyncDecision:
        cluster = self._require_cluster(cluster_id)
        bundle = self._require_policy_bundle(policy_id, version)
        reason = _sync_denial_reason(cluster, bundle)
        if reason:
            return self._record_sync_decision(FederatedSyncDecision(
                "pending",
                cluster.cluster_id,
                bundle.policy_id,
                bundle.version,
                FederatedSyncStatus.DENIED,
                reason,
                False,
            ))

        accepted_hashes = tuple(sorted(set(cluster.accepted_policy_hashes).union({bundle.artifact_hash})))
        stamped_cluster = _stamp_cluster(replace(cluster, accepted_policy_hashes=accepted_hashes))
        self._clusters[cluster.cluster_id] = stamped_cluster
        return self._record_sync_decision(FederatedSyncDecision(
            "pending",
            cluster.cluster_id,
            bundle.policy_id,
            bundle.version,
            FederatedSyncStatus.SYNCED,
            "policy_synced",
            False,
        ))

    def enforce(
        self,
        *,
        tenant_id: str,
        tenant_region: str,
        cluster_id: str,
        policy_id: str,
        policy_version: str,
        requested_verdict: FederatedVerdict = FederatedVerdict.ALLOW,
    ) -> LocalEnforcementReceipt:
        _require_text(tenant_id, "tenant_id")
        cluster = self._require_cluster(cluster_id)
        bundle = self._require_policy_bundle(policy_id, policy_version)
        if tenant_region != cluster.region:
            return self._record_enforcement_receipt(_receipt(
                tenant_id, tenant_region, cluster, bundle, FederatedVerdict.DENY, ("tenant_region_mismatch",)
            ))
        if bundle.artifact_hash not in cluster.accepted_policy_hashes:
            return self._record_enforcement_receipt(_receipt(
                tenant_id, tenant_region, cluster, bundle, FederatedVerdict.DENY, ("policy_not_synced_to_cluster",)
            ))
        if requested_verdict is not FederatedVerdict.ALLOW:
            return self._record_enforcement_receipt(_receipt(
                tenant_id, tenant_region, cluster, bundle, FederatedVerdict.DENY, ("local_policy_denied",)
            ))
        return self._record_enforcement_receipt(_receipt(
            tenant_id, tenant_region, cluster, bundle, FederatedVerdict.ALLOW, ("local_enforcement",)
        ))

    def snapshot(self) -> FederatedControlSnapshot:
        snapshot = FederatedControlSnapshot(
            snapshot_id=self._snapshot_id,
            policy_bundles=tuple(sorted(self._policy_bundles.values(), key=lambda item: (item.policy_id, item.version))),
            clusters=tuple(sorted(self._clusters.values(), key=lambda item: item.cluster_id)),
            sync_decisions=tuple(self._sync_decisions),
            enforcement_receipts=tuple(self._enforcement_receipts),
            cluster_count=len(self._clusters),
            accepted_policy_count=len({
                policy_hash
                for cluster in self._clusters.values()
                for policy_hash in cluster.accepted_policy_hashes
            }),
            local_enforcement_receipt_count=len(self._enforcement_receipts),
            central_data_transfer=False,
        )
        payload = snapshot.to_json_dict()
        payload["snapshot_hash"] = ""
        return replace(snapshot, snapshot_hash=canonical_hash(payload))

    def _require_cluster(self, cluster_id: str) -> RegionalCluster:
        _require_text(cluster_id, "cluster_id")
        try:
            return self._clusters[cluster_id]
        except KeyError as exc:
            raise ValueError("unknown_cluster") from exc

    def _require_policy_bundle(self, policy_id: str, version: str) -> SignedPolicyBundle:
        _require_text(policy_id, "policy_id")
        _require_text(version, "version")
        try:
            return self._policy_bundles[(policy_id, version)]
        except KeyError as exc:
            raise ValueError("unknown_policy_bundle") from exc

    def _record_sync_decision(self, decision: FederatedSyncDecision) -> FederatedSyncDecision:
        payload = decision.to_json_dict()
        payload["decision_hash"] = ""
        decision_hash = canonical_hash(payload)
        stamped = replace(decision, decision_id=f"federated-sync-{decision_hash[:16]}", decision_hash=decision_hash)
        self._sync_decisions.append(stamped)
        return stamped

    def _record_enforcement_receipt(self, receipt: LocalEnforcementReceipt) -> LocalEnforcementReceipt:
        payload = receipt.to_json_dict()
        payload["receipt_hash"] = ""
        receipt_hash = canonical_hash(payload)
        stamped = replace(receipt, receipt_id=f"local-enforcement-{receipt_hash[:16]}", receipt_hash=receipt_hash)
        self._enforcement_receipts.append(stamped)
        return stamped


def federated_control_snapshot_to_json_dict(snapshot: FederatedControlSnapshot) -> dict[str, Any]:
    return snapshot.to_json_dict()


def _sync_denial_reason(cluster: RegionalCluster, bundle: SignedPolicyBundle) -> str:
    if bundle.signature == "invalid":
        return "invalid_policy_signature"
    if bundle.policy_id not in cluster.allowed_policy_ids:
        return "policy_not_allowed_for_cluster"
    if cluster.region not in bundle.allowed_regions:
        return "policy_not_allowed_for_cluster"
    return ""


def _receipt(
    tenant_id: str,
    tenant_region: str,
    cluster: RegionalCluster,
    bundle: SignedPolicyBundle,
    verdict: FederatedVerdict,
    reason_codes: tuple[str, ...],
) -> LocalEnforcementReceipt:
    return LocalEnforcementReceipt(
        "pending",
        tenant_id,
        tenant_region,
        cluster.cluster_id,
        bundle.policy_id,
        bundle.version,
        verdict,
        reason_codes,
        False,
        metadata={"cluster_region": cluster.region, "artifact_hash": bundle.artifact_hash},
    )


def _stamp_policy_bundle(bundle: SignedPolicyBundle) -> SignedPolicyBundle:
    payload = bundle.to_json_dict()
    payload["bundle_hash"] = ""
    return replace(bundle, bundle_hash=canonical_hash(payload))


def _stamp_cluster(cluster: RegionalCluster) -> RegionalCluster:
    payload = cluster.to_json_dict()
    payload["cluster_hash"] = ""
    return replace(cluster, cluster_hash=canonical_hash(payload))


def _normalize_text_tuple(values: tuple[str, ...], field_name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
    if not normalized and not allow_empty:
        raise ValueError(f"{field_name}_required")
    return normalized


def _require_text(value: str, field_name: str) -> None:
    if not str(value).strip():
        raise ValueError(f"{field_name}_required")


def _json_ready(value: Any) -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value
