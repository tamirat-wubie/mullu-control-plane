# General Agent Capability Roadmap

Purpose: separate teachable skills from build-required capabilities for Mullu general-agent promotion.
Governance scope: capability registry expansion, skill admission, worker boundaries, approval gates, execution receipts, and production witness closure.
Dependencies: `docs/19_skill_system.md`, `docs/39_governed_capability_fabric.md`, `KNOWN_LIMITATIONS_v0.1.md`, `SECURITY_MODEL_v0.1.md`, and `DEPLOYMENT_STATUS.md`.
Invariants:
- Skills may encode prompts, runbooks, examples, policies, and domain knowledge, but may not create execution authority.
- Build-required capabilities must enter through the governed capability registry before use.
- Effect-bearing execution must produce command-bound receipts and verification evidence.
- External writes, login, submission, payment, scheduling, message send, and credentialed connector actions require explicit risk classification and approval policy.
- Public production claims require deployment witness evidence, not repository text alone.

## Architecture

Mullu should not add loose tools. Mullu should admit governed capability families, then let skills compose those families under policy.

```text
User intent
  -> governed message flow
  -> skill selection
  -> capability registry lookup
  -> policy, budget, approval, and isolation gate
  -> bounded worker execution
  -> effect receipt
  -> verification
  -> audit, proof, memory admission, and closure
```

The core gap is not symbolic intelligence. The core gap is real-world capability execution under safe boundaries.

## Two Classes

| Class | Admitted artifact | Can execute effects | Required governance |
| --- | --- | --- | --- |
| Teachable skills | Prompts, runbooks, examples, policies, domain knowledge | No | Skill descriptor, provenance, verification rule, promotion rule |
| Build-required capabilities | Adapters, sandboxes, workers, connectors, tests, receipts, UI | Yes | Capability registry entry, isolation profile, authority policy, receipt schema, effect assurance |

## Teachable Skills

Teachable skills are procedural and semantic assets. They improve selection, planning, interpretation, and review, but they do not grant new powers.

Examples:

```text
business process templates
customer-support workflows
invoice handling rules
report-writing patterns
policy interpretation rules
software-development runbooks
security-review checklists
deployment checklists
sales and CRM operating procedures
finance approval rules
healthcare, education, and manufacturing domain runbooks
Mullusi-specific company knowledge
```

Required skill shape:

```yaml
skill_id: support.ticket_triage.v1
goal: classify and route customer support tickets
inputs:
  - ticket_text
  - customer_tier
  - product_area
steps:
  - detect_urgency
  - detect_category
  - search_knowledge_base
  - draft_answer
  - request_approval_if_refund_security_or_legal
outputs:
  - category
  - priority
  - draft_response
  - evidence_refs
risk:
  low:
    - classify
    - summarize
  medium:
    - draft_response
  high:
    - send_external_response
approval_required:
  - refund
  - legal
  - account_security
  - payment
verification:
  - response_grounded_in_sources
  - no_pii_leak
  - policy_match
```

Admission rule: a teachable skill may be promoted only after a verified runbook closure records inputs, outputs, evidence references, policy checks, and failure modes.

## Build-Required Capabilities

These cannot be solved by prompting. They require executable adapters, bounded workers, connector credentials, test contracts, and receipts.

```text
real sandboxed computer control
real browser automation
PDF, Office, and structured-document parsing and generation
speech-to-text and text-to-speech
safe shell sandboxing
network egress control
OAuth and service-account connectors
external audit signing
operator web UI
live multi-agent runtime
production deployment witness
credentialed directory sync scheduling
organization-management UI
```

Build rule:

```text
capability request
  -> registry entry
  -> policy gate
  -> approval when risk requires it
  -> isolated worker
  -> no ambient host authority
  -> least-privilege network and secret scope
  -> changed-resource receipt
  -> effect verification
  -> rollback or compensation path
```

## Priority Capability Families

