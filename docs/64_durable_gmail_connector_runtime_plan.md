<!--
Purpose: Define the governed boundary for durable Gmail connector runtime access after the bounded live adapter evidence proof.
Governance scope: OAuth authority, least-privilege scope selection, secret redaction, refresh-token lifecycle, revocation, audit receipts, evidence freshness, tenant/mailbox binding, and release blocking.
Dependencies: gateway/email_calendar_connector_adapters.py, gateway/email_calendar_worker.py, gateway/gmail_oauth_lifecycle.py, examples/sdlc/requirement_durable_gmail_connector_runtime_20260611.json, examples/sdlc/security_review_durable_gmail_connector_runtime_20260611.json, schemas/durable_gmail_oauth_operator_handoff.schema.json, scripts/validate_durable_gmail_connector_runtime_plan.py, scripts/validate_durable_gmail_oauth_runtime_preflight.py, scripts/validate_durable_gmail_oauth_operator_handoff.py, scripts/validate_durable_gmail_oauth_live_receipt_freshness.py, scripts/validate_durable_gmail_account_binding_receipt.py, scripts/mint_gmail_oauth_access_token.py, scripts/produce_durable_gmail_oauth_operator_handoff.py, scripts/produce_durable_gmail_oauth_live_receipt.py.
Invariants: No Google Cloud credential creation, OAuth client creation, consent-screen publication, or production verification claim is performed by this repository-local plan.
-->

# Durable Gmail Connector Runtime Plan

## Architecture

The completed adapter-evidence milestone proved that the email/calendar worker can execute a bounded Gmail read probe when a scoped connector token is supplied. Durable runtime access is a different boundary:

```text
bounded evidence token
-> governed OAuth app boundary
-> least-privilege scope decision
-> refresh-token storage and rotation
-> revocation and failed-refresh recovery
-> evidence freshness validation
-> tenant/mailbox account binding
-> approval-gated write actions
-> production readiness witness
```

The prior live adapter receipt did not close durable runtime access by itself. Current repository and GitHub evidence closes only the read-only Gmail live-probe boundary as `SolvedVerified` when the provider-side OAuth witnesses, runtime lifecycle witnesses, live probe receipt, and evidence freshness receipt pass.

Tenant/mailbox binding is a separate claim. A read-only Gmail probe proves that a token can search Gmail; it does not by itself prove that the token is bound to the intended tenant mailbox. Tenant/mailbox binding becomes claimable only when a redacted account binding receipt passes with matching expected and observed account hashes, no raw mailbox address, no credential value disclosure, no external mailbox write, and fresh `checked_at` evidence.

Gmail draft/send authority, Calendar authority, public production readiness, and customer readiness remain `AwaitingEvidence` until separate account-binding, write, calendar, deployment, and customer-surface witnesses pass.

## Requirement Boundary

| Boundary | Required decision |
| --- | --- |
| Scope | Select the narrowest Gmail scope that satisfies the connector operation before any credential mutation. |
| Environment | Keep testing/staging and production OAuth projects separate when public production use is planned. |
| Consent | Configure consent-screen identity, support contact, domain ownership, and app use statement before user-data access is expanded. |
| Secret lifecycle | Store only secret presence and receipt refs in repository artifacts; never serialize access tokens, refresh tokens, client secrets, or private keys. |
| Runtime | Implement refresh, expiry, rotation, revocation, and failed-refresh recovery before durable access is claimed. |
| Tenant/mailbox binding | Bind the Gmail token to the intended tenant mailbox through a redacted account hash receipt before any tenant-specific or customer claim. |
| Approval | Keep Gmail send and draft actions approval-gated; a read-only probe token must not admit write operations. |

## Algorithm

1. Choose the connector operation family: read-only search, message metadata, draft creation, or send.
2. Map the operation family to the least-privilege Gmail scope using current Google Workspace documentation.
3. Classify the scope as non-sensitive, sensitive, or restricted before creating or changing provider credentials.
4. If sensitive or restricted, record the required Google verification path before public production use.
5. Create provider-side credentials only after explicit operator authority and record a redacted witness.
6. Bind runtime secrets through the governed secret store and record presence-only receipts.
7. Produce the repository-local operator handoff packet before any provider or secret-store mutation.
8. Classify refresh-token outcomes through the repository-local lifecycle contract: refreshed, retryable provider error, revoked or expired refresh token, OAuth client rejection, scope rejection, malformed provider response, and too-short access-token lifetime.
9. Run `scripts\mint_gmail_oauth_access_token.py` in the live-evidence workflow or `scripts\produce_durable_gmail_oauth_live_receipt.py` in local proof mode to refresh a transient access token, execute the existing Gmail read-only live probe, and persist only redacted refresh and adapter evidence.
10. Validate the live receipt freshness before relying on a read-only live-probe claim.
11. Validate `scripts\validate_durable_gmail_account_binding_receipt.py` before claiming the token belongs to the intended tenant mailbox.
12. Run approval-gated send/draft evidence only if write operations are in scope.
13. Update release readiness only after all receipts pass.

