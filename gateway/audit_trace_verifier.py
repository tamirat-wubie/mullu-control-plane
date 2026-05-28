"""Gateway audit-trace verifier — external-auditor read-only verification.

Purpose: given read-only access to a CommandLedger, verify that the per-
    command event hash chain is internally consistent, that the global event
    hash chain links every event to its predecessor, that terminal
    certificates are correctly bound to their commands, and that persisted
    anchors carry valid merkle roots and signatures.
Governance scope: external verification only — performs no writes, makes no
    governance decisions, and consults nothing outside the ledger.
Dependencies: gateway command spine canonical hashing and event contracts.
Invariants:
  - Verifier is read-only; no method mutates ledger state.
  - Failure modes are bounded and structured (no generic "verification failed").
  - An event_hash mismatch is reported per-event with the offending event_id.
  - Missing command and missing terminal certificate are distinct outcomes.
  - Global-chain breaks are reported per-event with the offending event_id.
  - Anchor signature verification uses the provided secret only; the secret
    is never logged, persisted, or compared against stored material.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from gateway.command_spine import (
    CommandAnchor,
    CommandEvent,
    CommandLedger,
    CommandState,
    _anchor_signature_payload,
    _compute_merkle_root,
    canonical_hash,
)
from gateway.authority_obligation_mesh import (
    ApprovalChainStatus,
    AuthorityObligationMesh,
)
from gateway.command_spine import ClosureDisposition
from gateway.trust_ledger import TrustLedger, TrustLedgerBundle


@dataclass(frozen=True, slots=True)
class AuditTraceVerification:
    """Bounded outcome of one command's audit-trace verification."""

    command_id: str
    command_present: bool
    event_count: int
    event_hash_chain_valid: bool
    terminal_certificate_present: bool
    terminal_certificate_id: str
    failures: tuple[str, ...]

    @property
    def all_links_verified(self) -> bool:
        """True iff the trace contains zero structured failures."""
        return not self.failures


