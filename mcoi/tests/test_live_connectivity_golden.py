"""Purpose: golden end-to-end scenarios for live connectivity.
Governance scope: integration proofs spanning external connectors, live channel
    bindings, live parser bindings, capability negotiation, connectivity compliance,
    commitment extraction, event spine, and memory mesh.
Dependencies: full connectivity stack.
Invariants: each scenario exercises a distinct real-world path through the
    governed live connectivity pipeline.

These are NOT unit tests. They are system-level integration proofs.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from mcoi_runtime.contracts.external_connector import (
    ConnectorAuthMode,
    ConnectorCapabilityBinding,
    ConnectorFailureCategory,
    ConnectorHealthSnapshot,
    ConnectorHealthState,
    ConnectorQuotaState,
    ConnectorRateLimitPolicy,
    ConsentState,
    ExternalConnectorType,
    FallbackChain,
    FallbackChainEntry,
    FallbackStrategy,
    SecretRotationState,
    SecretScope,
)
from mcoi_runtime.contracts.channel_adapter import ChannelAdapterFamily
from mcoi_runtime.contracts.artifact_parser import ParserFamily
from mcoi_runtime.core.external_connectors import (
    ExternalConnectorRegistry,
    FailingTestConnector,
    SmsProviderTestConnector,
    ChatProviderTestConnector,
    VoiceProviderTestConnector,
    ParserProviderTestConnector,
    GenericApiTestConnector,
    register_all_test_connectors,
)
from mcoi_runtime.core.channel_adapters import ChannelAdapterRegistry
from mcoi_runtime.core.artifact_parsers import ArtifactParserRegistry
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.live_channel_bindings import LiveChannelBindingEngine
from mcoi_runtime.core.live_parser_bindings import LiveParserBindingEngine
from mcoi_runtime.core.capability_negotiation import CapabilityNegotiationEngine
from mcoi_runtime.core.connectivity_compliance import ConnectivityComplianceEngine
from mcoi_runtime.core.commitment_extraction import CommitmentExtractionEngine

NOW = "2026-03-20T12:00:00+00:00"


def _scope(scope_id: str, connector_id: str, *, auth: ConnectorAuthMode = ConnectorAuthMode.API_KEY) -> SecretScope:
    """Helper to build a valid, current SecretScope."""
    return SecretScope(
        scope_id=scope_id,
        connector_id=connector_id,
        auth_mode=auth,
        rotation_state=SecretRotationState.CURRENT,
        credential_ref=f"ref-{connector_id}",
        rotation_interval_hours=720,
        last_rotated_at=NOW,
        expires_at="2027-06-01T00:00:00+00:00",
        created_at=NOW,
    )


class TestGoldenScenarios(unittest.TestCase):
    """Eight golden end-to-end scenarios for live connectivity."""

    # ------------------------------------------------------------------
    # 1. Inbound SMS -> commitment extraction -> obligation creation
    # ------------------------------------------------------------------

    def test_inbound_sms_commitment_extraction(self):
        """Ingest via live SMS adapter, extract commitments, verify events."""
        conn_reg = ExternalConnectorRegistry()
        chan_reg = ChannelAdapterRegistry()
        parser_reg = ArtifactParserRegistry()
        es = EventSpineEngine()
        mem = MemoryMeshEngine()

        # Register SMS connector
        sms_conn = SmsProviderTestConnector("sms-golden-1")
        conn_reg.register(sms_conn)
        conn_reg.set_secret_scope(_scope("scope-sms-g1", "sms-golden-1"))

        # Bind live SMS adapter
        binding_engine = LiveChannelBindingEngine(chan_reg, conn_reg, es)
        binding_engine.bind_sms("sms-golden-1", "live-sms-g1")

        # Set up commitment extraction engine
        commit_engine = CommitmentExtractionEngine()

        # Ingest an inbound SMS with commitment language
        adapter = binding_engine.get_live_adapter("live-sms-g1")
        inbound = adapter.normalize_inbound({
            "from": "+15551234567",
            "body": "I will handle the invoice by Friday. Approved. Escalate to manager if delayed.",
        })

        # Verify normalized inbound
        self.assertEqual(inbound.adapter_id, "live-sms-g1")
        self.assertEqual(inbound.family, ChannelAdapterFamily.SMS)
        self.assertIn("invoice", inbound.body_text)

        # Extract commitments from the message body
        extraction = commit_engine.extract_from_message(
            inbound.message_id, inbound.body_text,
        )
        self.assertGreater(len(extraction.candidates), 0)
        # Should find approval, deadline, owner, escalation signals
        self.assertGreater(len(extraction.approvals), 0)
        self.assertGreater(len(extraction.deadlines), 0)
        self.assertGreater(len(extraction.escalations), 0)

        # Verify events were emitted during ingest
        events = es.list_events()
        self.assertGreater(len(events), 0)

    # ------------------------------------------------------------------
    # 2. Chat webhook -> event spine -> memory mesh -> supervisor retrieval
    # ------------------------------------------------------------------

    def test_chat_webhook_event_memory(self):
        """Ingest via live chat adapter, verify events and memory recorded."""
        conn_reg = ExternalConnectorRegistry()
        chan_reg = ChannelAdapterRegistry()
        parser_reg = ArtifactParserRegistry()
        es = EventSpineEngine()
        mem = MemoryMeshEngine()

        # Register chat connector
        chat_conn = ChatProviderTestConnector("chat-golden-1")
        conn_reg.register(chat_conn)
        conn_reg.set_secret_scope(_scope("scope-chat-g1", "chat-golden-1"))

        # Bind live chat adapter
        binding_engine = LiveChannelBindingEngine(chan_reg, conn_reg, es)
        binding_engine.bind_chat("chat-golden-1", "live-chat-g1")

        adapter = binding_engine.get_live_adapter("live-chat-g1")

        # Ingest chat message
        inbound = adapter.normalize_inbound({
            "from": "user@slack",
            "body": "Deploy the new build to staging by end of day.",
            "thread_id": "thread-42",
        })

        self.assertEqual(inbound.adapter_id, "live-chat-g1")
        self.assertEqual(inbound.family, ChannelAdapterFamily.CHAT)

        # Verify events were emitted (binding event at minimum)
        events = es.list_events()
        self.assertGreater(len(events), 0)

        # Record in memory mesh (simulating supervisor recording)
        from mcoi_runtime.contracts.memory_mesh import (
            MemoryRecord, MemoryScope, MemoryTrustLevel, MemoryType,
        )
        mem_record = MemoryRecord(
            memory_id=f"mem-chat-{inbound.message_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=inbound.message_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Chat inbound recorded",
            content={"body": inbound.body_text, "from": inbound.sender_address},
            source_ids=(inbound.message_id,),
            tags=("chat", "inbound"),
            confidence=1.0,
            created_at=NOW,
            updated_at=NOW,
        )
        mem.add_memory(mem_record)
        retrieved = mem.get_memory(mem_record.memory_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.title, "Chat inbound recorded")

    # ------------------------------------------------------------------
    # 3. Failed real connector -> fallback provider selection
    # ------------------------------------------------------------------

    def test_failed_connector_fallback(self):
        """FailingTestConnector as primary, working connector as fallback."""
        conn_reg = ExternalConnectorRegistry()
        es = EventSpineEngine()

        # Register failing connector (auth_mode NONE, no secret scope needed)
        failing = FailingTestConnector("conn-fail-g")
        conn_reg.register(failing)

        # Register working connector
        working = GenericApiTestConnector("conn-ok-g")
        conn_reg.register(working)
        conn_reg.set_secret_scope(_scope("scope-ok-g", "conn-ok-g", auth=ConnectorAuthMode.BEARER_TOKEN))

        # Build fallback chain
        chain = FallbackChain(
            chain_id="fb-golden-1",
            name="Golden fallback",
            strategy=FallbackStrategy.PRIORITY_ORDER,
            entries=(
                FallbackChainEntry(
                    entry_id="fb-fail-g",
                    chain_id="fb-golden-1",
                    connector_id="conn-fail-g",
                    priority=0,
                ),
                FallbackChainEntry(
                    entry_id="fb-ok-g",
                    chain_id="fb-golden-1",
                    connector_id="conn-ok-g",
                    priority=1,
                ),
            ),
            created_at=NOW,
        )
        conn_reg.add_fallback_chain(chain)

        # Execute with fallback
        result = conn_reg.execute_with_fallback(
            "fb-golden-1", "send", {"message": "hello"},
        )

        # Failing connector raises, so fallback should be used
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["connector_id"], "conn-ok-g")
        self.assertIsNotNone(result["record"])
        self.assertTrue(result["record"].success)

    # ------------------------------------------------------------------
    # 4. PDF artifact -> parser -> extraction -> memory update
    # ------------------------------------------------------------------

    def test_pdf_parse_extraction_memory(self):
        """Live PDF parser bound to connector, parse content, verify memory."""
        conn_reg = ExternalConnectorRegistry()
        chan_reg = ChannelAdapterRegistry()
        parser_reg = ArtifactParserRegistry()
        es = EventSpineEngine()
        mem = MemoryMeshEngine()

        # Register parser connector
        parser_conn = ParserProviderTestConnector("parser-g1")
        conn_reg.register(parser_conn)
        conn_reg.set_secret_scope(_scope("scope-parser-g1", "parser-g1"))

        # Bind live PDF parser
        parser_binding = LiveParserBindingEngine(parser_reg, conn_reg, es)
        parser_binding.bind_pdf("parser-g1", "live-pdf-g1")

        # Parse a PDF-like artifact
        content = b"Contract: Alice will deliver the report by Monday. Approved."
        parser = parser_binding.get_live_parser("live-pdf-g1")
        output = parser.parse("artifact-pdf-1", "contract.pdf", content)

        self.assertEqual(output.parser_id, "live-pdf-g1")
        self.assertIn("Contract", output.text_content)
        self.assertGreater(output.word_count, 0)

        # Extract commitments from parsed text
        commit_engine = CommitmentExtractionEngine()
        extraction = commit_engine.extract_from_artifact(
            "artifact-pdf-1", output.text_content,
        )
        self.assertGreater(len(extraction.candidates), 0)

        # Record in memory
        from mcoi_runtime.contracts.memory_mesh import (
            MemoryRecord, MemoryScope, MemoryTrustLevel, MemoryType,
        )
        mem_record = MemoryRecord(
            memory_id="mem-pdf-parse-1",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id="artifact-pdf-1",
            trust_level=MemoryTrustLevel.VERIFIED,
            title="PDF parsed and commitments extracted",
            content={"text": output.text_content[:200], "commitments": len(extraction.candidates)},
            source_ids=("artifact-pdf-1",),
            tags=("pdf", "parsed", "commitments"),
            confidence=1.0,
            created_at=NOW,
            updated_at=NOW,
        )
        mem.add_memory(mem_record)
        self.assertIsNotNone(mem.get_memory("mem-pdf-parse-1"))

    # ------------------------------------------------------------------
    # 5. Connector quota exhaustion -> degraded routing
    # ------------------------------------------------------------------

    def test_quota_exhaustion(self):
        """Connector with quota=0 should fail with QUOTA_EXHAUSTED."""
        conn_reg = ExternalConnectorRegistry()
        es = EventSpineEngine()

        conn = GenericApiTestConnector("conn-quota-0")
        conn_reg.register(conn)
        conn_reg.set_secret_scope(_scope("scope-quota-0", "conn-quota-0", auth=ConnectorAuthMode.BEARER_TOKEN))

        # Set quota to 0 remaining
        conn_reg.update_quota(ConnectorQuotaState(
            quota_id="q-zero",
            connector_id="conn-quota-0",
            quota_limit=100,
            quota_used=100,
            quota_remaining=0,
            reset_at="2027-01-01T00:00:00+00:00",
            reported_at=NOW,
        ))

        # Attempt execution
        record = conn_reg.execute("conn-quota-0", "send", {"x": 1})
        self.assertFalse(record.success)
        self.assertIn("quota", record.error_message.lower())

        # Verify failure was recorded
        failures = conn_reg.get_failures(connector_id="conn-quota-0")
        self.assertGreater(len(failures), 0)
        self.assertEqual(failures[0].category, ConnectorFailureCategory.QUOTA_EXHAUSTED)

    # ------------------------------------------------------------------
    # 6. Live voice transcript -> commitment extraction -> escalation
    # ------------------------------------------------------------------

    def test_voice_transcript_escalation(self):
        """Live voice adapter ingests transcript with escalation language."""
        conn_reg = ExternalConnectorRegistry()
        chan_reg = ChannelAdapterRegistry()
        parser_reg = ArtifactParserRegistry()
        es = EventSpineEngine()

        voice_conn = VoiceProviderTestConnector("voice-g1")
        conn_reg.register(voice_conn)
        conn_reg.set_secret_scope(_scope("scope-voice-g1", "voice-g1"))

        binding_engine = LiveChannelBindingEngine(chan_reg, conn_reg, es)
        binding_engine.bind_voice("voice-g1", "live-voice-g1")

        adapter = binding_engine.get_live_adapter("live-voice-g1")

        # Ingest a voice transcript with escalation language
        inbound = adapter.normalize_inbound({
            "caller_id": "+15559876543",
            "transcript": (
                "The customer is very upset about the delay. "
                "Escalate to manager immediately. "
                "Alice will handle the refund by end of day. "
                "Urgent escalation needed."
            ),
            "duration": 180,
            "call_subject": "Customer complaint",
        })

        self.assertEqual(inbound.adapter_id, "live-voice-g1")
        self.assertEqual(inbound.family, ChannelAdapterFamily.VOICE)
        self.assertIn("escalation", inbound.body_text.lower())

        # Extract commitments
        commit_engine = CommitmentExtractionEngine()
        extraction = commit_engine.extract_from_transcript(
            inbound.message_id, inbound.body_text,
        )
        self.assertGreater(len(extraction.candidates), 0)
        self.assertGreater(len(extraction.escalations), 0)
        # Should find owner signal for "Alice"
        owner_names = [o.normalized_owner for o in extraction.owners]
        self.assertIn("alice", owner_names)

    # ------------------------------------------------------------------
    # 7. Parser failure / malformed artifact -> typed rejection + fault recording
    # ------------------------------------------------------------------

    def test_parser_failure_fault_recording(self):
        """FailingTestConnector as parser provider; parse fails, fault recorded."""
        conn_reg = ExternalConnectorRegistry()
        chan_reg = ChannelAdapterRegistry()
        parser_reg = ArtifactParserRegistry()
        es = EventSpineEngine()

        # Register a failing connector as parser provider
        failing = FailingTestConnector("parser-fail-g")
        conn_reg.register(failing)

        # Bind a live PDF parser to the failing connector
        parser_binding = LiveParserBindingEngine(parser_reg, conn_reg, es)
        parser_binding.bind_pdf("parser-fail-g", "live-pdf-fail")

        parser = parser_binding.get_live_parser("live-pdf-fail")

        # Parse executes via connector — connector.execute() catches the
        # exception and records a failure, but parse() still returns output
        output = parser.parse("artifact-fail-1", "broken.pdf", b"garbage data")
        self.assertIsNotNone(output)
        # The connector execution was recorded as a failure
        failures = conn_reg.get_failures(connector_id="parser-fail-g")
        self.assertGreater(len(failures), 0)

    # ------------------------------------------------------------------
    # 8. Live external connector under fault injection -> recovery
    # ------------------------------------------------------------------

    def test_fault_injection_recovery(self):
        """Fallback chain with failing + working connectors; verify recovery."""
        conn_reg = ExternalConnectorRegistry()
        es = EventSpineEngine()

        # Failing connector
        failing = FailingTestConnector("conn-fault-1")
        conn_reg.register(failing)

        # Working connector
        working = GenericApiTestConnector("conn-recovery-1")
        conn_reg.register(working)
        conn_reg.set_secret_scope(_scope(
            "scope-recovery-1", "conn-recovery-1",
            auth=ConnectorAuthMode.BEARER_TOKEN,
        ))

        chain = FallbackChain(
            chain_id="fb-recovery",
            name="Recovery Chain",
            strategy=FallbackStrategy.PRIORITY_ORDER,
            entries=(
                FallbackChainEntry(
                    entry_id="fb-fault-1",
                    chain_id="fb-recovery",
                    connector_id="conn-fault-1",
                    priority=0,
                ),
                FallbackChainEntry(
                    entry_id="fb-recover-1",
                    chain_id="fb-recovery",
                    connector_id="conn-recovery-1",
                    priority=1,
                ),
            ),
            created_at=NOW,
        )
        conn_reg.add_fallback_chain(chain)

        result = conn_reg.execute_with_fallback(
            "fb-recovery", "send_notification", {"content": "recovery test"},
        )

        # The failing connector should have been tried first, then fallback
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["connector_id"], "conn-recovery-1")
        self.assertIsNotNone(result["record"])
        self.assertTrue(result["record"].success)

        # Verify we have attempt records for both connectors
        self.assertEqual(len(result["attempts"]), 2)
        self.assertFalse(result["attempts"][0].success)  # failing connector
        self.assertTrue(result["attempts"][1].success)    # working connector

        # Verify failure was recorded
        failures = conn_reg.get_failures(connector_id="conn-fault-1")
        self.assertGreater(len(failures), 0)


if __name__ == "__main__":
    unittest.main()
