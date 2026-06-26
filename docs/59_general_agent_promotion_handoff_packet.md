<!--
> **In one box:** The single starting point that bundles the operator
> checklist, runbook, plans, and proofs for general-agent promotion. New? See
> the Plain-English Overview (docs/explain/PLAIN_ENGLISH.md). *(Doc type: How-to.)*

Purpose: Single entry-point handoff packet for general-agent promotion final validation.
Governance scope: Operator checklist, runbook, closure plans, validation reports, terminal approval gates, terminal certificate minting, and final promotion proof.
Dependencies: docs/58_general_agent_promotion_operator_runbook.md, examples/general_agent_promotion_operator_checklist.json, .change_assurance promotion closure artifacts.
Invariants: Production readiness is evidence-bound; live evidence closure, approval refs, terminal minting authority, and terminal certificates remain explicit and schema-valid.
-->

# General-Agent Promotion Handoff Packet

## Architecture

This packet is the operator entry point for final promotion validation. It binds the human-readable runbook, machine-readable checklist, generated closure plans, and validation reports into one traceable handoff.

| Field | Current value |
| --- | --- |
| Readiness level | `pilot-governed-core` |
| Capability capsules | 13 |
| Governed capabilities | 81 |
| Aggregate closure actions | 10 |
| Approval-required actions | 8 |
| Closure plan schema validation | `ok=true` |
| Closure plan drift validation | `ok=true` |
| Terminal certificate minting | 6 minted, 0 blocked; adapter evidence and upstream readiness remain open |
| Production promotion | blocked |

## Entry Points

| Purpose | Artifact |
| --- | --- |
| Human execution procedure | `docs/58_general_agent_promotion_operator_runbook.md` |
| Machine-readable checklist | `examples/general_agent_promotion_operator_checklist.json` |
| Machine-readable handoff packet | `examples/general_agent_promotion_handoff_packet.json` |
| Environment binding contract | `examples/general_agent_promotion_environment_bindings.json` |
| Checklist validator | `scripts/validate_general_agent_promotion_operator_checklist.py` |
| Handoff packet validator | `scripts/validate_general_agent_promotion_handoff_packet.py` |
| Environment binding validator | `scripts/validate_general_agent_promotion_environment_bindings.py` |
| Environment binding receipt emitter | `scripts/emit_general_agent_promotion_environment_binding_receipt.py` |
| Environment binding receipt validator | `scripts/validate_general_agent_promotion_environment_binding_receipt.py` |
| Handoff preflight | `scripts/preflight_general_agent_promotion_handoff.py` |
| Handoff preflight validator | `scripts/validate_general_agent_promotion_handoff_preflight.py` |
| Aggregate closure plan | `.change_assurance/general_agent_promotion_closure_plan.json` |
| Capability improvement portfolio | `.change_assurance/capability_improvement_portfolio.json` |
| Capability improvement proof receipt producer | `scripts/produce_capability_improvement_proof_receipt.py` |
| Capability improvement proof receipt schema | `schemas/capability_improvement_proof_receipt.schema.json` |
| Capability improvement proof receipts | `.change_assurance/capability_improvement_proof_receipt*.json` |
| Closure chain runner | `scripts/run_general_agent_promotion_closure_chain.py` |
| Schema validation report | `.change_assurance/general_agent_promotion_closure_plan_schema_validation.json` |
| Drift validation report | `.change_assurance/general_agent_promotion_closure_plan_validation.json` |
| Live-evidence queue planner | `scripts/plan_general_agent_promotion_live_evidence_queue.py` |
| Live-evidence queue | `.change_assurance/general_agent_promotion_live_evidence_queue.json` |
| Terminal approval receipt | `.change_assurance/general_agent_promotion_terminal_approvals.json` |
| Terminal approval receipt schema | `schemas/general_agent_promotion_terminal_approvals.schema.json` |
| Terminal approval receipt validator | `scripts/validate_general_agent_promotion_terminal_approvals.py` |
| Terminal certificate gate planner | `scripts/plan_general_agent_promotion_terminal_certificate_gate.py` |
| Terminal certificate gate | `.change_assurance/general_agent_promotion_terminal_certificate_gate.json` |
| Terminal certificate candidate planner | `scripts/plan_general_agent_promotion_terminal_certificate_candidates.py` |
| Terminal certificate candidates schema | `schemas/general_agent_promotion_terminal_certificate_candidates.schema.json` |
| Terminal certificate candidates | `.change_assurance/general_agent_promotion_terminal_certificate_candidates.json` |
| Terminal evidence reconciliation planner | `scripts/reconcile_general_agent_promotion_terminal_evidence.py` |
| Terminal evidence reconciliation schema | `schemas/general_agent_promotion_terminal_evidence_reconciliation.schema.json` |
| Terminal evidence reconciliation | `.change_assurance/general_agent_promotion_terminal_evidence_reconciliation.json` |
| Terminal minting gate planner | `scripts/gate_general_agent_promotion_terminal_minting.py` |
| Terminal minting gate schema | `schemas/general_agent_promotion_terminal_minting_gate.schema.json` |
| Terminal minting gate | `.change_assurance/general_agent_promotion_terminal_minting_gate.json` |
| Terminal certificate minting executor | `scripts/mint_general_agent_promotion_terminal_certificates.py` |
| Terminal certificate minting run schema | `schemas/general_agent_promotion_terminal_certificate_minting_run.schema.json` |
| Terminal certificate minting run | `.change_assurance/general_agent_promotion_terminal_certificate_minting_run.json` |
| Readiness report | `.change_assurance/general_agent_promotion_readiness.json` |
| Preflight report | `.change_assurance/general_agent_promotion_handoff_preflight.json` |
| Environment binding receipt | `.change_assurance/general_agent_promotion_environment_binding_receipt.json` |