class AuditTraceVerifier:
    """Read-only verifier for one CommandLedger's audit chain.

    This is the first slice of the RCS-JOINT v1.0.0 AuditTraceVerifier
    deliverable. It deliberately consumes only public read methods on
    CommandLedger so that an external auditor (with read-only access to a
    serialized governance log) could implement the same checks.
    """

    def __init__(self, command_ledger: CommandLedger) -> None:
        self._ledger = command_ledger

    def verify_command_trace(self, command_id: str) -> AuditTraceVerification:
        """Verify the audit chain for one command end-to-end."""
        command = self._ledger.get(command_id)
        if command is None:
            return AuditTraceVerification(
                command_id=command_id,
                command_present=False,
                event_count=0,
                event_hash_chain_valid=False,
                terminal_certificate_present=False,
                terminal_certificate_id="",
                failures=("command_not_found",),
            )

        failures: list[str] = []
        events = self._ledger.events_for(command_id)
        chain_valid = self._verify_event_hashes(events, failures)

        certificate = self._ledger.terminal_certificate_for(command_id)
        cert_present = certificate is not None
        cert_id = ""
        if certificate is not None:
            cert_id = certificate.certificate_id
            if certificate.command_id != command_id:
                failures.append("certificate_command_mismatch")
            if not certificate.evidence_refs:
                failures.append("certificate_evidence_refs_empty")

        return AuditTraceVerification(
            command_id=command_id,
            command_present=True,
            event_count=len(events),
            event_hash_chain_valid=chain_valid,
            terminal_certificate_present=cert_present,
            terminal_certificate_id=cert_id,
            failures=tuple(failures),
        )

    def verify_certificate_hash(self, command_id: str) -> "CertificateHashVerification":
        """Recompute the terminal certificate's content hash and confirm
        certificate_id matches.

        certificate_id is f"terminal-closure-{canonical_hash(seed)[:16]}"
        where the seed includes the FULL response_evidence_closure — which
        the certificate itself does not retain (it keeps only the closure's
        hash as response_evidence_closure_id). Recomputation therefore
        reconstructs the closure from the ledger's response_evidence_closed
        event and additionally confirms that closure hashes to the
        certificate's stored response_evidence_closure_id. This catches a
        tampered certificate (flipped disposition, altered metadata, swapped
        case_id) carrying a stale certificate_id.
        """
        command = self._ledger.get(command_id)
        if command is None:
            return CertificateHashVerification(
                command_id=command_id,
                certificate_present=False,
                certificate_id="",
                recomputed_certificate_id="",
                hash_matches=False,
                closure_binding_valid=True,
                failures=("command_not_found",),
            )
        certificate = self._ledger.terminal_certificate_for(command_id)
        if certificate is None:
            # Absence of a terminal certificate is informational, not a
            # failure (most commands are verified before terminal closure).
            return CertificateHashVerification(
                command_id=command_id,
                certificate_present=False,
                certificate_id="",
                recomputed_certificate_id="",
                hash_matches=True,
                closure_binding_valid=True,
                failures=(),
            )

        failures: list[str] = []
        closure_dict = self._reconstruct_response_evidence_closure(command_id)

        # Closure-binding: if the certificate carries a closure id, the
        # reconstructed closure must hash to it.
        closure_binding_valid = True
        closure_unrecoverable = False
        if certificate.response_evidence_closure_id:
            if closure_dict is None:
                closure_binding_valid = False
                closure_unrecoverable = True
                failures.append("certificate_closure_unrecoverable")
            elif canonical_hash(closure_dict) != certificate.response_evidence_closure_id:
                closure_binding_valid = False
                failures.append("certificate_closure_binding_mismatch")

        # Short-circuit hash recomputation when the closure is
        # unrecoverable. Without the closure dict, the seed below is
        # missing the response_evidence_closure field and the recomputed
        # id is guaranteed not to match — reporting that as a separate
        # certificate_hash_mismatch duplicates the root cause already
        # surfaced by certificate_closure_unrecoverable.
        if closure_unrecoverable:
            recomputed_certificate_id = ""
            hash_matches = False
        else:
            recomputed = canonical_hash({
                "command_id": certificate.command_id,
                "disposition": certificate.disposition.value,
                "evidence_refs": certificate.evidence_refs,
                "response_evidence_closure": closure_dict,
                "case_id": certificate.case_id,
                "accepted_risk_id": certificate.accepted_risk_id,
                "compensation_outcome_id": certificate.compensation_outcome_id,
                "metadata": certificate.metadata,
            })
            recomputed_certificate_id = f"terminal-closure-{recomputed[:16]}"
            hash_matches = recomputed_certificate_id == certificate.certificate_id
            if not hash_matches:
                failures.append("certificate_hash_mismatch")

        return CertificateHashVerification(
            command_id=command_id,
            certificate_present=True,
            certificate_id=certificate.certificate_id,
            recomputed_certificate_id=recomputed_certificate_id,
            hash_matches=hash_matches,
            closure_binding_valid=closure_binding_valid,
            failures=tuple(failures),
        )

    def _reconstruct_response_evidence_closure(self, command_id: str):
        # The full ResponseEvidenceClosure is stored as a dict in the
        # response_evidence_closed transition-event detail. Return the most
        # recent one, or None if the command never closed response evidence.
        for event in reversed(self._ledger.events_for(command_id)):
            closure = event.detail.get("response_evidence_closure")
            if isinstance(closure, dict):
                return closure
        return None

    def _verify_event_hashes(
        self,
        events: list[CommandEvent],
        failures: list[str],
    ) -> bool:
        # The event hash is canonical_hash over the event_seed used by
        # CommandLedger._append_event. Recomputing the seed from the public
        # event fields and comparing detects any tamper of the event payload.
        all_valid = True
        for event in events:
            if _recompute_event_hash(event) != event.event_hash:
                failures.append(f"event_hash_mismatch:{event.event_id}")
                all_valid = False
        return all_valid

    def verify_global_event_chain(self) -> "GlobalChainVerification":
        """Verify the ledger's append-order event chain end-to-end."""
        events = list(self._ledger._events)
        failures: list[str] = []
        previous_hash = ""
        for event in events:
            if event.prev_event_hash != previous_hash:
                failures.append(f"global_chain_break:{event.event_id}")
            if _recompute_event_hash(event) != event.event_hash:
                failures.append(f"event_hash_mismatch:{event.event_id}")
            previous_hash = event.event_hash
        return GlobalChainVerification(
            event_count=len(events),
            chain_intact=not failures,
            failures=tuple(failures),
        )

    def verify_anchor(
        self,
        anchor_id: str,
        *,
        signing_secret: str,
    ) -> "AnchorVerification":
        """Verify one persisted anchor's merkle root and HMAC signature."""
        if not signing_secret:
            raise ValueError("signing_secret_required")
        anchors = self._ledger.list_anchors(limit=10_000)
        anchor = next((item for item in anchors if item.anchor_id == anchor_id), None)
        if anchor is None:
            return AnchorVerification(
                anchor_id=anchor_id,
                anchor_present=False,
                merkle_root_valid=False,
                signature_valid=False,
                failures=("anchor_not_found",),
            )

        failures: list[str] = []
        events_in_range = self._events_for_anchor(anchor)
        if len(events_in_range) != anchor.event_count:
            failures.append("anchor_event_count_mismatch")
        # Recompute every event hash within the anchored range. The merkle
        # root below is computed over the stored event_hash values, so a
        # tampered event payload whose stored hash is left intact would
        # leave the merkle root matching while the underlying event is
        # corrupt. Recomputation catches that scenario inside verify_anchor
        # alone, so an auditor running only this method (e.g. when
        # validating a specific anchor's scope) is not silently misled.
        for event in events_in_range:
            if _recompute_event_hash(event) != event.event_hash:
                failures.append(f"anchored_event_hash_mismatch:{event.event_id}")
        recomputed_root = _compute_merkle_root([event.event_hash for event in events_in_range])
        merkle_valid = recomputed_root == anchor.merkle_root
        if not merkle_valid:
            failures.append("anchor_merkle_root_mismatch")

        expected_signature = hmac.new(
            signing_secret.encode(),
            _anchor_signature_payload(anchor).encode(),
            hashlib.sha256,
        ).hexdigest()
        signature_valid = hmac.compare_digest(expected_signature, anchor.signature)
        if not signature_valid:
            failures.append("anchor_signature_invalid")

        return AnchorVerification(
            anchor_id=anchor_id,
            anchor_present=True,
            merkle_root_valid=merkle_valid,
            signature_valid=signature_valid,
            failures=tuple(failures),
        )

    def verify_trust_bundle(
        self,
        bundle: TrustLedgerBundle,
        *,
        signing_secret: str,
    ) -> "TrustBundleVerification":
        """Verify a trust bundle's signature AND cross-reference with the ledger.

        TrustLedger.verify only checks the bundle's internal consistency
        (bundle_hash + HMAC signature). This method additionally cross-
        references the bundle's claims (command_id, tenant_id,
        terminal_certificate_id) against what the ledger actually contains —
        catching bundles that were signed by an authorized issuer but reference
        commands or certificates that do not exist or do not match.
        """
        if not signing_secret:
            raise ValueError("signing_secret_required")
        failures: list[str] = []
        internal = TrustLedger().verify(bundle, signing_secret=signing_secret)
        signature_valid = internal.verified
        if not signature_valid:
            failures.append(f"trust_ledger_verify_failed:{internal.reason}")

        command = self._ledger.get(bundle.command_id)
        if command is None:
            failures.append("bundle_command_not_in_ledger")
            return TrustBundleVerification(
                bundle_id=bundle.bundle_id,
                signature_valid=signature_valid,
                ledger_cross_reference_valid=False,
                failures=tuple(failures),
            )
        if command.tenant_id != bundle.tenant_id:
            failures.append("bundle_tenant_id_mismatch")

        certificate = self._ledger.terminal_certificate_for(bundle.command_id)
        if certificate is None:
            failures.append("bundle_certificate_not_in_ledger")
        elif certificate.certificate_id != bundle.terminal_certificate_id:
            failures.append("bundle_certificate_id_mismatch")

        cross_ref_failures = [
            failure for failure in failures
            if failure != f"trust_ledger_verify_failed:{internal.reason}"
        ]
        return TrustBundleVerification(
            bundle_id=bundle.bundle_id,
            signature_valid=signature_valid,
            ledger_cross_reference_valid=not cross_ref_failures,
            failures=tuple(failures),
        )

    def verify_approval_chain(
        self,
        command_id: str,
        *,
        obligation_mesh: AuthorityObligationMesh,
    ) -> "ApprovalChainVerification":
        """Verify the approval chain for a command is internally consistent
        and consistent with any terminal certificate.

        Catches insider scenarios where an authority chain claims SATISFIED
        but its approver list is too short or contains duplicates, and where
        a terminal certificate is COMMITTED for a command whose chain is
        DENIED, PENDING, or EXPIRED.
        """
        command = self._ledger.get(command_id)
        if command is None:
            return ApprovalChainVerification(
                command_id=command_id,
                chain_present=False,
                chain_status=None,
                approver_count=0,
                approvers_unique=True,
                certificate_disposition=None,
                failures=("command_not_found",),
            )
        chain = obligation_mesh.approval_chain_for(command_id)
        certificate = self._ledger.terminal_certificate_for(command_id)
        certificate_disposition = certificate.disposition if certificate is not None else None
        failures: list[str] = []
        approver_count = 0
        approvers_unique = True
        chain_status: ApprovalChainStatus | None = None
        if chain is not None:
            chain_status = chain.status
            approver_count = len(chain.approvals_received)
            approvers_unique = len(set(chain.approvals_received)) == approver_count
            if not approvers_unique:
                failures.append("approval_chain_duplicate_approvers")
            if chain.status is ApprovalChainStatus.SATISFIED:
                if approver_count < chain.required_approver_count:
                    failures.append("approval_chain_insufficient_approver_count")
        if certificate is not None and certificate.disposition is ClosureDisposition.COMMITTED:
            if chain is not None and chain.status not in {
                ApprovalChainStatus.SATISFIED,
                ApprovalChainStatus.NOT_REQUIRED,
            }:
                failures.append("committed_certificate_with_unsatisfied_chain")
        return ApprovalChainVerification(
            command_id=command_id,
            chain_present=chain is not None,
            chain_status=chain_status,
            approver_count=approver_count,
            approvers_unique=approvers_unique,
            certificate_disposition=certificate_disposition,
            failures=tuple(failures),
        )

    def verify_replay_state_consistency(self, command_id: str) -> "ReplayStateVerification":
        """Replay command events and compare the result with current ledger state."""
        command = self._ledger.get(command_id)
        if command is None:
            return ReplayStateVerification(
                command_id=command_id,
                command_present=False,
                replayed_state=None,
                live_state=None,
                transition_chain_valid=False,
                states_match=False,
                event_count=0,
                failures=("command_not_found",),
            )

        events = self._ledger.events_for(command_id)
        failures: list[str] = []
        replayed_state: CommandState | None = None
        transition_chain_valid = True
        for event in events:
            if replayed_state is None:
                if (
                    event.previous_state is not CommandState.RECEIVED
                    or event.next_state is not CommandState.RECEIVED
                ):
                    failures.append(f"replay_initial_state_gap:{event.event_id}")
                    transition_chain_valid = False
            elif event.previous_state != replayed_state:
                failures.append(f"replay_transition_gap:{event.event_id}")
                transition_chain_valid = False
            replayed_state = event.next_state

        if replayed_state is None:
            failures.append("replay_no_events_for_command")
            return ReplayStateVerification(
                command_id=command_id,
                command_present=True,
                replayed_state=None,
                live_state=command.state,
                transition_chain_valid=False,
                states_match=False,
                event_count=0,
                failures=tuple(failures),
            )

        states_match = replayed_state == command.state
        if not states_match:
            failures.append("replay_state_diverges_from_live")

        return ReplayStateVerification(
            command_id=command_id,
            command_present=True,
            replayed_state=replayed_state,
            live_state=command.state,
            transition_chain_valid=transition_chain_valid,
            states_match=states_match,
            event_count=len(events),
            failures=tuple(failures),
        )

    def verify_tenant_isolation(self, command_id: str) -> "TenantIsolationVerification":
        """Verify the command's tenant_id is consistent across its events.

        Catches tenant-leak scenarios where an event for this command
        carries a tenant_id that does not match the command's. The terminal
        certificate is bound by command_id (no tenant_id field), so this
        method also reports certificate_command_id_mismatch if it diverges.

        Approval-chain tenant verification is NOT covered here — the chain
        lives in AuthorityObligationMesh state (not the ledger), and the
        mesh is not part of this method's parameter set. verify_all could
        cross-reference if the chain is fetched there, but is not required
        by this method's contract.
        """
        command = self._ledger.get(command_id)
        if command is None:
            return TenantIsolationVerification(
                command_id=command_id,
                command_present=False,
                expected_tenant_id="",
                event_tenant_mismatches=(),
                certificate_tenant_mismatch=False,
                failures=("command_not_found",),
            )
        expected = command.tenant_id
        failures: list[str] = []
        event_mismatches: list[str] = []
        for event in self._ledger.events_for(command_id):
            if event.tenant_id != expected:
                event_mismatches.append(event.event_id)
        if event_mismatches:
            failures.append("event_tenant_mismatch")

        # Terminal certificates do not carry tenant_id directly — they bind
        # via command_id. We assert tenant consistency by re-reading the
        # command, which is the only authoritative source.
        cert = self._ledger.terminal_certificate_for(command_id)
        cert_mismatch = False
        if cert is not None and cert.command_id != command_id:
            cert_mismatch = True
            failures.append("certificate_command_id_mismatch")

        return TenantIsolationVerification(
            command_id=command_id,
            command_present=True,
            expected_tenant_id=expected,
            event_tenant_mismatches=tuple(event_mismatches),
            certificate_tenant_mismatch=cert_mismatch,
            failures=tuple(failures),
        )

    def verify_all(
        self,
        command_id: str,
        *,
        obligation_mesh: AuthorityObligationMesh,
        anchor_id: str = "",
        anchor_signing_secret: str = "",
        bundle: TrustLedgerBundle | None = None,
        bundle_signing_secret: str = "",
    ) -> "FullVerification":
        """Compose every verification relevant to one command into one report.

        Anchor and bundle checks are optional — pass an anchor_id (with the
        signing secret) and/or a bundle (with its secret) to include them.
        The trace, global-chain, and approval-chain checks always run.
        """
        trace = self.verify_command_trace(command_id)
        global_chain = self.verify_global_event_chain()
        approval = self.verify_approval_chain(command_id, obligation_mesh=obligation_mesh)
        tenant = self.verify_tenant_isolation(command_id)
        replay = self.verify_replay_state_consistency(command_id)
        certificate_hash = self.verify_certificate_hash(command_id)
        anchor: AnchorVerification | None = None
        if anchor_id:
            if not anchor_signing_secret:
                raise ValueError("anchor_signing_secret_required")
            anchor = self.verify_anchor(anchor_id, signing_secret=anchor_signing_secret)
        bundle_check: TrustBundleVerification | None = None
        if bundle is not None:
            if not bundle_signing_secret:
                raise ValueError("bundle_signing_secret_required")
            bundle_check = self.verify_trust_bundle(bundle, signing_secret=bundle_signing_secret)
        all_failures: list[str] = []
        all_failures.extend(trace.failures)
        all_failures.extend(global_chain.failures)
        all_failures.extend(approval.failures)
        all_failures.extend(tenant.failures)
        all_failures.extend(replay.failures)
        all_failures.extend(certificate_hash.failures)
        if anchor is not None:
            all_failures.extend(anchor.failures)
        if bundle_check is not None:
            all_failures.extend(bundle_check.failures)
        return FullVerification(
            command_id=command_id,
            trace=trace,
            global_chain=global_chain,
            approval=approval,
            tenant=tenant,
            replay=replay,
            certificate_hash=certificate_hash,
            anchor=anchor,
            bundle=bundle_check,
            failures=tuple(all_failures),
        )

    def _events_for_anchor(self, anchor: CommandAnchor) -> list[CommandEvent]:
        events = list(self._ledger._events)
        try:
            start = next(index for index, event in enumerate(events) if event.event_hash == anchor.from_event_hash)
        except StopIteration:
            return []
        try:
            # Search for end starting AT start, not from index 0. Anchors
            # are append-ordered (to_event_hash always > from_event_hash in
            # append order), so a to_event_hash appearing at index < start
            # is either a hash collision (sha256: impossible) or a forged
            # anchor pointing backwards. Refusing to slice backward avoids
            # silently over-claiming the range.
            end = next(
                start + offset
                for offset, event in enumerate(events[start:])
                if event.event_hash == anchor.to_event_hash
            )
        except StopIteration:
            return events[start:]
        return events[start : end + 1]


