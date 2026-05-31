# Nested-Mind Record Observation Staging Runbook

Purpose: stage one governed `record_observation` submission and verify the append-only evidence chain before P3 memory-lattice work.
Governance scope: staging-only nested-mind observation bridge; no public schema, no new route, no child-mind creation, no lawbook migration, and no semantic or procedural memory admission.
Dependencies: nested-mind build, submit, reconcile, report, and readiness CLIs; staging `MULLU_NESTED_MIND_*` environment gates.
Invariants: submit is default-off, reconciliation is read-only, bearer tokens and raw response bodies are never persisted, and P3 readiness requires a bound accepted submission, verified witness, and verified reconciliation.

## Preconditions

1. Use a staging nested-mind endpoint only.
2. Confirm the observation JSON is bounded and contains no bearer, authorization, token, or raw response body fields.
3. Prepare paths:

```powershell
$env:MULLU_NESTED_MIND_ENABLED="true"
$env:MULLU_NESTED_MIND_OBSERVATION_BRIDGE_ENABLED="true"
$env:MULLU_NESTED_MIND_BASE_URL="https://nested-staging.example"
$env:MULLU_NESTED_MIND_BEARER_TOKEN="<staging-token>"
$env:MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED="false"
$STORE=".tmp\nested-mind-staging-evidence.jsonl"
$PLAN=".tmp\nested-mind-observation-plan.json"
$EVIDENCE=".tmp\nested-mind-proposal-evidence.json"
$OBSERVATION=".tmp\nested-mind-observation.json"
```

## Procedure

1. Build the observation plan offline:

```powershell
python scripts/nested_mind_build_observation_plan.py `
  --mind-id root `
  --observation-id obs-1 `
  --observation $OBSERVATION `
  --mullu-receipt-hash <mullu-receipt-hash> `
  --authority-receipt-hash <authority-receipt-hash> `
  --plan-out $PLAN `
  --evidence-out $EVIDENCE
```

Expected result: stdout reports `status=planned`, and both output files exist. No network call occurs.

2. Dry-run submit:

```powershell
python scripts/nested_mind_submit_observation.py --plan $PLAN --evidence $EVIDENCE --dry-run
```

Expected result: status is `disabled`, blocker includes `dry_run_no_network_call`, and no evidence store append is required.

3. Enable staging submit gate only for the live submit window:

```powershell
$env:MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED="true"
```

4. Submit live `record_observation` and persist typed evidence:

```powershell
python scripts/nested_mind_submit_observation.py --plan $PLAN --evidence $EVIDENCE --submit --store $STORE
```

Expected result: status is `accepted` only when the nested-mind response binds the same mind, payload hash, Mullu receipt hash, authority receipt hash, and commit witness. Any mismatch returns `unverified_response`.

5. Disable submit immediately after the live attempt:

```powershell
$env:MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED="false"
```

Required assertion: the submit gate remains `false` after the run.

6. Reconcile the verified commit witness through read-only projection, audit, and optional replay:

```powershell
python scripts/nested_mind_reconcile_observation.py `
  --store $STORE `
  --plan-id <plan-id-from-plan-json> `
  --witness-id <witness-id-from-submit-report>
```

Expected result: status is `verified` only when projection and audit hashes match the commit witness. Reconciliation performs no writes to nested-mind and only appends a typed local report.

7. Report evidence:

```powershell
python scripts/report_nested_mind_evidence.py --store $STORE --mind-id root
```

Expected result: record counts include one plan, one submission report, one commit witness, and one reconciliation report. Bridge reports may be present when the operator also records the bridge closure report.

8. Validate P3 readiness:

```powershell
python scripts/validate_nested_mind_p3_readiness.py --store $STORE --mind-id root
```

Expected result: status is `ready` only for one bound causal chain.

## Safety Assertions

1. `MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED=false` after the run.
2. The evidence store contains no `bearer`, `authorization`, `token`, `raw_response_body`, `response_body`, or `raw_body` fields.
3. P3 readiness blocks when reconciliation is absent.
4. P3 readiness blocks when the verified witness is not bound to the accepted submission.
5. Receipt-indexed lookup for the Mullu receipt hash recovers the full available evidence chain.

## Rollback

1. Leave the submit gate disabled.
2. Preserve the append-only evidence store as the staging witness.
3. If a live submit is unverified, do not delete evidence; run read-only report and readiness commands to capture blockers.
4. Start a new observation plan for a retry with a new planned timestamp and deterministic payload hash.