## Open Blockers

```text
adapter_evidence_not_closed
```

## Terminal Approval Actions

```text
voice_dependency_missing:OPENAI_API_KEY
deployment_upstream_api_gate_not_ready
capability_improvement_required:financial.refund
capability_improvement_required:agentic_control.code_change.plan
capability_improvement_required:agentic_control.evidence.append
capability_improvement_required:agentic_control.governance_gate.evaluate
capability_improvement_required:agentic_control.incident_recovery.plan
```

Browser adapter sandbox and live evidence are closed. The five
repository-local capability-improvement actions were admitted through
explicit operator approval refs, reconciled against live evidence and proof
receipts, then minted into terminal closure certificates during the 2026-06-12
promotion-chain run. Voice credential binding, email/calendar connector
binding, upstream API/DNS readiness, and residual adapter live evidence remain
bounded before production promotion.

## Latest Terminal Minting Witness

| Artifact | Result |
| --- | --- |
| Approval receipt | `.tmp/promotion-chain-latest/general_agent_promotion_terminal_approvals.json` validated with 6 approvals and no serialized secret values |
| Terminal certificate gate | `.tmp/promotion-chain-latest/general_agent_promotion_terminal_certificate_gate.approved.json` admitted 6 actions, blocked 0 |
| Terminal evidence reconciliation | `.tmp/promotion-chain-latest/general_agent_promotion_terminal_evidence_reconciliation.ready.json` reconciled 6 candidates, missing evidence 0 |
| Terminal minting gate | `.tmp/promotion-chain-latest/general_agent_promotion_terminal_minting_gate.authorized.json` admitted 6 candidates under `approval://terminal-minting/general-agent-promotion/2026-06-12-operator-approved` |
| Minting run | `.tmp/promotion-chain-latest/general_agent_promotion_terminal_certificate_minting_run.json` minted 6 certificates, blocked 0, no serialized secret values |
| Certificate directory | `.tmp/promotion-chain-latest/terminal_certificates/` contains the 6 schema-valid terminal closure certificates |

## Operator Sequence

1. Validate the machine-readable handoff packet.
2. Validate the operator checklist.
3. Regenerate adapter evidence and readiness.
4. Run the closure artifact chain to regenerate adapter, deployment, portfolio, aggregate, schema, drift, live-evidence queue, terminal certificate gate, terminal certificate candidate, terminal evidence reconciliation, and terminal minting gate artifacts.
5. Review the activation-blocked capability improvement portfolio.
6. Inspect the live-evidence queue before executing any closure command.
7. Validate the terminal approval receipt when approval refs are supplied.
8. Inspect the terminal certificate gate before executing any closure command.
9. Inspect terminal certificate candidates and verify minting remains false.
10. Produce capability-improvement proof receipts for approved repository-local portfolio candidates.
11. Inspect terminal evidence reconciliation and verify passed receipts match candidate evidence.
12. Inspect terminal minting gate and verify minting readiness is admitted only when reconciliation is ready and explicit authority is supplied.
13. Run the terminal certificate minting executor only after the terminal minting gate is ready; the 2026-06-12 authorized run minted 6 terminal certificates.
14. Validate aggregate closure plan schema.
15. Validate aggregate closure plan drift.
16. Emit and validate the redacted environment binding receipt.
17. Re-run the live-evidence queue, terminal certificate gate, terminal certificate candidate, terminal evidence reconciliation, and terminal minting gate planners if bindings, approvals, receipts, or authority refs changed after the closure chain.
18. Complete dependency, credential, deployment, and portfolio actions with approval where required.
19. Produce live adapter receipts.
20. Publish deployment witness with approval only after runtime and authority responsibility debt are clear.
21. Update `DEPLOYMENT_STATUS.md` only after published witness, debt-clear witness fields, and matching health probe evidence exist.
22. Run final strict promotion validation.

Browser adapter evidence is closed only when the adapter evidence report
preserves both `browser-sandbox-evidence-*` and `sandbox-receipt-*` refs from
the browser sandbox proof.

## Terminal Proof Command

```powershell
python scripts\validate_general_agent_promotion.py --strict --output .change_assurance\general_agent_promotion_readiness.json
```

The terminal command must not pass unless upstream API readiness, governed
portfolio review actions, terminal certificate minting, deployment witness
publication, public health declaration, and live adapter evidence remain closed
for `api.mullusi.com`.

STATUS:
  Completeness: 92%
  Invariants verified: [single handoff entry point, machine-readable handoff packet linked, checklist linked, runbook linked, validation reports linked, live-evidence queue linked, terminal approval receipt contract linked, terminal certificate gate linked, terminal certificate candidate contract linked, capability improvement proof receipt linked, terminal evidence reconciliation contract linked, terminal minting gate linked, terminal certificate minting run contract linked, terminal certificates minted, blockers explicit, deployment witness published, public health declared, browser adapter evidence closed]
  Open issues: [voice credential binding, voice live receipt, email/calendar connector binding, email/calendar live receipt, final promotion validation remains blocked]
  Next action: bind governed voice and email/calendar evidence inputs, regenerate receipts, then rerun strict promotion validation
