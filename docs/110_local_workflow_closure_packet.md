# Local Workflow Closure Packet

Purpose: define the Local Developer Workflow v1 closure packet that summarizes
preview artifacts into one operator handoff.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: `mcoi/software_dev/local_developer_workflow_v1/closure_packet.py`,
Local Developer Workflow v1 artifacts, and optional operator workflow dashboard
projection.
Invariants: the packet is projection-only; it never grants file-write,
test-run, branch-push, pull-request creation, merge, deployment, connector,
external-write, or live-execution authority.

## Contract

The closure packet is emitted after the preview workflow artifacts exist:

1. repo status
2. patch plan
3. diff proposal
4. test plan
5. receipt
6. approval request
7. PR command preview

It adds one bounded handoff:

```text
preview artifacts
-> current gate
-> missing evidence refs
-> next required proof step
-> rollback boundary
-> approval boundary
-> command preview refs
-> closure packet hash
```

## Output

Default packet:

```text
.change_assurance/local_developer_workflow_v1_closure_packet.json
```

Core fields:

| Field | Meaning |
| --- | --- |
| `current_gate` | approval or dashboard gate currently blocking execution |
| `missing_evidence_refs` | refs required before any stronger claim |
| `next_required_proof_step` | concrete proof step to close next |
| `approval_boundary` | review-only approval state |
| `rollback` | non-executed rollback boundary |
| `command_preview` | PR commands with `execution_allowed=false` |
| `effect_boundary` | all live and external effects disabled |
| `packet_hash` | deterministic packet integrity hash |

## Commands

Build from existing workflow artifacts:

```powershell
python scripts/build_local_developer_workflow_closure_packet.py --strict
```

Run the local developer workflow and emit the closure packet automatically:

```powershell
python scripts/run_local_developer_workflow_v1.py --strict
```

Build workflow artifacts first if they are absent:

```powershell
python scripts/build_local_developer_workflow_closure_packet.py --build-if-missing --strict
```

Validate a packet:

```powershell
python scripts/validate_local_developer_workflow_closure_packet.py --strict
```

Validate the full workflow and require the closure packet:

```powershell
python scripts/validate_local_developer_workflow_v1.py --require-closure-packet --strict
```

## Non-Authority Boundary

The packet can support review and planning only. It cannot be used as evidence
that file mutation, test execution, PR creation, merge, deployment, connector
write, or rollback execution occurred.

Any stronger claim requires a separate execution receipt and post-execution
evidence.
