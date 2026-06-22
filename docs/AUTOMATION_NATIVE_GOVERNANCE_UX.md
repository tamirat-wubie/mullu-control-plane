# Automation-Native Governance UX

Status: Foundation guidance  
Scope: user-facing governance compression and request-to-task automation  
Non-goal: this document does not grant runtime authority, connector access, memory write permission, deployment mutation, or customer-readiness clearance.

## Purpose

Governance should protect users without becoming a headache for users, workers, or maintainers. The end goal of the agent is automation from requests: the user states what they want, the system atomizes the work, applies the right safety boundary, and moves forward without exposing unnecessary internal ceremony.

This policy defines how governance should feel from the user's side.

## Core UX rule

Governance should be invisible until risk requires visibility.

The user should not have to understand receipts, schemas, validators, route gates, readiness ledgers, or proof objects in order to get useful work done. Those artifacts are internal machinery. The user-facing layer should compress them into simple states.

## User-facing states

The agent should surface only a small set of clear states:

1. **Doing it** — the task is safe and can proceed automatically.
2. **Drafted for review** — the task is prepared but has no external effect yet.
3. **Needs your approval** — the next step affects the outside world or durable state.
4. **Blocked** — required evidence, authority, or configuration is missing.
5. **Cannot do safely** — the request conflicts with safety, policy, or system boundaries.

Everything else should remain behind the operator/debug layer unless the user asks for details.

## Request-to-task atomization

The agent should turn a user request into small task atoms automatically.

A task atom has:

- intent,
- input evidence,
- risk level,
- allowed action,
- blocked action,
- next safe step,
- receipt/proof reference when needed.

The user should not need to create these atoms manually. Self-atomization is an internal planning and governance function.

## Automation ladder

### Level A — automatic read/draft work

Use for understanding, summarizing, extracting facts, planning, creating drafts, building previews, and creating no-effect read models.

User experience: the agent proceeds and reports the useful result.

### Level B — automatic internal checks

Use for policy checks, shape checks, evidence matching, duplicate detection, and risk classification.

User experience: no interruption unless a check changes the outcome.

### Level C — approval interruption

Use when the next step changes the outside world, writes durable state, or creates a claim that could affect a user, customer, account, repository, deployment, or business process.

User experience: one clear approval prompt with what will happen, what will not happen, and what evidence supports it.

### Level D — blocked path

Use when the request lacks evidence, authority, configuration, or safe recovery.

User experience: explain the missing piece and propose the smallest safe next step.

## Approval prompt rule

When approval is needed, the prompt should be short and concrete:

- action proposed,
- target,
- expected result,
- risk summary,
- what remains blocked,
- approve / revise / cancel options.

Do not show raw internal governance unless requested.

## Operator/debug expansion

The system may expose full governance details through operator views:

- receipts,
- proofs,
- schemas,
- failed checks,
- route boundaries,
- risk classifications,
- rollback evidence.

These are not the default user experience. They are diagnostics.

## Anti-patterns

Avoid these patterns:

1. Asking users to manage governance artifacts directly.
2. Adding new control layers that do not reduce real risk.
3. Blocking safe read-only or draft-only work because a live-effect gate is missing.
4. Creating parallel route surfaces for the same product slice.
5. Turning every demo step into a production-readiness ritual.
6. Showing internal policy names when plain language is enough.

## Product behavior target

The desired product behavior is:

> Tell the agent what you want. It breaks the request into safe task atoms, completes what is safe, asks for approval only when real-world effect begins, and leaves an auditable trail behind the scenes.

## First usable demo application

For the invoice/email walkthrough:

- reading a fixture or preview is automatic,
- extracting invoice facts is automatic,
- drafting a reply is automatic,
- showing the approval packet is automatic,
- sending, provider draft creation, durable write, or customer-readiness claim requires explicit approval and stronger evidence.

The user should mostly see: **draft ready, approve to send later**, not the full governance machinery.

## Relationship to proportional governance

This policy applies the Proportional Governance Policy at the UX layer:

- Light governance should feel automatic.
- Medium governance should feel reviewable.
- Strict governance should feel approval-based.
- Blocked governance should explain the missing evidence.

Governance remains present, but it becomes an enabling layer instead of a user burden.
