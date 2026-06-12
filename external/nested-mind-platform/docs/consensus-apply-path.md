# Consensus Apply Path

v11 introduced consensus commit certificates. v12 adds the apply path for certificates whose operation is `replication_batch_commit`.

```text
ConsensusCommitCertificate
  -> verify quorum against active ConsensusMembership
  -> deserialize ReplicationBatch
  -> verify follower cursor / event-record hash chain
  -> append exact leader-produced EventRecord values
  -> ConsensusApplyReport
```

The apply path does not create new commits. It ingests leader-produced event records exactly, preserving the causal chain `H`.

API routes:

```text
GET  /system/consensus/apply-reports
POST /system/consensus/log/apply
```

Request body:

```json
{
  "certificate": {"...": "ConsensusCommitCertificate"},
  "follower_id": "node-b"
}
```
