# 33 - Governed Evolution Layer

## Purpose

The governed evolution layer makes changes to the platform first-class governed
objects. No code, schema, policy, capability, authority rule, provider behavior,
migration, deployment profile, or configuration change may enter production
unless it is represented as a `ChangeCommand` and certified by a
`ChangeCertificate`.

The layer answers: *what system law changed, what invariants could break, what
capabilities are affected, what replay scenarios must run, what rollback exists,
who approved the change, and what proof certifies the result?*

This layer governs evolution of the control plane itself. CI remains a tool
inside this layer; CI is not the owner of governance.

## Owned Artifacts

| Artifact | Role |
|---|---|
| `ChangeCommand` | Canonical command describing one proposed system evolution |
| `BlastRadiusReport` | Deterministic impact summary for affected files, contracts, capabilities, and invariants |
| `InvariantCheckReport` | Machine-checkable result for non-negotiable evolution laws |
| `ReplayCertificationReport` | Required replay scenarios, per-scenario outcomes, and failure reasons |
| `ChangeCertificate` | Release certificate binding all assurance evidence to one change |
| `.change_assurance/manifest.json` | Stable manifest hash for the emitted assurance bundle |

## Command Model

A `ChangeCommand` is derived from an explicit repository diff:

```bash
python scripts/certify_change.py --base HEAD --head current
```

Strict production certification requires approval and rollback evidence for
high-risk changes:

```bash
python scripts/certify_change.py \
  --base HEAD^ \
  --head HEAD \
  --strict \
  --approval-id ci-governance \
  --rollback-plan-ref RELEASE_CHECKLIST_v0.1.md
```

The command records:

| Field | Meaning |
|---|---|
| `change_id` | Stable identifier derived from base, head, changed files, and risk |
| `author_id` | Account responsible for the change |
| `branch` | Git branch carrying the change |
| `base_commit` / `head_commit` | Explicit causal boundary for the diff |
| `change_type` | Highest-ranked evolution surface touched by the diff |
| `risk` | Low, medium, high, or critical |
| `affected_files` | Tracked and untracked files in scope, excluding generated assurance output |
| `affected_contracts` | Contract/schema surfaces touched |
| `affected_capabilities` | Capability surfaces touched |
| `affected_invariants` | Governance laws implicated by the change |
| `required_replays` | Replay scenarios that must be certified |
| `requires_approval` | Whether authority evidence is required |
| `rollback_required` | Whether rollback or restore evidence is required |

## Classification Model

Changed files are classified by path and governance surface:

| Surface | Examples | Risk floor |
|---|---|---|
| Documentation | `*.md`, `*.txt` | Low |
| Configuration | `*.json`, `*.yaml`, `*.toml` | Medium |
| Code | runtime modules outside special surfaces | Medium |
| Deployment | `.github/`, `k8s/`, deployment profiles | Medium |
| Provider | provider or routing files | High |
| Schema/Contract | `schemas/`, `mcoi_runtime/contracts/` | High |
| Capability | `skills/`, capability descriptors | High |
| Authority/Policy | approval, authority, governance, command spine, proof, audit, verification | Critical |
| Migration | migration paths | Critical |

Mixed diffs receive the highest-ranked surface. A change touching approval,
authority, command spine, proof, audit, or verification is treated as a
system-law change.

## Replay Model

Replay certification is deterministic and side-effect free. Replay runners
validate local governed behavior without invoking live providers or mutating
production state.

| Scenario | Trigger | Local proof |
|---|---|---|
| `approval_gated_command` | Schema, capability, or policy change | Approval-gated pilot config/request artifacts validate |
| `effect_reconciliation` | Schema, capability, or policy change | Effect assurance produces terminal `MATCH` from observed effects |
| `schema_round_trip` | Schema, capability, or policy change | Canonical fixtures round-trip through Python contracts |
| `provider_failure` | Provider change | Streaming provider failure yields one governed error event |
| `budget_exhaustion` | Provider change | Tenant budget exhaustion blocks additional spend |
| `snapshot_restore` | Migration change | Rollback snapshot restores exact captured state |
| `state_persistence` | Migration change | Snapshot fetch preserves immutable state and checksum |

Strict mode fails if any required replay has no registered deterministic runner
or if any runner returns a failed result.

## Emitted Files

Certification writes the following generated artifacts:

```text
.change_assurance/change_command.json
.change_assurance/blast_radius.json
.change_assurance/invariant_report.json
.change_assurance/replay_report.json
.change_assurance/release_certificate.json
.change_assurance/manifest.json
```

These files are evidence surfaces. They are excluded from the next `current`
diff so certification does not recursively certify its own generated output.

## CI Gate

The build-verification job runs strict certification:

```bash
python scripts/certify_change.py --base HEAD^ --head HEAD --strict --approval-id ci-governance --rollback-plan-ref RELEASE_CHECKLIST_v0.1.md
```

`scripts/validate_release_status.py` also checks that this CI literal remains
present. Removing the gate therefore breaks release-status validation.

## Hard Invariants

1. No merge without a `ChangeCommand`.
2. No production deploy without a `ChangeCertificate`.
3. No policy, capability, or schema change without blast-radius analysis.
4. No high-risk change without authority approval.
5. No migration without rollback or explicit irreversible-change approval.
6. No approval-rule change without second approval.
7. No audit, proof, verification, or command-spine change without critical-risk
   classification.
8. No release certificate without replaying required governed scenarios.
9. No accepted limitation without expiration or owner.

## Prohibitions

1. **No silent evolution** - a change cannot be certified without an emitted
   `ChangeCommand`.
2. **No advisory-only replay** - strict replay failures fail the certificate.
3. **No live provider calls during replay** - replay runners must be local,
   deterministic, and side-effect free.
4. **No generated evidence recursion** - `.change_assurance/` output is not
   included in the next `current` diff.
5. **No high-risk bypass** - approval and rollback evidence are required in
   strict mode for high and critical changes.
6. **No CI ownership inversion** - CI executes the governance gate; governance
   defines what CI must prove.
