# Proportional Governance Policy

Status: Foundation guidance  
Scope: governance weight selection for Mullu Control Plane changes  
Owner: maintainers / operators  
Non-goal: this document is not a new runtime gate, validator, route, or product-readiness claim.

## Purpose

The control plane needs strong safety boundaries without turning every no-effect change into heavy ceremony. This policy defines how much governance is appropriate for a change based on the real-world effect it can cause.

The goal is balance:

- protect real external effects strongly,
- keep read-only product progress fast,
- avoid duplicate control layers,
- avoid PR loops that add governance about governance,
- make the first usable demo easier to complete.

## Core rule

Governance weight must match effect risk.

A change that cannot mutate state, invoke an external provider, write durable memory, dispatch work, mutate deployment, or claim customer readiness should not require the same evidence burden as a live external-effect path.

## Control levels

### Level 0 — text-only explanation

Use for naming notes, concept docs, README clarification, operator explanation, or non-normative architecture sketches.

Expected control: normal review only. Do not add a schema, CI gate, or receipt artifact unless the document changes a normative contract.

### Level 1 — static fixture or read model

Use for JSON fixtures, no-effect read models, static HTML renderers, example packets, and demo packets.

Expected control: focused shape validation when needed, unit tests for false authority fields, and private-payload scanning if user data could appear. Do not add live-effect receipts, route admission, or adapter readiness for this level.

### Level 2 — mounted read-only API route

Use for GET routes, operator console panels, and OpenAPI-visible no-effect surfaces.

Expected control: route test, mutation-method rejection test, OpenAPI check when the public route surface changes, and authority false-field assertions. This is enough for most first-demo console surfaces.

### Level 3 — dry-run adapter or approval preview

Use for draft-only proposals, approval review packets, simulated connector results, and dry-run receipt previews.

Expected control: approval matrix, redacted evidence references, dry-run receipt shape, rollback statement, and proof that approval is not execution. Do not claim live readiness at this level.

### Level 4 — live external-effect path

Use for changes that can affect external systems, durable records, provider state, worker execution, or deployment state.

Expected control: explicit operator approval, authority receipt, admission validation, effect receipt, rollback/recovery evidence, audit append, failure-mode tests, and incident handling plan.

### Level 5 — customer/pilot/business readiness

Use for public launch, paid pilot, customer data handling, support promise, or business-readiness claim.

Expected control: legal/business boundary review, privacy and data-handling review, support ownership, operational runbook, incident response, and explicit claim evidence. No repository artifact alone can satisfy this level.

## Stop rules

Do not add a new control layer when any of these are true:

1. The change is Level 0 or Level 1 and already has a focused test.
2. The proposed control only restates an existing no-effect boundary.
3. The proposed validator has no new failure mode.
4. The proposed receipt would only prove that another receipt exists.
5. The new PR duplicates a route, read model, or fixture already being handled by another branch.
6. The change makes the demo harder to understand without reducing real risk.

## Duplicate-work rule

Before opening a PR, check for overlapping open PRs in the same lane.

If two PRs solve the same product slice:

1. Prefer the PR that advances the existing product surface.
2. Prefer the PR with fewer route surfaces.
3. Prefer the PR with green CI.
4. Close the other PR as redundant with a short note.
5. Preserve any useful test idea as a follow-up only if it adds a new failure mode.

## Product-progress rule

For the first usable demo, prefer this order:

1. one existing console surface,
2. one no-effect walkthrough,
3. one approval preview,
4. one receipt/proof panel,
5. one explicit next action.

Avoid parallel surfaces unless the existing surface cannot support the product slice.

## Governance budget

Every change should state its governance budget:

- Light: doc, fixture, static read model.
- Medium: mounted read-only route or approval preview.
- Strict: live external effect or customer-readiness claim.

If a light change requires strict governance, explain the specific risk that justifies it.

## Recommended maintainer judgment

- No-effect demo work should move quickly with focused tests.
- Read-only routes should prove they reject mutation.
- Live effects should remain heavily controlled.
- Customer-readiness claims should remain blocked until external evidence exists.
- Control systems should delete or close redundant controls as actively as they add new ones.

## Current application

The First Usable Demo console lane is Level 2 after it is visible in the existing personal-assistant console route. The next product path, a draft-only invoice/email walkthrough, should be Level 3 until it attempts a live provider interaction or durable state change. Those live steps would move to Level 4.