## Non-Goals

- No Google Cloud credential creation in this change.
- No OAuth consent-screen publication in this change.
- No production verification submission in this change.
- No repository storage of token values, refresh-token values, client secrets, or private keys.
- No expansion from Gmail to Google Calendar or Microsoft Graph in this change.

## Evidence Gates

| Gate | Read-only Gmail live-probe boundary |
| --- | --- |
| OAuth consent-screen witness | Present for read-only probe |
| OAuth client witness | Present for read-only probe |
| Least-privilege scope receipt | Present for `gmail.readonly` |
| Refresh-token storage receipt | Present as witness ref; token value not serialized |
| Rotation and revocation receipt | Present as witness ref; destructive revocation drill not executed in this plan |
| Failed-refresh recovery receipt | Contract-tested; live failure drill remains optional unless required for promotion |
| Read-only Gmail probe receipt | `SolvedVerified` for Gmail search with no external mailbox write |
| Evidence freshness receipt | Required before relying on a prior live receipt |
| Tenant/mailbox binding receipt | Required before tenant-specific, customer, or production claims |
| Write-action approval receipt | `AwaitingEvidence`; required only if draft or send is enabled |
| Security review | Release-blocking for write, calendar, production, and customer claims |

## GitHub Runtime Inventory

The durable Gmail runtime preflight can read GitHub repository configuration without exposing credential values:

```powershell
gh variable set MULLU_EMAIL_CALENDAR_WORKER_ADAPTER --repo tamirat-wubie/mullu-control-plane --body google
python scripts\validate_durable_gmail_oauth_runtime_preflight.py --github-repo tamirat-wubie/mullu-control-plane --output .change_assurance\durable_gmail_oauth_runtime_preflight.json --json --require-ready
python scripts\produce_durable_gmail_oauth_operator_handoff.py --github-repo tamirat-wubie/mullu-control-plane --operator-approval-ref "$env:MULLU_GMAIL_OPERATOR_APPROVAL_REF" --output .change_assurance\durable_gmail_oauth_operator_handoff.json --json --require-live-probe
python scripts\validate_durable_gmail_oauth_operator_handoff.py --handoff .change_assurance\durable_gmail_oauth_operator_handoff.json --output .change_assurance\durable_gmail_oauth_operator_handoff_validation.json --require-live-probe --json
python scripts\validate_durable_gmail_oauth_live_receipt_freshness.py --receipt .change_assurance\durable_gmail_oauth_live_receipt.json --max-age-days 14 --require-fresh --json
python scripts\validate_durable_gmail_account_binding_receipt.py --receipt .change_assurance\durable_gmail_account_binding_receipt.json --max-age-days 14 --require-bound --json
```

The GitHub path treats repository secrets as presence-only bindings and admits only non-secret variables and witness-reference variables as readable values. Secret-shaped values in admitted variables are rejected. Local environment values and explicit env files retain precedence over GitHub repository inventory.

The operator handoff emits `store_command` templates only. Durable credential bindings use `gh secret set`; witness-reference bindings use `gh variable set ... --body <witness-ref>` so non-secret proof references remain readable by the preflight without exposing credential material.

Observed repository readiness inputs:

| Input | Evidence state |
| --- | --- |
| `MULLU_EMAIL_CALENDAR_WORKER_ADAPTER` | GitHub variable set to `google`. |
| `EMAIL_CALENDAR_CONNECTOR_ID` | GitHub variable set to `gmail`. |
| `GMAIL_SCOPE_ID` | GitHub variable set to `https://www.googleapis.com/auth/gmail.readonly`. |
| `MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY` | GitHub variable set to `read_only_search`. |
| Gmail OAuth credential bindings | GitHub secret-name inventory present; values are not read. |
| Provider and lifecycle witnesses | GitHub witness-reference variables present. |

## Live Evidence Witness

The email/calendar target was exercised through GitHub Actions run `27472200253`:

```powershell
gh workflow run capability-adapter-live-evidence.yml --repo tamirat-wubie/mullu-control-plane -f target=email-calendar -f email_calendar_connector_id=gmail -f email_calendar_query='newer_than:1d' -f strict=true
```

Downloaded artifact `capability-adapter-live-evidence` included:

| Receipt | Validation result |
| --- | --- |
| `gmail_oauth_refresh_receipt.json` | `passed`; OAuth refresh succeeded; token type `Bearer`; secret values not disclosed. |
| `email_calendar_live_receipt.json` | `passed`; provider operation `email.search`; external write `false`; ready `true`. |
| `general_agent_promotion_environment_binding_receipt.json` | Valid for Gmail bindings; aggregate readiness remains false because voice probe audio was not in scope. |
| `capability_adapter_evidence.json` | `communication.email_calendar_worker` status `closed`; aggregate adapter report remains not ready because browser, document, and voice targets were intentionally skipped. |

