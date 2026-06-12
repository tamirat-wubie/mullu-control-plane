# Nested Mind Activation Boundary Staging Handoff - 2026-06-12

Purpose: provide the exact operator handoff for the first live `record_observation` staging evidence chain after the Nested Mind import and activation-boundary witnesses.
Governance scope: local-to-staging Nested Mind bridge only; no worker activation, no child-mind topology, no lawbook migration, no system-of-record switch, and no production claim.
Dependencies: `scripts/nested_mind_submit_observation.py`, `scripts/nested_mind_reconcile_observation.py`, `scripts/report_nested_mind_evidence.py`, `scripts/validate_nested_mind_p3_readiness.py`, `.tmp/nested-mind-observation-plan-activation-boundary-20260612.json`, `.tmp/nested-mind-proposal-evidence-activation-boundary-20260612.json`.
Invariants: submit is default-off; staging submit requires HTTPS and operator-held credentials; raw tokens and raw response bodies are not persisted; P3 topology remains blocked until readiness returns `ready`.

## Prepared Inputs

| Input | Path |
| --- | --- |
| Observation | `.tmp/nested-mind-observation-activation-boundary-20260612.json` |
| Plan | `.tmp/nested-mind-observation-plan-activation-boundary-20260612.json` |
| Evidence | `.tmp/nested-mind-proposal-evidence-activation-boundary-20260612.json` |
| Evidence store target | `.tmp/nested-mind-staging-evidence-activation-boundary-20260612.jsonl` |

## Current Blocker

The local shell does not currently have the live staging gates:

```text
MULLU_NESTED_MIND_ENABLED=absent
MULLU_NESTED_MIND_OBSERVATION_BRIDGE_ENABLED=absent
MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED=absent
MULLU_NESTED_MIND_BASE_URL=absent
MULLU_NESTED_MIND_BEARER_TOKEN=absent
```

## Required Staging Environment

Use a real HTTPS staging endpoint. Do not use `http://`, localhost, loopback,
private-network URLs, metadata-network URLs, or credentials embedded in the
base URL.

```powershell
$env:MULLU_NESTED_MIND_ENABLED="true"
$env:MULLU_NESTED_MIND_OBSERVATION_BRIDGE_ENABLED="true"
$env:MULLU_NESTED_MIND_BASE_URL="https://<staging-nested-mind-host>"
$env:MULLU_NESTED_MIND_BEARER_TOKEN="<staging-token-if-required>"
$env:MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED="false"
```

## Dry-Run Confirmation

```powershell
python scripts/nested_mind_submit_observation.py `
  --plan .tmp/nested-mind-observation-plan-activation-boundary-20260612.json `
  --evidence .tmp/nested-mind-proposal-evidence-activation-boundary-20260612.json `
  --dry-run
```

Expected result:

```text
status=disabled
blocker=dry_run_no_network_call
```

## Live Submit Window

Enable submit only for the live staging attempt:

```powershell
$env:MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED="true"

python scripts/nested_mind_submit_observation.py `
  --plan .tmp/nested-mind-observation-plan-activation-boundary-20260612.json `
  --evidence .tmp/nested-mind-proposal-evidence-activation-boundary-20260612.json `
  --submit `
  --store .tmp/nested-mind-staging-evidence-activation-boundary-20260612.jsonl

$env:MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED="false"
```

Required assertion after submit:

```powershell
if ($env:MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED -ne "false") {
  throw "submit gate must be disabled after live attempt"
}
```

## Reconcile Accepted Submission

Run this only after a submit report returns an accepted and verified commit
witness.

```powershell
python scripts/nested_mind_reconcile_observation.py `
  --store .tmp/nested-mind-staging-evidence-activation-boundary-20260612.jsonl `
  --plan-id nested-mind-observation-plan-9fbcd0b3a249 `
  --witness-id <witness-id-from-submit-report>
```

## Report And Readiness Gate

```powershell
python scripts/report_nested_mind_evidence.py `
  --store .tmp/nested-mind-staging-evidence-activation-boundary-20260612.jsonl `
  --mind-id root

python scripts/validate_nested_mind_p3_readiness.py `
  --store .tmp/nested-mind-staging-evidence-activation-boundary-20260612.jsonl `
  --mind-id root
```

Expected readiness before live submit:

```text
status=blocked
accepted_submission_missing
verified_commit_witness_missing
verified_reconciliation_missing
```

Expected readiness after valid live submit and reconciliation:

```text
status=ready
one accepted submission
one verified commit witness
one verified reconciliation report
```

## Stop Rules

1. Do not use an `http://` base URL.
2. Do not include credentials in the base URL.
3. Do not use localhost, loopback, private-network, or metadata-network targets as live staging evidence.
4. Do not leave `MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED=true`.
5. Do not delete failed or unverified evidence; preserve it and report blockers.
6. Do not advance P3 topology until `validate_nested_mind_p3_readiness.py` returns `ready`.

## Rollback

1. Set `MULLU_NESTED_MIND_OBSERVATION_SUBMIT_ENABLED=false`.
2. Preserve `.tmp/nested-mind-staging-evidence-activation-boundary-20260612.jsonl`.
3. Run `scripts/report_nested_mind_evidence.py` and `scripts/validate_nested_mind_p3_readiness.py` to capture blockers.
4. Start a new observation plan only if the live attempt needs a retry.
