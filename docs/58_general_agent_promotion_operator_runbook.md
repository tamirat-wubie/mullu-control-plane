<!--
> **In one box:** Step-by-step for operators to execute the general-agent
> promotion final validation. Production readiness is evidence-bound and
> terminal minting remains authority-gated. New? See the Plain-English Overview
> (docs/explain/PLAIN_ENGLISH.md). *(Doc type: How-to.)*

Purpose: Operator runbook for executing governed general-agent promotion final validation.
Governance scope: Adapter evidence, credential binding, upstream API/DNS readiness, deployment witness publication, health declaration, residual portfolio review, capability improvement proof receipts, and promotion validation.
Dependencies: scripts/collect_capability_adapter_evidence.py, scripts/run_general_agent_promotion_closure_chain.py, scripts/plan_general_agent_promotion_closure.py, scripts/plan_general_agent_promotion_live_evidence_queue.py, scripts/validate_general_agent_promotion_terminal_approvals.py, scripts/plan_general_agent_promotion_terminal_certificate_gate.py, scripts/plan_general_agent_promotion_terminal_certificate_candidates.py, scripts/produce_capability_improvement_proof_receipt.py, scripts/reconcile_general_agent_promotion_terminal_evidence.py, scripts/collect_deployment_publication_evidence_packet.py, scripts/validate_deployment_publication_evidence_packet.py, scripts/emit_deployment_publication_operator_input_request.py, scripts/validate_deployment_publication_operator_input_request.py, scripts/emit_deployment_upstream_blocker_receipt.py, scripts/validate_deployment_upstream_blocker_receipt.py, scripts/emit_gateway_dns_target_binding_receipt.py, scripts/validate_gateway_dns_target_binding_receipt.py, scripts/collect_gateway_dns_resolution_receipt.py, scripts/validate_gateway_dns_resolution_receipt.py, scripts/validate_general_agent_promotion_closure_plan_schema.py, scripts/validate_general_agent_promotion_closure_plan.py, DEPLOYMENT_STATUS.md.
Invariants: Production readiness remains evidence-bound; terminal certificate minting requires explicit authority.
-->

# General-Agent Promotion Operator Runbook

## Architecture

This runbook executes the aggregate closure plan without bypassing governance:

```text
adapter evidence
-> promotion readiness
-> adapter closure plan
-> adapter closure schema validation
-> deployment closure plan
-> capability improvement portfolio
-> aggregate closure plan
-> aggregate closure schema validation
-> aggregate closure validation
-> live-evidence queue classification
-> terminal certificate admission gate
-> terminal certificate candidate planning
-> capability improvement proof receipt production
-> terminal evidence reconciliation
-> terminal minting gate
-> live execution with approvals
-> regenerated evidence
-> production promotion validation
```

The current expected aggregate plan contains:

| Measure | Value |
| --- | ---: |
| Total closure actions | 10 |
| Approval-required actions | 8 |
| Source plan types | `adapter`, `deployment`, and `portfolio` |
| Current readiness level | `pilot-governed-core` |

The target readiness remains `production-general-agent`, but final execution is
currently gated by adapter evidence, upstream API readiness, and governed
portfolio review actions.

## Prerequisites

| Boundary | Required input |
| --- | --- |
| Browser worker | Playwright package, browser runtime, sandbox receipt JSON path |
| Document worker | Parser imports and live parser receipt already closed; external effects remain approval-gated |
| Voice worker | OpenAI provider client, governed `OPENAI_API_KEY`, approved audio sample |
| Email/calendar worker | One scoped connector token and read-only probe target |
| Deployment publication | `MULLU_GATEWAY_URL`, `UPSTREAM_API_READINESS_REPORT`, upstream API/DNS readiness receipt, deployment publication evidence packet, deployment publication operator input request, `MULLU_GATEWAY_DNS_TARGET`, `MULLU_GATEWAY_DNS_RECORD_TYPE`, `MULLU_DNS_PROVIDER`, gateway DNS target-binding receipt, gateway DNS resolution receipt, runtime witness secret, conformance secret, deployment witness secret, runtime responsibility debt clear, authority responsibility debt clear, operator approval |
| Public health declaration | Published deployment witness and HTTPS health probe receipt |

