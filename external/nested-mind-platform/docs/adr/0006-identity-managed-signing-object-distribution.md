# ADR 0006: Identity, managed signing, object backup, and distributed strategy

## Status

Accepted for v7 scaffold.

## Decision

Add four production boundary models without coupling the symbolic kernel to vendor services:

```text
1. Trusted external identity assertions bound by local policy.
2. Managed signing abstraction over local Ed25519 and future HSM/KMS/secret-manager signers.
3. Object backup pointers over verifiable MindBackup objects.
4. Distributed event-store strategy guard for append authority.
```

## Rationale

The kernel must preserve these invariants:

```text
- no mutation without authorization
- no append without causal validation
- no required-signature event accepted unsigned
- no follower/archive node silently appending local events
- no backup trusted without hash-chain verification
```

Vendor identity providers, HSM/KMS services, and object stores are operational adapters. They should not define kernel semantics.

## Consequences

Constructive:

```text
+ identity, signing, backup, and distribution are explicit policy surfaces
+ local development remains dependency-light
+ production adapters can be added without changing 𝕊 semantics
+ unsafe distributed writes can be rejected before mutation
```

Fracture:

```text
- OIDC/JWKS verification is delegated to a trusted gateway in this scaffold
- HSM/KMS/secret-manager signing is modeled but not vendor-integrated
- object storage is file-backed until cloud adapters are added
- distributed replication/consensus is not implemented yet
```
