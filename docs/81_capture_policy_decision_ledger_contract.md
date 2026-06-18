# Capture Policy Decision Ledger Contract

Purpose: define the local Foundation Mode contract that records capture policy decisions before observed content becomes symbolic evidence.
Governance scope: source surface, policy scope, sensitivity floor, budget window, redaction boundary, authority denial, and pre-capture receipts.
Dependencies: `schemas/capture_policy_decision_ledger.schema.json`, `examples/capture_policy_decision_ledger.foundation.json`, and `scripts/validate_capture_policy_decision_ledger.py`.
Invariants: capture is denied until policy allows it; raw observed content is not serialized; raw secret material is not serialized; this contract grants no connector, execution, memory-write, runtime registration, deployment, or terminal closure authority.

## 1. Boundary

`CapturePolicyDecisionLedger` is a pre-capture governance object. It answers:

```text
Which source surface is being considered?
Which policy and tenant scope governs the capture?
Which sensitivity classes are blocked or require redaction?
Which budget window bounds the decision?
Which per-event decision applies?
What evidence proves the decision?
```

It does not capture browser DOM, documents, messages, files, connector payloads, or mailbox contents. It does not store raw observed content, raw secret material, or raw private payloads.

## 2. Decision States

| State | Meaning | Authority |
| --- | --- | --- |
| `CAPTURE_ALLOWED` | policy allows a bounded capture in a later governed step | no capture by this contract |
| `CAPTURE_REDACTED` | only a redacted symbolic reference may be retained later | no raw payload retention |
| `CAPTURE_BLOCKED_BY_POLICY` | policy denies capture | no capture authority |
| `CAPTURE_BLOCKED_BY_SENSITIVITY` | sensitivity floor denies capture | no capture or stored payload |
| `CAPTURE_BLOCKED_BY_BUDGET` | budget window denies capture | no capture authority |
| `CAPTURE_REVIEW_REQUIRED` | operator or governance review is required first | no capture authority |

## 3. Sensitivity Floor

| Classification | Required Handling |
| --- | --- |
| `credential` | blocked, no stored payload |
| `secret` | blocked, no stored payload |
| `payment` | blocked, no stored payload |
| `confidential` | redaction required |
| `sensitive` | redaction required |
| `restricted` | redaction required |
| `health` | redaction required |
| `minor` | redaction required |
| `biometric` | redaction required |

Raw value serialization remains `false` for all sensitivity classifications. A source marker that looks like a secret forces `CAPTURE_BLOCKED_BY_SENSITIVITY`.

## 4. Hard Guards

| Guard | Required Value |
| --- | --- |
| `capture_performed` | `false` |
| `raw_observed_content_serialized` | `false` |
| `raw_secret_material_included` | `false` |
| `connector_authority_granted` | `false` |
| `execution_authority_granted` | `false` |
| `memory_write_authority_granted` | `false` |
| `terminal_closure` | `false` |
| `mfidel_atomicity_preserved` | `true` |

## 5. Foundation Mode

Foundation Mode treats live browser, document, mailbox, local-file, and connector capture as `AwaitingEvidence` unless a later governed worker proves authority, budget, tenant scope, sensitivity handling, redaction, receipt emission, and verification.

This contract is the local proof thread for the decision ledger shape only. It improves control-plane readiness by making the capture admission boundary explicit before any observation can be promoted into evidence.
