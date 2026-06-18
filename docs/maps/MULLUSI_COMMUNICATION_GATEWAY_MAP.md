# Mullusi Communication Gateway Map

Status: Foundation Mode
Scope: private gateway map for channel intake, identity, tenant binding, deduplication, response routing, and communication receipts. This document is not a production channel readiness claim.

## 1. Gateway purpose

The communication gateway converts channel-specific messages into governed requests.

```text
Channel event
-> validation
-> message receipt
-> deduplication
-> identity binding
-> tenant binding
-> GatewayMessage
-> interpretation
```

Tenant identity must not be inferred from free-form message text.

## 2. Component map

| Component | Purpose | Inputs | Outputs | Current Status | Next Step |
| --- | --- | --- | --- | --- | --- |
| Channel Adapter | validate and parse channel events | webhook, web session, API request | normalized channel event | implemented / partial | Harden one channel at a time. |
| Message Normalizer | produce canonical message fields | channel event | `GatewayMessage` | implemented / partial | Add product-facing receipt field map. |
| Message Receipt Writer | record inbound message trace | raw message hash, channel IDs | MessageReceipt | partial | Ensure each channel writes the same core receipt fields. |
| Deduplicator | block duplicate webhook or replay | channel message ID, idempotency key | duplicate or accepted decision | implemented / partial | Add cross-channel replay cases. |
| Identity Resolver | bind sender to actor | session, webhook identity, API key | actor identity | implemented / partial | Use `channel_approval_strength_policy.foundation` when resolving external-channel approvals. |
| Tenant Resolver | bind actor to tenant | actor identity, workspace mapping | tenant identity | implemented / partial | Deny missing or ambiguous tenant mapping. |
| Conversation Context Store | bind thread and follow-up context | conversation ID, request ID | context snapshot | partial / unknown | Map expiration and scope rules. |
| Response Composer | format safe channel response | final receipt or blocker | channel-specific response | implemented / partial | Keep external channel formatting bounded by approval and receipt state. |
| Communication Receipt Writer | record outbound delivery | response payload hash, delivery result | FinalUserReceipt or delivery error | implemented / partial | Extend delivery observation events to each hardened external adapter. |

## 3. Channel trust requirements

| Channel | Required Identity Fields | Approval Ceiling | Required Hardening |
| --- | --- | --- | --- |
| Web dashboard | session user, tenant, role | operator-bound local default | strong auth, CSRF/session checks, audit trail |
| Slack | workspace ID, user ID, channel/thread ID | request-bound until operator-bound bridge exists | request ID binding, role mapping, event signature |
| Telegram | bot sender ID, chat ID | low to medium | stable sender ID, deduplication, approval expiration |
| WhatsApp | phone identity, provider message ID | request-bound only, high-risk blocked without operator-bound bridge | webhook signature, explicit request IDs, risk ceiling |
| Discord | guild ID, user ID, channel/thread ID | low unless role-bound | guild and role checks, shared-server ambiguity handling |
| Email | verified sender and thread ID | low by default | spoofing controls and signed approval links |
| API | scoped key or token identity | policy-defined | signed requests, rate limit, audit log |

## 4. Required gateway states

```text
RECEIVED
AUTHENTICATED
TENANT_BOUND
NORMALIZED
DEDUPLICATED
ROUTED
DELIVERY_RECORDED
```

Failure states:

```text
CHANNEL_VALIDATION_FAILED
AUTHENTICATION_FAILED
TENANT_MAPPING_MISSING
DUPLICATE_MESSAGE_IGNORED
DELIVERY_FAILED
```

## 5. Edge-case controls

| Edge Case | Required Behavior |
| --- | --- |
| Same webhook arrives twice | return prior trace or ignore duplicate with dedup receipt. |
| Display name changes | ignore display name for identity binding. |
| User approves from another channel | require cross-channel binding and request ID. |
| Approval arrives after expiration | deny and write expired approval receipt. |
| Channel delivery fails after execution | preserve execution receipt and record delivery failure separately. |
| Shared Slack or Discord room | require actor and tenant binding before action. |
