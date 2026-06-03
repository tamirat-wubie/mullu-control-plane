"""Purpose: declarative monitor for protected workspace paths.

Governance scope: detection and reporting of attempts to mutate a
protected workspace path — the governance/control-plane artifacts that a
governed code change must not silently rewrite (CI/CD workflows, schemas,
capability manifests, the governance package itself, proof/receipt/witness
stores, policy files, and secret material).

This module observes a proposed target path (or a set of changed paths)
and classifies which are protected; it never mutates a file and never
applies a patch. It is the path-space analogue of
``ProtectedVariableMonitor`` and follows the same adoption model: an
apply/patch site *can* wire it (gaining a fail-closed protected-path
gate), and a site that does not is unchanged — a contract plus an
optional default, no forced rewiring of existing callers.

Why this exists: ``LocalCodeAdapter`` already blocks writes *outside* the
workspace root, but treats every path *inside* the root uniformly.
Nothing stops a governed code change from patching the very files that
constrain it. This policy adds the missing intra-workspace dimension:
some in-root paths are protected and require elevated authority.

Dependencies: contract base helpers + stdlib only (pure data).
Invariants:
  - classify() is pure: no mutation, deterministic output.
  - Matching is on a normalized, forward-slash, workspace-relative form.
  - A path that cannot be normalized (absolute, a Windows drive/UNC path,
    or one containing a ``..`` traversal segment) is treated as PROTECTED
    — fail-closed. An apply site should already reject such paths; the
    policy must never silently classify an un-anchorable path as safe.
  - Outputs are frozen and JSON-serializable (ContractRecord).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fnmatch import fnmatchcase
from typing import Iterable

from mcoi_runtime.contracts._base import ContractRecord, require_non_empty_text


class ProtectedPathMatch(StrEnum):
    """How a path matched the protected policy (or why it is unprotected)."""

    NONE = "none"
    EXACT_FILE = "exact_file"
    WITHIN_DIRECTORY = "within_directory"
    GLOB = "glob"
    UNNORMALIZABLE = "unnormalizable"


@dataclass(frozen=True, slots=True)
class ProtectedPathVerdict(ContractRecord):
    """Result of classifying one path against a ProtectedPathPolicy."""

    path: str
    protected: bool
    match: ProtectedPathMatch = ProtectedPathMatch.NONE
    matched_pattern: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", require_non_empty_text(self.path, "path"))
        if not isinstance(self.protected, bool):
            raise ValueError("protected must be a bool")
        if not isinstance(self.match, ProtectedPathMatch):
            raise ValueError("match must be a ProtectedPathMatch")


def _normalize_relative_path(path: str) -> str | None:
    """Normalize to a forward-slash, workspace-relative path.

    Returns None for anything that cannot be safely anchored inside a
    workspace: a non-string, an empty string, an absolute path (POSIX
    root, a Windows drive ``C:/...`` or a UNC ``//host/...``), or any path
    containing a ``..`` traversal segment. Callers treat None as
    fail-closed (protected).
    """
    if not isinstance(path, str) or not path.strip():
        return None
    text = path.strip().replace("\\", "/")
    # Absolute: POSIX root / UNC ("//host"), or a Windows drive ("C:/...").
    if text.startswith("/") or (len(text) >= 2 and text[1] == ":"):
        return None
    parts: list[str] = []
    for part in text.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            return None
        parts.append(part)
    if not parts:
        return None
    return "/".join(parts)


def _dedupe_normalized(values: Iterable[str]) -> tuple[str, ...]:
    """Normalize, drop un-normalizable entries, de-duplicate, preserve order."""
    out: dict[str, None] = {}
    for value in values:
        normalized = _normalize_relative_path(value) if isinstance(value, str) else None
        if normalized is not None:
            out.setdefault(normalized, None)
    return tuple(out)


def _dedupe_globs(values: Iterable[str]) -> tuple[str, ...]:
    """Backslash-fold and de-duplicate glob patterns (not path-normalized)."""
    out: dict[str, None] = {}
    for value in values:
        if isinstance(value, str) and value.strip():
            out.setdefault(value.strip().replace("\\", "/"), None)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class ProtectedPathPolicy(ContractRecord):
    """Declarative set of protected workspace paths.

    Three pattern kinds, all matched against the normalized relative path:
      - ``files``: exact normalized file paths (e.g. ``"AGENTS.md"``).
      - ``directories``: directory prefixes; a path is protected if it
        equals the directory or lies beneath it (e.g. ``".github"``
        protects ``.github/workflows/ci.yml``).
      - ``globs``: ``fnmatch`` patterns. A glob containing no ``/`` also
        matches a path's basename, so ``"id_rsa"`` protects an ``id_rsa``
        file at any depth.

    An empty policy classifies nothing as protected (the no-op default).
    """

    files: tuple[str, ...] = ()
    directories: tuple[str, ...] = ()
    globs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", _dedupe_normalized(self.files))
        object.__setattr__(self, "directories", _dedupe_normalized(self.directories))
        object.__setattr__(self, "globs", _dedupe_globs(self.globs))

    @property
    def is_empty(self) -> bool:
        return not (self.files or self.directories or self.globs)

    def classify(self, path: str) -> ProtectedPathVerdict:
        """Classify one path. Pure, deterministic, fail-closed on bad input."""
        normalized = _normalize_relative_path(path)
        if normalized is None:
            display = path.strip() if isinstance(path, str) and path.strip() else "<empty>"
            return ProtectedPathVerdict(
                path=display,
                protected=True,
                match=ProtectedPathMatch.UNNORMALIZABLE,
                matched_pattern="",
                reason="path is absolute or contains a '..' traversal; refused fail-closed",
            )

        if normalized in self.files:
            return ProtectedPathVerdict(
                path=normalized,
                protected=True,
                match=ProtectedPathMatch.EXACT_FILE,
                matched_pattern=normalized,
                reason="path is a protected governance file",
            )

        for directory in self.directories:
            if normalized == directory or normalized.startswith(f"{directory}/"):
                return ProtectedPathVerdict(
                    path=normalized,
                    protected=True,
                    match=ProtectedPathMatch.WITHIN_DIRECTORY,
                    matched_pattern=directory,
                    reason=f"path is within protected directory '{directory}'",
                )

        basename = normalized.rsplit("/", 1)[-1]
        for glob in self.globs:
            if fnmatchcase(normalized, glob) or ("/" not in glob and fnmatchcase(basename, glob)):
                return ProtectedPathVerdict(
                    path=normalized,
                    protected=True,
                    match=ProtectedPathMatch.GLOB,
                    matched_pattern=glob,
                    reason=f"path matches protected pattern '{glob}'",
                )

        return ProtectedPathVerdict(
            path=normalized, protected=False, match=ProtectedPathMatch.NONE,
        )

    def protected_in(self, paths: Iterable[str]) -> tuple[ProtectedPathVerdict, ...]:
        """Classify many paths; return only the protected verdicts."""
        return tuple(v for v in (self.classify(p) for p in paths) if v.protected)


# ---------------------------------------------------------------------------
# Default protected set
# ---------------------------------------------------------------------------

_DEFAULT_PROTECTED_DIRECTORIES: tuple[str, ...] = (
    ".github",                       # CI/CD workflows, actions, CODEOWNERS
    ".gitlab", ".gitea", ".circleci",  # other CI surfaces
    "schemas",                       # proof/contract schemas
    "capabilities",                  # governed capability manifests/packs
    "capsules",                      # capability capsules
    "governance",                    # any top-level governance package/policies
    "mcoi/mcoi_runtime/governance",  # mullu governance SDK (in-repo)
    "mcoi_runtime/governance",
    "policy", "policies",            # policy files
    "proofs", "receipts", "witnesses",  # proof / receipt / witness stores
)

_DEFAULT_PROTECTED_FILES: tuple[str, ...] = (
    "AGENTS.md", "CLAUDE.md",
    "CODEOWNERS", ".github/CODEOWNERS",
    "DEPLOYMENT_STATUS.md", "STATUS.md",
)

_DEFAULT_PROTECTED_GLOBS: tuple[str, ...] = (
    "*.pem", "*.key", "*.pfx", "*.p12",       # private key material
    ".env", "*.env", ".env.*",                # environment / secret files
    "id_rsa", "id_ed25519",                   # ssh private keys
    "secrets.*", "*secret*.json", "*secret*.yaml", "*secret*.yml",
    "docs/*governance*",                      # governance docs (one level)
)


def default_governance_protected_paths() -> ProtectedPathPolicy:
    """A sensible default protected set for a Mullu control-plane workspace.

    Targets the governance/control-plane artifacts a governed code change
    must not silently rewrite: CI/CD workflows, schemas, capability
    manifests, the governance package, proof/receipt/witness stores,
    policy files, and secret material. This is a *default*, not a ceiling
    — operators should compose their own ``ProtectedPathPolicy`` for a
    given workspace. Tuning the patterns never weakens the mechanism.
    """
    return ProtectedPathPolicy(
        files=_DEFAULT_PROTECTED_FILES,
        directories=_DEFAULT_PROTECTED_DIRECTORIES,
        globs=_DEFAULT_PROTECTED_GLOBS,
    )


# Frozen singleton used as the default-on policy by apply/patch seams.
# Safe to share because ProtectedPathPolicy is immutable.
DEFAULT_GOVERNANCE_PROTECTED_PATHS: ProtectedPathPolicy = default_governance_protected_paths()
