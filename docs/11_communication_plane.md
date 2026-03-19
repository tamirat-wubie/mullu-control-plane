# Communication Plane (MCCI)

Scope: all Mullu Platform modules that send or receive structured messages.

The Communication Plane manages structured message exchange: approvals, escalations, notifications, and explanations. It does not handle free-form email or arbitrary messaging. Every outbound message passes through this plane. No module may send a message to a user, agent, or external party directly.

## Purpose

Provide reliable, policy-governed, auditable message delivery across declared channels. Ensure every message has attribution, a correlation chain, and a delivery result.

## Owned artifacts

- **Communication messages**: structured message payloads with sender, recipient, channel, and correlation metadata. Schema: `communication_message.schema.json`.
- **Delivery results**: per-message delivery outcome with status and timing. Schema: `delivery_result.schema.json`.
- **Approval requests**: messages on the `approval` channel that block a workflow until a response is received.
- **Escalation records**: messages on the `escalation` channel that elevate a decision to a higher authority.

## Channel types

| Channel | Purpose | Blocking |
|---|---|---|
| `approval` | Request explicit approval from a human or governance authority. | Yes. Workflow blocks until response. |
| `escalation` | Elevate a decision or failure to a higher authority. | No. Delivery is fire-and-confirm. |
| `notification` | Inform a recipient of an event. No response expected. | No. |
| `explanation` | Provide a structured explanation of a decision or outcome. | No. |

Rules:
- Every channel MUST be declared in the platform configuration before use.
- A message MUST specify exactly one channel.
- New channel types require a platform configuration change and policy review.

## Message structure

Every communication message MUST contain these fields:

`message_id`, `sender_id`, `recipient_id`, `channel`, `message_type`, `payload`, `correlation_id`, `created_at`

Rules:
- `message_id` MUST be unique per message instance.
- `sender_id` MUST identify the originating plane, agent, or system component. MUST NOT be fabricated.
- `recipient_id` MUST resolve to a known recipient in the platform's identity lattice.
- `channel` MUST be one of the declared channel types.
- `correlation_id` MUST link the message to its causal trace or workflow.
- `payload` is channel-specific. Its structure is validated per channel type.

## Delivery verification

Every message send MUST produce exactly one `DeliveryResult`.

| Status | Meaning |
|---|---|
| `delivered` | Message accepted by the recipient's channel endpoint. |
| `failed` | Delivery attempted and rejected or errored. |
| `pending` | Message accepted for delivery but not yet confirmed. |

Rules:
- A `pending` status MUST resolve to `delivered` or `failed` within a declared timeout.
- Delivery results MUST be linked to the originating message by `message_id`.
- A missing delivery result is a platform defect.

## Policy hooks

- **Outbound policy review**: messages on channels where policy applies MUST pass a `PolicyDecision` check before delivery. The governance plane defines which channels require review.
- **Message attribution enforcement**: the plane verifies that `sender_id` matches the authenticated identity of the sending component. Fabricated attribution is rejected.
- **Rate limiting**: per-sender and per-channel rate limits MAY be enforced to prevent message flooding.

## Failure modes

| Mode | Meaning | Recoverability |
|---|---|---|
| `delivery_failure` | Channel endpoint rejected the message or returned an error. | Retryable depending on error. |
| `channel_unavailable` | Declared channel is temporarily unreachable. | Retryable after backoff. |
| `recipient_unknown` | `recipient_id` does not resolve in the identity lattice. | Not retryable. Requires correction. |
| `policy_blocked` | Governance policy rejected the message. | Not retryable without policy change or escalation. |

Every failure MUST be recorded in the delivery result and linked to the originating trace.

## Prohibitions

- MUST NOT route messages to undeclared channels.
- MUST NOT send messages without policy review when policy applies to the channel.
- MUST NOT fabricate message attribution. `sender_id` MUST reflect the true originator.
- MUST NOT silently drop messages. Every send attempt produces a delivery result.
- MUST NOT deliver messages to recipients outside the identity lattice without explicit external integration through the External Integration Plane.

## Dependencies

- Governance Plane: outbound message policy, channel declarations, rate limits.
- Coordination Plane: multi-agent message routing.
- External Integration Plane: delivery to external recipients (when supported).
- Identity Lattice: recipient resolution.