@dataclass(frozen=True, slots=True)
class GlobalChainVerification:
    """Bounded outcome of global event-chain verification."""

    event_count: int
    chain_intact: bool
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AnchorVerification:
    """Bounded outcome of one anchor's merkle + signature verification."""

    anchor_id: str
    anchor_present: bool
    merkle_root_valid: bool
    signature_valid: bool
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CertificateHashVerification:
    """Bounded outcome of recomputing a terminal certificate's content hash."""

    command_id: str
    certificate_present: bool
    certificate_id: str
    recomputed_certificate_id: str
    hash_matches: bool
    closure_binding_valid: bool
    failures: tuple[str, ...]

    @property
    def fully_verified(self) -> bool:
        """True iff zero structured failures."""
        return not self.failures


@dataclass(frozen=True, slots=True)
class ReplayStateVerification:
    """Bounded outcome of one command's state-replay verification."""

    command_id: str
    command_present: bool
    replayed_state: CommandState | None
    live_state: CommandState | None
    transition_chain_valid: bool
    states_match: bool
    event_count: int
    failures: tuple[str, ...]

    @property
    def fully_replayed(self) -> bool:
        """True iff zero structured failures."""
        return not self.failures


@dataclass(frozen=True, slots=True)
class TenantIsolationVerification:
    """Bounded outcome of one command's tenant-boundary check."""

    command_id: str
    command_present: bool
    expected_tenant_id: str
    event_tenant_mismatches: tuple[str, ...]
    certificate_tenant_mismatch: bool
    failures: tuple[str, ...]

    @property
    def fully_isolated(self) -> bool:
        """True iff zero structured failures."""
        return not self.failures