Secrets must be bound through the governed worker or deployment secret store. Do not print secret values in receipts, logs, status files, or closure plans.

For GitHub-hosted live adapter evidence, use the manual
`Capability Adapter Live Evidence` workflow. The workflow can target `all`,
`browser`, `document`, `voice`, or `email-calendar`. Browser evidence runs on
GitHub-hosted Ubuntu, builds a minimal local `mullu-agent-runner:latest` sandbox
probe image, validates the sandbox receipt, and then emits the browser live
receipt. Document evidence emits the parser-family receipt without external
effects. Voice evidence expects `MULLU_VOICE_PROBE_AUDIO_B64` as a repository
secret containing the approved audio sample bytes encoded with base64.
Email/calendar evidence expects `EMAIL_CALENDAR_CONNECTOR_TOKEN` as a
repository secret for a read-only probe. The workflow decodes audio only inside
the runner, sets `MULLU_VOICE_PROBE_AUDIO` to the temporary runner path, and
uploads only JSON evidence artifacts. It does not upload raw audio, browser
screenshots, or secret values. The uploaded live receipts must still be
reviewed and merged into the current `.change_assurance` evidence packet before
terminal promotion validation is claimed.

The deployment witness publication path requires all of these bound names before
the handoff preflight can pass: `OPENAI_API_KEY`,
`EMAIL_CALENDAR_CONNECTOR_TOKEN`, `MULLU_GATEWAY_URL`,
`MULLU_GATEWAY_DNS_TARGET`, `MULLU_GATEWAY_DNS_RECORD_TYPE`,
`MULLU_DNS_PROVIDER`,
`MULLU_RUNTIME_WITNESS_SECRET`, `MULLU_RUNTIME_CONFORMANCE_SECRET`,
`MULLU_DEPLOYMENT_WITNESS_SECRET`, and `MULLU_AUTHORITY_OPERATOR_SECRET`.

## Algorithm

0. Validate the machine-readable operator checklist:

```powershell
python scripts\validate_general_agent_promotion_operator_checklist.py --checklist examples\general_agent_promotion_operator_checklist.json --json
python scripts\validate_general_agent_promotion_handoff_packet.py --packet examples\general_agent_promotion_handoff_packet.json --json
python scripts\validate_general_agent_promotion_environment_bindings.py --contract examples\general_agent_promotion_environment_bindings.json --json
python scripts\emit_general_agent_promotion_environment_binding_receipt.py --output .change_assurance\general_agent_promotion_environment_binding_receipt.json --json
python scripts\validate_general_agent_promotion_environment_binding_receipt.py --receipt .change_assurance\general_agent_promotion_environment_binding_receipt.json --require-ready --json
```

1. Generate the evidence and plans:

```powershell
python scripts\collect_capability_adapter_evidence.py --output .change_assurance\capability_adapter_evidence.json
python scripts\validate_general_agent_promotion.py --output .change_assurance\general_agent_promotion_readiness.json
python scripts\plan_capability_adapter_closure.py --output .change_assurance\capability_adapter_closure_plan.json
python scripts\plan_deployment_publication_closure.py --output .change_assurance\deployment_publication_closure_plan.json
python scripts\run_general_agent_promotion_closure_chain.py --json --strict
```

2. Run handoff preflight. The binding receipt and preflight record only environment variable names and presence status; they must not print secret values.

```powershell
python scripts\preflight_general_agent_promotion_handoff.py --output .change_assurance\general_agent_promotion_handoff_preflight.json --strict --json
python scripts\validate_general_agent_promotion_handoff_preflight.py --report .change_assurance\general_agent_promotion_handoff_preflight.json --require-ready --json
```

