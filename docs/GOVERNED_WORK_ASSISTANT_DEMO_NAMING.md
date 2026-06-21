# Governed Work Assistant Demo Naming Bridge

Date: 2026-06-21
Scope: naming and product interpretation only. This document does not grant runtime, connector, worker, repository-write, receipt-append, deployment, customer, or production authority.

## Decision

Use **Governed Work Assistant Demo v0** as the operator-facing name for the current demo lane.

Keep existing internal identifiers such as `governed_team_assistant_pilot_v0` until a separate compatibility-safe rename is prepared.

## Why this bridge exists

The current demo behaves mostly like a governed personal/work assistant. It helps one operator inspect readiness, preview drafts, preview approvals, inspect receipts, and understand blocked actions.

Calling it a full team assistant too early can confuse the product story because true team coordination requires visible multi-person handoff, reviewer/approver roles, shared ownership, and team-level state.

## Product ladder

1. Governed Personal Assistant
2. Governed Work Assistant
3. Governed Team Assistant
4. Governed Organization Assistant
5. Governed Work OS

The current merged demo sits between level 1 and level 2.

## Naming rule

Use this wording in operator-facing summaries:

- Current product lane: **Governed Work Assistant Demo v0**
- Legacy/internal pilot id: `governed_team_assistant_pilot_v0`
- Future team-capable lane: **Governed Team Assistant**

## What the current demo may claim

The current demo may claim:

- read-only assistant readiness preview
- skill catalog visibility
- blocked-action explanation
- draft preview
- approval preview
- dry-run receipt trail
- closure evidence view
- fixture-backed deterministic replay

## What the current demo must not claim

The current demo must not claim:

- live connector execution
- live mailbox read or mutation
- external sends
- repository writes
- worker dispatch
- live receipt append
- production readiness
- customer readiness
- autonomous execution authority

## Compatibility plan

Do not rename route paths, schema keys, or fixture identifiers in one broad edit. A future rename should be split into small steps:

1. Add operator-facing alias fields.
2. Update schemas to accept the alias without breaking existing IDs.
3. Update fixtures.
4. Update tests.
5. Only then consider renaming internal identifiers if necessary.

## Next implementation step

Add a read-only operator dashboard projection that displays this name and the current no-effect boundaries clearly.
