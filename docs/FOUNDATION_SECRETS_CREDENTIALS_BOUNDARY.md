<!--
Purpose: define the Foundation Mode secrets and credentials boundary before any real secret storage, credential activation, provider account binding, external call readiness, or deployment claim.
Governance scope: secrets posture, credential posture, environment-variable posture, provider-access posture, no real secret storage, no credential activation, no private key storage, no external call readiness, and no deployment claim.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_secrets_credentials_witness.awaiting_evidence.json, examples/foundation_secrets_credentials_current_packet.awaiting_evidence.json, scripts/validate_foundation_secrets_credentials_boundary.py.
Invariants: no real secret storage, no credential activation, no provider account binding, no API key creation, no OAuth app creation, no service account creation, no environment file commit, no private key storage, no secret rotation readiness claim, no secret scan pass claim, no external call readiness, no deployment claim.
-->

# Foundation Secrets Credentials Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** secrets and credentials preparation means drafting the names,
> questions, storage rules, and scanning checklist that would be needed before
> connecting real accounts. It does not store real secrets, create keys, bind
> provider accounts, activate credentials, commit environment files, enable
> external calls, or deploy anything.

Witness packet: [`../examples/foundation_secrets_credentials_witness.awaiting_evidence.json`](../examples/foundation_secrets_credentials_witness.awaiting_evidence.json)

Application packet: [`../examples/foundation_secrets_credentials_current_packet.awaiting_evidence.json`](../examples/foundation_secrets_credentials_current_packet.awaiting_evidence.json)

Rule: Secrets/credentials preparation is a local planning boundary, not permission to store or activate real credentials.

No real-secret storage, credential activation, provider-account binding, API
key creation, OAuth app creation, service account creation, environment-file
commit, private-key storage, secret-rotation readiness, external-call
readiness, or deployment claim is permitted by this boundary.

## What This Boundary Solves

External tools usually require credentials before they can do useful work.
Foundation Mode needs the opposite order: define the credential boundary first,
then connect nothing until the local proof chain and private recovery posture
are strong enough.

This boundary keeps the work small:

1. Draft credential categories locally.
2. Draft environment-variable names without assigning values.
3. Draft provider-access, key, OAuth, service-account, rotation, and recovery
   questions locally.
4. Keep real secrets, tokens, account identifiers, private paths, and provider
   bindings out of the repository.
5. Keep external-call and deployment readiness in `AwaitingEvidence`.

## Current State

```text
secrets_credentials_boundary_state=AwaitingEvidence
real_secret_storage_allowed=false
credential_activation_allowed=false
provider_account_binding_allowed=false
api_key_creation_allowed=false
oauth_app_creation_allowed=false
service_account_creation_allowed=false
env_file_commit_allowed=false
private_key_storage_allowed=false
secret_rotation_claimed=false
secret_scan_pass_claimed=false
external_call_allowed=false
deployment_allowed=false
```

## Public-Safe Preparation Surfaces

| Surface | Public-safe record here | Do not store or claim here |
| --- | --- | --- |
| Credential inventory draft | Credential categories only. | Real secret values, account IDs, or live provider bindings. |
| Environment variable plan | Variable names and purpose only. | `.env` files or assigned environment values. |
| Provider access questions | Provider categories and review questions only. | Provider account IDs, console links, or connected accounts. |
| API key questions | Key-need questions only. | Created keys, key values, or key readiness. |
| OAuth app questions | App-scope questions only. | Client secrets, callback URLs, or live app IDs. |
| Service account questions | Role and boundary questions only. | Service account keys or account emails. |
| Rotation/recovery questions | Recovery procedure questions only. | Rotation-readiness claim or recovery secrets. |
| Secret scan checklist | Local checklist only. | Scan-pass claim without current validator evidence. |

## Current Packet Screening Application

The current application packet records only public-safe screening categories:

| Category | Meaning |
| --- | --- |
| Secret value pattern guard | Secret-shaped value patterns are treated as blocked evidence, not clearance. |
| Environment assignment guard | Assigned environment values remain outside public artifacts. |
| Private path guard | Private machine paths remain outside public artifacts. |
| Token shape guard | Token-shaped values remain blocked from public artifacts. |
| Provider binding guard | Provider account binding remains blocked. |
| Source-control publication stop rule | Staging, commit, push, and pull request remain blocked. |
| Current packet category-only review | The dirty packet is described by categories, not private values or file lists. |

It does not record changed-file lists, secret values, credential values,
assigned environment values, private paths, account identifiers, provider
bindings, customer identifiers, legal conclusions, company filings, patent
filings, payment details, Git refs, endpoint targets, or deployment targets.
It also does not claim a secret scan pass, secret clearance, credential
readiness, external-call readiness, or deployment readiness.

## Operator Procedure

1. Keep secrets/credentials materials as local drafts.
2. Do not create, paste, store, or commit real secrets in Foundation Mode.
3. Do not bind provider accounts, create keys, create OAuth apps, or create
   service accounts without a later signed witness and private owner procedure.
4. Do not commit `.env` files, private keys, tokens, passwords, recovery codes,
   or account-specific identifiers.
5. Treat every credential surface as `AwaitingEvidence` until a later private
   witness promotes it.

## Validation

Run:

```powershell
python scripts/validate_foundation_secrets_credentials_boundary.py
```

The validator checks that the witness packet:

1. keeps every secrets/credentials surface in `AwaitingEvidence`;
2. blocks real secret storage, credential activation, provider binding, key
   creation, environment-file commits, external calls, and deployment;
3. rejects URL, email, private-path, assignment-shaped, key-shaped, token-shaped,
   or private-key-shaped values; and
4. verifies the current-packet screening application remains category-only and
   keeps scan-pass, Git, publication, deployment, customer, legal, company,
   patent, money, and credential actions blocked; and
5. rejects secrets/credentials readiness-promotion phrases.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Prepare private recovery safely | [Foundation Private Recovery Boundary](FOUNDATION_PRIVATE_RECOVERY_BOUNDARY.md) |
| Prepare source-control safely | [Foundation Source Control Boundary](FOUNDATION_SOURCE_CONTROL_BOUNDARY.md) |

STATUS:
  Completeness: 100%
  Invariants verified: real secret storage blocked, credential activation blocked, provider account binding blocked, API key creation blocked, OAuth app creation blocked, service account creation blocked, environment file commit blocked, private key storage blocked, secret scan pass blocked, external calls blocked, deployment blocked
  Open issues: private owner storage procedure, provider account review, key-creation review, OAuth review, service-account review, rotation review, current-packet scan-pass evidence, and deployment evidence remain AwaitingEvidence
  Next action: run the secrets/credentials boundary validator, then keep all real credentials outside public artifacts until private evidence promotes them
