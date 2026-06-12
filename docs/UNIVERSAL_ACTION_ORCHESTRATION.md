# Universal Action Orchestration

Purpose: define the governed v1 action-shape contract for effect-bearing control-plane actions.
Governance scope: OCE action envelope completeness, RAG trace-to-receipt linkage, CDCV no-execution-by-claim causality, CQTE decidable admission shape, UWMA fixture witness anchoring, and PRS terminal closure state.
Dependencies: `schemas/universal_action_orchestration.schema.json`, `schemas/universal_action_orchestration_validation_receipt.schema.json`, `scripts/validate_universal_action_orchestration.py`, `scripts/detect_uao_runtime_bypass.py`, `scripts/validate_universal_action_orchestration_receipt_contract.py`, `scripts/validate_universal_action_orchestration_receipt.py`, `docs/LIFE_MEANING_GOVERNANCE_KERNEL.md`, `docs/LIFE_CONTINUITY_CONFLICT_DOCTRINE.md`, `docs/universal-action-orchestration-validation-receipt-example.json`, `mcoi/mcoi_runtime/core/life_meaning_governance.py`, `mcoi/mcoi_runtime/core/universal_action_kernel.py`, and examples in `examples/`.
Invariants: UAO v1 validates existence and shape only; it does not execute actions, dispatch workers, call external systems, send messages, move money, mutate schedules, or write memory.

## Architecture

UAO v1 hardens a core idea into repository law:

```text
passive doc -> schema contract -> example fixtures -> validator -> workspace preflight required gate
validator -> validation receipt -> receipt replay -> workspace preflight required gate
```

The v1 record is a non-executing Universal Action Envelope plus admission, trace, receipt, and closure references:

```text
UniversalActionOrchestration :=
  <action_envelope, decision, trace_ref, admission_receipt_ref,
   execution_receipt_ref, closure_state>
```

| Contract field | Purpose |
| --- | --- |
| `action_envelope` | Source, actor, tenant, intent, target, risk, requested time, approval, evidence, and capability references. |
| `decision` | Admission decision: `allow`, `block`, `defer`, `escalate`, or `simulate`. |
| `trace_ref` | Causal decision trace reference bound to the trace stage output. |
| `admission_receipt_ref` | Receipt reference proving admission was recorded. |
| `execution_receipt_ref` | Receipt reference proving execution only when execution is admitted; otherwise null. |
| `recovery_plan` | Explicit rollback or compensation path available before effect-bearing execution closure. |
| `claim_ledger` | Typed operational claims, evidence references, confidence, verification state, and unverified claim IDs. |
| `fracture_report` | Pre-dispatch contradiction report covering policy, identity, budget, schema, capability, memory, claim, recovery, authority, duplicate-command, and prompt-injection checks. |
| `life_meaning_judgment` | Mullu Life-Meaning Governance Kernel judgment for affected symbols, life impact, feeling impact, meaning impact, truth, dignity, consent, love, resonance, domination, justice, continuity, reversibility, approval, rollback, and decision. |
| `life_continuity_judgment` | Conflict-law judgment for life impact, feeling observer impact, meaning impact, dignity boundary, truth preservation, domination risk, and review decision. |
| `closure_state` | Terminal closure state mirrored from `closure.status`. |
| `closure.reconciliation_ref` | Reconciliation stage output retained in the closure receipt boundary. |
| `closure.memory_ref` | Admitted memory update reference retained in the closure receipt boundary, or null when no memory update is admitted. |
| `memory_update.constitution` | Governed memory constitution binding source refs, owner, scope, confidence, sensitivity, expiry, allowed uses, forbidden uses, evidence refs, verification time, and mutation history. |

The runtime export path is:

```text
UniversalActionRequest + UniversalActionResult -> build_universal_action_orchestration_record -> UAO v1 record
```

