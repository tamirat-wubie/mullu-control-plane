"""Purpose: built-in shell command allowlist policies for each deployment profile.
Governance scope: shell policy definition and lookup only.
Dependencies: shell_policy contracts.
Invariants:
  - Policies are immutable once defined.
  - All profiles deny known destructive patterns.
  - Policy selection is explicit, not inferred.
"""

from __future__ import annotations

from mcoi_runtime.contracts.shell_policy import ShellCommandPolicy

# Common denied patterns: destructive or injection-prone commands
_COMMON_DENIED_PATTERNS: tuple[str, ...] = (
    r"\brm\s+.*-\s*r\s*f\b",       # rm -rf
    r"\bmkfs\b",                     # mkfs (format filesystem)
    r"\bdd\b.*\bof\s*=\s*/dev/",    # dd of=/dev/*
    r"\bcurl\b.*\|\s*sh\b",         # curl | sh
    r"\bwget\b.*\|\s*sh\b",         # wget | sh
    r"\bcurl\b.*\|\s*bash\b",       # curl | bash
    r"\bwget\b.*\|\s*bash\b",       # wget | bash
)

SANDBOXED = ShellCommandPolicy(
    policy_id="shell-sandboxed",
    allowed_executables=("python3", "python", "echo", "cat", "ls", "head", "tail", "wc"),
    denied_patterns=_COMMON_DENIED_PATTERNS,
    max_argv_length=100,
    max_single_arg_bytes=65536,
    allow_absolute_paths=False,
)

LOCAL_DEV = ShellCommandPolicy(
    policy_id="shell-local-dev",
    allowed_executables=(
        "python3", "python", "echo", "cat", "ls", "head", "tail", "wc",
        "grep", "find", "sort", "jq",
    ),
    denied_patterns=_COMMON_DENIED_PATTERNS,
    max_argv_length=100,
    max_single_arg_bytes=65536,
    allow_absolute_paths=True,
)

PILOT_PROD = ShellCommandPolicy(
    policy_id="shell-pilot-prod",
    allowed_executables=("python3", "python"),
    denied_patterns=_COMMON_DENIED_PATTERNS,
    max_argv_length=50,
    max_single_arg_bytes=32768,
    allow_absolute_paths=False,
)

PILOT_PROD_DISABLED = ShellCommandPolicy(
    policy_id="shell-pilot-prod-disabled",
    allowed_executables=("echo",),
    denied_patterns=_COMMON_DENIED_PATTERNS,
    enabled=False,
    max_argv_length=50,
    max_single_arg_bytes=32768,
    allow_absolute_paths=False,
)

BUILTIN_SHELL_POLICIES: dict[str, ShellCommandPolicy] = {
    p.policy_id: p for p in (SANDBOXED, LOCAL_DEV, PILOT_PROD, PILOT_PROD_DISABLED)
}


def get_shell_policy(policy_id: str) -> ShellCommandPolicy | None:
    """Look up a built-in shell command policy by ID."""
    return BUILTIN_SHELL_POLICIES.get(policy_id)


def list_shell_policies() -> tuple[ShellCommandPolicy, ...]:
    """List all built-in shell command policies."""
    return tuple(sorted(BUILTIN_SHELL_POLICIES.values(), key=lambda p: p.policy_id))