The handoff preflight is not ready unless `.change_assurance\capability_adapter_closure_plan_schema_validation.json` reports `ok=true` before aggregate closure reports are accepted.

The closure chain also writes `.change_assurance\capability_improvement_portfolio.json`, `.change_assurance\general_agent_promotion_closure_plan_schema_validation.json`, `.change_assurance\general_agent_promotion_closure_plan_validation.json`, `.change_assurance\general_agent_promotion_live_evidence_queue.json`, `.change_assurance\general_agent_promotion_terminal_certificate_gate.json`, `.change_assurance\general_agent_promotion_terminal_certificate_candidates.json`, `.change_assurance\general_agent_promotion_terminal_evidence_reconciliation.json`, and `.change_assurance\general_agent_promotion_terminal_minting_gate.json`; portfolio actions, terminal certificate candidates, and terminal minting gates are planning work and are not execution grants. When `.change_assurance\general_agent_promotion_terminal_approvals.json` exists, it must validate before the gate can admit approval-bound items.

Capability-improvement candidates can be reconciled by passed local proof receipts matching `.change_assurance\capability_improvement_proof_receipt*.json`. A proof receipt is not an execution grant, does not activate capabilities, does not mutate the registry, does not mint terminal certificates, and must not serialize secret values.

3. Inspect `.change_assurance\general_agent_promotion_live_evidence_queue.json` before executing any closure command. The queue classifies each source action as `runnable_local`, `requires_environment_binding`, `requires_execution_environment`, `requires_dependency_closure`, `requires_approval`, `approval_and_environment_blocked`, or `review_only`; it is not an execution grant.

4. Inspect `.change_assurance\general_agent_promotion_terminal_certificate_gate.json`. The gate admits only `runnable_local` queue items or approval-bound items with explicit approval refs; it does not admit environment-blocked or dependency-blocked actions by approval alone.

If terminal approval refs are supplied, validate them before rerunning the gate:

```powershell
python scripts\validate_general_agent_promotion_terminal_approvals.py --receipt .change_assurance\general_agent_promotion_terminal_approvals.json --json
python scripts\plan_general_agent_promotion_terminal_certificate_gate.py --queue .change_assurance\general_agent_promotion_live_evidence_queue.json --approval-receipt .change_assurance\general_agent_promotion_terminal_approvals.json --output .change_assurance\general_agent_promotion_terminal_certificate_gate.json --json --strict
python scripts\plan_general_agent_promotion_terminal_certificate_candidates.py --gate .change_assurance\general_agent_promotion_terminal_certificate_gate.json --output .change_assurance\general_agent_promotion_terminal_certificate_candidates.json --json --strict
python scripts\produce_capability_improvement_proof_receipt.py --portfolio .change_assurance\capability_improvement_portfolio.json --capability-id agentic_control.governance_gate.evaluate --output .change_assurance\capability_improvement_proof_receipt.json --json --strict
python scripts\produce_capability_improvement_proof_receipt.py --portfolio .change_assurance\capability_improvement_portfolio.json --capability-id agentic_control.code_change.plan --output .change_assurance\capability_improvement_proof_receipt_agentic_control_code_change_plan.json --json --strict
python scripts\produce_capability_improvement_proof_receipt.py --portfolio .change_assurance\capability_improvement_portfolio.json --capability-id agentic_control.evidence.append --output .change_assurance\capability_improvement_proof_receipt_agentic_control_evidence_append.json --json --strict
python scripts\produce_capability_improvement_proof_receipt.py --portfolio .change_assurance\capability_improvement_portfolio.json --capability-id agentic_control.incident_recovery.plan --output .change_assurance\capability_improvement_proof_receipt_agentic_control_incident_recovery_plan.json --json --strict
python scripts\reconcile_general_agent_promotion_terminal_evidence.py --candidates .change_assurance\general_agent_promotion_terminal_certificate_candidates.json --output .change_assurance\general_agent_promotion_terminal_evidence_reconciliation.json --json --strict
python scripts\gate_general_agent_promotion_terminal_minting.py --reconciliation .change_assurance\general_agent_promotion_terminal_evidence_reconciliation.json --output .change_assurance\general_agent_promotion_terminal_minting_gate.json --json --strict
```

