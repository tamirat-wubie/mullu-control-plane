# Governed consensus membership changes

v10 turns consensus membership changes into explicit proposals and judgments.

```text
ConsensusMembership
  → ConsensusChangeProposal
  → expected configuration id / term check
  → apply ConsensusMembershipChange ops
  → validate resulting membership
  → ConsensusChangeJudgment
  → SQLite ledger
```

The proposal must include:

```text
cluster_id
expected_configuration_id
expected_term
actor
reason
changes[]
```

A judgment records:

```text
before_configuration_id
after_configuration_id
before_hash
after_hash
resulting_membership
```

API:

```text
POST /system/consensus/membership/changes
```

CLI:

```bash
cargo run -p mind-cli -- consensus-change \
  ./data/membership.json \
  ./data/consensus-change-proposal.json
```

This still does not implement a full consensus protocol. It makes configuration changes auditable and reversible at the platform-governance layer.