The export is pure and does not dispatch work. It materializes the already-issued kernel certificates, receipts, closure state, memory decision, and lineage delta into the same schema validated for static examples.
Command-ledger dispatch persists this record under `universal_action_orchestration`, and the gateway exposes it through `/commands/{command_id}/universal-action-orchestration` as a read-only replay surface.
The replay surface fails closed unless the persisted command event came from a universal action kernel dispatch or block event and the embedded UAO v1 record preserves the expected command identity, event identity, decision, receipt, closure, and no-private-reasoning shape.
Operator read-model summaries must expose the replay-validated `reconciliation_ref` and `memory_ref` alongside `closure_state`; summaries may omit execution detail, but they must not reduce closure to status-only evidence.
The workspace governance witness must retain UAO doctrine, fixtures, schemas, validators, receipt evidence, bypass detection, and replay tests so preflight can detect removal of the UAO law surface before repository closure.

## Algorithm

The validator applies these rules deterministically:

1. Every UAO example must have an `action_envelope`.
2. Every envelope must include `source`, `actor`, `tenant`, `intent`, `target`, `risk`, and `requested_at`.
3. Every decision must be one of `allow`, `block`, `defer`, `escalate`, or `simulate`.
4. Every effect-bearing action must include `trace_ref`, `admission_receipt_ref`, and `closure_state`.
5. Every admitted `allow` action must include an emitted `execution_receipt_ref`.
6. Every blocked, deferred, or escalated action must include a reason code.
7. No example may claim execution unless an execution receipt exists.
8. No raw private reasoning field may exist anywhere in the record.
9. No high-risk `allow` action may pass without approval, evidence, and capability references.
10. Every example must include `closure_state`.
11. Every runtime-exported UAO record must pass the same schema and semantic validator as static fixtures.
12. Every command replay record must come from persisted command events, not from an in-memory kernel result.
13. Every command replay record must fail closed when the persisted candidate is malformed or exposes private reasoning fields.
14. Every command replay record must bind to the command id, tenant, actor, and persisted event identity before exposure.
15. Every command replay record must bind emitted receipts to the matching pipeline stage, receipt kind, tier, and root receipt reference before exposure.
16. Every command replay record must bind to the same event-local universal action proof detail, including action id, trace, receipts, closure state, orchestration id, and lineage delta before exposure.
17. Every command replay record must come from a command event whose event hash recomputes from the persisted event payload before exposure.
18. Every command replay record must come from a command event whose source channel, idempotency key, policy version, and trace id match the command envelope before exposure.
19. Every command replay record must carry the canonical ordered UAO pipeline stage sequence before exposure.
20. Runtime bypass detection scans effect-bearing dispatch and execute call sites for UAO or governed binding before closure.
21. Every command replay record must bind proof hash to an independent recomputation of the persisted event-local universal action proof detail before exposure.
22. Every closure receipt must bind closure state to reconciliation and memory references before exposure.
23. Every effect-bearing `allow` or post-dispatch review action must carry an available `recovery_plan` with rollback or compensation references before closure.
24. Every UAO record must expose a `claim_ledger`; verified claims require evidence refs and evidence-free claims must be marked unverified.
25. Every memory update must expose a `constitution`; recorded memory requires evidence refs, owner, scope, source refs, allowed uses, and mutation history.
26. Every UAO record must expose a `fracture_report`; execution-allowed records require fracture status `passed`, no blocking checks, and a canonical fracture pipeline stage before execution.
27. Every canonical UAO record must expose a `life_meaning_judgment`.
28. Life-meaning judgment must cite `docs/LIFE_MEANING_GOVERNANCE_KERNEL.md` through the schema and record affected symbols, life, feeling, meaning, dignity, consent, truth, domination, love, resonance, justice, continuity, reversibility, approval, rollback, and decision fields.
29. `life_meaning_judgment.decision = pass -> truth preserved, dignity boundary pass, no domination risk, consent satisfied when required, and no unknown effect-bearing meaning impact`.
30. Every canonical UAO record must expose a `life_continuity_judgment`.
31. Life-continuity judgment must cite `docs/LIFE_CONTINUITY_CONFLICT_DOCTRINE.md` through a conflict-law reference and record life, feeling, meaning, dignity, truth, domination, love, resonance, meaning-continuity, and review fields.
32. `life_continuity_judgment.decision = pass -> truth preserved, dignity boundary pass, no domination risk, and no high or unknown lived-meaning risk`.
33. Unknown meaning-impact on an effect-bearing action cannot pass; it must pause, block, or escalate before execution.