5. Inspect `.change_assurance\general_agent_promotion_terminal_certificate_candidates.json`. Candidate entries must have `certificate_minted=false`, `execution_performed=false`, and `ready_for_terminal_certificate_minting=false`.

6. Inspect `.change_assurance\general_agent_promotion_terminal_evidence_reconciliation.json`. Minting readiness must stay false until every candidate evidence requirement is matched by passed receipt artifacts.

7. Inspect `.change_assurance\general_agent_promotion_terminal_minting_gate.json`. Minting readiness must stay false until reconciliation is ready and an explicit terminal minting authority ref is supplied.

8. Run the terminal certificate minting executor only when `.change_assurance\general_agent_promotion_terminal_minting_gate.json` has `ready_for_terminal_certificate_minting=true`.

```powershell
python scripts\mint_general_agent_promotion_terminal_certificates.py --gate .change_assurance\general_agent_promotion_terminal_minting_gate.json --output .change_assurance\general_agent_promotion_terminal_certificate_minting_run.json --certificate-dir .change_assurance\terminal_certificates --json --strict --require-minted
```

The executor must produce `terminal_certificates_minted=true` only when every emitted certificate validates against `schemas\terminal_closure_certificate.schema.json`.

9. Inspect `.change_assurance\general_agent_promotion_closure_plan.json`.

10. Confirm adapter-worker dependency actions and governed credential bindings are already closed by the live-evidence witness.

11. Complete only the residual approval-required portfolio review actions when those actions are in scope for terminal certificate minting.

12. Produce live adapter receipts:

```powershell
python scripts\produce_browser_sandbox_evidence.py --output "$env:MULLU_BROWSER_SANDBOX_EVIDENCE" --strict
python scripts\validate_sandbox_execution_receipt.py --receipt "$env:MULLU_BROWSER_SANDBOX_EVIDENCE" --capability-prefix browser. --require-no-workspace-changes --json
python scripts\validate_browser_sandbox_evidence.py --evidence "$env:MULLU_BROWSER_SANDBOX_EVIDENCE" --json
python scripts\produce_capability_adapter_live_receipts.py --target browser --browser-sandbox-evidence "$env:MULLU_BROWSER_SANDBOX_EVIDENCE" --strict
python scripts\produce_capability_adapter_live_receipts.py --target document --strict
python scripts\produce_capability_adapter_live_receipts.py --target voice --voice-audio-path "$env:MULLU_VOICE_PROBE_AUDIO" --strict
python scripts\produce_capability_adapter_live_receipts.py --target email-calendar --email-calendar-connector-id gmail --email-calendar-query newer_than:1d --strict
```

13. Regenerate adapter evidence:

```powershell
python scripts\collect_capability_adapter_evidence.py --strict --output .change_assurance\capability_adapter_evidence.json
```

The browser adapter evidence is not closed unless `.change_assurance\capability_adapter_evidence.json` preserves both `browser-sandbox-evidence-*` and `sandbox-receipt-*` refs from the browser live receipt.
The generic sandbox receipt gate must also report `valid=true`; it proves the nested worker receipt still has no network, read-only rootfs, `/workspace` mount, no forbidden effects, and no workspace mutation.

14. Publish deployment witness only after approval:

