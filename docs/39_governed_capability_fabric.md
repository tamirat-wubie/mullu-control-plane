# Governed Capability Fabric

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

## Maturity Projection

Registry entries do not self-promote. Gateway-built fabric read models derive a `capability_maturity_assessment` from each installed entry and attach the C0-C7 summary to both the internal capability projection and the governed operator record. Certification can lift a capability to mock-evaluated maturity, but production readiness still requires explicit sandbox, live receipt, worker deployment, recovery, and autonomy evidence through `extensions.capability_maturity_evidence`.

Checked-in default packs include two concrete C6 witnesses. `connector.github.read` is read-only and carries sandbox, live-read, worker deployment, and recovery evidence references; because it is not world-mutating, the live-write gate is not required. `financial.send_payment` is effect-bearing and reaches C6 only because it also carries live-write evidence. Both examples remain below C7 until bounded autonomy controls are supplied.

Certification pipelines can avoid hand-authored maturity flags by emitting `extensions.capability_certification_evidence` with concrete certification, sandbox, live-read, optional live-write, worker, recovery, and autonomy-control references. The maturity synthesizer converts that bundle into the canonical `capability_maturity_evidence` extension shape, validates the capability identity, and can run in strict mode when a caller requires production readiness before writing the generated extension.

## Capability Forge

The capability forge emits candidate packages and certification handoffs, never registry mutations. A candidate handoff binds the package id, package hash, sandbox receipt, live receipt, worker deployment, recovery evidence, and optional autonomy-control reference into a `CapabilityCertificationEvidenceBundle` that the maturity synthesizer can consume. Effect-bearing handoffs fail closed until live-write and recovery evidence references are present.

The forge-side registry handoff installer accepts only a stamped handoff for an already certified registry entry. It writes the bundle as `extensions.capability_certification_evidence`, refuses direct `capability_maturity_evidence` overrides, and validates production readiness through the maturity synthesizer without installing executable capability records or bypassing capsule admission.

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
  -> fixture and read-model registration
  -> certification report
```

Compiler output must include registry manifests, policy packs, evidence packs, approval packs, recovery packs, obligation templates, fixture references, read-model descriptors, operator-view descriptors, and a certification report. Marketplace installation is blocked until the certification report marks the capsule `certified`.

## Closure Rule

The fabric does not authorize text-only success claims. Effect-bearing capabilities must return command-bound evidence, then effect assurance reconciles observed state, and only terminal closure can certify completion.

## Command Admission Rule

Typed command intents resolve by exact `intent_name -> capability_id` lookup against the installed governed capability registry. A command that does not resolve to an installed capability receives an explicit rejected admission decision before dispatch. Accepted decisions carry the capability domain, owner team, and evidence obligations forward into execution planning.
