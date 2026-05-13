# Trust Ledger Offline Verification

Purpose: define the operator replay path for signed trust-ledger evidence bundles
and external anchor receipts.

Governance scope: offline evidence verification, schema-gated replay, terminal
closure anchoring, and anchor receipt tamper detection.

Dependencies:

- `scripts/verify_evidence_bundle.py`
- `scripts/verify_anchor_receipt.py`
- `schemas/trust_ledger_bundle.schema.json`
- `schemas/trust_ledger_anchor_receipt.schema.json`
- `schemas/trust_ledger_evidence_artifacts.schema.json`

Invariants:

- Bundle verification validates schema, bundle hash, and HMAC signature.
- Anchor verification validates bundle, receipt, and artifact schemas before typed reconstruction.
- Anchor verification binds the receipt to the bundle id, bundle hash, artifact root, receipt id, receipt hash, and HMAC signature.
- Anchor receipts do not replace terminal closure certificates.
- Missing signing secrets fail closed.

## Export Inputs

| File | Contract | Role |
| --- | --- | --- |
| `bundle.json` | `trust_ledger_bundle.schema.json` | Signed terminal-closure evidence bundle |
| `anchor_receipt.json` | `trust_ledger_anchor_receipt.schema.json` | Signed external anchor receipt |
| `artifacts.json` | `trust_ledger_evidence_artifacts.schema.json` | Typed evidence artifact list used to recompute the artifact root |
| `package.json` | `trust_ledger_export_package.schema.json` | Portable manifest binding expected file names, content hashes, bundle id, receipt id, and artifact root |

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
  "schema_valid": true
}
```

Fail-closed reasons include:

| Reason | Meaning |
| --- | --- |
| `signing_secret_required` | No anchor HMAC secret was provided |
| `schema_validation_failed` | Bundle, receipt, or artifact JSON violates its schema |
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

## Operator Procedure

1. Export `bundle.json`, `anchor_receipt.json`, `artifacts.json`, and `package.json` from the same command closure.
2. Verify `bundle.json` first with `scripts/verify_evidence_bundle.py`.
3. Verify the anchor with `scripts/verify_anchor_receipt.py`.
4. Confirm `package.json` file hashes match the exported file contents before moving the package across trust boundaries.
5. Compare `command_id`, `terminal_certificate_id`, `bundle_id`, and `anchor_receipt_id` in the JSON reports.
6. Treat any invalid report as `GovernanceBlocked` until the source export is regenerated or the tamper source is identified.

## Resolution Stamp

STATUS:
  Completeness: 100%
  Invariants verified: schema-gated bundle replay, schema-gated anchor replay, typed artifact root replay, terminal closure remains final closure authority
  Open issues: none
  Next action: use this runbook during trust-ledger export audits and release evidence review