```powershell
# From the upstream mullusi-site checkout, this must pass before DNS work.
node scripts\check-api-production-readiness.mjs --require-ready --production-image-published --runtime-host-ready --managed-postgres-ready --schema-applied --production-secrets-stored --deploy-env-ready --release-preflight-ready --persistence-ready --host-firewall-configured --tls-certificate-ready --rollback-path-defined --private-runtime-witness-ready --dns-authority-ready --output "$env:UPSTREAM_API_READINESS_REPORT"

python scripts\collect_deployment_publication_evidence_packet.py --output-dir .change_assurance\deployment_publication_evidence_packet --gateway-url "$env:MULLU_GATEWAY_URL" --expected-environment "$env:MULLU_EXPECTED_RUNTIME_ENV" --upstream-readiness-report "$env:UPSTREAM_API_READINESS_REPORT" --dns-record-type "$env:MULLU_GATEWAY_DNS_RECORD_TYPE" --dns-target "$env:MULLU_GATEWAY_DNS_TARGET" --dns-provider "$env:MULLU_DNS_PROVIDER" --dispatch-witness --json
python scripts\validate_deployment_publication_evidence_packet.py --packet .change_assurance\deployment_publication_evidence_packet\deployment_publication_evidence_packet.json --output .change_assurance\deployment_publication_evidence_packet\deployment_publication_evidence_packet_validation.json --require-ready --json
python scripts\emit_deployment_publication_operator_input_request.py --packet .change_assurance\deployment_publication_evidence_packet\deployment_publication_evidence_packet.json --output .change_assurance\deployment_publication_evidence_packet\deployment_publication_operator_input_request.json --json
python scripts\validate_deployment_publication_operator_input_request.py --request .change_assurance\deployment_publication_evidence_packet\deployment_publication_operator_input_request.json --output .change_assurance\deployment_publication_evidence_packet\deployment_publication_operator_input_request_validation.json --json

python scripts\emit_deployment_upstream_blocker_receipt.py --target-gateway-url "$env:MULLU_GATEWAY_URL" --upstream-readiness-report "$env:UPSTREAM_API_READINESS_REPORT" --output .change_assurance\deployment_upstream_blocker_receipt.json --json
python scripts\validate_deployment_upstream_blocker_receipt.py --receipt .change_assurance\deployment_upstream_blocker_receipt.json --output .change_assurance\deployment_upstream_blocker_receipt_validation.json --require-ready
python scripts\emit_gateway_dns_target_binding_receipt.py --gateway-host "$env:MULLU_GATEWAY_HOST" --gateway-url "$env:MULLU_GATEWAY_URL" --expected-environment "$env:MULLU_EXPECTED_RUNTIME_ENV" --record-type "$env:MULLU_GATEWAY_DNS_RECORD_TYPE" --target "$env:MULLU_GATEWAY_DNS_TARGET" --provider "$env:MULLU_DNS_PROVIDER" --output .change_assurance\gateway_dns_target_binding_receipt.json --json
python scripts\validate_gateway_dns_target_binding_receipt.py --receipt .change_assurance\gateway_dns_target_binding_receipt.json --output .change_assurance\gateway_dns_target_binding_receipt_validation.json --require-ready
python scripts\collect_gateway_dns_resolution_receipt.py --gateway-url "$env:MULLU_GATEWAY_URL" --output .change_assurance\gateway_dns_resolution_receipt.json --json
python scripts\validate_gateway_dns_resolution_receipt.py --receipt .change_assurance\gateway_dns_resolution_receipt.json --output .change_assurance\gateway_dns_resolution_receipt_validation.json --require-resolved
python scripts\publish_gateway_publication.py --gateway-url "$env:MULLU_GATEWAY_URL" --dispatch-witness --dispatch --receipt-output .change_assurance\gateway_publication_receipt.json
python scripts\validate_gateway_publication_receipt.py --receipt .change_assurance\gateway_publication_receipt.json --require-ready --require-dispatched --require-success
python scripts\validate_deployment_publication_closure.py
```

