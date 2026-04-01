# Mullu Platform MCOI Runtime -- Security Model v0.1.0

**Version:** 0.4.0 (v3.13.0)
**Date:** 2026-03-30
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

### HTTP API Key Authentication

The FastAPI HTTP boundary supports bearer API-key authentication through the
governance middleware. Invalid keys fail closed, authenticated keys bind the
request tenant, and stricter deployment profiles can require authentication on
all `/api/*` routes. By default, `local_dev` and `test` remain permissive for
developer workflow compatibility, while `pilot` and `production` require auth
unless explicitly overridden.

## What Is NOT Implemented

This is an internal alpha. The following security capabilities are still absent
or incomplete:

### No End-User Identity or RBAC

There is still no user authentication, role-based access control, or delegated
authorization model for human operators. Any process that can invoke the CLI or
import the runtime module still has full local access to all operations. Shared
or production environments should front the runtime with authenticated gateways
and least-privilege operating-system controls.

### No Encryption at Rest

Persistence stores (traces, snapshots, replay records, registry data) write JSON
files to the local filesystem with no encryption. Anyone with filesystem access can
read persisted data.

### No External Audit Log Signing

The in-memory audit trail is hash-chained and supports integrity verification,
but persisted JSON snapshots and replay exports are not externally signed or
anchored in an immutable store. An attacker with filesystem write access can
still replace persisted files unless the host environment provides stronger
storage guarantees.

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
