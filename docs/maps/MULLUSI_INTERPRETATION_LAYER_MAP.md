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
  raw_message_hash
  missing_fields
  reason
  max_questions
  safe_default
  question
  created_at
}
```

## 4b. CapabilityPlanPreview contract

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
  execution_allowed
  safe_default
  created_at
}
```

Preview rule:

```text
The preview exposes plan topology, risk, approval, and evidence obligations.
It does not grant execution authority.
It does not store raw goal text or raw step params.
```

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