The deployment publication evidence packet validation must report `valid=true`
with `--require-ready` before publication is actionable. The upstream blocker
validation must report `valid=true` with `--require-ready` before DNS target
selection is treated as actionable. The upstream API reporter must also report
ready before DNS target selection is treated as actionable.
The target-binding validation must report `valid=true` with `--require-ready`
before DNS publication is treated as actionable.
The DNS receipt validation must report `valid=true` with `--require-resolved`
before publication dispatch.
If target binding reports `ready=false`, select the gateway origin target,
record type, and authoritative provider first. If DNS reports `resolved=false`,
publish an A, AAAA, or CNAME record for the gateway host and rerun both receipt
validators before any deployment witness command.

15. Update `DEPLOYMENT_STATUS.md` only when `.change_assurance/deployment_witness.json` has `deployment_claim=published`, `runtime_responsibility_debt_clear=true`, `authority_responsibility_debt_clear=true`, and the public health endpoint equals `<gateway_url>/health`.

16. Run final promotion validation:

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
| Capability improvement proof receipt is unsafe | Do not reconcile the candidate; regenerate the receipt only after `proof_is_not_execution=true`, `capability_activation_performed=false`, `registry_mutated=false`, `terminal_certificates_minted=false`, and `secret_values_serialized=false` |
| Deployment witness is not published | Do not update `DEPLOYMENT_STATUS.md`; current `api.mullusi.com` deployment witness is published |
| Deployment publication evidence packet is not ready | Do not publish DNS or dispatch workflows; inspect `deployment_publication_evidence_packet_validation.json`, emit `deployment_publication_operator_input_request.json`, close the named inputs, then rerun `collect_deployment_publication_evidence_packet.py` plus `validate_deployment_publication_evidence_packet.py --require-ready` |
| Upstream API/DNS readiness is not ready | Do not publish DNS; complete upstream recovery, runtime host, managed PostgreSQL, schema, secret store, preflight, persistence, firewall, TLS, rollback, private runtime witness, runtime witness closure, and DNS publication authority gates, then rerun the upstream `check-api-production-readiness.mjs --require-ready --output "$env:UPSTREAM_API_READINESS_REPORT"` command plus `emit_deployment_upstream_blocker_receipt.py --upstream-readiness-report "$env:UPSTREAM_API_READINESS_REPORT"` and `validate_deployment_upstream_blocker_receipt.py --require-ready` |
| Gateway DNS target-binding receipt is not ready | Do not publish DNS; select `MULLU_GATEWAY_DNS_TARGET`, `MULLU_GATEWAY_DNS_RECORD_TYPE`, and `MULLU_DNS_PROVIDER`, then rerun `emit_gateway_dns_target_binding_receipt.py` plus `validate_gateway_dns_target_binding_receipt.py --require-ready` |
| Gateway DNS receipt is unresolved | Do not publish deployment witness; publish DNS and rerun `collect_gateway_dns_resolution_receipt.py` plus `validate_gateway_dns_resolution_receipt.py --require-resolved` |
| Runtime or authority responsibility debt is not clear | Do not publish deployment witness and inspect `/authority/responsibility` |
| Health endpoint mismatch | Do not claim public production health |

STATUS:
  Completeness: 99%
  Invariants verified: [aggregate plan validation before execution, live-evidence queue classified before execution, terminal approval receipt schema-validated when present, terminal certificate gate checked before execution, terminal certificate candidates are non-minting, capability improvement proof receipt is non-executing, terminal evidence reconciliation gates minting readiness, terminal minting gate requires explicit authority, terminal certificate minting executor requires ready gate, credential approval required, live receipts required, deployment publication evidence packet require-ready gate, upstream API/DNS validation require-ready gate, gateway DNS target-binding validation require-ready gate, gateway DNS receipt validation require-resolved gate, deployment status mutation evidence-gated, production promotion validation terminal]
  Open issues: [external dependencies, governed credentials, adapter live receipts]
  Next action: execute this runbook in the credentialed adapter-worker and deployment environment
