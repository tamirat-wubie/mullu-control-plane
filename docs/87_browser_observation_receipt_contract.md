# Browser Observation Receipt Contract

Purpose: define a digest-only browser observation receipt for operator evidence before any browser-control authority is considered.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `docs/FOUNDATION_MODE.md`, `docs/82_cross_repo_opportunity_map.md`, `schemas/browser_observation_receipt.schema.json`, `schemas/capture_policy_decision_ledger.schema.json`, `schemas/evidence_classification_manifest.schema.json`, `schemas/universal_action_orchestration.schema.json`, `schemas/life_meaning_judgment.schema.json`.
Invariants: browser observation stores no raw URL, raw DOM, raw screenshot, raw secret, cookie, or session payload; browser observation grants no navigation, click, form-submit, keystroke-injection, connector, external-write, publication, terminal-closure, or success authority.

## Boundary

`BrowserObservationReceipt` is an evidence receipt, not a browser-control adapter.

It may bind:

1. Hashed source URL evidence.
2. DOM, screenshot, and title digest refs.
3. Viewport and capture-policy refs.
4. Consent scope and UAO ref.
5. Privacy guards and authority-denial flags.
6. Receipt refs for capture policy, evidence classification, UAO, and LifeMeaningJudgment.

It must not bind:

1. Raw URL bodies.
2. Raw DOM bodies.
3. Raw screenshot files.
4. Raw secret values.
5. Cookies or sessions.
6. Click, submit, keystroke, navigation, or connector authority.
7. Publication, terminal closure, or success claims.

## Foundation Example

The Foundation Mode example is:

```text
examples/browser_observation_receipt.foundation.json
```

The validator is:

```powershell
python scripts\validate_browser_observation_receipt.py
```

Expected result:

```text
[PASS] browser_observation_receipt
```

## Authority Denials

The Foundation example requires these fields to remain `false`:

| Field | Denial |
| --- | --- |
| `navigation_performed` | no navigation authority |
| `click_performed` | no click authority |
| `form_submit_performed` | no form-submit authority |
| `keystroke_injection_performed` | no keystroke-injection authority |
| `cookie_or_session_read` | no cookie or session access |
| `secret_captured` | no secret capture |
| `external_write_performed` | no external writes |
| `file_write_performed` | no file writes |
| `connector_call_performed` | no connector calls |
| `publication_allowed` | no external publication |
| `terminal_closure_allowed` | no terminal closure |
| `success_claim_allowed` | no success claim |

## Privacy Guards

The Foundation example requires raw storage fields to remain `false` and review guards to remain `true`:

| Field | Required value |
| --- | --- |
| `raw_url_stored` | `false` |
| `raw_dom_stored` | `false` |
| `raw_screenshot_stored` | `false` |
| `raw_secret_value_stored` | `false` |
| `private_payload_redacted` | `true` |
| `operator_review_required` | `true` |

## Verification

Run:

```powershell
python scripts\validate_browser_observation_receipt.py
python -m pytest tests\test_validate_browser_observation_receipt.py -q
python scripts\validate_protocol_manifest.py
python scripts\proof_coverage_matrix.py --check
python scripts\validate_sdlc_artifact.py
python scripts\validate_sdlc_security_review.py --review examples\sdlc\security_review_browser_observation_receipt_20260616.json --strict
```

STATUS:
  Completeness: 100%
  Invariants verified: digest-only observation, no raw URL, no raw DOM, no raw screenshot, no raw secret, no browser mutation authority, no connector authority, no publication, no terminal closure
  Open issues: none
  Next action: use BrowserObservationReceipt before any future browser-control approval gate
