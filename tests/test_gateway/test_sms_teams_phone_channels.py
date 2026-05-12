"""Channel adapter tests for the new SMS, Teams, and phone adapters.

Tests: signature verification, message parsing, send-payload shape.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.channels.phone import PhoneAdapter  # noqa: E402
from gateway.channels.sms import SmsAdapter  # noqa: E402
from gateway.channels.teams import TeamsAdapter  # noqa: E402


# ── SMS ──


def _twilio_signature(token: str, url: str, params: dict[str, str]) -> str:
    signed = url
    for key in sorted(params):
        signed += key + str(params[key])
    digest = hmac.new(token.encode("utf-8"), signed.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def test_sms_parse_message_returns_canonical_gateway_message() -> None:
    adapter = SmsAdapter(
        account_sid="AC123",
        auth_token="auth-token",
        sender="+15555550111",
        webhook_url="https://example.com/webhook/sms",
    )
    msg = adapter.parse_message({
        "From": "+15555550100",
        "To": "+15555550111",
        "Body": "hello",
        "MessageSid": "SM123",
        "NumMedia": "0",
    })
    assert msg is not None
    assert msg.channel == "sms"
    assert msg.sender_id == "+15555550100"
    assert msg.body == "hello"
    assert msg.message_id == "sms-SM123"
    assert msg.metadata["to"] == "+15555550111"


def test_sms_parse_message_returns_none_on_missing_sender() -> None:
    adapter = SmsAdapter(account_sid="AC123", auth_token="auth-token")
    assert adapter.parse_message({"Body": "hi", "MessageSid": "SM123"}) is None


def test_sms_verify_signature_accepts_valid_twilio_signature() -> None:
    adapter = SmsAdapter(
        account_sid="AC123",
        auth_token="auth-token",
        webhook_url="https://example.com/webhook/sms",
    )
    params = {"From": "+15555550100", "To": "+15555550111", "Body": "hello", "MessageSid": "SM123"}
    signature = _twilio_signature("auth-token", "https://example.com/webhook/sms", params)
    assert adapter.verify_signature("https://example.com/webhook/sms", params, signature) is True


def test_sms_verify_signature_rejects_bad_signature() -> None:
    adapter = SmsAdapter(
        account_sid="AC123",
        auth_token="auth-token",
        webhook_url="https://example.com/webhook/sms",
    )
    params = {"From": "+15555550100", "Body": "hello", "MessageSid": "SM123"}
    assert adapter.verify_signature("https://example.com/webhook/sms", params, "bogus") is False


def test_sms_send_payload_uses_form_encoded_messages_api() -> None:
    adapter = SmsAdapter(account_sid="AC123", auth_token="auth-token", sender="+15555550111")
    body = adapter.build_send_payload("+15555550100", "hello")
    assert "From=%2B15555550111" in body
    assert "To=%2B15555550100" in body
    assert "Body=hello" in body


# ── Teams ──


def test_teams_parse_message_returns_canonical_gateway_message() -> None:
    adapter = TeamsAdapter(access_token="teams-token", shared_secret="secret")
    msg = adapter.parse_message({
        "type": "message",
        "id": "act-1",
        "from": {"id": "user-1", "name": "Alice"},
        "conversation": {"id": "19:abcd@thread.v2"},
        "text": "hello",
    })
    assert msg is not None
    assert msg.channel == "teams"
    assert msg.sender_id == "user-1"
    assert msg.body == "hello"
    assert msg.message_id == "teams-act-1"
    assert msg.conversation_id == "19:abcd@thread.v2"


def test_teams_parse_message_skips_non_message_activities() -> None:
    adapter = TeamsAdapter(access_token="teams-token", shared_secret="secret")
    assert adapter.parse_message({
        "type": "conversationUpdate",
        "id": "act-2",
        "from": {"id": "user-1"},
        "text": "hi",
    }) is None


def test_teams_verify_signature_accepts_hmac_with_shared_secret() -> None:
    secret = "shared-secret"
    adapter = TeamsAdapter(access_token="teams-token", shared_secret=secret)
    body = b'{"type":"message"}'
    expected = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    assert adapter.verify_signature(body, expected) is True


def test_teams_verify_signature_rejects_bad_signature() -> None:
    adapter = TeamsAdapter(access_token="teams-token", shared_secret="shared-secret")
    assert adapter.verify_signature(b'{}', "sha256=bad") is False


def test_teams_verify_signature_rejects_when_secret_unset() -> None:
    adapter = TeamsAdapter(access_token="teams-token", shared_secret="")
    assert adapter.verify_signature(b'{}', "sha256=anything") is False


def test_teams_send_payload_uses_graph_chat_message_shape() -> None:
    adapter = TeamsAdapter(access_token="teams-token", shared_secret="secret")
    payload = adapter.build_send_payload("19:abcd@thread.v2", "hello team")
    assert payload == {"body": {"contentType": "text", "content": "hello team"}}


# ── Phone (Twilio Voice) ──


def test_phone_parse_message_returns_event_with_metadata() -> None:
    adapter = PhoneAdapter(
        account_sid="AC123",
        auth_token="auth-token",
        caller_id="+15555550111",
        webhook_url="https://example.com/webhook/phone",
    )
    msg = adapter.parse_message({
        "CallSid": "CA123",
        "From": "+15555550100",
        "To": "+15555550111",
        "CallStatus": "ringing",
        "SpeechResult": "",
        "Digits": "",
    })
    assert msg is not None
    assert msg.channel == "phone"
    assert msg.sender_id == "+15555550100"
    assert msg.conversation_id == "CA123"
    assert msg.metadata["call_sid"] == "CA123"
    assert msg.metadata["call_status"] == "ringing"
    assert msg.body == "ringing"


def test_phone_parse_message_prefers_speech_result_over_status() -> None:
    adapter = PhoneAdapter(account_sid="AC123", auth_token="auth-token")
    msg = adapter.parse_message({
        "CallSid": "CA123",
        "From": "+15555550100",
        "CallStatus": "in-progress",
        "SpeechResult": "schedule appointment",
        "Digits": "",
    })
    assert msg is not None
    assert msg.body == "schedule appointment"


def test_phone_verify_signature_accepts_valid_twilio_signature() -> None:
    adapter = PhoneAdapter(
        account_sid="AC123",
        auth_token="auth-token",
        webhook_url="https://example.com/webhook/phone",
    )
    params = {
        "CallSid": "CA123",
        "From": "+15555550100",
        "To": "+15555550111",
        "CallStatus": "ringing",
    }
    signature = _twilio_signature("auth-token", "https://example.com/webhook/phone", params)
    assert adapter.verify_signature("https://example.com/webhook/phone", params, signature) is True


def test_phone_build_say_twiml_escapes_xml_payload() -> None:
    adapter = PhoneAdapter(account_sid="AC123", auth_token="auth-token")
    twiml = adapter.build_say_twiml('Hello <Bob & "Jane">')
    assert (
        twiml
        == "<Response><Say>Hello &lt;Bob &amp; &quot;Jane&quot;&gt;</Say></Response>"
    )
