# Branch protection policy generator

v20 adds a generated branch-protection policy artifact for release enforcement.

```text
required readiness checks
  → BranchProtectionPolicy
  → GitHub REST branch-protection payload
  → BranchProtectionEvaluationReport
```

Default required checks:

```text
cargo fmt
cargo clippy
cargo test
mandatory-readiness-gates
readiness-evidence
```

Default review constraints:

```text
2 approving reviews
code owner reviews required
dismiss stale reviews
last-push approval required
conversation resolution required
linear history required
admin enforcement enabled
force-push/delete disabled
```

The generator does not silently apply settings to GitHub. It emits a policy and REST payload that operators can apply after review.

CLI:

```bash
cargo run -p mind-cli -- branch-protection-policy mullusi/nested-mind-platform main
cargo run -p mind-cli -- branch-protection-evaluate ./data/branch-policy.json cargo\ test,mandatory-readiness-gates
```

API:

```text
GET  /system/github/branch-protection/policies
POST /system/github/branch-protection/policies
GET  /system/github/branch-protection/evaluations
POST /system/github/branch-protection/evaluations
```
