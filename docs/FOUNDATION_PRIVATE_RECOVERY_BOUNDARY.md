<!--
Purpose: define the public-safe boundary for private recovery inventory work.
Governance scope: account recovery, deployment blockers, secret exclusion, private owner evidence, and Foundation Mode promotion gates.
Dependencies: docs/FOUNDATION_MODE.md, docs/FOUNDATION_PREREQUISITES.md, examples/foundation_private_recovery_inventory.redacted.json, scripts/validate_foundation_private_recovery_boundary.py.
Invariants: no secret values, no recovery code values, no provider account IDs, no DNS target values, no billing details, no private storage paths, no deployment claim.
-->

# Foundation Private Recovery Boundary

<!-- TYPE: Explanation -->
<!-- AUDIENCE: solo founder, assisting developer agents, future reviewers -->

> **In one box:** private recovery work means preparing the owner-only account
> safety records needed before infrastructure work. This repository may track
> the checklist and public-safe witness state. It must not store the private
> values themselves.

Descriptor: [`../examples/foundation_private_recovery_inventory.redacted.json`](../examples/foundation_private_recovery_inventory.redacted.json)

Public-safe witness: [`../examples/foundation_recovery_witness.awaiting_evidence.json`](../examples/foundation_recovery_witness.awaiting_evidence.json)

Rule: Recovery evidence is a prerequisite for deployment, not deployment evidence.

No secret values are permitted in Git. Private inventory remains outside this repository.

## What This Boundary Solves

Before runtime infrastructure, DNS mutation, customer access, or paid provider
setup, the owner needs a way to recover the root accounts that control the
project. Losing one of those accounts can block the whole system.

This document keeps that work small:

1. This repository records only the public-safe checklist.
2. The actual private inventory is created and maintained outside Git.
3. Validators reject secret-shaped fields in the redacted example.
4. Promotion remains `AwaitingEvidence` until the operator manually confirms
   the private inventory.

## Public-Safe Categories

| Category | Public-safe record here | Private record outside Git |
| --- | --- | --- |
| Cloud account recovery | Whether recovery is still `AwaitingEvidence`. | Storage location and verification date. |
| Source account recovery | Whether source-control recovery is still `AwaitingEvidence`. | Recovery method location and verification date. |
| Workspace/email recovery | Whether admin recovery is still `AwaitingEvidence`. | Admin recovery path and verification date. |
| Domain registrar recovery | Whether registrar recovery is still `AwaitingEvidence`. | Recovery path, transfer-lock check, renewal owner. |
| DNS provider recovery | Whether DNS recovery is still `AwaitingEvidence`. | Recovery path and verification date. |
| Password manager recovery | Whether emergency access is still `AwaitingEvidence`. | Emergency access instructions and location. |
| Offline backup recovery | Whether offline backup is still `AwaitingEvidence`. | Encrypted backup location and restore note. |
| Billing renewal recovery | Whether renewal ownership is still `AwaitingEvidence`. | Renewal owner, calendar location, and payment owner. |

## Forbidden Content

Do not store recovery codes, passwords, provider account IDs, DNS targets,
billing details, private storage paths, tokens, session exports, or private keys
in this repository.

The committed redacted example may name the class of thing that must stay out of
Git. It must not contain the value itself.

## Current State

```text
private_recovery_boundary_state=AwaitingEvidence
private_inventory_required=true
private_inventory_stored_in_git=false
api_provisioning_allowed=false
dns_publication_allowed=false
```

Public-safe state is `AwaitingEvidence` until the operator completes the private
inventory outside Git and records a separate public-safe witness without secret
content. The committed public-safe witness is an AwaitingEvidence template, not
a readiness claim.

## Operator Procedure

1. Open the redacted example and use it as a checklist, not as a place to fill
   secrets.
2. Create the real owner-only inventory outside this repository.
3. Record only storage location categories and verification dates in that
   private inventory.
4. Keep raw account recovery material inside a password manager or encrypted
   offline backup.
5. After manual confirmation, update only a public-safe witness with
   `ReadyForProvisioning` state. Do not write private values into Git.

## Validation

Run:

```powershell
python scripts/validate_foundation_private_recovery_boundary.py
```

The validator checks that the redacted inventory example and public-safe witness:

1. uses only the approved public-safe fields;
2. keeps all entries in `AwaitingEvidence`;
3. keeps provisioning and DNS publication blocked;
4. avoids URL values, token-shaped values, card-shaped values, private-key
   material, and unapproved extra fields.

## Go Deeper / Where To Go Next

| You now want to... | Go to |
| --- | --- |
| See the whole Foundation Mode posture | [Foundation Mode](FOUNDATION_MODE.md) |
| See the prerequisite ledger | [Foundation Prerequisites](FOUNDATION_PREREQUISITES.md) |
| Run the harmless local proof thread | [Foundation Local Proof Thread](FOUNDATION_LOCAL_PROOF_THREAD.md) |
| Check deployment truth | [Deployment Status](../DEPLOYMENT_STATUS.md) |

STATUS:
  Completeness: 100%
  Invariants verified: no secret values in Git, private inventory outside repository, public-safe witness AwaitingEvidence, provisioning blocked, DNS publication blocked
  Open issues: operator must complete private inventory outside Git
  Next action: run the private recovery boundary validator, then keep the real inventory outside the repository
