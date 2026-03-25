# 24 -- Organizational Awareness Layer

## Purpose

The organizational awareness layer provides the runtime with a directory of
people, teams, roles, ownership mappings, and escalation chains.  Its purpose is
to answer four questions deterministically:

1. **Who owns what?** -- map resources (repositories, services, workflows) to the
   responsible team or individual.
2. **Who approves what?** -- identify the person holding the approver role on the
   owning team for a given resource.
3. **Who should be escalated to?** -- given an escalation chain, determine the
   next contact and the channel to use based on elapsed time.
4. **How should communications be routed?** -- preferred channel per person,
   team-level lead, ordered escalation with timeout progression.

This layer does **not** send emails, post chat messages, or perform any I/O.  It
provides the data structures and lookup logic that other layers (communication
plane, approval engine, runbook executor) consume.

## Owned Artifacts

| Contract             | Location                                     |
|----------------------|----------------------------------------------|
| `RoleType`           | `contracts/organization.py`                  |
| `ContactChannel`     | `contracts/organization.py`                  |
| `Person`             | `contracts/organization.py`                  |
| `Team`               | `contracts/organization.py`                  |
| `OwnershipMapping`   | `contracts/organization.py`                  |
| `EscalationStep`     | `contracts/organization.py`                  |
| `EscalationChain`    | `contracts/organization.py`                  |
| `EscalationState`    | `contracts/organization.py`                  |
| `OrgDirectory`       | `core/organization.py`                       |
| `EscalationManager`  | `core/organization.py`                       |

## Role Types

Every `Person` carries a tuple of `RoleType` values describing their
organizational function:

| Role               | Meaning                                              |
|--------------------|------------------------------------------------------|
| `owner`            | Responsible for the resource's lifecycle.             |
| `approver`         | Authorized to approve actions on owned resources.     |
| `reviewer`         | Authorized to review changes but not approve them.    |
| `operator`         | Day-to-day operations contact.                        |
| `escalation_target`| Designated recipient in an escalation chain.          |

## Ownership

`OwnershipMapping` binds a resource (identified by `resource_id` and
`resource_type`) to a team and optionally an individual:

- `resource_type` is a free-form string (`repo`, `service`, `workflow`, etc.).
- `owner_team_id` is required; every resource must be owned by a team.
- `owner_person_id` is optional and designates a point-of-contact within the
  team.

The `OrgDirectory.find_owner(resource_id)` method returns the mapping or `None`.
The `OrgDirectory.find_approver(resource_id)` method walks the owning team's
member list and returns the first person holding the `approver` role.

## Escalation

An `EscalationChain` is an ordered sequence of `EscalationStep` records.  Each
step specifies:

- `step_order` -- 1-based position in the chain.
- `target_person_id` -- who to contact.
- `target_team_id` -- optional; if the person is unavailable, fan out to the team.
- `timeout_minutes` -- how long to wait before progressing to the next step.
- `channel` -- preferred contact method (`email`, `chat`, `notification`).

The `EscalationManager` tracks runtime state via `EscalationState`:

1. `start_escalation(chain_id)` creates state at step 1.
2. `check_escalation(state, now)` compares elapsed time against the current
   step's timeout and returns whether advancement is needed.
3. `advance_escalation(state)` moves to the next step.
4. `resolve_escalation(state)` marks the chain resolved and halts further
   progression.

## Prohibitions

1. **No contact without policy check.** The runtime must not use organizational
   data to send communications without a prior policy evaluation.
2. **No escalation skip.** Steps must be followed in order; jumping ahead is
   forbidden.
3. **No fabricated org data.** Person, Team, and OwnershipMapping records must
   come from explicit registration; the runtime must never invent contacts.
