# Consensus commit certificates

v10 governed membership changes. v11 adds commit certificates for consensus log entries.

```text
ConsensusLogEntry
  -> cluster/configuration/term
  -> leader
  -> operation hash
  -> entry hash

ConsensusCommitVote
  -> voter
  -> entry hash
  -> accepted/rejected

ConsensusCommitCertificate
  -> required quorum
  -> accepted votes
  -> committed bool
```

The certificate verifies that:

```text
entry matches the active membership
leader is a voting member
votes target the same entry/term/hash
votes come from voting members
accepted votes >= quorum
```

## API

```text
GET  /system/consensus/commit-certificates
POST /system/consensus/commit-certificates
```

Example:

```json
{
  "operation_kind": "replication_batch_commit",
  "operation": {"batch_id": "batch-1"},
  "voters": ["node-a", "node-b"],
  "previous_entry_hash": null
}
```

## CLI

```bash
cargo run -p mind-cli -- consensus-commit \
  ./data/membership.json \
  replication_batch_commit \
  '{"batch_id":"batch-1"}' \
  node-a,node-b \
  none
```
