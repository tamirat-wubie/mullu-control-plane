"""Purpose: build compact WHQR replay bindings from verified canonical metadata.
Governance scope: preserve canonical WHQR replay identity across closure read models and proof surfaces.
Dependencies: WHQR document contract and immutable metadata mappings.
Invariants: missing WHQR metadata yields no binding; partial or tampered metadata fails closed; replay_ref binds canonical_hash.
"""

from __future__ import annotations

from typing import Any, Mapping

from mcoi_runtime.contracts.whqr import WHQRDocument


WHQR_REPLAY_BINDING_FIELDS = frozenset(
    {"replay_ref", "canonical_hash", "semantics_hash", "version"}
)


def build_whqr_replay_binding_from_metadata(
    metadata: Mapping[str, Any],
    *,
    context_label: str,
) -> dict[str, str] | None:
    """Build one compact WHQR replay binding from terminal certificate metadata.

    Input contract: metadata may omit all WHQR replay keys for legacy records.
    Output contract: returns None for fully absent metadata, otherwise a compact
    replay binding with replay_ref, canonical_hash, semantics_hash, and version.
    Error contract: raises ValueError when any WHQR replay key is partial,
    malformed, noncanonical, or semantically mismatched.
    """
    if not isinstance(metadata, Mapping):
        raise ValueError(f"{context_label} WHQR metadata must be a mapping")

    canonical_json = metadata.get("whqr_canonical_json")
    canonical_hash = metadata.get("whqr_canonical_hash")
    semantics_hash = metadata.get("whqr_semantics_hash")
    whqr_version = metadata.get("whqr_version")
    if (
        canonical_json is None
        and canonical_hash is None
        and semantics_hash is None
        and whqr_version is None
    ):
        return None
    if not isinstance(canonical_json, str) or not canonical_json:
        raise ValueError(f"{context_label} requires WHQR canonical replay document")
    if not isinstance(canonical_hash, str) or not canonical_hash:
        raise ValueError(f"{context_label} requires WHQR canonical hash")
    try:
        document = WHQRDocument.from_canonical_json(
            canonical_json,
            expected_canonical_hash=canonical_hash,
        )
    except ValueError as exc:
        raise ValueError(f"{context_label} WHQR replay document is invalid") from exc
    if semantics_hash is not None and semantics_hash != document.semantics_hash:
        raise ValueError(f"{context_label} WHQR semantics hash mismatch")
    if whqr_version is not None and whqr_version != document.whqr_version:
        raise ValueError(f"{context_label} WHQR version mismatch")
    return {
        "replay_ref": f"whqr://replay/{canonical_hash}",
        "canonical_hash": canonical_hash,
        "semantics_hash": document.semantics_hash,
        "version": document.whqr_version,
    }
