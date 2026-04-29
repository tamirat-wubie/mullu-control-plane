# Authority Directory Sync

Purpose: define the bounded import contract that maps external organization
directories into the gateway authority-obligation mesh.

Governance scope: ownership bindings, approval policies, escalation policies,
tenant identity roles, read-model witnesses, and runtime conformance evidence.

Dependencies: `gateway/tenant_identity.py`,
`gateway/authority_obligation_mesh.py`, `/authority/ownership`,
`/authority/policies`, `/authority/approval-chains`, `/authority/obligations`,
and `/runtime/conformance`.

Invariants:

1. No imported person, team, role, owner, approver, or escalation target is
   trusted without source evidence.
2. No external directory import may delete the last owner of a high-risk
   capability.
3. No import may weaken an approval policy without a governed change command.
4. No imported approval policy may allow sole self-approval for high-risk
   world-mutating actions.
5. No accepted-risk or compensated closure may rely on a fallback synthetic
   owner.
6. Every import batch has a deterministic hash and replayable source refs.
7. Runtime conformance must expose whether ownership and policy read models are
   live after sync.

## Directory Sources

The sync contract is provider-neutral. SCIM, SAML group export, LDAP export,
GitHub teams, Google Workspace groups, and static YAML are source adapters, not
authority by themselves.

Each source adapter must emit a normalized batch:

```json
{
  "batch_id": "directory-batch-...",
  "tenant_id": "tenant-1",
  "source_system": "scim",
  "source_ref": "scim://example/export/2026-04-29T12:00:00Z",
  "source_hash": "sha256:...",
  "people": [],
  "teams": [],
  "role_assignments": [],
  "ownership_bindings": [],
  "approval_policies": [],
  "escalation_policies": []
}
```

## Import Targets

| Imported object | Runtime target |
|---|---|
| Person identity | `TenantMapping.identity_id` and role metadata |
| Team membership | authority policy and ownership lookup input |
| Resource ownership | `TeamOwnership` |
| Approval rule | `ApprovalPolicy` |
| Escalation route | `EscalationPolicy` |
| Operator role | tenant identity roles such as `authority_operator` |

## Minimal Import Algorithm

1. Parse the source adapter output as structured data.
2. Validate `tenant_id`, `source_system`, `source_ref`, and `source_hash`.
3. Canonicalize records without renaming people, teams, roles, or resources.
4. Reject duplicate primary keys within the same batch.
5. Simulate the batch against current authority state.
6. Reject policy weakening unless the batch carries governed change evidence.
7. Reject high-risk ownership removal that would leave no explicit owner.
8. Persist accepted records through existing authority stores.
9. Emit a directory sync receipt containing applied counts and rejected records.
10. Optionally write the normalized batch as a replayable review artifact.
11. Verify `/authority/ownership`, `/authority/policies`, and
    `/runtime/conformance` after import.

## Required Receipt

```json
{
  "receipt_id": "authority-directory-sync-...",
  "tenant_id": "tenant-1",
  "batch_id": "directory-batch-...",
  "source_ref": "scim://example/export/...",
  "source_hash": "sha256:...",
  "applied_ownership_count": 0,
  "applied_approval_policy_count": 0,
  "applied_escalation_policy_count": 0,
  "rejected_record_count": 0,
  "apply_mode": "dry_run",
  "persisted": false,
  "evidence_refs": [
    "authority:ownership_read_model",
    "authority:policy_read_model",
    "runtime_conformance:authority_configuration"
  ]
}
```

## Static Adapter

`scripts/sync_authority_directory.py` implements the first bounded source
adapter for JSON and a deliberately small YAML subset.

Dry-run mode writes a receipt without mutating authority state:

```bash
python scripts/sync_authority_directory.py authority-directory.yaml
```

Replay mode also writes the normalized batch:

```bash
python scripts/sync_authority_directory.py authority-directory.yaml \
  --batch-output .change_assurance/authority_directory_batch.json
```

Apply mode persists accepted records through the authority-obligation mesh store
and marks the receipt as persisted:

```bash
python scripts/sync_authority_directory.py authority-directory.yaml --apply
```

## SCIM Export Adapter

`scripts/scim_authority_directory_adapter.py` implements the first external
source wrapper. It accepts a bounded SCIM JSON export plus a separate authority
mapping JSON file and emits the normalized directory JSON consumed by the static
sync adapter.

SCIM user and group records are identity evidence only. They do not become
owners, approvers, approval policies, or escalation routes unless the mapping
file explicitly declares those authority relationships.

```bash
python scripts/scim_authority_directory_adapter.py \
  --tenant-id tenant-1 \
  --scim-export scim-export.json \
  --mapping authority-mapping.json \
  --output .change_assurance/authority_directory_from_scim.json
```

The resulting JSON can then be reviewed, dry-run, replayed, or applied through:

```bash
python scripts/sync_authority_directory.py \
  .change_assurance/authority_directory_from_scim.json \
  --batch-output .change_assurance/authority_directory_batch.json
```

## Prohibitions

1. No implicit team creation from free-form labels.
2. No role elevation from display names.
3. No deletion-only batch without a replacement owner plan.
4. No source adapter may write directly to the command ledger.
5. No directory sync may bypass authority operator protection.
6. No imported policy may hide from `/authority/policies`.
7. No imported ownership binding may hide from `/authority/ownership`.

## Runtime Status

The repository exposes the authority configuration read models, binds them into
runtime conformance, includes a static JSON / bounded-YAML adapter that emits
normalized batches and receipts, and includes a SCIM-export wrapper that emits
the same normalized contract. Live SCIM API polling, LDAP, SAML-group,
GitHub-team, and workspace-directory adapters remain a future implementation
layer.

STATUS:
  Completeness: 100%
  Invariants verified: source evidence required, no fabricated org data, explicit ownership required, duplicate records rejected, bounded parser failures, SCIM identity evidence separated from authority mappings, read-model verification required
  Open issues: live SCIM API polling, LDAP, SAML-group, GitHub-team, and workspace-directory adapters not implemented
  Next action: wire live SCIM API polling through the SCIM export adapter contract
