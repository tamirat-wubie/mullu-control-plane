<!--
Purpose: define the Foundation Mode repository observation evidence packet and its live read-only local repository producer.
Governance scope: OCE field completeness, RAG repository-source binding, CDCV observation-to-admission causality, CQTE freshness and proof-state gates, UWMA receipt anchoring, SRCA finite validation, and PRS focused validator closure.
Dependencies: docs/94_observation_evidence_acquisition_architecture.md, schemas/repository_observation_evidence_packet.schema.json, examples/repository_observation_evidence_packet.foundation.json, scripts/produce_repository_observation_evidence_packet.py, scripts/validate_repository_observation_evidence_packet.py, tests/test_validate_repository_observation_evidence_packet.py.
Invariants: repository observation is not execution; the Foundation example performs no live repository read; live packets use only allowlisted read-only git commands; no packet serializes raw git output, file contents, secrets, connector calls, runtime dispatch, deployment mutation, terminal closure, or success claims; hard-constraint planning remains blocked unless live evidence has ProofState Pass.
-->

# Repository Observation Evidence Packet Contract

<!-- TYPE: Reference -->
<!-- AUDIENCE: architecture maintainers, repository adapter implementers, governance reviewers -->

> **In one box:** This page defines the first source-specific evidence packet
> for the observation architecture: local repository state. The checked-in
> packet is a Foundation Mode shape; `scripts/produce_repository_observation_evidence_packet.py`
> can produce a live digest-only local read observation.

---

## Boundary

`RepositoryObservationEvidencePacket` is a digest-only planning evidence packet.
It is not a repository worker, runtime dispatch, file reader, connector, or
terminal closure certificate.

It binds:

1. Repository and worktree references.
2. Branch, status, diff, and file-inventory digest refs.
3. Planning admission state.
4. Authority denials.
5. Privacy guards.
6. Recovery action for future live read-only observation.

It denies in every mode:

1. Source filesystem mutation.
2. File-content payload serialization.
3. Secret reads.
4. Connector calls.
5. External writes.
6. Runtime dispatch.
7. Deployment mutation.
8. Terminal closure.
9. Success claims.

Live repository read authority is allowed only for `local_read_only_git_status`
packets produced by the fixed command allowlist below.

## Foundation Example

The Foundation Mode example is:

```text
examples/repository_observation_evidence_packet.foundation.json
```

It intentionally records:

```text
planning_admission = defer
proof_state = Unknown
solver_outcome = AwaitingEvidence
hard_constraint_planning_allowed = false
soft_utility_planning_allowed = true
live_evidence_required = true
```

The packet can support soft planning discussion only. It cannot support
hard-constraint planning until a live read-only repository observation receipt
exists.

## Live Read-Only Producer

The live producer is:

```text
scripts/produce_repository_observation_evidence_packet.py
```

It runs only this command set, without shell expansion:

| Command name | Argv |
| --- | --- |
| `branch` | `git rev-parse --abbrev-ref HEAD` |
| `git_status` | `git status --short --branch --untracked-files=all` |
| `diff` | `git diff --name-status --no-ext-diff --` |
| `file_inventory` | `git ls-files -z` |

The producer hashes command output in memory and writes only digest refs into
the packet. It does not serialize branch text, status text, diff text,
file-inventory text, file contents, or secret-shaped values.

Run:

```powershell
python scripts/produce_repository_observation_evidence_packet.py --json
```

The default output path is:

```text
.change_assurance/repository_observation_evidence_packet.live.json
```

That path is workspace-local and ignored by git.

## Required Validators

Run:

```powershell
python scripts/validate_repository_observation_evidence_packet.py
python -m pytest tests/test_validate_repository_observation_evidence_packet.py -q
python scripts/produce_repository_observation_evidence_packet.py --json
python scripts/validate_observation_evidence_acquisition_architecture.py
python -m pytest tests/test_validate_observation_evidence_acquisition_architecture.py -q
```

STATUS:
  Completeness: 100%
  Invariants verified: digest-only repository observation, Foundation fixture blocks live-read claims, live producer uses allowlisted read-only git commands, no raw output serialization, no source filesystem mutation, no file-content payload serialization, no secret read, no connector call, no runtime dispatch, no deployment mutation, no terminal closure, hard-constraint planning blocked unless live proof state is Pass
  Open issues: provider and connector observation packets remain future proof threads
  Next action: bind admitted repository world-state projections into ProblemStar evidence input
