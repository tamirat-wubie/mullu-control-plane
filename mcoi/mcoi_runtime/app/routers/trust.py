"""Public trust-boundary endpoints.

Purpose: expose the published Ed25519 verification key so an external
party can verify Mullu's signed transition receipts *without trusting
this process* — the operational half of the "public trust boundary".
Governance scope: read-only key publication. No receipt is accepted,
mutated, or verified server-side here on purpose: verification belongs
to the receipt holder (using the pure `fully_verify_receipt` +
`Ed25519ReceiptVerifier`), not to the server being asked to vouch for
itself.
Dependencies: FastAPI, pure `published_verification_key()` (no
proof_bridge / store coupling, so this cannot affect request handling).
Invariants:
  - GET-only; mutates no trace, replay, tenant, budget, or policy state
    (and therefore does not enter the receipt-coverage ratchet).
  - Honest when signing is disabled: reports mode="unsigned" rather than
    implying an assurance that does not exist.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from mcoi_runtime.contracts.receipt_signing import published_verification_key

router = APIRouter()


@router.get("/trust/verification-key")
def verification_key() -> dict[str, Any]:
    """The public artifact a third party fetches to independently verify
    signed receipts. Carries the Ed25519 public key + key_id when signing
    is configured, or an honest ``mode="unsigned"`` when it is not.
    """
    return published_verification_key()
