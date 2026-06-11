<!--
Purpose: define the repository-local trusted control studio authorization for Codex-assisted Mullusi engineering work.
Governance scope: AGENTS.md authorization, local workstation autonomy, task-relevant secret handling, external-effect stop rules, and validation evidence.
Dependencies: AGENTS.md, docs/FOUNDATION_MODE.md, scripts/validate_trusted_local_control_studio.py.
Invariants: local autonomy is repository-scoped, secrets are not disclosed, external-effect boundaries remain blocked without explicit task context, platform and connector controls are not bypassed, and Mullusi hard governance laws remain active.
-->

# Trusted Local Control Studio

<!-- TYPE: Policy -->
<!-- AUDIENCE: operator, assisting developer agents, future reviewers -->

This document records the operator-designated local control studio posture for
Codex-assisted Mullusi engineering work. It clarifies that the workstation and
repository are trusted local surfaces for autonomous technical execution, while
public, financial, legal, destructive, and external-account effects remain
bounded by explicit task context and governance witnesses.

## Authorization Boundary

| Surface | Authorized by default | Still blocked without explicit task context |
| --- | --- | --- |
| Repository inspection | Read source, docs, schemas, tests, logs, receipts, local config, and generated artifacts needed for the active task. | Reading unrelated private material outside the task boundary. |
| Repository edits | Create and edit repository-local files, tests, validators, receipts, and docs needed for governed work. | Destructive operations outside the intended workspace. |
| Local commands | Run deterministic shell commands, validators, formatters, tests, local services, and package metadata checks needed for verification. | Privileged, destructive, or machine-wide changes unrelated to the active task. |
| Network use | Look up documentation, package metadata, source references, and task-relevant API status. | Publishing production systems, changing external accounts, or contacting customers. |
| Local secrets | Inspect presence, names, scopes, and bounded shape when required for diagnosis or execution. | Reading raw values without explicit task-scoped instruction, printing full secret values, exfiltrating credentials, or committing raw credentials. |

## Secret Handling

Task-relevant secret metadata can be checked inside the local control studio,
but raw values remain sensitive and fail-closed. The required behavior is:

1. Prefer presence, shape, scope, and configuration checks over value access.
2. Read raw secret values only when the operator gives explicit task-scoped
   instruction for a concrete diagnosis or recovery action.
3. Do not print full tokens, private keys, passwords, recovery codes, or access
   credentials in user-facing output.
4. Do not persist raw secret values in Git, docs, fixtures, logs, receipts, or
   generated artifacts.
5. Stop and report `AwaitingEvidence` when an action needs an external witness
   or would cross a tenant, billing, legal, deployment, public, or
   external-account boundary.

## Hard Stop Rules

Codex remains blocked from these actions unless the operator gives explicit
task-scoped instruction and the required governance witness exists:

1. Move money, process payments, or bind payment providers.
2. File legal paperwork, form a company, make patent filings, or claim legal
   clearance.
3. Publish production systems, promote deployment status, change DNS, or open
   customer access.
4. Contact customers, send external communications, or collect personal data.
5. Change external account security settings or bypass connector authentication.
6. Bypass platform-level controls, operating-system permission controls, or
   Mullusi hard governance laws.

## Validation

Run:

```powershell
python scripts/validate_trusted_local_control_studio.py
```

The validator checks that:

1. `AGENTS.md` contains the trusted local control studio authorization block.
2. Local autonomy includes repository inspection, repository edits, local
   commands, task-relevant network use, and bounded secret metadata inspection.
3. Secret handling preserves no-disclosure and no-exfiltration boundaries.
4. Hard stop rules preserve destructive, legal, financial, public-facing,
   external-account, platform, connector, and Mullusi governance boundaries.
5. This document remains linked to the validator and reports a status block.

STATUS:
  Completeness: 100%
  Invariants verified: local autonomy scoped, secret metadata inspection bounded, raw secret value access explicit-instruction only, secret disclosure blocked, external-effect stop rules retained, platform and connector controls retained
  Open issues: none
  Next action: run the trusted local control studio validator after any AGENTS.md authorization edit
