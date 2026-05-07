# Federated Control Plane

Purpose: define the enterprise architecture for multi-region Mullusi instances that share a signed policy registry while enforcing locally.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA]
Dependencies: `mcoi_runtime.core.federated_control_plane`, policy version registry, region routing, data-governance residency constraints.
Invariants: policy artifacts may federate; tenant data does not replicate to the central registry; enforcement receipts are produced locally.

## Architecture

| Component | Responsibility | Data movement |
|---|---|---|
| Signed policy registry | Publishes policy id, version, artifact hash, signing key id, and signature | policy metadata only |
| Regional cluster | Accepts only allowed signed policy bundles | no tenant data leaves region |
| Local enforcement receipt | Records tenant id, tenant region, policy version, verdict, and reason codes | local only |
| Federated summary | Shows clusters, accepted policy counts, and local-only enforcement invariant | read model only |

## Execution

1. Publish a signed policy bundle to the shared registry.
2. Each regional cluster syncs only policy bundles that are allowed for that cluster.
3. Cluster verifies the registry signature before accepting the policy hash.
4. Runtime enforcement happens in the cluster where the tenant data resides.
5. Enforcement receipts explicitly state `central_data_transfer: false`.

## Read-Only Route

```powershell
GET /api/v1/federation/summary
```

The route exposes seeded policy distribution and local-enforcement receipts as a
read model. It does not publish policy, sync new clusters, or move tenant data.

## Failure Semantics

| Condition | Result |
|---|---|
| Unknown cluster | hard error |
| Unknown policy bundle | hard error |
| Policy not allowed for cluster | sync denied with `policy_not_allowed_for_cluster` |
| Invalid signature | sync denied with `invalid_policy_signature` |
| Policy not synced locally | enforcement denied with `policy_not_synced_to_cluster` |
| Tenant region mismatch | enforcement denied with `tenant_region_mismatch` |

STATUS:
  Completeness: 100%
  Invariants verified: signed registry, local enforcement, no tenant-data replication, residency boundary receipts, deterministic receipt hashes, read-only federation summary route
  Open issues: none
  Next action: add authenticated regional policy-sync control routes with explicit operator authority