| Priority | Capability family | Type | Required closure |
| ---: | --- | --- | --- |
| 1 | Sandboxed computer control | Build | Isolated worker, no-network default, workspace diff, rollback receipt |
| 2 | Browser automation | Build | URL before/after, screenshot before/after, clicked element, domain list, forbidden-effect check |
| 3 | PDF, Office, and structured documents | Build | Parser-first extraction, generated artifact verification, version comparison receipt |
| 4 | Automatic governed memory | Build + teach | Admission policy, redaction path, forget path, closure-grounded summary |
| 5 | Email and calendar | Build | Draft/send split, approval for external send and calendar invite, connector receipt |
| 6 | Data and SaaS connectors | Build | OAuth scope allowlist, tenant binding, rate limit, revocation path |
| 7 | Live multi-agent runtime | Build | Role, lease, budget, timeout, output contract, review rule |
| 8 | Voice | Build | Transcript-first intent extraction, risk classification, confirmation for high-risk actions |
| 9 | Workflow automation | Build | State machine, checkpoint, retry policy, idempotency key, approval wait state |
| 10 | Runtime evaluations | Build | Grounding, tool selection, cost, risk, extraction, memory write, and regression checks |
| 11 | Domain runbooks | Teach | Provenance, examples, evidence rules, promotion record |
| 12 | Customer-specific policies | Teach | Tenant binding, policy owner, override path, audit trail |
| 13 | Cost-routing symbolic intelligence | Build + teach | Provider capability profile, budget policy, deterministic tie-break |
| 14 | Operator web UI | Build | Authenticated read models, approval views, audit/proof views |
| 15 | Public deployment witness | Deploy | Published health, runtime witness, conformance certificate, signed deployment claim |

## Capability Contracts

### Sandboxed Computer Control

Registry surface:

```text
computer.sandbox.run
computer.file.read
computer.file.write.workspace
computer.code.patch
computer.test.run
computer.package.install.limited
computer.process.observe
computer.network.request.allowlisted
computer.rollback.workspace
```

Execution boundary:

```text
agent request
  -> policy gate
  -> approval if high risk
  -> isolated worker
  -> container or microVM
  -> no host root access
  -> network deny by default
  -> changed-file diff
  -> command receipt
  -> effect verification
```

### Browser Automation

Registry surface:

```text
browser.open
browser.search
browser.click
browser.type
browser.extract_text
browser.extract_table
browser.screenshot
browser.download
browser.submit.with_approval
```

Risk model:

| Action class | Risk |
| --- | --- |
| Read-only browsing | Low or medium |
| Login | High |
| Form submission | High |
| Purchase, payment, or message send | Critical |

Receipt requirements:

```text
url_before
url_after
screenshot_before
screenshot_after
clicked_element
network_domain_list
forbidden_effect_check
receipt_hash
```

### Documents

Registry surface:

```text
document.pdf.extract_text
document.pdf.extract_tables
document.pdf.summarize
document.pdf.generate
document.docx.read
document.docx.generate
document.xlsx.read
document.xlsx.analyze
document.xlsx.generate
document.pptx.generate
document.form.fill
document.compare_versions
```

Execution rule:

```text
parser first
symbolic reasoning second
verification third
```

No document fact may be guessed when a parser can extract it.

### Voice

Registry surface:

```text
voice.speech_to_text
voice.text_to_speech
voice.intent_confirm
voice.meeting_transcribe
voice.meeting_summarize
voice.action_items_extract
```

Governance rule:

```text
voice input
  -> transcript
  -> intent extraction
  -> risk classification
  -> user confirmation for high-risk action
  -> normal governed pipeline
```

Voice does not directly execute tools.

### Automatic Governed Memory

Registry surface:

```text
memory.auto_restore
memory.session_summary
memory.user_preference
memory.project_state
memory.episodic_closure
memory.semantic_admission
memory.procedural_runbook_admission
memory.forget
memory.redact
memory.memory_audit
```

Memory model:

| Memory class | Admission source |
| --- | --- |
| Working memory | Current task state |
| Episodic memory | Completed verified events |
| Semantic memory | Admitted general knowledge |
| Procedural memory | Admitted runbooks |
| Preference memory | User-approved stable preferences |

Rule: store only admitted facts, and generalize only after verified closure.

### Live Multi-Agent Runtime

Registry surface:

```text
agent.spawn
agent.delegate
agent.negotiate
agent.handoff
agent.vote
agent.review
agent.merge_results
agent.kill
agent.timeout
agent.lease
```

Initial worker set:

```text
planner_agent
research_agent
browser_agent
document_agent
code_agent
finance_agent
review_agent
```

Each worker requires role, allowed capabilities, budget, timeout, lease, output contract, review rule, and failure mode.

### Data Connectors

Registry surface:

```text
connector.google_drive
connector.google_docs
connector.google_sheets
connector.google_calendar
connector.gmail
connector.github
connector.postgres
connector.mysql
connector.supabase
connector.stripe
connector.slack
connector.notion
connector.airtable
connector.hubspot
connector.salesforce
connector.shopify
connector.zapier_or_n8n
```

