# Governed consensus membership changes

v10 adds a governed membership-change object around the v9 consensus model.

```text
ConsensusMembership
  -> ConsensusChangeProposal
  -> validate expected configuration id + term
  -> apply requested changes to simulated next membership
  -> hash before/after configuration
  -> ConsensusChangeJudgment
  -> ledger record
```

## Proposal

```rust
ConsensusChangeProposal {
    cluster_id,
    expected_configuration_id,
    expected_term,
    actor,
    reason,
    changes,
}
```

The proposal is rejected if the expected configuration id or term is stale.

## Judgment

```rust
ConsensusChangeJudgment {
    proposal_id,
    accepted,
    before_configuration_id,
    after_configuration_id,
    before_hash,
    after_hash,
    resulting_membership,
}
```

The judgment verifies that the before hash matches the current membership and that the after hash matches the resulting membership.

## API route

```text
POST /system/consensus/membership/changes
```

## CLI command

```bash
cargo run -p mind-cli -- consensus-change \
  ./data/membership.json \
  ./data/proposal.json
```

## Governance invariant

A membership change is not a silent config mutation. It is a judgment with an actor, reason, stale-state checks, and before/after hashes.
