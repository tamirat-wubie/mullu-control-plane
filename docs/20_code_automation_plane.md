# Code Automation Plane

Scope: governed local code/repository automation. All file mutation is bounded to a declared workspace root.

## 1. Purpose

Make coding a first-class governed automation surface: repository inspection, file read/write, patch application, build/test execution, and code review — all under the same autonomy, approval, verification, replay, and provider rules as other planes.

## 2. Owned Artifacts

- `RepositoryDescriptor` — identity, root path, language hints
- `WorkspaceState` — snapshot of workspace file listing and status
- `SourceFile` — typed reference to a file with content hash
- `PatchProposal` — unified diff with target file, description
- `PatchApplicationResult` — success/failure of patch apply
- `BuildResult` — typed build command outcome
- `TestResult` — typed test command outcome with pass/fail/error counts
- `CodeReviewRecord` — summary of a code review assessment

## 3. Inputs

- Local repository/workspace root path
- File paths (must be inside workspace root)
- Unified diff patches
- Build/test commands

## 4. Outputs

- Typed workspace state snapshots
- File content with hashes
- Patch application results
- Build/test results with structured output
- Code review summaries

## 5. Prohibited Behaviors

- MUST NOT access files outside the declared workspace root
- MUST NOT execute shell expansion (glob, variable expansion, backticks)
- MUST NOT push to remote repositories
- MUST NOT publish packages
- MUST NOT modify files without approval when autonomy/profile requires it
- MUST NOT silently accept malformed patches
- MUST NOT fabricate test results

## 6. Governance Integration

- Code-changing actions (write, patch apply) require the same autonomy mode checks as execution actions
- Approval-required mode blocks code mutations without explicit approval
- All code operations are typed, replayable, and persistable
- Successful verified code runs can be promoted into runbooks

## 7. Failure Modes

- `path_outside_root` — attempted access outside workspace
- `file_not_found` — target file does not exist
- `malformed_patch` — patch cannot be parsed or applied
- `build_failed` — build command returned nonzero
- `test_failed` — test command returned failures
- `write_blocked` — mutation denied by autonomy/approval

## 8. Adapter Boundaries

The local code adapter:
- Operates only on the local filesystem
- Uses subprocess for build/test commands with timeout
- Captures stdout, stderr, and exit code
- Enforces workspace root containment via path resolution
