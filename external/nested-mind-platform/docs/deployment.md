# Deployment

The repo includes deployment templates under `deploy/`.

```text
deploy/kubernetes  Kubernetes single-replica SQLite deployment
deploy/systemd     Linux service unit
deploy/fly         Fly.io-style Docker deployment
```

## Kubernetes

Apply in order after replacing secret values and image names:

```bash
kubectl apply -f deploy/kubernetes/namespace.yaml
kubectl apply -f deploy/kubernetes/configmap.yaml
kubectl apply -f deploy/kubernetes/secret.example.yaml
kubectl apply -f deploy/kubernetes/pvc.yaml
kubectl apply -f deploy/kubernetes/deployment.yaml
kubectl apply -f deploy/kubernetes/service.yaml
```

The manifest uses one replica because SQLite is single-writer local state. Do not scale replicas above one until the event store is replaced with a distributed store or consensus-backed writer.

## Backups

`deploy/kubernetes/backup-cronjob.yaml` calls the protected backup API and writes a verified backup JSON file onto the mounted volume. Copy that file to external object storage as a separate operational step.

## Systemd

Install the binary and create `/etc/nested-mind/mind-api.env`, then:

```bash
sudo cp deploy/systemd/mind-api.service /etc/systemd/system/mind-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now mind-api
```

## Runtime invariants

```text
- persistent volume required
- stable MIND_ROOT_ID required
- signing key must not rotate silently
- bootstrap token must not be checked into git
- run one SQLite writer at a time
```

## v7 deployment variables

```bash
MIND_TRUSTED_IDENTITY_HEADERS=false
MIND_IDENTITY_ALLOWED_ISSUERS=
MIND_IDENTITY_REQUIRED_AUDIENCES=
MIND_IDENTITY_REQUIRED_CLIENT_CERT_SHA256=
MIND_SIGNING_BACKEND=env_ed25519
MIND_BACKUP_OBJECT_DIR=/app/data/object-store
MIND_BACKUP_OBJECT_BUCKET=mind-backups
MIND_EVENT_STORE_STRATEGY=single_writer
MIND_NODE_ID=local
MIND_NODE_ROLE=single
MIND_VOTING_MEMBERS=1
MIND_QUORUM_SIZE=1
MIND_ALLOW_LOCAL_APPENDS=true
```

When `MIND_TRUSTED_IDENTITY_HEADERS=true`, only expose the API behind a gateway that strips client-supplied identity headers and injects verified OIDC/mTLS claims.

## v8 deployment variables

```bash
MIND_OIDC_JWKS_FILE=./config/jwks.json
MIND_OIDC_ISSUER=https://issuer.example
MIND_OIDC_AUDIENCES=nested-mind-api
MIND_OIDC_ALLOWED_ALGORITHMS=RS256
MIND_OIDC_DEFAULT_ROLE=observer
MIND_CLOUD_BACKUP_PROVIDER=s3
MIND_CLOUD_BACKUP_BUCKET=mind-backups
MIND_CLOUD_BACKUP_PREFIX=root
MIND_REPLICATION_LEADER_ID=leader-a
MIND_REPLICATION_MAX_RECORDS_PER_BATCH=100
MIND_REPLICATION_REQUIRED_ACKS=1
```

## v9 deployment variables

```bash
MIND_OIDC_DISCOVERY_FILE=./config/openid-configuration.json
MIND_OIDC_REFRESH_TTL_SECONDS=3600
MIND_CLOUD_OBJECT_MIRROR_DIR=./data/cloud-mirror
MIND_REPLICATION_INBOX_LOG=./data/replication-inbox.jsonl
MIND_REPLICATION_FOLLOWERS=node-b=http://node-b:8080,node-c=http://node-c:8080
MIND_CONSENSUS_CLUSTER_ID=mind-cluster
MIND_CONSENSUS_MEMBERS=node-a,node-b,node-c
MIND_CONSENSUS_LEADER_ID=node-a
```
