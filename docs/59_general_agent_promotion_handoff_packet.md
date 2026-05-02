<!--
Purpose: Single entry-point handoff packet for general-agent promotion closure execution.
Governance scope: Operator checklist, runbook, closure plans, validation reports, blockers, and final promotion proof.
Dependencies: docs/58_general_agent_promotion_operator_runbook.md, examples/general_agent_promotion_operator_checklist.json, .change_assurance promotion closure artifacts.
Invariants: Does not claim production readiness; keeps live evidence and approval blockers explicit.
-->

# General-Agent Promotion Handoff Packet

## Architecture

This packet is the operator entry point for the remaining promotion work. It binds the human-readable runbook, machine-readable checklist, generated closure plans, and validation reports into one traceable handoff.

| Field | Current value |
| --- | --- |
| Readiness level | `pilot-governed-core` |
| Capability capsules | 10 |
| Governed capabilities | 52 |
| Aggregate closure actions | 14 |
| Approval-required actions | 4 |
| Closure plan schema validation | `ok=true` |
| Closure plan drift validation | `ok=true` |
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
| Handoff preflight | `scripts/preflight_general_agent_promotion_handoff.py` |
| Aggregate closure plan | `.change_assurance/general_agent_promotion_closure_plan.json` |
| Schema validation report | `.change_assurance/general_agent_promotion_closure_plan_schema_validation.json` |
| Drift validation report | `.change_assurance/general_agent_promotion_closure_plan_validation.json` |
| Readiness report | `.change_assurance/general_agent_promotion_readiness.json` |
| Preflight report | `.change_assurance/general_agent_promotion_handoff_preflight.json` |

## Open Blockers

```text
adapter_evidence_not_closed
browser_adapter_not_closed
document_adapter_not_closed
voice_adapter_not_closed
email_calendar_adapter_not_closed
deployment_witness_not_published
production_health_not_declared
```

## Approval-Required Actions

```text
voice_dependency_missing:OPENAI_API_KEY
email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN
deployment_witness_not_published
production_health_not_declared
```

## Operator Sequence

1. Validate the machine-readable handoff packet.
2. Validate the operator checklist.
3. Regenerate adapter evidence and readiness.
4. Regenerate adapter, deployment, and aggregate closure plans.
5. Validate aggregate closure plan schema.
6. Validate aggregate closure plan drift.
7. Complete dependency and credential actions with approval where required.
8. Produce live adapter receipts.
9. Publish deployment witness with approval.
10. Update `DEPLOYMENT_STATUS.md` only after published witness and matching health probe evidence exist.
11. Run final strict promotion validation.

## Terminal Proof Command

```powershell
python scripts\validate_general_agent_promotion.py --strict --output .change_assurance\general_agent_promotion_readiness.json
```

The terminal command must not pass until live adapter evidence, deployment witness publication, and public health declaration are all closed.

STATUS:
  Completeness: 99%
  Invariants verified: [single handoff entry point, machine-readable handoff packet linked, checklist linked, runbook linked, validation reports linked, blockers explicit, production readiness not claimed]
  Open issues: [external dependencies, governed credentials, live adapter receipts, deployment witness publication, public health probe]
  Next action: execute the validated checklist and runbook in the credentialed adapter-worker and deployment environment