The Gmail read-only durable probe is therefore `SolvedVerified` for the email/calendar adapter. This does not claim production-customer readiness, Gmail write authority, calendar authority, or full capability-adapter promotion.

## Verification

Run:

```powershell
python scripts\validate_durable_gmail_connector_runtime_plan.py
python scripts\produce_durable_gmail_oauth_operator_handoff.py --json
python scripts\validate_durable_gmail_oauth_operator_handoff.py --output .change_assurance\durable_gmail_oauth_operator_handoff_validation.json --require-blocked --json
python scripts\validate_durable_gmail_oauth_runtime_preflight.py --output .change_assurance\durable_gmail_oauth_runtime_preflight.json --json
python scripts\validate_durable_gmail_oauth_runtime_preflight.py --github-repo tamirat-wubie/mullu-control-plane --output .change_assurance\durable_gmail_oauth_runtime_preflight.json --json --require-ready
python scripts\produce_durable_gmail_oauth_operator_handoff.py --github-repo tamirat-wubie/mullu-control-plane --operator-approval-ref "$env:MULLU_GMAIL_OPERATOR_APPROVAL_REF" --output .change_assurance\durable_gmail_oauth_operator_handoff.json --json --require-live-probe
python scripts\validate_durable_gmail_oauth_operator_handoff.py --handoff .change_assurance\durable_gmail_oauth_operator_handoff.json --output .change_assurance\durable_gmail_oauth_operator_handoff_validation.json --require-live-probe --json
python scripts\mint_gmail_oauth_access_token.py --json
python scripts\produce_durable_gmail_oauth_live_receipt.py --json
python scripts\validate_durable_gmail_oauth_live_receipt_freshness.py --receipt .change_assurance\durable_gmail_oauth_live_receipt.json --max-age-days 14 --require-fresh --json
python scripts\validate_durable_gmail_account_binding_receipt.py --receipt .change_assurance\durable_gmail_account_binding_receipt.json --max-age-days 14 --require-bound --json
python scripts\validate_sdlc_security_review.py --review examples\sdlc\security_review_durable_gmail_connector_runtime_20260611.json --strict
python -m pytest tests\test_durable_gmail_connector_runtime_plan.py tests\test_validate_durable_gmail_oauth_runtime_preflight.py tests\test_validate_durable_gmail_oauth_operator_handoff.py tests\test_validate_durable_gmail_oauth_live_receipt_freshness.py tests\test_validate_durable_gmail_account_binding_receipt.py tests\test_mint_gmail_oauth_access_token.py tests\test_produce_durable_gmail_oauth_operator_handoff.py tests\test_produce_durable_gmail_oauth_live_receipt.py tests\test_gateway\test_gmail_oauth_lifecycle.py -q
```

The plan validator must pass while still blocking production-customer claims. The operator handoff producer emits only command templates, expected evidence refs, scope decisions, recommended non-secret defaults, and presence-only binding names; its preflight summary is based on observed runtime inputs without applying those defaults, and it performs no Google Cloud, Gmail, or GitHub secret mutation. The OAuth runtime preflight emits a presence-only receipt and reaches `SolvedVerified` for the read-only Gmail live-probe boundary when the GitHub repo inventory or local environment contains the required adapter mode, connector id, Gmail scope, durable secret presence, provider witnesses, refresh-token storage receipt, and revocation/recovery receipt. The workflow token mint helper writes the access token only to the requested runtime environment file, and the durable live receipt producer performs one token refresh and one Gmail read-only probe before writing only redacted refresh classification, access-token digest evidence, and existing email/calendar worker receipt refs. The freshness validator blocks stale, future-skewed, non-passing, unrecognized, or secret-contaminated evidence before any prior live receipt can support a current claim. The account binding validator blocks mismatched account hashes, missing profile-probe evidence, raw mailbox addresses, credential-shaped values, stale evidence, and external mailbox writes before any tenant/mailbox binding claim. The lifecycle contract classifies refresh outcomes without printing token, refresh-token, client-secret, or private-key values.

STATUS:
  Completeness: 100%
  Invariants verified: [external credential mutation blocked, least-privilege scope gate defined, secret value serialization blocked, operator handoff packet redacted, refresh and revocation evidence required, failed-refresh recovery classified, read-only live probe verified, evidence freshness gate defined, tenant/mailbox binding gate defined, write actions approval-gated]
  Open issues: [no Gmail write-action authority claimed, no Calendar authority claimed, destructive revocation drill not executed, no production/customer claim without account-binding receipt, full adapter aggregate still blocked by browser/document/voice live evidence]
  Next action: produce a redacted live account-binding receipt from a Gmail profile probe before tenant-specific claims
