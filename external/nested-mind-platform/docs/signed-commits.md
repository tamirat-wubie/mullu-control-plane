# Signed Commits

Commits can be signed with Ed25519 before append. The signature covers the commit body excluding the signature field:

```text
commit id, proposal id, mind id, parent commit, actor, reason, timestamp,
patch, topology, before_hash, after_hash, judgment
```

Runtime configuration:

```text
MIND_REQUIRE_SIGNATURES=true
MIND_COMMIT_SIGNING_KEY_ID=root-runtime-ed25519
MIND_COMMIT_SIGNING_SEED_HEX=<64 hex characters>
```

When signatures are required, the event store rejects unsigned commits and replay can require signature verification.

## v7 managed signing

v7 keeps Ed25519 as the commit signature algorithm and adds a backend status model:

```text
disabled
local_ed25519
secret_manager
hsm
kms
external_request
```

`env_ed25519` signs inline. `secret_manager`, `hsm`, `kms`, and `external_request` create an external-completion boundary for future adapter integration. The current API refuses required-signature mutation without an inline signer, preventing unsigned appends.

```bash
MIND_SIGNING_BACKEND=env_ed25519
```
