"""Purpose: cryptographic authenticity for transition receipts (Ed25519).

Governance scope: signing/verification of `TransitionReceipt.receipt_hash`
only. This module adds *authenticity* (an authorized kernel key produced
this receipt) on top of the existing *integrity* property (receipt_hash is
the content-address of the receipt body, verifiable by `ProofBridge.
verify_receipt`). The two compose: integrity proves the hash matches the
content; the signature proves the hash was endorsed by a holder of the
signing key.

Dependencies: standard library + optional `cryptography` (declared in the
`encryption`/`dev` extras of mcoi/pyproject.toml; runtime `dependencies`
is empty, so it may be absent).

Invariants:
  - Absence of a configured key is NOT an error: `default_signer()`
    returns a NullReceiptSigner and receipts are emitted unsigned
    (`signature == ""`), exactly matching pre-signing behavior. This
    mirrors the graceful-degradation rationale of `ReceiptStore` /
    `AuditStore` ("the in-process anchor still works").
  - A *misconfigured* key IS an error: a present-but-malformed key or a
    signing request while `cryptography` is unavailable raises, because
    the operator intended signing and silently dropping it would be a
    trust regression.
  - The signed payload is the receipt_hash string's UTF-8 bytes. Signing
    the content-address (not a re-serialization) keeps the signature
    independent of any additive receipt field and free of circularity.
  - Signatures are lowercase hex of the 64-byte Ed25519 signature.
  - key_id = "ed25519:" + sha256(raw_public_key)[:16] — stable, derived
    from the public key so a verifier can select the right key.

This module never imports `contracts.proof` at runtime; the verifier
duck-types the receipt (needs `.receipt_hash`, `.signature`,
`.signing_key_id`) so `proof.py` can import this module without a cycle.
"""

from __future__ import annotations

import enum
import hashlib
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Mapping

if TYPE_CHECKING:  # pragma: no cover - typing only
    from mcoi_runtime.contracts.proof import TransitionReceipt

try:  # optional dependency — see module docstring
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    CRYPTO_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without cryptography
    CRYPTO_AVAILABLE = False


_SEED_LEN = 32
_ENV_KEY_HEX = "MCOI_RECEIPT_SIGNING_KEY"
_ENV_KEY_FILE = "MCOI_RECEIPT_SIGNING_KEY_FILE"


class ReceiptSignatureStatus(enum.Enum):
    """Outcome of verifying a receipt's signature.

    UNSIGNED and NO_VERIFIER_KEY are not failures by themselves — they
    describe *why* a cryptographic decision could not be reached, so the
    caller (a trust boundary) decides whether that is acceptable for its
    surface. SIGNED_INVALID is always a hard failure.
    """

    SIGNED_VALID = "signed_valid"
    SIGNED_INVALID = "signed_invalid"
    UNSIGNED = "unsigned"
    NO_VERIFIER_KEY = "no_verifier_key"
    CRYPTO_UNAVAILABLE = "crypto_unavailable"


def public_key_id(raw_public_key: bytes) -> str:
    """Stable key id derived from the raw 32-byte Ed25519 public key."""
    return "ed25519:" + hashlib.sha256(raw_public_key).hexdigest()[:16]


class ReceiptSigner:
    """Base signer. The default implementation signs nothing.

    A bare `ReceiptSigner()` (or `NullReceiptSigner`) yields
    `("", "")` so `certify_transition` produces byte-identical
    pre-signing receipts when no key is configured.
    """

    key_id: str = ""

    def sign(self, receipt_hash: str) -> tuple[str, str]:
        """Return (signature_hex, signing_key_id). Default: unsigned."""
        return "", ""


class NullReceiptSigner(ReceiptSigner):
    """Explicit no-op signer (used when no key is configured)."""


class Ed25519ReceiptSigner(ReceiptSigner):
    """Signs `receipt_hash` with an Ed25519 private key."""

    def __init__(self, seed: bytes) -> None:
        if not CRYPTO_AVAILABLE:
            raise RuntimeError(
                "receipt signing requested but the 'cryptography' package "
                "is not installed (install mcoi-runtime[encryption])"
            )
        if not isinstance(seed, (bytes, bytearray)) or len(seed) != _SEED_LEN:
            raise ValueError("ed25519 signing seed must be exactly 32 bytes")
        self._private = Ed25519PrivateKey.from_private_bytes(bytes(seed))
        raw_pub = self._private.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )
        self._public_hex = raw_pub.hex()
        self.key_id = public_key_id(raw_pub)

    @classmethod
    def from_seed_hex(cls, seed_hex: str) -> "Ed25519ReceiptSigner":
        try:
            seed = bytes.fromhex(seed_hex.strip())
        except ValueError as exc:
            raise ValueError("ed25519 signing seed must be valid hex") from exc
        return cls(seed)

    @classmethod
    def generate(cls) -> "Ed25519ReceiptSigner":
        if not CRYPTO_AVAILABLE:
            raise RuntimeError("cannot generate a key without 'cryptography'")
        seed = Ed25519PrivateKey.generate().private_bytes_raw()
        return cls(seed)

    @property
    def public_key_hex(self) -> str:
        return self._public_hex

    def sign(self, receipt_hash: str) -> tuple[str, str]:
        if not isinstance(receipt_hash, str) or not receipt_hash:
            raise ValueError("receipt_hash must be a non-empty string to sign")
        signature = self._private.sign(receipt_hash.encode("utf-8"))
        return signature.hex(), self.key_id


