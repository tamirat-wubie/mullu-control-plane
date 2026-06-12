# Consensus membership model

v9 adds consensus configuration primitives without claiming to implement a full consensus protocol.

## Kernel types

```text
ConsensusMember
ConsensusMemberRole
ConsensusMembership
ConsensusMembershipChange
ElectionVote
ElectionTally
```

## Invariants

```text
+ cluster_id is required
+ member ids are non-empty and unique
+ at least one voting member exists
+ configured leader must be a member
+ election candidate must be a voting member
+ quorum = floor(voting_members / 2) + 1
```

## API

```text
GET /system/consensus/membership
```

## CLI

```bash
cargo run -p mind-cli -- consensus-membership \
  mind-cluster \
  node-a,node-b,node-c \
  node-a
```

## Fracture boundary

```text
- membership state is modeled and ledgered
- vote tally is deterministic
- leader election loop, log replication consensus, and dynamic reconfiguration protocol are not implemented yet
```
