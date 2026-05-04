<!--
Purpose: Human-readable closure manifest for the governed general-agent capability buildout.
Governance scope: Records the capability families, readiness stamp, production blockers, and verification evidence.
Dependencies: docs/56_general_agent_capability_roadmap.md, scripts/validate_general_agent_promotion.py, scripts/plan_capability_adapter_closure.py, scripts/plan_deployment_publication_closure.py, scripts/plan_general_agent_promotion_closure.py, scripts/validate_general_agent_promotion_closure_plan.py, capability packs, capsules, gateway tests.
Invariants: Uses symbolic intelligence terminology, separates built governed capability surface from live production evidence, and preserves explicit blocker traceability.
-->

# General Agent Capability Closure Manifest

## Architecture

The current build moves Mullu from prompt-only extension toward governed capability execution. The control plane now exposes a default governed capability fabric with:

| Measure | Value |
| --- | ---: |
| Capability capsules | 10 capsules |
| Governed capabilities | 52 capabilities |
| Promotion readiness level | `pilot-governed-core` |

The closure boundary is precise:

```text
Mullu control plane
-> governed capability registry
-> policy / ownership / approval / obligation checks
-> bounded worker or connector contract
-> receipt / evidence record
-> promotion-readiness validation
```

This is not a public-production claim. It is a governed-core readiness claim with explicit adapter and deployment blockers still open.

## Capability Families Closed

| Family | Closure state | Representative governed capability |
| --- | --- | --- |
| Capability registry | Built | `capability.registry.read` |
| Sandboxed computer control | Built as governed worker contract | `computer.sandbox.run` |
| Document worker | Built as parser-first worker contract | `document.pdf.extract_text` |
| Browser worker | Built as receipt-first worker contract | `browser.open` |
| Email and calendar | Built as approval-gated worker contract | `email.send.with_approval` |
| Data connectors | Built as scoped connector capability packs | `connector.github.read` |
| Automatic governed memory | Built as admission-gated closure memory | `memory.episodic_closure` |
| Workflow automation | Built as checkpointed governed execution | `workflow.resume` |
| Specialist delegation | Built as bounded lease runtime | `agent.delegate` |
| Voice | Built as transcript-to-intent worker contract | `voice.intent_confirm` |
| Runtime Reflex Engine | Built as operator-gated evaluation and proposal surface | `/runtime/self/witness` |
| Operator capability console | Built as read-only governed surface | `/operator/capabilities` |
| Deployment witness | Built as governed publication capability | `deployment.witness.publish.with_approval` |
| Adapter closure planning | Built as blocker-to-action planner | `scripts/plan_capability_adapter_closure.py` |
| Deployment closure planning | Built as publication blocker planner | `scripts/plan_deployment_publication_closure.py` |
| Promotion closure planning | Built as aggregate closure planner | `scripts/plan_general_agent_promotion_closure.py` |
| Adapter closure schema | Built as public source-plan contract | `schemas/capability_adapter_closure_plan.schema.json` |
| Adapter closure schema validation | Built as shape, proof-contract, and blocker coverage gate | `scripts/validate_capability_adapter_closure_plan_schema.py` |
| Promotion closure schema | Built as public plan contract | `schemas/general_agent_promotion_closure_plan.schema.json` |
| Promotion closure schema validation | Built as shape and count gate | `scripts/validate_general_agent_promotion_closure_plan_schema.py` |
| Promotion closure validation | Built as aggregate plan drift gate | `scripts/validate_general_agent_promotion_closure_plan.py` |
| Promotion operator runbook | Built as external execution procedure | `docs/58_general_agent_promotion_operator_runbook.md` |
| Promotion operator checklist | Built as machine-readable execution checklist | `examples/general_agent_promotion_operator_checklist.json` |
| Promotion handoff packet | Built as single operator entry point | `docs/59_general_agent_promotion_handoff_packet.md` |
| Promotion machine handoff packet | Built as schema-backed handoff artifact | `examples/general_agent_promotion_handoff_packet.json` |
| Promotion handoff packet validation | Built as packet schema and blocker gate | `scripts/validate_general_agent_promotion_handoff_packet.py` |
| Promotion environment binding contract | Built as no-secret binding ontology | `examples/general_agent_promotion_environment_bindings.json` |
| Promotion environment binding validation | Built as contract/checklist drift gate | `scripts/validate_general_agent_promotion_environment_bindings.py` |
| Promotion environment binding receipt | Built and validated as redacted binding presence witness | `scripts/emit_general_agent_promotion_environment_binding_receipt.py`, `scripts/validate_general_agent_promotion_environment_binding_receipt.py` |
| Promotion handoff preflight | Built as local execution readiness check | `scripts/preflight_general_agent_promotion_handoff.py` |
| Runtime Reflex proof coverage | Built as non-mutating runtime evaluation witness | `scripts/proof_coverage_matrix.py` |

## Open Production Blockers

The readiness validator still reports these blockers:

