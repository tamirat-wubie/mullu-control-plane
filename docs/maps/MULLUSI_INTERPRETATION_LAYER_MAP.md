# Mullusi Interpretation Layer Map

Status: Foundation Mode
Scope: private interpretation map. This document records boundaries for turning user text into governed request objects; it does not claim implementation completeness or production readiness.

## 1. Interpretation purpose

The interpretation layer records what the system believes the user requested before planning, search, approval, or execution.

```text
GatewayMessage
-> deterministic resolver
-> LLM-assisted interpretation when useful
-> slot extraction
-> confidence check
-> clarification, denial, answer path, or plan path
-> InterpretationReceipt
```

## 2. Resolver order

```text
1. explicit command parser
2. deterministic capability patterns
3. LLM-assisted interpretation as a proposal
4. confidence and policy validation
5. clarification when unclear
```

The deterministic resolver keeps higher authority than LLM-assisted interpretation. LLM output is never direct execution authority.

## 3. InterpretedRequest contract

```text
InterpretedRequest {
  request_id
  tenant_id
  actor_id
  channel
  conversation_id
  raw_message_hash
  intent_class
  capability_id
  extracted_slots
  missing_slots
  constraints
  search_needed
  action_needed
  risk_estimate
  approval_required
  confidence
  interpreter_kind
  rejected_interpretations
  created_at
}
```

## 4. InterpretationReceipt contract

```text
InterpretationReceipt {
  receipt_id
  request_id
  raw_message_hash
  interpreted_intent
  extracted_slots
  missing_slots
  confidence
  model_or_rule_used
  rejected_interpretations
  risk_precheck
  created_at
}
```

## 4a. ClarificationRequest contract

```text
ClarificationRequest {
  clarification_id
  request_id
  tenant_id
  actor_id
  channel
  conversation_id
  raw_message_hash
  missing_fields
  reason
  max_questions = 1
  safe_default
  question
  created_at
}
```

## 4b. LLMInterpretationProposal contract

```text
LLMInterpretationProposal {
  proposal_id
  request_id
  raw_message_hash
  proposal_source
  proposed_intent_class
  proposed_capability_id
  proposed_slot_names
  proposed_slots_hash
  proposal_confidence
  deterministic_intent_class
  deterministic_capability_id
  deterministic_confidence
  validation_status
  authority_level = proposal_only
  deterministic_override_allowed = false
  action_authority_granted = false
  execution_allowed = false
  rejected_reasons
  created_at
}
```

Proposal rule:

```text
LLM-assisted interpretation may produce a lower-authority proposal record only.
It cannot override deterministic interpretation, grant action authority, grant
execution authority, or retain raw message or slot text. Proposed slots are
represented by names plus a hash.
```

Public schema:

```text
schemas/llm_interpretation_proposal.schema.json
```

## 4c. CapabilityPlanPreview contract

```text
CapabilityPlanPreview {
  preview_id
  plan_id
  tenant_id
  identity_id
  goal_hash
  step_count
  steps
  risk_tier
  approval_required
  evidence_required
  budget
  tools
  execution_allowed
  safe_default
  created_at
}
```

Preview rule:

```text
The preview exposes plan topology, risk, approval, evidence obligations, budget display state, and tool requirements.
It does not grant execution authority.
It does not store raw goal text or raw step params.
Budget values that require the runtime budget gate remain explicit as not calculated.
```

Goal Intake binding:

```text
/operator/goal-intake
-> form submission
-> /operator/goal-intake/preview
-> CapabilityPlanBuilder
-> CapabilityPlanPreview
-> redacted HTML review
-> /operator/goal-intake/approve or /operator/goal-intake/deny
-> approved preview uses internal operator_goal_intake channel
-> governed router handoff
-> /operator/current-task/read-model projects preview id, goal hash, plan id,
   step id, and approval request id
-> /operator/current-task/approval resolves request-bound approval and resumes
   waiting plans when terminal command evidence exists
```

The preview binding blocks non-compilable goals and does not create commands,
write plan witnesses, echo raw goal text, or grant execution authority. Approval
and denial forms carry only `preview_id`; raw goal text stays server-side until
an explicit approved handoff sends it into the governed router. The handoff UI
renders allowlisted ids and statuses only. Current Task recovery forms carry
only `request_id` and a decision value; tenant, channel, command, and plan
context are loaded from governed ledger state.

Receipt rule:

```text
The receipt records interpretation evidence.
It does not record secrets.
It does not store raw private content when a hash or redacted summary is enough.
```

## 5. Intent classes

| Intent Class | Action Needed | Search Needed | Required Path |
| --- | --- | --- | --- |
| question | no | maybe | answer path with evidence when needed |
| action_request | yes | maybe | plan path with risk, policy, budget, and approval gates |
| explicit_command | yes | maybe | command parser, policy, budget, approval as needed |
| approval_response | maybe | no | approval router with request ID binding |
| correction | maybe | no | re-interpret or re-plan |
| follow_up | maybe | maybe | conversation context check |
| support_issue | maybe | maybe | clarify, triage, or deny depending on authority |
| document_instruction | maybe | maybe | document safety and prompt-injection boundary |
| connector_request | maybe | maybe | connector authority and credential boundary |
| unclear_message | no | no | clarification request with safe default `no_execution` |
| blocked_request | no | no | structured denial |

## 6. Clarification rule

```text
ClarificationNeeded {
  missing_fields
  reason
  max_questions
  safe_default
}
```

Rules:

```text
Ask the fewest required questions.
For the public Foundation Mode contract, ask exactly one focused question.
Never ask for details not needed for the next safe step.
Use read-only diagnosis as the default only when tenant, policy, and budget allow it.
Do not infer missing authority from conversational phrasing.
```

## 7. Required blockers

| Condition | Required Output |
| --- | --- |
| confidence below threshold | clarification request |
| missing tenant | denial or identity-binding blocker |
| action and question mixed | split into answer path and plan path |
| unsafe bypass request | denial receipt |
| requested connector unavailable | blocker with safe explanation |
| hidden authority request | denial or stronger authentication requirement |
