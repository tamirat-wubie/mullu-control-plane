<!--
Purpose: define the foundation-stage Mullu Component Harness registry boundary.
Governance scope: component identity, classification, lifecycle, wiring,
authority, proof posture, receipt requirement, health source, dependencies,
owner surfaces, and blocked actions.
Dependencies: schemas/component_registry.schema.json,
schemas/component_router_inventory.schema.json, schemas/component_proof_binding.schema.json,
schemas/component_read_model.schema.json,
examples/component_registry.foundation.json, examples/component_router_inventory.foundation.json,
examples/component_proof_binding.foundation.json, examples/component_read_model.foundation.json,
scripts/validate_component_registry.py,
scripts/validate_component_router_inventory.py, scripts/validate_component_proof_binding.py,
scripts/validate_component_read_model.py, tests/test_validate_component_registry.py,
tests/test_validate_component_router_inventory.py, tests/test_validate_component_proof_binding.py,
tests/test_validate_component_read_model.py, mcoi/tests/test_component_read_model_route.py,
and docs/40_proof_coverage_matrix.md.
Invariants: mounted does not mean live; bootstrapped does not mean authorized;
registry presence and proof binding do not grant route binding, connector
mutation, filesystem write, external send, public readiness, or terminal
closure; component bundles group components for readiness without becoming
execution routes.
-->

# Mullu Component Harness

Mullu Control Plane is now treated as a governed component operating layer:

```text
Mullu Control Plane = governed component harness + proof-bound execution boundary.
```

This document covers the foundation Component Harness inventory. It creates the
canonical registry, selected router inventory, component bundles, proof binding
gates, and read-only component read-model route. It does not add request
routing, product bundle compilation, request simulation, or live execution.

## Architecture

| Layer | Role | PR 1 state |
| --- | --- | --- |
| Component Registry | Names every governed component and records classification, state, authority, proof posture, receipt requirement, health source, dependencies, and owner surface. | Added as schema, example, validator, and tests. |
| Router Inventory | Binds selected component-owned declared route families to registered component IDs and proof surfaces. | Added as a read-only schema, example, validator, and tests. |
| Lifecycle Engine | Governs movement from present to registered, validated, bootstrapped, mounted, read-only, draft-only, live-probe, approval-required, approved live action, blocked, or deprecated. | Declared only. No transition engine is added. |
| Authority Envelope | Records component authority flags so mounted or bootstrapped components cannot imply live execution. | Embedded in registry entries with live authority flags false. |
| Component Bundles | Groups components into foundation/demo/read-only product lanes while retaining blocked-action gates. | Added as static bundle inventory. No bundle compiler or router is added. |
| Component Router | Routes operator requests only through allowed components. | Not added in PR 1. |
| Read Model | Exposes component posture through `GET /api/v1/components/read-model`. | Added as a read-only schema, example, route, validator, and tests. |
| Proof Binding | Bridges registry entries and router inventory proof declarations to proof coverage matrix rows and runtime witnesses. | Added as a read-only schema, example, validator, and tests. |

## Registry Contract

Each component declares:

| Field | Meaning |
| --- | --- |
| `id` | Canonical component identity. |
| `name` | Operator-readable component name. |
| `aliases` | Alternate names that must resolve to one component. |
| `type` | Platform lane such as governance, runtime, reasoning, assistant, connector, memory, execution, operations, security, or domain. |
| `mode` | Current operating mode, bounded to foundation/read-only/draft/live-probe/approval/blocked states. |
| `lifecycle_state` | Component lifecycle posture. |
| `wiring_state` | Import, bootstrap, mount, read-only, live-probe, approval, blocked, or deprecation posture. |
| `authority_level` | Summary authority classification. |
| `authority` | Explicit booleans for read, preview, draft, execute, mutate, connector call, file write, external send, receipt emission, and terminal closure. |
| `proof_surface` | Proof posture: not applicable, awaiting binding, declared, or proof-bound. |
| `receipt_required` | Whether the component needs receipt evidence for claims. |
| `health_source` | Doc, route, validator, witness, read model, or none. |
| `blocked_actions` | Actions denied for the current foundation posture. |
| `dependencies` | Other registered component IDs this component depends on. |
| `owner_surface` | Governance, runtime, reasoning, assistant, connector, memory, execution, operations, security, or domain ownership lane. |

## Bundle Contract

Each bundle declares:

| Field | Meaning |
| --- | --- |
| `bundle_id` | Canonical product or platform grouping identity. |
| `allowed_mode` | Highest allowed registry mode for the grouping: foundation, demo v0, read-only, or draft-only. |
| `components` | Registered component IDs required by the bundle. |
| `blocked_actions` | Actions denied for the bundle posture. |
| `receipt_required` | Whether bundle claims need receipt evidence. |
| `bundle_is_not_execution_route` | Hard assertion that the bundle cannot execute requests. |
| `terminal_closure_required` | Hard assertion that the bundle is not terminal closure. |