@dataclass(frozen=True, slots=True)
class FullVerification:
    """Aggregate report composing every verifier method run for one command."""

    command_id: str
    trace: "AuditTraceVerification"
    global_chain: "GlobalChainVerification"
    approval: "ApprovalChainVerification"
    tenant: "TenantIsolationVerification"
    replay: "ReplayStateVerification"
    certificate_hash: "CertificateHashVerification"
    anchor: "AnchorVerification | None"
    bundle: "TrustBundleVerification | None"
    failures: tuple[str, ...]

    @property
    def fully_verified(self) -> bool:
        """True iff every method that ran reported zero structured failures."""
        return not self.failures


@dataclass(frozen=True, slots=True)
class ApprovalChainVerification:
    """Bounded outcome of one command's approval-chain verification."""

    command_id: str
    chain_present: bool
    chain_status: ApprovalChainStatus | None
    approver_count: int
    approvers_unique: bool
    certificate_disposition: ClosureDisposition | None
    failures: tuple[str, ...]

    @property
    def fully_verified(self) -> bool:
        """True iff zero structured failures."""
        return not self.failures


@dataclass(frozen=True, slots=True)
class TrustBundleVerification:
    """Bounded outcome of a trust bundle's signature + ledger cross-reference."""

    bundle_id: str
    signature_valid: bool
    ledger_cross_reference_valid: bool
    failures: tuple[str, ...]

    @property
    def fully_verified(self) -> bool:
        """True iff signature is valid AND every cross-reference matches."""
        return self.signature_valid and self.ledger_cross_reference_valid


def _recompute_event_hash(event: CommandEvent) -> str:
    return canonical_hash({
        "command_id": event.command_id,
        "previous_state": event.previous_state.value,
        "next_state": event.next_state.value,
        "policy_version": event.policy_version,
        "risk_tier": event.risk_tier,
        "budget_decision": event.budget_decision,
        "approval_id": event.approval_id,
        "tool_name": event.tool_name,
        "input_hash": event.input_hash,
        "output_hash": event.output_hash,
        "trace_id": event.trace_id,
        "prev_event_hash": event.prev_event_hash,
        "timestamp": event.timestamp,
        "detail": event.detail,
    })
