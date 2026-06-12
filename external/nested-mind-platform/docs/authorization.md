# Authorization

Protected operations must pass through `AuthorizationPolicy::require` before proposal evaluation.

```text
Observer    → public/summary projection
Operator    → public projection + propose patch + attach child
Auditor     → public/internal projection + events + replay + replay audit + read snapshots
Maintainer  → auditor powers + create snapshot + propose patch + attach child + migrate lawbook
Admin       → all permissions + administer
```

Runtime token bindings:

```text
MIND_BOOTSTRAP_TOKEN    admin
MIND_OPERATOR_TOKEN     operator
MIND_AUDITOR_TOKEN      auditor
MIND_MAINTAINER_TOKEN   maintainer
```

Mutation requests may omit `actor`; the authenticated principal id becomes the actor. Supplying a different actor requires `Administer` permission.

Lawbook migrations require `MigrateLawbook`; snapshot creation requires `CreateSnapshot`; replay audit requires `AuditReplay`.

## v6 permissions

```text
ExportTelemetry   export internal or OTLP-shaped telemetry payloads
ReadBackups       list persisted backup manifests
CreateBackup      generate an in-memory/file backup bundle from current runtime stores
VerifyBackup      verify a submitted backup object
RestoreBackup     reserved for restore-capable maintenance tools; live API restore is intentionally absent
```

Auditors can export telemetry, read backup manifests, and verify backups. Maintainers and admins can create backup artifacts; object-store backup creation requires `CreateObjectBackup`. Restore remains a CLI/file-level maintenance operation.

## v7 identity source

Authorization still uses `Principal` and `Role`. v7 adds a second authentication source: trusted OIDC/mTLS headers from an upstream gateway. Those headers are converted into a `Principal` only after `IdentityBindingPolicy` accepts the assertion.