class Ed25519ReceiptVerifier:
    """Verifies receipt signatures against one or more public keys.

    Construct with a single public key hex, or a `{key_id: public_key_hex}`
    mapping when multiple signing keys are in rotation. Verification keys
    the receipt's `signing_key_id` to the matching public key; a single
    bare key verifies any receipt regardless of recorded key_id.
    """

    def __init__(
        self,
        *,
        public_key_hex: str | None = None,
        key_ring: Mapping[str, str] | None = None,
    ) -> None:
        self._single: "Ed25519PublicKey | None" = None
        self._ring: dict[str, "Ed25519PublicKey"] = {}
        if not CRYPTO_AVAILABLE:
            return
        if public_key_hex:
            self._single = self._load(public_key_hex)
        for kid, pub_hex in (key_ring or {}).items():
            self._ring[kid] = self._load(pub_hex)

    @staticmethod
    def _load(public_key_hex: str) -> "Ed25519PublicKey":
        try:
            raw = bytes.fromhex(public_key_hex.strip())
        except ValueError as exc:
            raise ValueError("ed25519 public key must be valid hex") from exc
        return Ed25519PublicKey.from_public_bytes(raw)

    def verify(self, receipt: "TransitionReceipt") -> ReceiptSignatureStatus:
        signature = getattr(receipt, "signature", "") or ""
        receipt_hash = getattr(receipt, "receipt_hash", "") or ""
        key_id = getattr(receipt, "signing_key_id", "") or ""
        if not signature:
            return ReceiptSignatureStatus.UNSIGNED
        if not CRYPTO_AVAILABLE:
            return ReceiptSignatureStatus.CRYPTO_UNAVAILABLE
        public = self._ring.get(key_id, self._single)
        if public is None:
            return ReceiptSignatureStatus.NO_VERIFIER_KEY
        try:
            sig_bytes = bytes.fromhex(signature)
        except ValueError:
            return ReceiptSignatureStatus.SIGNED_INVALID
        try:
            public.verify(sig_bytes, receipt_hash.encode("utf-8"))
        except InvalidSignature:
            return ReceiptSignatureStatus.SIGNED_INVALID
        return ReceiptSignatureStatus.SIGNED_VALID


def generate_keypair() -> tuple[str, str, str]:
    """Return (seed_hex, public_key_hex, key_id) for bootstrap/ops/tests."""
    signer = Ed25519ReceiptSigner.generate()
    seed_hex = signer._private.private_bytes_raw().hex()
    return seed_hex, signer.public_key_hex, signer.key_id


_default_lock = threading.Lock()
_default_signer: ReceiptSigner | None = None


def _build_default_signer() -> ReceiptSigner:
    seed_hex = os.environ.get(_ENV_KEY_HEX, "").strip()
    key_file = os.environ.get(_ENV_KEY_FILE, "").strip()
    if not seed_hex and key_file:
        seed_hex = Path(key_file).read_text(encoding="utf-8").strip()
    if not seed_hex:
        # No key configured: graceful no-op, receipts emitted unsigned.
        return NullReceiptSigner()
    # A key WAS configured: a malformed key or missing crypto is a loud
    # failure, not a silent downgrade.
    return Ed25519ReceiptSigner.from_seed_hex(seed_hex)


def default_signer() -> ReceiptSigner:
    """Process-wide signer derived from environment, built once.

    Returns a NullReceiptSigner when no key is configured (the default),
    so importing/calling this never changes behavior unless an operator
    explicitly sets a signing key.
    """
    global _default_signer
    if _default_signer is None:
        with _default_lock:
            if _default_signer is None:
                _default_signer = _build_default_signer()
    return _default_signer


def reset_default_signer_cache() -> None:
    """Drop the cached default signer (tests / key rotation)."""
    global _default_signer
    with _default_lock:
        _default_signer = None


def published_verification_key() -> dict[str, str]:
    """The public trust artifact: what an external party fetches to
    verify receipts *without trusting this process*.

    Returns a JSON-serializable record. When signing is configured it
    carries the Ed25519 public key + key_id so a third party can run
    `Ed25519ReceiptVerifier` themselves. When no key is configured it
    reports `mode="unsigned"` honestly rather than implying a trust
    guarantee that does not exist — the same graceful-degradation
    contract as the null signer.

    This function is pure and side-effect-free so any surface (a
    read-only HTTP route, the CLI, a health endpoint, or an offline
    auditor) can expose it without coupling to the web stack.
    """
    signer = default_signer()
    public_hex = getattr(signer, "public_key_hex", "") or ""
    if not public_hex:
        return {
            "mode": "unsigned",
            "algorithm": "ed25519",
            "key_id": "",
            "public_key_hex": "",
        }
    return {
        "mode": "signed",
        "algorithm": "ed25519",
        "key_id": signer.key_id,
        "public_key_hex": public_hex,
    }
