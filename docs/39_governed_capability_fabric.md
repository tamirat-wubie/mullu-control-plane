# Governed Capability Fabric

> **In one box:** The shared "plug" that turns any domain's work into a governed
> [capability](GLOSSARY.md#capability--capability-plane) the platform can run
> safely — the connector between domain packs and the governed core. New here?
> → [Plain-English Overview](explain/PLAIN_ENGLISH.md). *(Doc type: Reference.)*

Purpose: define the shared contract surface that turns domain work into governed capability execution.
Governance scope: capability registry entries, domain capsules, capsule compiler inputs, authority, evidence, recovery, and obligation routing.
Dependencies: `docs/06_capability_planes.md`, `docs/31_operational_graph.md`, `docs/37_terminal_closure_certificate.md`, `schemas/capability_registry_entry.schema.json`, and `schemas/domain_capsule.schema.json`.
Invariants:
- No command can execute without a typed capability registry entry.
- No capability registry entry is complete without authority, isolation, evidence, recovery, cost, and obligation models.
- Registry read models expose derived C-level maturity without mutating source registry entries.
- No domain capsule is deployable without owner team, policies, evidence rules, recovery rules, test fixtures, read models, and operator views.
- Terminal closure remains the only success authority for effect-bearing actions.

## Architecture

The platform becomes general purpose by admitting every domain action through the same governed lifecycle:

```text
Command -> Typed Intent -> Capability -> Authority -> Effect -> Evidence -> Closure -> Obligation
```

A capability registry entry defines one executable action. A domain capsule packages the operating model for one domain. The capsule compiler turns certified capsule inputs into registry entries, policies, fixtures, read models, and operator views.

## Capability Registry Entry

Each registry entry carries the minimum information needed to execute an action without weakening closure law.

| Field | Governance role |
| --- | --- |
| `capability_id` | Stable action identity |
| `domain` | Domain ownership boundary |
| `input_schema_ref` | Typed intent contract |
| `output_schema_ref` | Typed result contract |
| `effect_model` | Expected and forbidden effects |
| `evidence_model` | Proof receipts required for closure |
| `authority_policy` | Roles, approval chain, and separation of duty |
| `isolation_profile` | Execution plane, network boundary, and secret scope |
| `recovery_plan` | Rollback, compensation, and review behavior |
| `cost_model` | Budget class and maximum estimated cost |
| `obligation_model` | Owner, due time, and escalation path |
| `certification_status` | Lifecycle gate for admission |

## GCI Execution Contract

Runtime tool execution is now gated by a fixed GCI `CapabilityContract` before any executor, worker, or adapter can run. The contract is the runtime-local admission unit that binds capability identity to governance depth, effect class, source trust, and five cost/risk axes.

| Field | Governance role |
| --- | --- |
| `capability` | Stable action identity used by the execution gate |
| `layer` | Runtime layer that owns the action boundary |
| `cap_level` | Capability autonomy or mutation level requested |
| `gov_tier` | Governance depth available for this request |
| `axis_T` | Temporal validity and freshness constraint |
| `axis_E` | Economic or budget constraint |
| `axis_C` | Cognitive/operator-review load constraint |
| `axis_R` | Risk tier carried into admission |
| `axis_V` | Effect class: `value_producing` or `effectful` |
| `precond` | Preconditions that must hold before execution |
| `fail_mode` | Explicit blocked or degraded behavior |
| `reversible` | Whether the action can be reversed without compensation |
| `intent_source` | Source-trust binding for authorization |

The central admission rule is:

```text
enable(capability @ Cn)
<=> gov_tier >= Gn
AND axis_T, axis_E, axis_C, axis_R, axis_V are populated
AND effectful requests are sourced from user_direct authorization
```

If the rule is not satisfied, `Phi_gov` blocks execution and the tool gateway records the denied path in the causal ledger. A command found in monitored content, a document, an email, or an external signal can inform planning, but it cannot become direct authorization for an effectful action.

Value-producing capabilities may create information only. Effectful capabilities mutate external or durable state and require the stronger gate.

| Capability | Effect class |
| --- | --- |
| summarize document | `value_producing` |
| draft email | `value_producing` |
| send email | `effectful` |
| deploy service | `effectful` |
| modify issue | `effectful` |
| delete file | `effectful` |

Reused plans, memory, repository state, deployment state, finance context, calendar facts, infrastructure facts, and security assumptions must pass `OP_reground` before they guide effectful execution. Digital state claims that affect closure must pass L2 reality verification because digital state and reality state can diverge.

`GovernedToolRegistry.capability_contract_coverage()` exposes the runtime read model for this gate. Operators can inspect registered tool count, enabled tool count, explicit versus synthesized contract count, blocked contract count, per-tool admission status, and rejected reasons without invoking any tool. A complete report means every registered tool has a populated `CapabilityContract` that satisfies the CxG grid; a blocked report identifies the exact `Phi_gov` reason before execution is possible.

`GovernedToolRegistry.decision_read_model()` exposes the bounded live operator view of recent tool decisions. It shows allowed count, blocked count, decision stage, source trust, effect class, capability level, governance tier, and reasons such as `effectful_action_requires_user_direct_intent_source`. This is visibility only; durable rejected-path receipts remain the audit authority for long-term evidence.

## Maturity Projection

Registry entries do not self-promote. Gateway-built fabric read models derive a `capability_maturity_assessment` from each installed entry and attach the C0-C7 summary to both the internal capability projection and the governed operator record. Certification can lift a capability to mock-evaluated maturity, but production readiness still requires explicit sandbox, live receipt, worker deployment, recovery, and autonomy evidence through `extensions.capability_maturity_evidence`.

Read models also expose a derived `maturity_label` for operator scanning. The label is not admission authority: `Specified` covers C0-C2, `Implemented` covers C3-C5, and `Verified` covers C6-C7. Runtime admission, production readiness, and autonomy readiness continue to use the C-level evidence gates and cannot be promoted by changing the label.

Checked-in default packs include two concrete C6 witnesses. `connector.github.read` is read-only and carries sandbox, live-read, worker deployment, and recovery evidence references; because it is not world-mutating, the live-write gate is not required. `financial.send_payment` is effect-bearing and reaches C6 only because it also carries live-write evidence. Both examples remain below C7 until bounded autonomy controls are supplied.

Certification pipelines can avoid hand-authored maturity flags by emitting `extensions.capability_certification_evidence` with concrete certification, sandbox, live-read, optional live-write, worker, recovery, and autonomy-control references. The maturity synthesizer converts that bundle into the canonical `capability_maturity_evidence` extension shape, validates the capability identity, and can run in strict mode when a caller requires production readiness before writing the generated extension.

## Capability Unlock Ladder

The C0-C7 maturity model remains the evidence-derived readiness contract. The
Level 0-9 unlock ladder is a reusable operator profile over that maturity model:
it says which gates must be present before a class of work may run. It does not
promote a capability and it does not create execution authority.

Canonical implementation:

```text
mcoi/mcoi_runtime/core/capability_unlock_ladder.py
```

Reusable gate templates:

| Gate template | Purpose |
| --- | --- |
| `evidence_intake_gate` | Collects bounded evidence before action selection. |
| `approval_gate` | Records explicit operator decision before a hard boundary. |
| `verifier_gate` | Checks observed state against the expected proof surface. |
| `workspace_write_gate` | Confines file writes to the controlled workspace or branch. |
| `connector_lease_gate` | Confines credentialed connector access to a scoped lease. |
| `execution_receipt_gate` | Requires command-bound execution receipts. |
| `rollback_gate` | Requires rollback, compensation, or recovery evidence. |
| `operator_review_gate` | Preserves human review before escalation or PR evidence. |

Unlock levels:

| Level | Name | Required boundary |
| ---: | --- | --- |
| 0 | Read-only | Evidence intake only; no durable or external effects. |
| 1 | Local demo | Local dry run plus verifier and receipt. |
| 2 | File preparation | Diffs, docs, schemas, tests, and review packets only. |
| 3 | File writing | Workspace write, receipt, rollback, and operator review. |
| 4 | Test execution | Bounded tests with verifier, receipt, and rollback. |
| 5 | PR creation | PR evidence preparation; opening requires approval. |
| 6 | Human approval | Approval or rejection is recorded as the effect. |
| 7 | Live connector probe | Scoped read-only credentialed connector lease and live witness. |
| 8 | Approved live action | Approved live write with receipt and recovery. |
| 9 | Customer-ready product | Customer exposure requires production witnesses, support, monitoring, and rollback. |

The focused contract test is:

```powershell
python -m pytest mcoi/tests/test_capability_unlock_ladder.py -q
```

### Admission Projection

`CommandCapabilityAdmissionGate` resolves `metadata.unlock_ladder` during typed
intent admission. Accepted decisions now carry the ladder id, level, gate
template ids, and approval, receipt, rollback, and live-witness booleans. This
turns the ladder from documentation metadata into a reusable runtime policy
surface without granting new authority.

Malformed ladder metadata fails closed with a stable reason and structured
rejection codes:

```text
reason: capability unlock profile invalid
rejection_codes: (<profile_error_code>, ...)
```

The admission resolver preserves older capability entries that do not declare a
ladder profile, but any entry that declares one must match the canonical ladder
exactly. This keeps future capability packs from silently substituting weaker
gates for effect-bearing actions.

## Friction Control Projection

The operator console now derives a `capability_friction_control` read model from
governed capability records. This projection does not grant execution authority.
It converts many fine-grained gates into four operator-facing questions:

| Question | Read-model source |
| --- | --- |
| What is unlocked? | `unlock_level`, `friction_status`, and mode admission fields. |
| What is blocked? | `blocked_actions` projected from forbidden effects, approval, and production evidence. |
| Why is it blocked? | `required_before_unlock` and `next_unlock`. |
| What boundary applies? | `operating_boundary`, `lab_mode_allowed`, and `real_world_mode_allowed`. |

Canonical unlock levels are:

```text
L0 read-only
L1 plan-only
L2 prepare-only
L3 write-to-sandbox
L4 run tests
L5 create PR
L6 merge with approval
L7 live connector read
L8 live connector write
L9 production/customer mode
```

Friction modes are read-model policy summaries:

| Mode | Meaning |
| --- | --- |
| `strict` | Approval before effect-bearing action and production evidence before real-world writes. |
| `balanced` | Read and prepare are automatic; risky local changes require approval. |
| `fast` | Local lab actions are automatic only when sandbox, receipt, rollback, and no-network constraints hold. |

The lab boundary is the default for Foundation Mode. Lab mode may write local
sandbox files, run tests, create demos, and prepare review packets. Real-world
mode remains blocked until the relevant capability carries production witness
evidence and any approval policy is satisfied.

Safe automatic zones:

```text
write_docs
write_tests
write_examples
write_local_demo_files
update_readme
generate_schemas
generate_validators
```

Dangerous zones:

```text
delete_files
touch_secrets
send_email
move_money
deploy
merge_to_main
write_production_data
```

Rollback is part of the friction contract: every world-mutating local capability
must expose receipt and rollback or compensation requirements before it can be
treated as fast-mode lab-ready.

Canonical artifacts:

| Artifact | Role |
| --- | --- |
| `schemas/capability_friction_control.schema.json` | Strict operator read-model contract. |
| `examples/capability_friction_control.foundation.json` | Foundation Mode software-development projection. |
| `scripts/validate_capability_friction_control.py` | Runtime and schema validator. |
| `tests/test_validate_capability_friction_control.py` | Contract and rejection coverage. |
| `/operator/capabilities/friction-control/read-model` | Read-only gateway route for the live operator projection. |

Validation:

```powershell
python scripts/validate_capability_friction_control.py
python -m pytest tests/test_validate_capability_friction_control.py -q
python scripts/validate_schemas.py
```

## Capability Forge

The capability forge emits candidate packages and certification handoffs, never registry mutations. A candidate handoff binds the package id, package hash, sandbox receipt, live receipt, worker deployment, recovery evidence, and optional autonomy-control reference into a `CapabilityCertificationEvidenceBundle` that the maturity synthesizer can consume. Effect-bearing handoffs fail closed until live-write and recovery evidence references are present.

The forge-side registry handoff installer accepts only a stamped handoff for an already certified registry entry. It writes the bundle as `extensions.capability_certification_evidence`, refuses direct `capability_maturity_evidence` overrides, and validates production readiness through the maturity synthesizer without installing executable capability records or bypassing capsule admission.

For capsule compilation, the batch installer requires exact coverage between registry entries and handoffs, preserves entry order, and returns a hash-stamped batch witness. The capsule compiler then serializes those evidence-bearing entries, and `GovernedCapabilityRegistry.install` still performs the only executable registry admission.

## Capsule Admission Shortcut

Operators do not need to hand-correlate forge handoffs, compiler artifacts, and registry installation records. `install_certified_capsule_with_handoff_evidence` composes the existing gates in one deterministic sequence:

```text
registry entries + certification handoffs
  -> exact handoff evidence batch
  -> domain capsule compilation
  -> GovernedCapabilityRegistry.install
  -> capsule admission receipt
```

The receipt records the batch hash, handoff hashes, compilation id, installation id, capability ids, artifact ids, certification-evidence manifest id, warnings, errors, and post-install registry counts. It is an audit witness only; `GovernedCapabilityRegistry.install` remains the admission authority. If strict admission rejects a compiled capsule, the function still returns a rejected receipt without mutating registry state.

The gateway exposes this shortcut through the authority-operator boundary:

| Route | Method | Role |
| --- | --- | --- |
| `/capability-fabric/capsule-admissions` | `POST` | Accepts one capsule, registry entry set, handoff set, and `require_production_ready` flag; returns the receipt, evidence batch, compilation result, and installation record. |
| `/capability-fabric/capsule-admission-receipts` | `GET` | Returns recent admission receipts with optional `status`, `limit`, and `offset` bounds. |

The POST surface fails closed when capability fabric admission is disabled, rejects malformed payloads before registry mutation, and stores only the hash-stamped receipt in the bounded in-process operator receipt window.

## Domain Capsule

A domain capsule is a packaged operating model, not a free-form plugin.

| Capsule part | Required relation |
| --- | --- |
| `ontology_refs` | Defines domain symbols and resource identities |
| `capability_refs` | Binds the capsule to executable registry actions |
| `policy_refs` | Binds action admission to policy law |
| `evidence_rules` | Defines proof required before terminal closure |
| `approval_rules` | Defines authority and escalation paths |
| `recovery_rules` | Defines rollback, compensation, and review obligations |
| `test_fixture_refs` | Defines certification fixtures |
| `read_model_refs` | Defines certified state projections |
| `operator_view_refs` | Defines console surfaces over certified state |
| `owner_team` | Owns unresolved risk and post-closure obligations |

## Capsule Compiler

The capsule compiler has one responsibility: convert a domain capsule into deployable governed artifacts without changing global command law.

```text
capsule source
  -> schema validation
  -> ontology reference validation
  -> capability reference validation
  -> policy/evidence/recovery compilation
  -> registry entry emission
  -> certification evidence manifest emission
  -> fixture and read-model registration
  -> certification report
```

Compiler output must include registry manifests, certification evidence manifests, policy packs, evidence packs, approval packs, recovery packs, obligation templates, fixture references, read-model descriptors, operator-view descriptors, and a certification report. The certification evidence manifest is an operator audit artifact over `extensions.capability_certification_evidence`; it is not admission authority. Marketplace installation is blocked until the certification report marks the capsule `certified`.

## Closure Rule

The fabric does not authorize text-only success claims. Effect-bearing capabilities must return command-bound evidence, then effect assurance reconciles observed state, and only terminal closure can certify completion.

## Command Admission Rule

Typed command intents resolve by exact `intent_name -> capability_id` lookup against the installed governed capability registry. A command that does not resolve to an installed capability receives an explicit rejected admission decision before dispatch. Accepted decisions carry the capability domain, owner team, and evidence obligations forward into execution planning.
