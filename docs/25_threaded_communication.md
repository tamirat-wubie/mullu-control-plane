# Threaded Communication Layer

Scope: all Mullu Platform modules that manage multi-turn conversations, clarification requests, follow-ups, and status reporting.

The Threaded Communication Layer maintains structured, multi-turn conversations between agents, operators, and system components. Every message belongs to a thread. Every thread has a lifecycle. No message may exist without thread context.

## Purpose

Maintain multi-turn conversations, track threads across their lifecycle, support clarification requests and follow-up scheduling, and provide structured status reporting. This layer is the conversation model only — it does not handle email delivery, network transport, or external messaging.

## Owned artifacts

- **ConversationThread**: a tracked conversation with subject, status, message history, and optional linkage to goals and workflows.
- **ThreadMessage**: a single message within a thread, carrying direction, type, sender, recipient, and content.
- **ClarificationRequest**: a structured question sent within a thread that blocks progress until answered.
- **ClarificationResponse**: the answer to a clarification request.
- **FollowUpRecord**: a scheduled follow-up action linked to a thread and the temporal engine.
- **StatusReport**: a point-in-time progress report for a thread or linked goal.

## Thread lifecycle

| Status | Meaning |
|---|---|
| `open` | Thread created, no messages yet. |
| `active` | At least one message has been added. Conversation is ongoing. |
| `waiting` | A clarification has been requested. Thread blocks until response. |
| `resolved` | Conversation objective met. No further messages expected. |
| `closed` | Thread finalized. No mutation permitted. |

State transitions:

```
open -> active        (first message added)
active -> waiting     (clarification requested)
waiting -> active     (clarification response received)
active -> resolved    (objective met)
waiting -> resolved   (resolved while waiting)
open -> resolved      (resolved before any messages)
resolved -> closed    (thread finalized)
```

Rules:
- A thread MUST start in `open` status.
- Transition to `active` happens automatically on the first message.
- Transition to `waiting` happens when a clarification request is issued.
- Transition back to `active` happens when a clarification response is received.
- Any non-closed status MAY transition to `resolved`.
- Only `resolved` threads MAY transition to `closed`.
- A `closed` thread MUST NOT accept new messages or state changes.

## Message types

| Type | Direction | Description |
|---|---|---|
| `request` | outbound | Initial request or action prompt sent to a recipient. |
| `response` | inbound | Reply to a request or prior message. |
| `clarification_request` | outbound | Question seeking additional information before proceeding. |
| `clarification_response` | inbound | Answer to a clarification request. |
| `status_update` | outbound | Progress or status information within a thread. |
| `follow_up` | outbound | Scheduled follow-up message triggered by the temporal engine. |

Rules:
- Every message MUST specify a `direction` (outbound or inbound).
- Every message MUST specify a `message_type` from the declared set.
- `sender_id` and `recipient_id` MUST be explicit. Attribution MUST NOT be fabricated.

## Follow-up rules

Follow-ups are linked to the temporal engine and scheduled for future execution.

- Every `FollowUpRecord` MUST specify a `scheduled_at` timestamp.
- Follow-ups MAY have a configurable timeout after which they are considered overdue.
- A follow-up is tracked as unresolved until explicitly marked resolved or its thread closes.
- Follow-up scheduling does not block the thread — the thread remains in its current status.

## Prohibitions

- No message without thread context: every `ThreadMessage` MUST reference a valid `thread_id`.
- No fabricated inbound messages: inbound messages MUST originate from an identified external source. The system MUST NOT synthesize inbound messages.
- No thread mutation after close: once a thread reaches `closed` status, no fields, messages, or linked records may be added or modified.
- No orphaned clarification requests: every `ClarificationRequest` MUST belong to an active or waiting thread.
- No status reports on closed threads: `StatusReport` generation MUST be rejected for closed threads.
