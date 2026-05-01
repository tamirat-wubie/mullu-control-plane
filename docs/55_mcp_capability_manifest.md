# MCP Capability Manifest

Purpose: define the operator-facing contract for importing MCP tools into the
gateway capability fabric with certified authority-obligation records.
Governance scope: MCP capability certification, command admission, team
ownership, approval policy, and escalation policy.
Dependencies: `gateway/mcp_capability_fabric.py`,
`scripts/validate_mcp_capability_manifest.py`, and
`examples/mcp_capability_manifest.json`.
Invariants:

1. No MCP tool is executable until the manifest produces a certified capability entry.
2. Every imported capability has an owner team, primary owner, fallback owner, and escalation team.
3. Every imported capability has an approval policy.
4. Every manifest import has an escalation policy.
5. Gateway startup reads the manifest only from `MULLU_MCP_CAPABILITY_MANIFEST_PATH`.

## Architecture

| Layer | Input | Output | Responsibility |
| --- | --- | --- | --- |
| Manifest | JSON file | MCP tool descriptors | Operator-declared tool boundary |
| Certification | `certified_by`, `certification_evidence_ref` | Certified capability entries | Import provenance |
| Admission | Certified entries | Command capability admission gate | Runtime dispatch permission |
| Authority mesh | Entries plus owners | Ownership, approval, escalation records | Organizational responsibility |
| Startup | `MULLU_MCP_CAPABILITY_MANIFEST_PATH` | Gateway state | Install admission and responsibility records |

## Manifest Fields

| Field | Required | Contract |
| --- | --- | --- |
| `tenant_id` | yes | Tenant that owns imported tools |
| `primary_owner_id` | yes | Person responsible for active capability ownership |
| `fallback_owner_id` | yes | Person used by escalation policy |
| `escalation_team` | yes | Team notified after unresolved approval or obligation |
| `certified_by` | yes | Operator or process that certified the import |
| `certification_evidence_ref` | yes | Evidence reference for import certification |
| `owner_team` | no | Default owner team for tools without tool-level owner |
| `timeout_seconds` | no | Positive approval timeout, default `300` |
| `capsule_id` | no | MCP domain capsule id, default `mcp.imported_tools.v0` |
| `tools` | yes | Non-empty list of MCP tool declarations |

Tool declarations require `server_id`, `name`, `description`, and
`input_schema`. Optional fields are `annotations`, `required_roles`,
`owner_team`, and `max_estimated_cost`.

## Algorithm

1. Load JSON manifest from `MULLU_MCP_CAPABILITY_MANIFEST_PATH`.
2. Convert each tool declaration into an MCP capability descriptor.
3. Stamp certification provenance onto every capability entry.
4. Build a certified MCP domain capsule and admission gate.
5. Build ownership, approval policy, and escalation records.
6. Install those authority records into the gateway authority-obligation mesh.
7. Expose imported capability state through `/mcp/operator/read-model`.

## Validation

Run the validator before setting the startup environment variable:

```powershell
python scripts\validate_mcp_capability_manifest.py --manifest examples\mcp_capability_manifest.json
```

Expected success output:

```text
mcp capability manifest ok capabilities=1 ownership=1 approval_policies=1
```

For machine-readable evidence:

```powershell
python scripts\validate_mcp_capability_manifest.py --manifest examples\mcp_capability_manifest.json --json
```

Deployment witness preflight also validates the same manifest when
`MULLU_MCP_CAPABILITY_MANIFEST_PATH` is set, or when the path is supplied
directly:

```powershell
python scripts\preflight_deployment_witness.py --gateway-host gateway.mullusi.com --mcp-capability-manifest examples\mcp_capability_manifest.json --skip-endpoint-probes
```

The preflight report includes an `mcp capability manifest` step. Deployment
readiness fails if the manifest cannot produce certified capabilities,
ownership records, approval policies, and an escalation policy.

## Startup

```powershell
$env:MULLU_MCP_CAPABILITY_MANIFEST_PATH = "examples\mcp_capability_manifest.json"
python -m gateway.server
```

If the manifest is present, startup installs:

1. Certified MCP capability entries.
2. A command admission gate for the MCP capsule.
3. Team ownership records.
4. Approval policies.
5. Escalation policy.

The manifest path cannot be combined with explicit MCP overrides or a separately
configured capability admission gate.

STATUS:
  Completeness: 100%
  Invariants verified: [certified import, ownership binding, approval policy, escalation policy, startup binding]
  Open issues: none
  Next action: validate and publish an environment-specific manifest
