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

## Operator Procedure

Use this sequence when an environment imports MCP tools through a manifest.
The machine-readable handoff checklist is
`examples/mcp_operator_handoff_checklist.json`; validate it with:

```powershell
python scripts\validate_mcp_operator_checklist.py --checklist examples\mcp_operator_handoff_checklist.json --json
```

1. Validate the manifest before startup.

```powershell
python scripts\validate_mcp_capability_manifest.py --manifest examples\mcp_capability_manifest.json --json
```

Required evidence:

| Field | Expected |
| --- | --- |
| `valid` | `true` |
| `capability_count` | Greater than `0` |
| `ownership_count` | Equal to `capability_count` |
| `approval_policy_count` | Equal to `capability_count` |
| `escalation_policy_count` | Greater than `0` |

2. Start the gateway with the same manifest path.

```powershell
$env:MULLU_MCP_CAPABILITY_MANIFEST_PATH = "examples\mcp_capability_manifest.json"
python -m gateway.server
```

3. Inspect the operator read model.

```powershell
curl -H "X-Mullu-Authority-Secret: $env:MULLU_AUTHORITY_OPERATOR_SECRET" `
  "http://localhost:8001/mcp/operator/read-model?audit_limit=25"
```

Required read-model evidence:

| Field | Expected |
| --- | --- |
| `mcp_manifest_configured` | `true` |
| `mcp_manifest_valid` | `true` |
| `mcp_manifest_ref` | File URI for the configured manifest |
| `mcp_manifest_capability_count` | Same count as validator output |
| `ownership_count` | At least the imported MCP capability count |
| `approval_policy_count` | At least the imported MCP capability count |

4. Check runtime conformance.

```powershell
python scripts\collect_runtime_conformance.py `
  --gateway-url "$env:MULLU_GATEWAY_URL" `
  --conformance-secret "$env:MULLU_RUNTIME_CONFORMANCE_SECRET" `
  --authority-operator-secret "$env:MULLU_AUTHORITY_OPERATOR_SECRET" `
  --expected-environment pilot
```

Required signed certificate evidence:

| Field | Expected |
| --- | --- |
| `mcp_capability_manifest_configured` | `true` |
| `mcp_capability_manifest_valid` | `true` |
| `mcp_capability_manifest_capability_count` | Same count as validator output |
| `capability_plan_bundle_canary_passed` | `true` |
| `open_conformance_gaps` | Must not include `mcp_capability_manifest_invalid` |

5. Run deployment witness preflight before dispatch.

```powershell
python scripts\preflight_deployment_witness.py `
  --gateway-host "$env:MULLU_GATEWAY_HOST" `
  --expected-environment pilot `
  --mcp-capability-manifest examples\mcp_capability_manifest.json
```

The preflight must include a passing `mcp capability manifest` step and a passing
`runtime conformance endpoint` step. If the configured manifest is invalid, both
preflight readiness and deployment witness publication remain blocked.

6. Require the MCP handoff checklist during orchestration.

```powershell
python scripts\orchestrate_deployment_witness.py `
  --gateway-host "$env:MULLU_GATEWAY_HOST" `
  --expected-environment pilot `
  --require-mcp-operator-checklist `
  --require-preflight `
  --orchestration-output "$env:MULLU_DEPLOYMENT_ORCHESTRATION_OUTPUT"
```

The orchestration receipt must include `mcp_operator_checklist_required=true`,
`mcp_operator_checklist_valid=true`, and the
`mcp_operator_checklist:valid:true` evidence reference.

7. Persist the deployment orchestration receipt.

```powershell
python scripts\orchestrate_deployment_witness.py `
  --gateway-host "$env:MULLU_GATEWAY_HOST" `
  --expected-environment pilot `
  --require-preflight `
  --orchestration-output "$env:MULLU_DEPLOYMENT_ORCHESTRATION_OUTPUT"
```

Required receipt evidence:

| Field | Expected |
| --- | --- |
| `receipt_id` | Starts with `deployment-witness-orchestration-` |
| `mcp_operator_checklist_required` | `true` when the checklist gate is required |
| `mcp_operator_checklist_valid` | `true` when the checklist artifact passed validation |
| `preflight_required` | `true` |
| `preflight_ready` | `true` |
| `evidence_refs` | Non-empty |

## Failure Handling

| Failure | Cause | Required action |
| --- | --- | --- |
| `MCP manifest requires at least one tool` | Empty `tools` list | Add at least one tool declaration |
| `MCP manifest requires a configured string field` | Missing tenant, owner, escalation, certification, or tool string | Fill the required field and re-run validation |
| `mcp_capability_manifest_invalid` | Runtime conformance rejected the configured manifest | Fix manifest, restart gateway, collect conformance again |
| `mcp_manifest_valid=false` in deployment witness | Signed conformance says the manifest is invalid | Do not dispatch deployment witness until conformance is clean |
| `mcp_manifest_configured=false` in read model | Gateway was not started with `MULLU_MCP_CAPABILITY_MANIFEST_PATH` | Set the environment variable and restart |
| `capability_plan_bundle_canary_passed=false` | Runtime conformance cannot export a plan evidence bundle | Keep deployment blocked until `/capability-plans/{plan_id}/closure` returns `plan_evidence_bundle` |

STATUS:
  Completeness: 100%
  Invariants verified: [certified import, ownership binding, approval policy, escalation policy, startup binding, operator read model, runtime conformance witness, capability plan evidence bundle canary, deployment preflight gate, machine-readable handoff checklist, deployment orchestration receipt]
  Open issues: none
  Next action: publish an environment-specific manifest and collect signed conformance evidence