Each connector requires OAuth or service-account boundary, scope allowlist, tenant binding, read/write classification, rate limit, audit receipt, and revocation path.

### Email And Calendar

Registry surface:

```text
email.read
email.search
email.draft
email.send.with_approval
email.classify
email.reply_suggest
calendar.read
calendar.schedule
calendar.reschedule
calendar.invite
calendar.conflict_check
```

Risk model:

| Action class | Risk |
| --- | --- |
| Draft | Medium |
| Send | High |
| External send | Approval required |
| Calendar invite | Approval required |

### Workflow Automation

Registry surface:

```text
workflow.create
workflow.run
workflow.pause
workflow.resume
workflow.retry
workflow.cancel
workflow.schedule
workflow.await_approval
workflow.await_external_event
workflow.recover
```

Durable execution requires state machine, checkpoint, retry policy, idempotency key, failure receipt, and human approval gate.

### Runtime Evaluations

Registry surface:

```text
eval.answer_grounding
eval.tool_selection
eval.cost_estimate
eval.risk_classification
eval.document_extraction
eval.browser_task_success
eval.memory_write_correctness
eval.regression_suite
eval.customer_workflow_replay
```

Every new skill and capability family should ship with unit tests, integration tests, red-team tests, cost tests, latency tests, governance tests, and receipt tests.

## Recommended Build Order

1. Capability registry hardening
2. Sandboxed execution worker
3. Document worker
4. Browser worker
5. Email and calendar connector
6. Google Drive, GitHub, and Postgres connectors
7. Automatic governed memory
8. Workflow engine
9. Live multi-agent runtime
10. Voice worker
11. Operator web UI
12. Deployment witness publication

## Implementation Status

This roadmap is now represented in the default governed capability fabric, but
fabric admission is not the same as public production readiness. Current closure
state:

| Build item | Repository state | Remaining production gate |
| --- | --- | --- |
| Capability registry | Default capsules and governed records install through the capability fabric | Keep all new powers registry-first |
| Sandboxed execution | Gateway sandbox runner validates workspace boundaries and no-network defaults | Publish live sandbox evidence |
| Document worker | Parser-first worker and production parser dependency probes exist | Publish live parser receipt evidence |
| Browser worker | Restricted browser worker contract and receipt checks exist | Publish live browser worker evidence |
| Email/calendar | Signed worker contract and communication capsule exist | Publish credentialed connector receipts |
| Data connectors | Drive, GitHub, and Postgres connector records exist | Publish live connector receipts and revocation proof |
| Automatic governed memory | Closure-grounded episodic admission exists | Add automatic restore/admission scheduling where policy permits |
| Workflow engine | Resume checkpoint validation and recovery receipts exist | Publish durable workflow replay evidence |
| Live multi-agent runtime | Bounded specialist leases exist in the gateway | Build networked or multi-process worker runtime if required |
| Voice worker | Transcript-first STT, TTS, confirmation, meeting summary, and action item actions exist | Publish live STT/TTS evidence |
| Operator web UI | Minimal browser capability console and JSON read model exist | Build full approval, audit, proof, and organization UI |
| Deployment witness publication | `deployment` capability capsule governs witness collection and publish-with-approval | Publish signed deployment witness and HTTPS public health endpoint |

## Minimal Operating Model

```text
Mullu Control Plane
  -> Governance
  -> Capability Registry
  -> Skill Registry
  -> Policy Engine
  -> Budget Engine
  -> Approval Engine
  -> Memory Admission Engine
  -> Effect Assurance Engine
  -> Audit and Proof Engine

Capability Workers
  -> computer-worker
  -> browser-worker
  -> document-worker
  -> email-worker
  -> data-worker
  -> voice-worker
  -> payment-worker
  -> mcp-worker
```

## Promotion Gate

Mullu may claim general-agent readiness only when all required build families have:

1. A typed capability registry entry.
2. A worker or connector implementation with bounded authority.
3. A policy and approval contract.
4. A receipt schema.
5. Tests for success, boundary conditions, violations, rollback, and receipt integrity.
6. Operator-visible audit and proof surfaces.
7. Deployment witness evidence when the capability depends on public runtime infrastructure.

STATUS:
  Completeness: 100%
  Invariants verified: [skill/capability separation, registry-first execution, receipt-bound effects, approval-gated high risk, deployment-witness production claim]
  Open issues: none
  Next action: implement the priority capability families in the recommended build order