## Router Inventory Contract

The router inventory is a read-only binding layer. It records which registered
component owns a selected route family, which proof matrix surface classifies
that route, and which actions remain blocked. It does not dispatch requests and
does not grant live action authority.

Each route binding declares:

| Field | Meaning |
| --- | --- |
| `component_id` | Registered component that owns the selected route family. |
| `binding_state` | `bound`, `no_declared_route`, or `deferred`. |
| `proof_surface_ids` | Proof matrix surfaces that classify the bound routes. |
| `route_prefixes` | Declared route prefixes watched for drift. |
| `expected_routes` | Exact declared routes currently accepted under those prefixes. |
| `blocked_actions` | Actions denied for the route family. |
| `binding_is_not_execution_authority` | Hard assertion that the binding cannot execute. |
| `can_enable_live_action` | Hard false in foundation mode. |

## Proof Binding Contract

The proof binding is a read-only bridge across the component registry, router
inventory, and proof coverage matrix. It verifies that a component claim has a
registered component identity, a matching router-inventory proof declaration,
proof matrix coverage, evidence files, runtime witnesses, blocked actions, and
terminal-closure denial.

Each component proof binding declares:

| Field | Meaning |
| --- | --- |
| `component_id` | Registered component identity. |
| `proof_binding_state` | `proof_bound`, `awaiting_binding`, or `not_applicable`. |
| `required_surface_ids` | Proof matrix surfaces required by the registry claim. |
| `inventory_surface_ids` | Proof matrix surfaces mirrored from router inventory. |
| `required_evidence_files` | Evidence files that must appear on referenced proof matrix surfaces and exist in the repository. |
| `required_runtime_witnesses` | Runtime witness labels that must appear on referenced proof matrix surfaces. |
| `receipt_required` | Must match the registry receipt requirement. |
| `blocked_actions` | Must include all registry blocked actions. |
| `binding_is_not_execution_authority` | Hard assertion that proof binding cannot execute. |
| `can_claim_terminal_closure` | Hard false in foundation mode. |

## Foundation Inventory

The committed foundation example includes the current audit-critical set:

| Component | Current posture | Authority result |
| --- | --- | --- |
| `governance_core` | Registered foundation governance surface. | Read-only advisory; no live execution. |
| `agentic_service_harness` | Mounted status/read-model shell. | Read-only; no adapter or mutation authority. |
| `snet` | Mounted symbolic mesh read model. | Read-only advisory; no execution, connector, filesystem, or terminal closure. |
| `inceptadive_shadow` | Mounted shadow health and console posture. | Read-only advisory; execution authority false. |
| `personal_assistant` | Draft/read-only assistant projection. | Draft-only; no send, mailbox mutation, or calendar write. |
| `teamops_shared_inbox` | Live-probe evidence posture. | Read-only probe; provider write and send blocked. |
| `gmail_account_binding_gate` | Approval-required account-binding gate. | No account-bound live authority claim. |
| `worker_runtime` | Bootstrapped worker mesh posture. | Dispatch blocked for product authority. |
| `capability_workers` | Restricted signed worker pathway posture. | Future product authority gated. |
| `nested_mind_bridge` | Bridge/submission infrastructure present. | Live memory topology activation blocked. |

The registry also declares three non-executing bundles:

| Bundle | Purpose | Blocked result |
| --- | --- | --- |
| `personal_assistant_v0` | Groups assistant, Gmail gate, SNet, InceptaDive shadow, and governance surfaces for Demo v0 posture. | Send, mailbox mutation, calendar write, connector call, memory activation, external send, and terminal closure blocked. |
| `symbolic_reasoning_read_only` | Groups SNet and InceptaDive shadow for advisory reasoning. | Route execution, connector call, filesystem write, runtime mutation, external send, and terminal closure blocked. |
| `worker_runtime_foundation` | Groups worker runtime and capability workers for inventory and evidence tracking. | Live dispatch, autonomous execution, provider write, filesystem write, runtime mutation, and terminal closure blocked. |

The router inventory currently binds 28 declared routes across the selected
component-owned families: governance core, agentic service harness,
InceptaDive shadow, Personal Assistant, TeamOps shared inbox, and capability
workers. SNet, Gmail account binding, worker runtime, and Nested Mind are
explicitly recorded as `no_declared_route` for foundation posture.

The proof binding currently binds nine proof-bound components to 12 proof
coverage surfaces. `nested_mind_bridge` remains `awaiting_binding`, with no
receipt claim and no live memory topology activation.

The component read model exposes `GET /api/v1/components/read-model`. The route
returns the joined registry/router/proof posture for 10 components and three
bundles. It is GET-only, has `read_model_is_not_execution_authority=true`, and
keeps live execution, connector send, mutation, and terminal closure blocked.

## Algorithm

Validation follows this deterministic sequence:

