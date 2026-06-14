# Personal Assistant Risk Boundary

Purpose: define the approval and execution boundary for personal-assistant skills.
Governance scope: UAO no-bypass enforcement, approval classification, connector privacy, no-secret serialization, no public-readiness overclaim, and no live Nested Mind activation.
Dependencies: `schemas/personal_assistant_skill.schema.json`, `schemas/personal_assistant_approval.schema.json`, `schemas/personal_assistant_receipt.schema.json`, `governance/personal_assistant_approval_matrix.yaml`, and existing communication, software-development, deployment, finance, and Nested Mind gates.
Invariants: effect-bearing actions require explicit approval and receipts; P5 actions remain blocked until named evidence and operator approval exist.

## Risk Classes

| Level | Meaning | Approval |
| --- | --- | --- |
| P0 | Public read-only, no private connector | Not required |
| P1 | Private read-only | Connector proof required |
| P2 | Draft-only | Approval not required for draft artifact; execution remains blocked |
| P3 | Internal write | Explicit approval required |
| P4 | External communication | Explicit approval required |
| P5 | Money, legal, public, deployment, customer-impacting, or system-of-record action | Explicit approval plus evidence required |

## Default Allow List

The assistant may do these by default when schema, policy, and connector proof allow them:

1. Read public information.
2. Read private connector data only with connector proof.
3. Summarize.
4. Classify priority.
5. Ask clarification.
6. Produce a plan.
7. Produce a draft artifact.
8. Produce a redacted receipt.
9. Recommend a next action.

## Default Block List

The assistant may not do these without explicit approval and receipts:

1. Send email, messages, posts, or invitations.
2. Delete, archive, forward, or batch-label mailbox items.
3. Create, move, cancel, or invite calendar events.
4. Share, publish, sign, submit, or delete documents.
5. Store new contacts or export contact lists.
6. Open pull requests, merge, push, publish releases, or deploy services.
7. Move money, pay invoices, start subscriptions, or make legal filings.
8. Mutate connector state, systems of record, deployment state, or customer-facing state.
9. Activate live Nested Mind memory topology.
10. Claim customer readiness, enterprise SLA, production readiness, or live activation without named witness evidence.

## Connector Privacy

Connector-backed skills must project only bounded evidence:

| Allowed projection | Blocked projection |
| --- | --- |
| connector id | access token |
| query hash | refresh token |
| response digest | raw mailbox payload |
| redacted summary | private message body |
| evidence ref | private key |
| provider receipt ref | credential value |

Receipts record action names and evidence references, not raw private payloads.

## Memory Privacy

Memory observation previews may store only a claim-level candidate for operator
review. They may not store raw chat logs, raw connector payloads, credentials,
tokens, private keys, or full private message bodies.

Required memory read-model flags:

```text
live_memory_write_allowed = false
nested_mind_live_activation_allowed = false
raw_private_payload_storage_allowed = false
secret_value_storage_allowed = false
candidate_only = true
```

Every memory candidate receipt must record that live memory was not written,
Nested Mind was not activated, raw chat logs were not stored, raw connector
payloads were not stored, and system-of-record state was not mutated.

## Approval Rules

Approval is valid only when it binds:

```text
approval_id
request_id
plan_id
risk_level
proposed_actions
approver_ref
approval_state
evidence_refs
receipt_ref
```

Approval for one action does not authorize a batch, future recurrence, different recipient, deployment, payment, or connector mutation unless that scope is explicit.

## Failure Rules

| Failure | Required behavior |
| --- | --- |
| Missing entity binding | Ask WHQR clarification |
| Missing evidence binding | Ask WHQR clarification |
| Unknown hard-law risk | Block and plan sensing |
| P4/P5 without approval | Block |
| Raw secret detected | Reject receipt or registry |
| Raw connector payload detected | Reject receipt |
| Live Nested Mind activation requested | Mark `AwaitingEvidence` |
| Public-readiness claim without witness | Reject overclaim |

## Outcome Terms

Use `SolvedVerified` only when schemas, policies, examples, validators, tests, and workspace governance checks pass. Use `AwaitingEvidence` for live connector access, customer readiness, deployment readiness, or Nested Mind activation.