```text
adapter_evidence_not_closed
browser_adapter_not_closed
voice_adapter_not_closed
email_calendar_adapter_not_closed
deployment_witness_not_published
production_health_not_declared
```

These blockers mean the governed contracts exist, but browser, voice, email/calendar, public deployment witness publication, and declared production health are not yet closed. Document parser adapter evidence is closed; external document send, sign, and submit effects remain approval-gated.

## Algorithm

The promotion-readiness path is:

1. Load the default governed capability fabric.
2. Verify capability capsule count and required domains.
3. Verify governed record surfaces and MCP manifest alignment.
4. Verify adapter evidence markers.
5. Verify deployment status markers.
6. Emit a readiness level and blocker list.
7. Optionally write `.change_assurance/general_agent_promotion_readiness.json`.

The adapter-closure planning path is:

1. Collect adapter evidence into `.change_assurance/capability_adapter_evidence.json`.
2. Preserve every blocker from browser, document, voice, and email/calendar evidence.
3. Map dependency blockers to image/runtime installation actions.
4. Map credential blockers to governed secret-store actions with approval.
5. Map live-evidence blockers to receipt-production commands.
6. Write `.change_assurance/capability_adapter_closure_plan.json` without claiming closure.

The deployment-closure planning path is:

1. Read `.change_assurance/general_agent_promotion_readiness.json`.
2. Preserve `deployment_witness_not_published` and `production_health_not_declared`.
3. Map witness publication to an approval-gated `publish_gateway_publication.py` action.
4. Map health declaration to an evidence-gated `DEPLOYMENT_STATUS.md` update action.
5. Write `.change_assurance/deployment_publication_closure_plan.json` without mutating status.

The aggregate promotion-closure planning path is:

1. Read adapter and deployment closure plans.
2. Preserve all source blockers and source plan names.
3. Tag each action with its source plan type.
4. Count approval-required actions.
5. Write `.change_assurance/general_agent_promotion_closure_plan.json`.

The aggregate promotion-closure schema validation path is:

1. Load `schemas/general_agent_promotion_closure_plan.schema.json`.
2. Validate `.change_assurance/general_agent_promotion_closure_plan.json`.
3. Recompute total action and approval-required action counts.
4. Require non-empty plans to include adapter and deployment source actions.
5. Write `.change_assurance/general_agent_promotion_closure_plan_schema_validation.json`.

The aggregate promotion-closure validation path is:

1. Load readiness, adapter plan, deployment plan, and aggregate plan artifacts.
2. Recompute expected action count from source plans.
3. Recompute approval-required action count from source actions.
4. Verify every source action appears once with its source plan type.
5. Write `.change_assurance/general_agent_promotion_closure_plan_validation.json`.

The handoff preflight path is:

1. Validate the operator checklist and schema-backed handoff packet.
2. Validate the environment binding contract against the checklist.
3. Emit `.change_assurance/general_agent_promotion_environment_binding_receipt.json` with names and presence only.
4. Validate `.change_assurance/general_agent_promotion_environment_binding_receipt.json` against the contract before preflight.
5. Verify required environment bindings by variable name without serializing secret values.
6. Verify adapter source-plan schema validation before aggregate promotion validation.
7. Verify aggregate schema validation, aggregate drift validation, and readiness report counts.
8. Write `.change_assurance/general_agent_promotion_handoff_preflight.json`.

## Verification

Latest local verification covered:

| Verification target | Result |
| --- | --- |
| Adapter closure planning tests | passed |
| Deployment closure planning tests | passed |
| Promotion closure planning tests | passed |
| Adapter closure schema tests | passed |
| Promotion closure schema tests | passed |
| Promotion closure validation tests | passed |
| Promotion operator runbook tests | passed |
| Promotion operator checklist tests | passed |
| Promotion handoff packet tests | passed |
| Promotion environment binding tests | passed |
| Promotion environment binding receipt tests | passed |
| Promotion handoff preflight tests | passed |
| Promotion handoff packet validator tests | passed |
| Promotion readiness tests | passed |
| Governed-core validation sweep | 519 passed |
| Ruff on changed gateway, scripts, and tests | passed |

The generated readiness artifact reported:

```text
readiness_level: pilot-governed-core
capability_count: 52
capsule_count: 10
```

STATUS:
  Completeness: 97%
  Invariants verified: [governed capability count recorded, capsule count recorded, production blockers explicit, adapter closure plan bound to evidence, deployment closure plan approval-gated, aggregate promotion closure plan source-tagged, aggregate closure plan schema gate present, aggregate closure plan validation gate present, operator execution runbook present, machine-readable operator checklist present, single handoff packet present, schema-backed handoff packet present, deployment witness capability named, public-production claim avoided]
  Open issues: [live adapter evidence, deployment witness publication, production health declaration]
  Next action: run the aggregate promotion closure plan after live worker dependencies, governed connector credentials, and deployment publication approval are available
