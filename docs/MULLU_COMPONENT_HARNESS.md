<!--
Purpose: define the foundation-stage Mullu Component Harness registry boundary.
Governance scope: component identity, classification, lifecycle, wiring,
authority, proof posture, receipt requirement, health source, dependencies,
owner surfaces, and blocked actions.
Dependencies: schemas/component_registry.schema.json,
schemas/component_router_inventory.schema.json, schemas/component_proof_binding.schema.json,
schemas/component_read_model.schema.json,
schemas/component_autopsy.schema.json,
schemas/component_request_simulation.schema.json,
schemas/component_bundle_compilation.schema.json,
schemas/component_graph.schema.json,
schemas/component_dead_component_detection.schema.json,
schemas/component_lifecycle_transition_receipts.schema.json,
examples/component_registry.foundation.json, examples/component_router_inventory.foundation.json,
examples/component_proof_binding.foundation.json, examples/component_read_model.foundation.json,
examples/component_autopsy.nested_mind_bridge.json,
examples/component_request_simulation.foundation.json,
examples/component_bundle_compilation.personal_assistant_v0.json,
examples/component_graph.foundation.json,
examples/component_dead_component_detection.foundation.json,
examples/component_lifecycle_transition_receipts.foundation.json,
scripts/validate_component_registry.py,
scripts/validate_component_router_inventory.py, scripts/validate_component_proof_binding.py,
scripts/validate_component_read_model.py,
scripts/validate_component_autopsy.py,
scripts/validate_component_request_simulation.py,
scripts/validate_component_bundle_compiler.py,
scripts/validate_component_graph.py,
scripts/validate_component_dead_detector.py,
scripts/validate_component_lifecycle_transition_receipts.py,
tests/test_validate_component_registry.py,
tests/test_validate_component_router_inventory.py, tests/test_validate_component_proof_binding.py,
tests/test_validate_component_read_model.py,
tests/test_validate_component_autopsy.py,
tests/test_validate_component_request_simulation.py,
tests/test_validate_component_bundle_compiler.py,
tests/test_validate_component_graph.py,
tests/test_validate_component_dead_detector.py,
tests/test_validate_component_lifecycle_transition_receipts.py,
mcoi/tests/test_component_read_model_route.py,
mcoi/tests/test_component_autopsy_route.py,
mcoi/tests/test_component_request_simulator.py,
mcoi/tests/test_component_bundle_compiler.py,
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
gates, lifecycle transition receipts, read-only component read-model route,
read-only component autopsy route, preview-only request simulation, and
preview-only product bundle compilation, component graph projection, and
dead-component detection report.
It does not add live request routing or live execution.

## Architecture

| Layer | Role | PR 1 state |
| --- | --- | --- |
| Component Registry | Names every governed component and records classification, state, authority, proof posture, receipt requirement, health source, dependencies, and owner surface. | Added as schema, example, validator, and tests. |
| Router Inventory | Binds selected component-owned declared route families to registered component IDs and proof surfaces. | Added as a read-only schema, example, validator, and tests. |
| Lifecycle Receipts | Records current-state component lifecycle transitions against an allowed graph, evidence refs, and authority guardrails. | Added as a non-executing schema, example, validator, and tests. No transition engine is added. |
| Authority Envelope | Records component authority flags so mounted or bootstrapped components cannot imply live execution. | Embedded in registry entries with live authority flags false. |
| Component Bundles | Groups components into foundation/demo/read-only product lanes while retaining blocked-action gates. | Added as static bundle inventory consumed by the preview compiler. No live router is added. |
| Component Router | Routes operator requests only through allowed components. | Not added in PR 1. |
| Read Model | Exposes component posture through `GET /api/v1/components/read-model`. | Added as a read-only schema, example, route, validator, and tests. |
| Component Autopsy | Explains one component's blockers, evidence, missing evidence, forbidden actions, and next transition previews. | Added as a GET-only schema, example, route, validator, and tests. |
| Request Simulator | Predicts component path, blocked actions, approvals, receipts, and missing evidence for an operator request. | Added as a preview-only POST route, schema, example, validator, and tests. |
| Product Bundle Compiler | Compiles static bundle registry entries into preview readiness reports using read model and simulator evidence. | Added as a preview-only schema, example, runtime module, validator, and tests. |
| Component Graph | Projects dependencies, request-path edges, bundle memberships, and blocked paths into one read-only relationship graph. | Added as a non-executing schema, example, runtime module, validator, and tests. |
| Dead-Component Detector | Classifies active governed, watched, blocked-governed, and dead-candidate components from graph/read-model evidence. | Added as a non-executing schema, example, runtime module, validator, and tests. |
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