1. Load the schema and each registry example as strict JSON objects.
2. Validate each example against `schemas/component_registry.schema.json`.
3. Verify foundation guardrails: registry-only, no route binding, no proof-matrix enforcement claim, no live execution, no live connector send, no public customer-readiness claim, and no terminal-closure claim.
4. Verify required closure validators are declared with exact commands.
5. Verify canonical foundation component IDs are present.
6. Reject duplicate component IDs and alias collisions.
7. Reject dependencies that do not resolve to registered components.
8. Verify required component bundles are present, non-executing, reference registered components, and block terminal closure.
9. Reject live authority flags such as execute, mutate, connector call, file write, external send, or terminal closure.
10. Reject foundation lifecycle or wiring states that claim approved live action or live action enabled.
11. Reject mounted, bootstrapped, live-probe, approval-required, or live-action-labeled components that do not list blocked actions.
12. Reject receipt-required components unless they are proof-bound.
13. Reject proof-bound components without a proof surface ID and evidence references.
14. Reject proof-surface evidence that is not also present in component evidence references.

Router inventory validation follows this deterministic sequence:

1. Load the router inventory schema, foundation inventory, and component registry.
2. Validate the router inventory against `schemas/component_router_inventory.schema.json`.
3. Reuse the component registry validator before accepting route bindings.
4. Generate the proof coverage matrix and declared route report.
5. Reject unregistered component IDs.
6. Reject duplicate component route bindings.
7. Reject bound routes that are not declared.
8. Reject bound routes whose proof surface differs from the inventory surface.
9. Reject unrecorded routes under a watched prefix.
10. Reject duplicate route ownership across components.
11. Reject route bindings that enable live action or omit terminal-closure blocking.

Proof binding validation follows this deterministic sequence:

1. Load the proof binding schema, foundation binding, component registry, router inventory, and proof matrix fixture.
2. Validate the proof binding against `schemas/component_proof_binding.schema.json`.
3. Reuse the component registry and router inventory validators before accepting proof bindings.
4. Generate the proof coverage matrix from source.
5. Reject component bindings that are missing, duplicated, or not registered.
6. Reject source reference drift for registry, router inventory, or proof matrix paths.
7. Reject proof-bound components whose registry surface is not in `required_surface_ids`.
8. Reject `inventory_surface_ids` that differ from router inventory proof declarations.
9. Reject surfaces missing from the generated or fixture proof matrix.
10. Reject proof-bound surfaces whose coverage state is not proven or witnessed.
11. Reject required evidence files absent from referenced proof surfaces or missing on disk.
12. Reject receipt-required components without runtime witnesses.
13. Reject proof bindings that omit registry blocked actions or claim terminal closure.

Read-model validation follows this deterministic sequence:

1. Load `schemas/component_read_model.schema.json` and `examples/component_read_model.foundation.json`.
2. Rebuild the projection from registry, router inventory, and proof binding sources.
3. Validate the example against the read-model schema.
4. Reject example drift from the runtime projection.
5. Reject live execution, connector send, or terminal-closure authority claims.
6. Reject receipt-required components that are not proof-bound or lack runtime witness counts.
7. Verify the route remains GET-only through focused FastAPI tests.

## Verification

Run:

```powershell
python scripts/validate_component_registry.py --strict
python scripts/validate_component_router_inventory.py --strict
python scripts/validate_component_proof_binding.py --strict
python scripts/validate_component_read_model.py --strict
python -m pytest tests/test_validate_component_registry.py -q
python -m pytest tests/test_validate_component_router_inventory.py -q
python -m pytest tests/test_validate_component_proof_binding.py -q
python -m pytest tests/test_validate_component_read_model.py mcoi/tests/test_component_read_model_route.py -q
python scripts/validate_protocol_manifest.py
```

The full workspace preflight also includes the component registry and component
router inventory validators, plus the component proof binding and component
read-model validators.

## Non-Goals

The current harness boundary does not:

1. Bind every proof-relevant declared route to a final component owner.
2. Enforce proof matrix binding against every route outside the current selected harness set.
3. Compile product bundles.
4. Simulate request routing.
5. Enable live action, connector calls, filesystem writes, mailbox mutation, external sends, deployment, public readiness, or terminal closure.

The router inventory refinement does not:

1. Bind all 422 proof-relevant declared routes to final product components.
2. Create a runtime component router.
3. Promote `no_declared_route` components to mounted route posture.
4. Enable live action, connector calls, filesystem writes, mailbox mutation, external sends, deployment, public readiness, or terminal closure.

STATUS:
  Completeness: 100%
  Invariants verified: component identity declared, aliases unique, dependencies registered, selected component route families bound, router proof surfaces mirrored, proof-bound components tied to proof matrix surfaces, receipt-required components tied to runtime witnesses, component read model route GET-only, bundles non-executing, mounted is not live, bootstrapped is not authorized, live authority false, live-action state labels blocked, proof evidence files present, foundation guardrails closed
  Open issues: full-route component binding, product bundle compiler, request simulator
  Next action: add component request simulator without enabling live execution
