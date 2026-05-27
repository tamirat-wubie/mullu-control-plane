# Trust Ledger Offline Verification

> **In one box:** How someone can independently check Mullu's
> [proof receipts](GLOSSARY.md#proof-receipt--execution-receipt) and
> [trust ledger](GLOSSARY.md#trust-ledger) *without* access to the live system —
> "don't trust us, verify it yourself, even offline." This is the
> operator/auditor replay path. *(Doc type: Reference.)*

Purpose: define the operator replay path for signed trust-ledger evidence bundles
and external anchor receipts.

Governance scope: offline evidence verification, schema-gated replay, terminal
closure anchoring, and anchor receipt tamper detection.

Dependencies:

- `scripts/verify_evidence_bundle.py`
- `scripts/verify_anchor_receipt.py`
- `scripts/preflight_trust_ledger_remote_submission.py`
- `scripts/submit_trust_ledger_anchor_export.py`
- `schemas/trust_ledger_bundle.schema.json`
- `schemas/trust_ledger_bundle_verification_report.schema.json`
- `schemas/trust_ledger_anchor_receipt.schema.json`
- `schemas/trust_ledger_remote_submission_preflight.schema.json`
- `schemas/trust_ledger_anchor_submission_receipt.schema.json`
- `schemas/trust_ledger_evidence_artifacts.schema.json`
- `schemas/trust_ledger_export_package.schema.json`
- `schemas/trust_ledger_anchor_verification_report.schema.json`

Invariants:

- Bundle verification validates schema, bundle hash, and HMAC signature.
- Bundle verifier JSON output validates against `trust_ledger_bundle_verification_report.schema.json` for both valid and fail-closed reports.
- Anchor verification validates bundle, receipt, and artifact schemas before typed reconstruction.
- Anchor verification binds the receipt to the bundle id, bundle hash, artifact root, receipt id, receipt hash, and HMAC signature.
- Anchor verifier JSON output validates against `trust_ledger_anchor_verification_report.schema.json` for both valid and fail-closed reports.
- Anchor receipts do not replace terminal closure certificates.
- OrgOS anchor export packaging validates generated export schemas before publishing files.
- OrgOS anchor export packaging stages output files and rolls back partial publish failures.
- Anchor submission requires explicit operator authority, prior package verification, and a signed hash-chained ledger receipt.
- Remote submission preflight is read-only: it never posts to the transparency log and never appends to the local submission ledger.
- Effect-bearing remote submission requires a matching preflight receipt before any HTTPS POST or local ledger append.
- Submission ledger replay, optional remote submission, and local append execute under one cross-process lock.
- Missing signing secrets fail closed.

## Export Inputs

| File | Contract | Role |
| --- | --- | --- |
| `bundle.json` | `trust_ledger_bundle.schema.json` | Signed terminal-closure evidence bundle |
| `anchor_receipt.json` | `trust_ledger_anchor_receipt.schema.json` | Signed external anchor receipt |
| `artifacts.json` | `trust_ledger_evidence_artifacts.schema.json` | Typed evidence artifact list used to recompute the artifact root |
| `package.json` | `trust_ledger_export_package.schema.json` | Portable manifest binding expected file names, content hashes, bundle id, receipt id, and artifact root |
| `submission_receipt.json` | `trust_ledger_anchor_submission_receipt.schema.json` | Signed operator submission receipt after package verification |

Required artifact classes for external anchoring:

```text
command
execution_receipt
verification_result
terminal_certificate
```

Optional artifact classes may include:

```text
approval
effect_reconciliation
learning_decision
deployment_witness
```

## Bundle Replay

Command:

```bash
python scripts/verify_evidence_bundle.py \
  --bundle bundle.json \
  --signing-secret "$MULLU_TRUST_LEDGER_SECRET" \
  --json
```

Pass condition:

```json
{
  "valid": true,
  "reason": "verified",
  "schema_valid": true
}
```

Fail-closed reasons include:

| Reason | Meaning |
| --- | --- |
| `signing_secret_required` | No HMAC secret was provided |
| `schema_validation_failed` | Bundle JSON does not satisfy the public schema |
| `bundle_hash_mismatch` | Bundle content no longer matches `bundle_hash` |
| `signature_mismatch` | HMAC signature no longer matches the bundle |

## Anchor Replay

Command:

```bash
python scripts/verify_anchor_receipt.py \
  --bundle bundle.json \
  --receipt anchor_receipt.json \
  --artifacts artifacts.json \
  --package package.json \
  --signing-secret "$MULLU_TRUST_LEDGER_ANCHOR_SECRET" \
  --json
```

Pass condition:

```json
{
  "valid": true,
  "reason": "anchor_verified",
  "schema_valid": true,
  "package_present": true,
  "package_valid": true,
  "package_id": "trust-export-..."
}
```

Fail-closed reasons include:

| Reason | Meaning |
| --- | --- |
| `signing_secret_required` | No anchor HMAC secret was provided |
| `schema_validation_failed` | Bundle, receipt, or artifact JSON violates its schema |
| `package_hash_mismatch` | `package.json` no longer matches its own package hash |
| `package_bundle_hash_mismatch` | `package.json` no longer matches `bundle.json` |
| `package_anchor_receipt_hash_mismatch` | `package.json` no longer matches `anchor_receipt.json` |
| `package_artifacts_hash_mismatch` | `package.json` no longer matches `artifacts.json` |
| `anchor_bundle_mismatch` | Receipt references a different bundle id |
| `anchor_bundle_hash_mismatch` | Receipt references a different bundle hash |
| `artifact_count_mismatch` | Receipt artifact count differs from artifact export |
| `command_artifact_id_mismatch` | Command artifact no longer binds the bundle command |
| `terminal_artifact_id_mismatch` | Terminal certificate artifact no longer binds the bundle terminal certificate |
| `artifact_root_hash_mismatch` | Artifact export no longer recomputes to the receipt artifact root |
| `anchor_receipt_id_mismatch` | Receipt id is not canonical for bundle, artifact root, and target |
| `anchor_receipt_hash_mismatch` | Receipt body no longer matches its receipt hash |
| `anchor_signature_mismatch` | HMAC signature no longer matches the receipt |

## OrgOS Anchor Packaging

OrgOS event receipts may be packaged as optional supporting artifacts only after
the terminal trust-ledger bundle and required terminal artifacts already exist.
The packager validates the generated package schema before publishing any files,
then writes through staged files so a publish failure does not leave a partial
export surface.

Packaging fail-closed reasons include:

| Reason | Meaning |
| --- | --- |
| `package_schema_validation_failed` | The generated `package.json` would violate the public export-package schema; no export files are published |
| `generated_export_schema_validation_failed` | A generated bundle, receipt, or artifact output would violate its public schema; no export files are published |
| `anchor_export_publish_failed:*` | Staged output publishing failed and rollback was attempted before returning |

## Operator Procedure

1. Export `bundle.json`, `anchor_receipt.json`, `artifacts.json`, and `package.json` from the same command closure.
2. Verify `bundle.json` first with `scripts/verify_evidence_bundle.py`.
3. Verify the anchor with `scripts/verify_anchor_receipt.py`.
4. Confirm `package.json` file hashes match the exported file contents before moving the package across trust boundaries.
5. Compare `command_id`, `terminal_certificate_id`, `bundle_id`, and `anchor_receipt_id` in the JSON reports.
6. Treat any invalid report as `GovernanceBlocked` until the source export is regenerated or the tamper source is identified.

## Remote Submission Preflight

Before a real HTTPS transparency-log write, emit a read-only readiness receipt:

```bash
python scripts/preflight_trust_ledger_remote_submission.py \
  --bundle bundle.json \
  --receipt anchor_receipt.json \
  --artifacts artifacts.json \
  --package package.json \
  --ledger-path external_anchor_submissions.jsonl \
  --operator-id "$MULLU_OPERATOR_ID" \
  --authority-ref "proof://approval/anchor-submit" \
  --submitted-at "2026-05-05T12:20:00+00:00" \
  --verification-secret "$MULLU_TRUST_LEDGER_ANCHOR_SECRET" \
  --submission-secret "$MULLU_TRUST_LEDGER_SUBMISSION_SECRET" \
  --signature-key-id "$MULLU_TRUST_LEDGER_SUBMISSION_KEY_ID" \
  --remote-submit-url "$MULLU_TRUST_LEDGER_REMOTE_SUBMISSION_URL" \
  --remote-api-token "$MULLU_TRUST_LEDGER_REMOTE_SUBMISSION_TOKEN" \
  --output .change_assurance/trust_ledger_remote_submission_preflight.json \
  --strict \
  --json
```

Pass condition:

```json
{
  "ready": true,
  "outcome": "SolvedVerified",
  "next_ledger_sequence": 1,
  "expected_remote_submission_payload_hash": "<hash remote must echo>",
  "expected_remote_idempotency_key": "<same hash sent as Idempotency-Key>",
  "metadata": {
    "preflight_only": true,
    "remote_submit_executed": false,
    "ledger_append_executed": false
  }
}
```

Blocked conditions:

| Outcome | Meaning |
| --- | --- |
| `AwaitingEvidence` | Required operator input, secret presence, or remote token evidence is missing |
| `GovernanceBlocked` | Authority, URL, timeout, submitted timestamp, anchor export replay, or existing submission ledger replay failed |

## Governed Submission

Command:

```bash
python scripts/submit_trust_ledger_anchor_export.py \
  --bundle bundle.json \
  --receipt anchor_receipt.json \
  --artifacts artifacts.json \
  --package package.json \
  --ledger-path external_anchor_submissions.jsonl \
  --receipt-out submission_receipt.json \
  --operator-id "$MULLU_OPERATOR_ID" \
  --authority-ref "proof://approval/anchor-submit" \
  --submitted-at "2026-05-05T12:20:00+00:00" \
  --verification-secret "$MULLU_TRUST_LEDGER_ANCHOR_SECRET" \
  --submission-secret "$MULLU_TRUST_LEDGER_SUBMISSION_SECRET" \
  --signature-key-id "$MULLU_TRUST_LEDGER_SUBMISSION_KEY_ID" \
  --confirm-submit \
  --json
```

For a real HTTPS transparency log, add the remote gate:

```bash
python scripts/submit_trust_ledger_anchor_export.py \
  --bundle bundle.json \
  --receipt anchor_receipt.json \
  --artifacts artifacts.json \
  --package package.json \
  --ledger-path external_anchor_submissions.jsonl \
  --operator-id "$MULLU_OPERATOR_ID" \
  --authority-ref "proof://approval/anchor-submit" \
  --submitted-at "2026-05-05T12:20:00+00:00" \
  --verification-secret "$MULLU_TRUST_LEDGER_ANCHOR_SECRET" \
  --submission-secret "$MULLU_TRUST_LEDGER_SUBMISSION_SECRET" \
  --remote-preflight-receipt .change_assurance/trust_ledger_remote_submission_preflight.json \
  --remote-submit-url "https://transparency.example/anchors" \
  --remote-api-token "$MULLU_TRUST_LEDGER_REMOTE_SUBMISSION_TOKEN" \
  --allow-remote-submit \
  --confirm-submit \
  --json
```

The remote endpoint must return JSON containing:

```json
{
  "external_anchor_ref": "https://transparency.example/entries/1",
  "observed_submission_payload_hash": "<same hash received in X-Mullu-Anchor-Submission-Hash>",
  "remote_receipt_hash": "sha256:..."
}
```

The local receipt is not written if the remote endpoint fails, returns a non-2xx
status, emits invalid JSON, omits a valid external anchor ref, or fails to echo
the submitted payload hash.

The remote POST is not attempted unless the preflight receipt validates against
`trust_ledger_remote_submission_preflight.schema.json`, reports
`outcome=SolvedVerified`, and matches the final operator id, authority ref,
remote URL, timeout, ledger sequence, previous ledger hash, and projected remote
payload hash. The submitter also recomputes the canonical preflight receipt id
and rejects receipt-id drift before any remote or ledger effect.

Pass condition:

```json
{
  "valid": true,
  "reason": "anchor_submission_recorded",
  "submitted": true
}
```

Submission fail-closed reasons include:

| Reason | Meaning |
| --- | --- |
| `operator_confirmation_required` | The operator did not pass `--confirm-submit`; no ledger append occurred |
| `operator_id_invalid` | The operator id is missing, too long, or contains whitespace/control characters |
| `authority_ref_invalid` | The operator authority reference is missing or not a bounded `proof://` or `authority://` reference |
| `submission_secret_required` | No submission HMAC secret was provided |
| `anchor_verification_failed:*` | Offline anchor/package verification failed before submission |
| `submission_ledger_lock_timeout` | Another process holds the submission-ledger replay/append lock |
| `submission_ledger_lock_timeout_seconds_invalid` | The requested lock wait timeout is out of bounds |
| `submission_ledger_stale_lock_seconds_invalid` | The requested stale-lock window is out of bounds |
| `remote_submission_confirmation_required` | A remote URL was provided without `--allow-remote-submit` |
| `remote_submit_url_must_be_https` | Remote submission endpoint was not HTTPS |
| `remote_timeout_seconds_invalid` | Remote submission timeout was non-finite, zero, negative, or above the maximum |
| `remote_api_token_required` | Remote submission was requested without a bearer token |
| `remote_preflight_receipt_required` | Remote submission was requested without a preflight receipt |
| `remote_preflight_receipt_failed:*` | The preflight receipt was unreadable, schema-invalid, blocked, stale, or mismatched the final payload |
| `remote_submission_failed:*` | Remote transparency-log submission did not produce a matching payload-hash witness |
| `submission_ledger_invalid:*` | Existing ledger replay failed before append |
| `submission_receipt_schema_validation_failed` | The generated submission receipt violated the public schema |

## Resolution Stamp

STATUS:
  Completeness: 100%
  Invariants verified: schema-gated bundle replay, schema-gated anchor replay, typed artifact root replay, terminal closure remains final closure authority
  Open issues: none
  Next action: use this runbook during trust-ledger export audits and release evidence review
