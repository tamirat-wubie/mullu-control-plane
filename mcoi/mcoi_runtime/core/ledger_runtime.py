"""Purpose: blockchain / ledger / verifiable settlement runtime engine.
Governance scope: recording ledger accounts, transactions, settlement proofs,
    anchor records, wallets, violations, assessments, snapshots, and closure
    reports with immutable state tracking.
Dependencies: ledger_runtime contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise.
  - Terminal states block further transitions.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.ledger_runtime import (
    AnchorDisposition,
    AnchorRecord,
    LedgerAccount,
    LedgerAssessment,
    LedgerClosureReport,
    LedgerDecision,
    LedgerNetworkKind,
    LedgerSnapshot,
    LedgerStatus,
    LedgerViolation,
    LedgerViolationKind,
    LedgerTransaction,
    SettlementProof,
    SettlementProofStatus,
    WalletRecord,
    WalletStatus,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str = "") -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-ldgr", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_PROOF_TERMINAL = frozenset({
    SettlementProofStatus.CONFIRMED,
    SettlementProofStatus.FAILED,
})

_ANCHOR_TERMINAL = frozenset({
    AnchorDisposition.ANCHORED,
    AnchorDisposition.FAILED,
    AnchorDisposition.REVOKED,
})

_WALLET_TERMINAL = frozenset({
    WalletStatus.CLOSED,
    WalletStatus.COMPROMISED,
})


class LedgerRuntimeEngine:
    """Blockchain / ledger / verifiable settlement runtime engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._accounts: dict[str, LedgerAccount] = {}
        self._transactions: dict[str, LedgerTransaction] = {}
        self._proofs: dict[str, SettlementProof] = {}
        self._anchors: dict[str, AnchorRecord] = {}
        self._wallets: dict[str, WalletRecord] = {}
        self._decisions: dict[str, LedgerDecision] = {}
        self._violations: dict[str, LedgerViolation] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        """Get current time from injected clock."""
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def account_count(self) -> int:
        return len(self._accounts)

    @property
    def transaction_count(self) -> int:
        return len(self._transactions)

    @property
    def proof_count(self) -> int:
        return len(self._proofs)

    @property
    def anchor_count(self) -> int:
        return len(self._anchors)

    @property
    def wallet_count(self) -> int:
        return len(self._wallets)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Accounts
    # ------------------------------------------------------------------

    def register_account(
        self,
        account_id: str,
        tenant_id: str,
        display_name: str,
        *,
        network: LedgerNetworkKind = LedgerNetworkKind.PRIVATE,
        balance: float = 0.0,
    ) -> LedgerAccount:
        """Register a new ledger account."""
        if account_id in self._accounts:
            raise RuntimeCoreInvariantError(f"Duplicate account_id: {account_id}")
        now = self._now()
        acct = LedgerAccount(
            account_id=account_id,
            tenant_id=tenant_id,
            display_name=display_name,
            status=LedgerStatus.ACTIVE,
            network=network,
            balance=balance,
            created_at=now,
        )
        self._accounts[account_id] = acct
        _emit(self._events, "account_registered", {
            "account_id": account_id, "tenant_id": tenant_id,
        }, account_id, self._now())
        return acct

    def get_account(self, account_id: str) -> LedgerAccount:
        """Get account by ID."""
        acct = self._accounts.get(account_id)
        if acct is None:
            raise RuntimeCoreInvariantError(f"Unknown account_id: {account_id}")
        return acct

    def accounts_for_tenant(self, tenant_id: str) -> tuple[LedgerAccount, ...]:
        """Return all accounts for a tenant."""
        return tuple(a for a in self._accounts.values() if a.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Wallets
    # ------------------------------------------------------------------

    def register_wallet(
        self,
        wallet_id: str,
        tenant_id: str,
        identity_ref: str,
        public_key_ref: str,
    ) -> WalletRecord:
        """Register a new wallet."""
        if wallet_id in self._wallets:
            raise RuntimeCoreInvariantError(f"Duplicate wallet_id: {wallet_id}")
        now = self._now()
        w = WalletRecord(
            wallet_id=wallet_id,
            tenant_id=tenant_id,
            identity_ref=identity_ref,
            status=WalletStatus.ACTIVE,
            public_key_ref=public_key_ref,
            created_at=now,
        )
        self._wallets[wallet_id] = w
        _emit(self._events, "wallet_registered", {
            "wallet_id": wallet_id, "tenant_id": tenant_id,
        }, wallet_id, self._now())
        return w

    def get_wallet(self, wallet_id: str) -> WalletRecord:
        """Get wallet by ID."""
        w = self._wallets.get(wallet_id)
        if w is None:
            raise RuntimeCoreInvariantError(f"Unknown wallet_id: {wallet_id}")
        return w

    def freeze_wallet(self, wallet_id: str) -> WalletRecord:
        """Freeze a wallet."""
        old = self.get_wallet(wallet_id)
        if old.status in _WALLET_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot freeze wallet in terminal status {old.status.value}"
            )
        updated = WalletRecord(
            wallet_id=old.wallet_id,
            tenant_id=old.tenant_id,
            identity_ref=old.identity_ref,
            status=WalletStatus.FROZEN,
            public_key_ref=old.public_key_ref,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._wallets[wallet_id] = updated
        _emit(self._events, "wallet_frozen", {
            "wallet_id": wallet_id,
        }, wallet_id, self._now())
        return updated

    def close_wallet(self, wallet_id: str) -> WalletRecord:
        """Close a wallet."""
        old = self.get_wallet(wallet_id)
        if old.status in _WALLET_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot close wallet in terminal status {old.status.value}"
            )
        updated = WalletRecord(
            wallet_id=old.wallet_id,
            tenant_id=old.tenant_id,
            identity_ref=old.identity_ref,
            status=WalletStatus.CLOSED,
            public_key_ref=old.public_key_ref,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._wallets[wallet_id] = updated
        _emit(self._events, "wallet_closed", {
            "wallet_id": wallet_id,
        }, wallet_id, self._now())
        return updated

    def mark_compromised(self, wallet_id: str) -> WalletRecord:
        """Mark a wallet as compromised."""
        old = self.get_wallet(wallet_id)
        if old.status in _WALLET_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot mark compromised wallet in terminal status {old.status.value}"
            )
        updated = WalletRecord(
            wallet_id=old.wallet_id,
            tenant_id=old.tenant_id,
            identity_ref=old.identity_ref,
            status=WalletStatus.COMPROMISED,
            public_key_ref=old.public_key_ref,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._wallets[wallet_id] = updated
        _emit(self._events, "wallet_compromised", {
            "wallet_id": wallet_id,
        }, wallet_id, self._now())
        return updated

    def wallets_for_tenant(self, tenant_id: str) -> tuple[WalletRecord, ...]:
        """Return all wallets for a tenant."""
        return tuple(w for w in self._wallets.values() if w.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Transactions
    # ------------------------------------------------------------------

    def create_transaction(
        self,
        transaction_id: str,
        tenant_id: str,
        from_account: str,
        to_account: str,
        amount: float,
        reference_ref: str,
    ) -> LedgerTransaction:
        """Create a ledger transaction."""
        if transaction_id in self._transactions:
            raise RuntimeCoreInvariantError(f"Duplicate transaction_id: {transaction_id}")
        # Validate from_account exists
        if from_account not in self._accounts:
            raise RuntimeCoreInvariantError(f"Unknown from_account: {from_account}")
        now = self._now()
        tx = LedgerTransaction(
            transaction_id=transaction_id,
            tenant_id=tenant_id,
            from_account=from_account,
            to_account=to_account,
            amount=amount,
            reference_ref=reference_ref,
            created_at=now,
        )
        self._transactions[transaction_id] = tx
        _emit(self._events, "transaction_created", {
            "transaction_id": transaction_id, "amount": amount,
        }, transaction_id, self._now())
        return tx

    def get_transaction(self, transaction_id: str) -> LedgerTransaction:
        """Get transaction by ID."""
        tx = self._transactions.get(transaction_id)
        if tx is None:
            raise RuntimeCoreInvariantError(f"Unknown transaction_id: {transaction_id}")
        return tx

    def transactions_for_tenant(self, tenant_id: str) -> tuple[LedgerTransaction, ...]:
        """Return all transactions for a tenant."""
        return tuple(t for t in self._transactions.values() if t.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Settlement proofs
    # ------------------------------------------------------------------

    def create_settlement_proof(
        self,
        proof_id: str,
        tenant_id: str,
        transaction_ref: str,
        proof_hash: str,
    ) -> SettlementProof:
        """Create a settlement proof in PENDING status."""
        if proof_id in self._proofs:
            raise RuntimeCoreInvariantError(f"Duplicate proof_id: {proof_id}")
        now = self._now()
        p = SettlementProof(
            proof_id=proof_id,
            tenant_id=tenant_id,
            transaction_ref=transaction_ref,
            status=SettlementProofStatus.PENDING,
            proof_hash=proof_hash,
            created_at=now,
        )
        self._proofs[proof_id] = p
        _emit(self._events, "proof_created", {
            "proof_id": proof_id, "transaction_ref": transaction_ref,
        }, proof_id, self._now())
        return p

    def confirm_proof(self, proof_id: str) -> SettlementProof:
        """Confirm a settlement proof."""
        old = self._proofs.get(proof_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown proof_id: {proof_id}")
        if old.status in _PROOF_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot confirm proof in terminal status {old.status.value}"
            )
        if not old.proof_hash.strip():
            raise RuntimeCoreInvariantError("Cannot confirm proof with empty proof_hash")
        now = self._now()
        updated = SettlementProof(
            proof_id=old.proof_id,
            tenant_id=old.tenant_id,
            transaction_ref=old.transaction_ref,
            status=SettlementProofStatus.CONFIRMED,
            proof_hash=old.proof_hash,
            verified_at=now,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._proofs[proof_id] = updated
        _emit(self._events, "proof_confirmed", {
            "proof_id": proof_id,
        }, proof_id, self._now())
        return updated

    def fail_proof(self, proof_id: str) -> SettlementProof:
        """Fail a settlement proof."""
        old = self._proofs.get(proof_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown proof_id: {proof_id}")
        if old.status in _PROOF_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot fail proof in terminal status {old.status.value}"
            )
        updated = SettlementProof(
            proof_id=old.proof_id,
            tenant_id=old.tenant_id,
            transaction_ref=old.transaction_ref,
            status=SettlementProofStatus.FAILED,
            proof_hash=old.proof_hash,
            verified_at=old.verified_at,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._proofs[proof_id] = updated
        _emit(self._events, "proof_failed", {
            "proof_id": proof_id,
        }, proof_id, self._now())
        return updated

    def dispute_proof(self, proof_id: str) -> SettlementProof:
        """Dispute a settlement proof."""
        old = self._proofs.get(proof_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown proof_id: {proof_id}")
        if old.status in _PROOF_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot dispute proof in terminal status {old.status.value}"
            )
        updated = SettlementProof(
            proof_id=old.proof_id,
            tenant_id=old.tenant_id,
            transaction_ref=old.transaction_ref,
            status=SettlementProofStatus.DISPUTED,
            proof_hash=old.proof_hash,
            verified_at=old.verified_at,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._proofs[proof_id] = updated
        _emit(self._events, "proof_disputed", {
            "proof_id": proof_id,
        }, proof_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Anchors
    # ------------------------------------------------------------------

    def create_anchor(
        self,
        anchor_id: str,
        tenant_id: str,
        source_ref: str,
        content_hash: str,
        anchor_ref: str,
    ) -> AnchorRecord:
        """Create an anchor record in PENDING disposition."""
        if anchor_id in self._anchors:
            raise RuntimeCoreInvariantError(f"Duplicate anchor_id: {anchor_id}")
        now = self._now()
        ar = AnchorRecord(
            anchor_id=anchor_id,
            tenant_id=tenant_id,
            source_ref=source_ref,
            content_hash=content_hash,
            disposition=AnchorDisposition.PENDING,
            anchor_ref=anchor_ref,
            created_at=now,
        )
        self._anchors[anchor_id] = ar
        _emit(self._events, "anchor_created", {
            "anchor_id": anchor_id, "source_ref": source_ref,
        }, anchor_id, self._now())
        return ar

    def confirm_anchor(self, anchor_id: str) -> AnchorRecord:
        """Confirm an anchor (ANCHORED)."""
        old = self._anchors.get(anchor_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown anchor_id: {anchor_id}")
        if old.disposition in _ANCHOR_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot confirm anchor in terminal disposition {old.disposition.value}"
            )
        updated = AnchorRecord(
            anchor_id=old.anchor_id,
            tenant_id=old.tenant_id,
            source_ref=old.source_ref,
            content_hash=old.content_hash,
            disposition=AnchorDisposition.ANCHORED,
            anchor_ref=old.anchor_ref,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._anchors[anchor_id] = updated
        _emit(self._events, "anchor_confirmed", {
            "anchor_id": anchor_id,
        }, anchor_id, self._now())
        return updated

    def fail_anchor(self, anchor_id: str) -> AnchorRecord:
        """Fail an anchor."""
        old = self._anchors.get(anchor_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown anchor_id: {anchor_id}")
        if old.disposition in _ANCHOR_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot fail anchor in terminal disposition {old.disposition.value}"
            )
        updated = AnchorRecord(
            anchor_id=old.anchor_id,
            tenant_id=old.tenant_id,
            source_ref=old.source_ref,
            content_hash=old.content_hash,
            disposition=AnchorDisposition.FAILED,
            anchor_ref=old.anchor_ref,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._anchors[anchor_id] = updated
        _emit(self._events, "anchor_failed", {
            "anchor_id": anchor_id,
        }, anchor_id, self._now())
        return updated

    def revoke_anchor(self, anchor_id: str) -> AnchorRecord:
        """Revoke an anchor."""
        old = self._anchors.get(anchor_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown anchor_id: {anchor_id}")
        if old.disposition in _ANCHOR_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot revoke anchor in terminal disposition {old.disposition.value}"
            )
        updated = AnchorRecord(
            anchor_id=old.anchor_id,
            tenant_id=old.tenant_id,
            source_ref=old.source_ref,
            content_hash=old.content_hash,
            disposition=AnchorDisposition.REVOKED,
            anchor_ref=old.anchor_ref,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._anchors[anchor_id] = updated
        _emit(self._events, "anchor_revoked", {
            "anchor_id": anchor_id,
        }, anchor_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Proof verification
    # ------------------------------------------------------------------

    def verify_proof(self, proof_id: str, expected_hash: str) -> bool:
        """Check if a proof is CONFIRMED and proof_hash matches expected_hash."""
        p = self._proofs.get(proof_id)
        if p is None:
            return False
        return p.status == SettlementProofStatus.CONFIRMED and p.proof_hash == expected_hash

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def ledger_assessment(
        self,
        assessment_id: str,
        tenant_id: str,
    ) -> LedgerAssessment:
        """Produce a tenant-scoped ledger assessment."""
        tenant_proofs = [p for p in self._proofs.values() if p.tenant_id == tenant_id]
        confirmed = sum(1 for p in tenant_proofs if p.status == SettlementProofStatus.CONFIRMED)
        failed = sum(1 for p in tenant_proofs if p.status == SettlementProofStatus.FAILED)
        disputed = sum(1 for p in tenant_proofs if p.status == SettlementProofStatus.DISPUTED)
        total = confirmed + failed + disputed
        integrity = confirmed / total if total > 0 else 1.0
        now = self._now()
        assessment = LedgerAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_confirmed=confirmed,
            total_failed=failed,
            total_disputed=disputed,
            integrity_score=integrity,
            assessed_at=now,
        )
        _emit(self._events, "ledger_assessment", {
            "assessment_id": assessment_id, "integrity_score": integrity,
        }, assessment_id, self._now())
        return assessment

    # ------------------------------------------------------------------
    # Snapshot (contract-level, tenant-scoped)
    # ------------------------------------------------------------------

    def ledger_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> LedgerSnapshot:
        """Produce a tenant-scoped ledger snapshot."""
        now = self._now()
        snap = LedgerSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_accounts=sum(1 for a in self._accounts.values() if a.tenant_id == tenant_id),
            total_transactions=sum(1 for t in self._transactions.values() if t.tenant_id == tenant_id),
            total_proofs=sum(1 for p in self._proofs.values() if p.tenant_id == tenant_id),
            total_anchors=sum(1 for a in self._anchors.values() if a.tenant_id == tenant_id),
            total_wallets=sum(1 for w in self._wallets.values() if w.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            captured_at=now,
        )
        _emit(self._events, "ledger_snapshot", {
            "snapshot_id": snapshot_id,
        }, snapshot_id, self._now())
        return snap

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_ledger_violations(self, tenant_id: str) -> tuple[LedgerViolation, ...]:
        """Detect ledger violations for a tenant. Idempotent by violation ID."""
        now = self._now()
        new_violations: list[LedgerViolation] = []

        # Failed proofs
        for p in self._proofs.values():
            if p.tenant_id == tenant_id and p.status == SettlementProofStatus.FAILED:
                vid = stable_identifier("viol-ldgr", {
                    "proof": p.proof_id, "kind": "proof_failed",
                })
                if vid not in self._violations:
                    v = LedgerViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        kind=LedgerViolationKind.PROOF_FAILED,
                        operation=f"proof:{p.proof_id}",
                        reason=f"Settlement proof {p.proof_id} failed verification",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # Failed anchors (anchor_expired maps to FAILED anchors)
        for a in self._anchors.values():
            if a.tenant_id == tenant_id and a.disposition == AnchorDisposition.FAILED:
                vid = stable_identifier("viol-ldgr", {
                    "anchor": a.anchor_id, "kind": "anchor_expired",
                })
                if vid not in self._violations:
                    v = LedgerViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        kind=LedgerViolationKind.ANCHOR_EXPIRED,
                        operation=f"anchor:{a.anchor_id}",
                        reason=f"Anchor {a.anchor_id} failed/expired",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # Compromised wallets
        for w in self._wallets.values():
            if w.tenant_id == tenant_id and w.status == WalletStatus.COMPROMISED:
                vid = stable_identifier("viol-ldgr", {
                    "wallet": w.wallet_id, "kind": "wallet_compromised",
                })
                if vid not in self._violations:
                    v = LedgerViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        kind=LedgerViolationKind.WALLET_COMPROMISED,
                        operation=f"wallet:{w.wallet_id}",
                        reason=f"Wallet {w.wallet_id} is compromised",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        if new_violations:
            _emit(self._events, "ledger_violations_detected", {
                "tenant_id": tenant_id, "count": len(new_violations),
            }, "violation-scan", self._now())

        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Engine state management
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "accounts": self._accounts,
            "transactions": self._transactions,
            "proofs": self._proofs,
            "anchors": self._anchors,
            "wallets": self._wallets,
            "decisions": self._decisions,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
        """Capture complete engine state as a serializable dict."""
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
        result["_state_hash"] = self.state_hash()
        return result

    def state_hash(self) -> str:
        """Compute SHA-256 hash of engine state. No timestamps in hash keys."""
        parts: list[str] = []
        for name, collection in sorted(self._collections().items()):
            if isinstance(collection, dict):
                for k in sorted(collection):
                    v = collection[k]
                    status = ""
                    for attr in ("status", "disposition", "kind"):
                        val = getattr(v, attr, None)
                        if val is not None:
                            status = f":{val.value}" if hasattr(val, "value") else f":{val}"
                            break
                    parts.append(f"{name}:{k}{status}")
        return sha256("|".join(parts).encode()).hexdigest()