The core invariant is:

```text
effect_bearing(action) -> trace_ref and admission_receipt_ref and closure_state
effect_bearing(action) and execution_closure(action) -> recovery_plan.available
claim.verified -> non_empty(claim.evidence_refs)
empty(claim.evidence_refs) -> claim_id in claim_ledger.unverified_claim_ids
memory_update.status = recorded -> non_empty(memory_update.constitution.evidence_refs)
memory_update.learning_allowed = true -> "learning" in memory_update.constitution.allowed_uses
intersection(allowed_uses, forbidden_uses) != empty -> reject
decision.execution_allowed -> fracture_report.status = passed
decision.execution_allowed -> empty(fracture_report.blocking_check_ids)
stage_order(fracture) < stage_order(execution)
life_meaning_judgment.decision = pass -> truth_preserved
life_meaning_judgment.decision = pass -> dignity_boundary = pass
life_meaning_judgment.decision = pass -> domination_risk = false
life_meaning_judgment.consent_required = true -> consent_present or decision != pass
effect_bearing(action) and life_meaning_judgment.meaning_impact = unknown -> decision != allow
life_continuity_judgment.decision = pass -> truth_preserved
life_continuity_judgment.decision = pass -> dignity_boundary = pass
life_continuity_judgment.decision = pass -> domination_risk = false
effect_bearing(action) and meaning_impact = unknown -> decision != allow
```

Invalid UAO is a preflight-blocking condition:

```text
not UAO_valid(action) -> preflight_fail
```

## Fixtures

The default validator set covers allowed, blocked, deferred, and simulated outcomes:

- `examples/universal_action_orchestration.allowed_status_publish.json`
- `examples/universal_action_orchestration.blocked_invoice_payment.json`
- `examples/uao/blocked_missing_approval.json`
- `examples/uao/deferred_stale_evidence.json`
- `examples/uao/simulated_low_risk_readonly.json`

## Verification

Run:

```powershell
python scripts/validate_universal_action_orchestration.py
python scripts/detect_uao_runtime_bypass.py
python scripts/validate_universal_action_orchestration.py --json --receipt-path .tmp/uao-validation-receipt.json
python scripts/validate_universal_action_orchestration_receipt.py --receipt .tmp/uao-validation-receipt.json
python -m pytest mcoi/tests/test_universal_action_kernel.py -q
python scripts/validate_universal_action_orchestration_receipt_contract.py
python scripts/validate_universal_action_orchestration_receipt.py
python -m pytest tests/test_gateway/test_webhooks.py -q
python -m unittest discover -s tests -p "test_validate_universal_action_orchestration.py"
python scripts/run_workspace_governance_checks.py
```

The workspace preflight includes the validator, so UAO drift blocks repository closure.
The optional JSON receipt is read-only and records validity, check names, workspace-relative example path labels, error counts, and bounded errors for autonomous preflight consumers.
Canonical validation receipts require the default schema, doctrine, and fixture set.
Ad hoc `--example` validation may be used for local diagnosis, but non-canonical schema, doctrine, or fixture inputs cannot be emitted or persisted as a governance validation receipt.
The validation receipt has its own schema contract and remains non-terminal closure evidence: `terminal_closure_required = true` and `receipt_is_not_terminal_closure = true`.
The kernel export and gateway replay tests cover allowed execution, blocked admission, missing-record 404 behavior, and schema plus semantic validation.
The saved receipt replay validator admits persisted UAO validation receipts only when the recorded status is passed and the check order, counts, canonical schema/document/example artifact labels, and non-terminal closure flags still satisfy the same contract.