The router inventory currently binds 30 declared routes across the selected
component-owned families: governance core, agentic service harness,
InceptaDive shadow, Personal Assistant, TeamOps shared inbox, and capability
workers. SNet, Gmail account binding, worker runtime, and Nested Mind are
explicitly recorded as `no_declared_route` for foundation posture.

The proof binding currently binds nine proof-bound components to 14 proof
coverage surfaces. `nested_mind_bridge` remains `awaiting_binding`, with no
receipt claim and no live memory topology activation.

The component read model exposes `GET /api/v1/components/read-model`. The route
returns the joined registry/router/proof/lifecycle posture for 10 components
and three bundles. It is GET-only, has
`read_model_is_not_execution_authority=true`, and keeps live execution,
connector send, mutation, and terminal closure blocked.

The component autopsy route exposes
`GET /api/v1/components/{component_id}/autopsy`. The route returns one
component's blockers, evidence present, missing evidence, forbidden actions,
expected receipts, and next transition candidates. It has
`autopsy_is_not_execution_authority=true`, never performs the transition, and
keeps live execution, connector send, mutation, file write, external send, and
terminal closure false.

The component request simulator exposes `POST /api/v1/components/simulate`.
The route returns a deterministic preview for known foundation intents such as
send email, inbox readiness, deep symbolic analysis, worker dispatch, Nested
Mind activation, and unknown component requests. It has
`simulation_is_not_execution_authority=true`, keeps live execution, connector
calls, mutation, and terminal closure false, and emits only predicted path,
blocked actions, approval need, expected receipts, and missing evidence.

The product bundle compiler compiles registry bundle entries such as
`personal_assistant_v0` into a preview-only readiness report. It joins component
states from the read model and matching simulator scenarios, reports blocked
actions, blocked components, expected receipts, missing evidence, and forbidden
public claims, and keeps `compiler_is_not_execution_authority=true`.

The lifecycle transition receipt set records one current-state receipt for each
registered component. Each receipt names the allowed transition pair, current
wiring state, authority level, evidence refs, validator refs, blocked actions,
and authority guardrails. The receipt set keeps
`receipt_set_is_not_execution_authority=true`, requires terminal closure, and
does not permit transition to `approved_live_action`.

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
2. Rebuild the projection from registry, router inventory, proof binding, and lifecycle receipt sources.
3. Validate the example against the read-model schema.
4. Reject example drift from the runtime projection.
5. Reject live execution, connector send, or terminal-closure authority claims.
6. Reject receipt-required components that are not proof-bound or lack runtime witness counts.
7. Reject components whose lifecycle receipt does not target the current registry state.
8. Verify the route remains GET-only through focused FastAPI tests.

Component autopsy validation follows this deterministic sequence:

1. Load `schemas/component_autopsy.schema.json` and `examples/component_autopsy.nested_mind_bridge.json`.
2. Rebuild the autopsy from the validated component read model and lifecycle receipts.
3. Validate the example against the autopsy schema.
4. Reject example drift from the runtime autopsy.
5. Build autopsies for all foundation components.
6. Reject live execution, connector call, mutation, file write, external send, or terminal-closure claims.
7. Reject transition previews that target `approved_live_action` or claim authority.
8. Require `nested_mind_bridge` missing evidence to name proof binding and memory topology activation witnesses.

Request simulation validation follows this deterministic sequence:

1. Load `schemas/component_request_simulation.schema.json` and `examples/component_request_simulation.foundation.json`.
2. Rebuild the simulation from the validated component read model.
3. Validate the example against the request simulation schema.
4. Reject example drift from the runtime projection.
5. Validate every built-in foundation scenario for registered component IDs, blocked actions, expected receipts, and missing evidence.
6. Reject live execution, connector call, mutation, or terminal-closure claims.
7. Verify the simulator route remains POST-only and preview-only through focused FastAPI tests.

Product bundle compiler validation follows this deterministic sequence:

1. Load `schemas/component_bundle_compilation.schema.json` and `examples/component_bundle_compilation.personal_assistant_v0.json`.
2. Rebuild the compilation from the registry, component read model, and request simulator.
3. Validate the example against the bundle compilation schema.
4. Reject example drift from the runtime compilation.
5. Compile every foundation bundle and reject unregistered component references.
6. Reject live execution, connector call, mutation, live-action-ready, or terminal-closure claims.
7. Reject public claim drift such as production ready, customer ready, live Gmail enabled, or autonomous execution.

Component graph validation follows this deterministic sequence:

