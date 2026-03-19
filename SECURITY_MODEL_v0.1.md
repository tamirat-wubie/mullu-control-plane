# Mullu Platform MCOI Runtime -- Security Model v0.1.0

**Version:** 0.1.0 (internal alpha)
**Date:** 2026-03-19
**Audience:** Internal developers and operators evaluating this alpha.

This document describes what security properties the runtime provides today and,
equally important, what it does not.

## What Is Enforced

### Credential Isolation

Credential secrets are never stored in contracts, execution traces, persistence
snapshots, or replay records. The runtime references credentials by scope ID only.
Actual secrets are expected to be held in an external credential store or environment
variables, resolved at execution time by the relevant adapter.

### Provider Scope Enforcement

Each registered provider declares:
- **URL allowlists:** Which endpoints the provider may contact.
- **Operation allowlists:** Which operation types the provider may perform.
- **Rate limits:** Maximum invocation frequency.

Requests that fall outside a provider's declared scope are rejected before dispatch.

### Policy Gate

All execution flows through the policy engine. A request must receive an `allow`
decision before the dispatcher will route it. `deny` and `escalate` decisions block
dispatch entirely. There is no bypass path.

### Verification Closure

No action is considered complete until the verification engine produces a result.
Unverified executions remain in an open state and are surfaced as such in operator
reports.

### Fail-Closed Defaults

The runtime fails closed in the following situations:
- Malformed or invalid request data (validation errors block dispatch)
- Missing or unregistered provider for a required capability
- Provider scope violations (URL, operation, or rate limit exceeded)
- Unknown configuration profile names
- Template validation failures

In all cases, the run terminates with a structured error rather than proceeding in a
degraded or permissive state.

## What Is NOT Implemented

This is an internal alpha. The following security capabilities are absent:

### No Authentication or Authorization

There is no user authentication, role-based access control, or authorization system.
Any process that can invoke the CLI or import the runtime module has full access to
all operations. This is acceptable for single-operator internal use; it is not
acceptable for shared or production environments.

### No Encryption at Rest

Persistence stores (traces, snapshots, replay records, registry data) write JSON
files to the local filesystem with no encryption. Anyone with filesystem access can
read persisted data.

### No Audit Log Signing or Tamper Detection

Trace and replay records are stored as plain JSON. There is no cryptographic signing,
hash chaining, or tamper-detection mechanism. A modified trace file is
indistinguishable from an unmodified one.

### Shell Executor Permissions

The shell executor adapter invokes `subprocess.run` and inherits the OS-level
permissions of the Python process. There is no sandboxing, chroot, or capability
restriction beyond what the operating system provides. A malicious or misconfigured
template with `action_type: shell_command` can execute arbitrary commands with the
runtime's privileges.

## Recommendations for Internal Use

1. Run the runtime under a least-privilege OS user account.
2. Do not persist sensitive data through the runtime's trace or snapshot stores.
3. Review all templates before execution -- the policy gate validates structure, not
   intent.
4. Do not expose the CLI or runtime module to untrusted users or networks.
5. Treat persisted JSON files as potentially containing operational data (commands
   executed, results observed) even though credential secrets are excluded.
