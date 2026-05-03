<!--
Purpose: Operator runbook for executing the governed general-agent promotion closure plan.
Governance scope: Adapter evidence, credential binding, deployment witness publication, health declaration, and promotion validation.
Dependencies: scripts/collect_capability_adapter_evidence.py, scripts/plan_general_agent_promotion_closure.py, scripts/validate_general_agent_promotion_closure_plan_schema.py, scripts/validate_general_agent_promotion_closure_plan.py, DEPLOYMENT_STATUS.md.
Invariants: Does not claim production readiness before live evidence, approval, and publication closure validate.
-->

# General-Agent Promotion Operator Runbook

## Architecture

This runbook executes the aggregate closure plan without bypassing governance:

```text
adapter evidence
-> promotion readiness
-> adapter closure plan
-> deployment closure plan
-> aggregate closure plan
-> aggregate closure schema validation
-> aggregate closure validation
-> live execution with approvals
-> regenerated evidence
-> production promotion validation
```

The current expected aggregate plan contains:

| Measure | Value |
| --- | ---: |
| Total closure actions | 7 |
| Approval-required actions | 4 |
| Source plan types | `adapter`, `deployment` |
| Current readiness level | `pilot-governed-core` |

## Prerequisites

| Boundary | Required input |
| --- | --- |
| Browser worker | Playwright package, browser runtime, sandbox receipt JSON path |
| Document worker | Parser imports and live parser receipt already closed; external effects remain approval-gated |
| Voice worker | OpenAI provider client, governed `OPENAI_API_KEY`, approved audio sample |
| Email/calendar worker | One scoped connector token and read-only probe target |
| Deployment publication | `MULLU_GATEWAY_URL`, runtime witness secret, conformance secret, operator approval |
| Public health declaration | Published deployment witness and HTTPS health probe receipt |

Secrets must be bound through the governed worker or deployment secret store. Do not print secret values in receipts, logs, status files, or closure plans.

## Algorithm

0. Validate the machine-readable operator checklist:

```powershell
python scripts\validate_general_agent_promotion_operator_checklist.py --checklist examples\general_agent_promotion_operator_checklist.json --json
python scripts\validate_general_agent_promotion_handoff_packet.py --packet examples\general_agent_promotion_handoff_packet.json --json
python scripts\validate_general_agent_promotion_environment_bindings.py --contract examples\general_agent_promotion_environment_bindings.json --json
python scripts\emit_general_agent_promotion_environment_binding_receipt.py --output .change_assurance\general_agent_promotion_environment_binding_receipt.json --json
python scripts\validate_general_agent_promotion_environment_binding_receipt.py --receipt .change_assurance\general_agent_promotion_environment_binding_receipt.json --require-ready --json
```

1. Generate the non-production evidence and plans:

```powershell
python scripts\collect_capability_adapter_evidence.py --output .change_assurance\capability_adapter_evidence.json
python scripts\validate_general_agent_promotion.py --output .change_assurance\general_agent_promotion_readiness.json
python scripts\plan_capability_adapter_closure.py --output .change_assurance\capability_adapter_closure_plan.json
python scripts\plan_deployment_publication_closure.py --output .change_assurance\deployment_publication_closure_plan.json
python scripts\plan_general_agent_promotion_closure.py --output .change_assurance\general_agent_promotion_closure_plan.json
python scripts\validate_general_agent_promotion_closure_plan_schema.py --output .change_assurance\general_agent_promotion_closure_plan_schema_validation.json --strict
python scripts\validate_general_agent_promotion_closure_plan.py --output .change_assurance\general_agent_promotion_closure_plan_validation.json --strict
```

2. Run handoff preflight. The binding receipt and preflight record only environment variable names and presence status; they must not print secret values.

```powershell
python scripts\preflight_general_agent_promotion_handoff.py --output .change_assurance\general_agent_promotion_handoff_preflight.json --strict --json
python scripts\validate_general_agent_promotion_handoff_preflight.py --report .change_assurance\general_agent_promotion_handoff_preflight.json --require-ready --json
```

3. Inspect `.change_assurance/general_agent_promotion_closure_plan.json`.

4. Complete dependency actions in the adapter-worker images.

5. Complete approval-required credential actions:

```text
voice_dependency_missing:OPENAI_API_KEY
email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN
deployment_witness_not_published
production_health_not_declared
```

6. Produce live adapter receipts:

```powershell
python scripts\produce_browser_sandbox_evidence.py --output "$env:MULLU_BROWSER_SANDBOX_EVIDENCE" --strict
python scripts\validate_browser_sandbox_evidence.py --evidence "$env:MULLU_BROWSER_SANDBOX_EVIDENCE" --json
python scripts\produce_capability_adapter_live_receipts.py --target browser --browser-sandbox-evidence "$env:MULLU_BROWSER_SANDBOX_EVIDENCE" --strict
python scripts\produce_capability_adapter_live_receipts.py --target document --strict
python scripts\produce_capability_adapter_live_receipts.py --target voice --voice-audio-path "$env:MULLU_VOICE_PROBE_AUDIO" --strict
python scripts\produce_capability_adapter_live_receipts.py --target email-calendar --strict
```

7. Regenerate adapter evidence:

```powershell
python scripts\collect_capability_adapter_evidence.py --strict --output .change_assurance\capability_adapter_evidence.json
```

8. Publish deployment witness only after approval:

```powershell
python scripts\publish_gateway_publication.py --gateway-url "$env:MULLU_GATEWAY_URL" --dispatch-witness --dispatch --receipt-output .change_assurance\gateway_publication_receipt.json
python scripts\validate_gateway_publication_receipt.py --receipt .change_assurance\gateway_publication_receipt.json --require-ready --require-dispatched --require-success
python scripts\validate_deployment_publication_closure.py
```

9. Update `DEPLOYMENT_STATUS.md` only when `.change_assurance/deployment_witness.json` has `deployment_claim=published` and the public health endpoint equals `<gateway_url>/health`.

10. Run final promotion validation:

```powershell
python scripts\validate_general_agent_promotion.py --strict --output .change_assurance\general_agent_promotion_readiness.json
```

## Failure Rules

| Failure | Required response |
| --- | --- |
| Aggregate validation fails | Regenerate source plans, then validate again |
| Aggregate schema validation fails | Regenerate the aggregate plan and stop before approval |
| Dependency import fails | Rebuild the affected worker image and keep promotion blocked |
| Credential action lacks approval | Do not bind the secret and keep promotion blocked |
| Live receipt fails | Preserve the failed receipt and blocker |
| Deployment witness is not published | Do not update `DEPLOYMENT_STATUS.md` |
| Health endpoint mismatch | Do not claim public production health |

STATUS:
  Completeness: 99%
  Invariants verified: [aggregate plan validation before execution, credential approval required, live receipts required, deployment status mutation evidence-gated, production promotion validation terminal]
  Open issues: [external dependencies, governed credentials, live deployment witness, public health probe]
  Next action: execute this runbook in the credentialed adapter-worker and deployment environment