1. Load `schemas/component_graph.schema.json` and `examples/component_graph.foundation.json`.
2. Rebuild the graph from the registry, read model, request simulations, and autopsies.
3. Validate the example against the component graph schema.
4. Reject example drift from the runtime graph.
5. Reject edge endpoints that do not reference registered component nodes.
6. Require blocked paths to cover every component.
7. Reject live execution, connector call, mutation, or terminal-closure claims.

Dead-component detector validation follows this deterministic sequence:

1. Load `schemas/component_dead_component_detection.schema.json` and `examples/component_dead_component_detection.foundation.json`.
2. Rebuild the report from the component graph and read model.
3. Validate the example against the detector schema.
4. Reject example drift from the runtime report.
5. Require summary counts to match component detections.
6. Require blocked-governed components to carry proof or evidence signals.
7. Require true dead candidates to carry multiple missing relationship signals.
8. Reject live execution, connector call, mutation, or terminal-closure claims.

Lifecycle transition receipt validation follows this deterministic sequence:

1. Load `schemas/component_lifecycle_transition_receipts.schema.json`, `examples/component_lifecycle_transition_receipts.foundation.json`, and the component registry.
2. Validate the receipt set against the lifecycle transition receipt schema.
3. Reuse the component registry validator before accepting lifecycle receipts.
4. Require the allowed transition graph to match the foundation allowed pairs.
5. Require exactly one transition receipt for every registered component.
6. Require each receipt target state, wiring state, and authority level to match the registry.
7. Reject missing evidence refs, missing validator refs, proof states other than `Pass`, external effects, terminal-closure claims, and live authority guardrail drift.
8. Reject transition targets that would grant `approved_live_action`.

## Verification

Run:

```powershell
python scripts/validate_component_registry.py --strict
python scripts/validate_component_router_inventory.py --strict
python scripts/validate_component_proof_binding.py --strict
python scripts/validate_component_read_model.py --strict
python scripts/validate_component_autopsy.py --strict
python scripts/validate_component_request_simulation.py --strict
python scripts/validate_component_bundle_compiler.py --strict
python scripts/validate_component_graph.py --strict
python scripts/validate_component_dead_detector.py --strict
python scripts/validate_component_lifecycle_transition_receipts.py --strict
python -m pytest tests/test_validate_component_registry.py -q
python -m pytest tests/test_validate_component_router_inventory.py -q
python -m pytest tests/test_validate_component_proof_binding.py -q
python -m pytest tests/test_validate_component_read_model.py tests/test_validate_component_autopsy.py tests/test_validate_component_request_simulation.py tests/test_validate_component_bundle_compiler.py tests/test_validate_component_graph.py tests/test_validate_component_dead_detector.py tests/test_validate_component_lifecycle_transition_receipts.py mcoi/tests/test_component_read_model_route.py mcoi/tests/test_component_autopsy_route.py mcoi/tests/test_component_request_simulator.py mcoi/tests/test_component_bundle_compiler.py -q
python scripts/validate_protocol_manifest.py
```

The full workspace preflight also includes the component registry and component
router inventory validators, plus the component proof binding, component
read-model, component autopsy, component request simulation, component bundle
compiler, component graph, component dead detector, and component lifecycle
transition receipt validators.

## Non-Goals

The current harness boundary does not:

1. Bind every proof-relevant declared route to a final component owner.
2. Enforce proof matrix binding against every route outside the current selected harness set.
3. Enable live action, connector calls, filesystem writes, mailbox mutation, external sends, deployment, public readiness, or terminal closure.

The router inventory refinement does not:

1. Bind all 424 proof-relevant declared routes to final product components.
2. Create a runtime component router.
3. Promote `no_declared_route` components to mounted route posture.
4. Enable live action, connector calls, filesystem writes, mailbox mutation, external sends, deployment, public readiness, or terminal closure.

STATUS:
  Completeness: 100%
  Invariants verified: component identity declared, aliases unique, dependencies registered, lifecycle transitions receipt-bound, selected component route families bound, router proof surfaces mirrored, proof-bound components tied to proof matrix surfaces, receipt-required components tied to runtime witnesses, component read model route GET-only, component autopsy route GET-only, component request simulator route POST-only and preview-only, product bundle compiler preview-only, component graph endpoint-closed, dead-component detector separates blocked-governed from dead-candidate posture, bundles non-executing, mounted is not live, bootstrapped is not authorized, live authority false, live-action state labels blocked, proof evidence files present, foundation guardrails closed
  Open issues: full-route component binding
  Next action: extend router inventory binding toward the remaining declared route families without enabling live execution
