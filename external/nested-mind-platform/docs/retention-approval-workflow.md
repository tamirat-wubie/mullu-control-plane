# Consensus retention approval workflow

v16 adds explicit approval before retention enforcement can be treated as governed maintenance.

```text
ConsensusRetentionEnforcementPlan
  → ConsensusRetentionApprovalProposal
  → voting-member approvals/rejections
  → ConsensusRetentionApprovalCertificate
  → retention enforcement may proceed
```

The approval certificate checks:

```text
cluster id
configuration id
term
backup guard hash
voting membership
quorum/minimum approval count
proposal hash binding
```

## Runtime endpoint

```text
GET  /system/consensus/log/retention/approvals
POST /system/consensus/log/retention/approvals
```

## CLI

```bash
cargo run -p mind-cli -- retention-approval \
  ./data/retention-plan.json \
  ./data/membership.json \
  ./data/votes.json \
  maintainer-a \
  2
```

## Governance rule

Physical evidence deletion is not a single-operator action. The approval certificate must bind the exact retention plan and the active consensus membership before deletion is considered authorized.
