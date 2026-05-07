"""Worker contract import tests without the HTTP dependency.

Purpose: prove governed worker request, policy, execution, and receipt
contracts remain importable for CLI receipt producers when FastAPI is absent.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: gateway browser, voice, and email/calendar worker contracts.
Invariants:
  - Missing FastAPI does not hide typed fail-closed worker receipts.
  - HTTP app creation still fails explicitly when FastAPI is absent.
  - Non-HTTP contracts remain usable by adapter evidence producers.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent.parent


def test_worker_contracts_import_without_fastapi() -> None:
    script = r"""
import importlib.abc
import json
import sys


class BlockFastapi(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "fastapi" or fullname.startswith("fastapi."):
            raise ModuleNotFoundError("fastapi blocked for contract import test")
        return None


sys.meta_path.insert(0, BlockFastapi())

from gateway import browser_worker, email_calendar_worker, voice_worker

browser_request = browser_worker.BrowserActionRequest(
    request_id="browser-no-fastapi",
    tenant_id="tenant-1",
    capability_id="browser.extract_text",
    action="browser.extract_text",
    url="https://docs.mullusi.com/",
)
browser_response = browser_worker.execute_browser_request(
    browser_request,
    adapter=browser_worker.UnavailableBrowserAdapter(),
    policy=browser_worker.BrowserWorkerPolicy(),
)

voice_request = voice_worker.VoiceActionRequest(
    request_id="voice-no-fastapi",
    tenant_id="tenant-1",
    capability_id="voice.speech_to_text",
    action="voice.speech_to_text",
    session_id="voice-session-1",
    audio_base64="dm9pY2UtYnl0ZXM=",
)
voice_response = voice_worker.execute_voice_request(
    voice_request,
    adapter=voice_worker.UnavailableVoiceAdapter(),
    policy=voice_worker.VoiceWorkerPolicy(),
)

email_request = email_calendar_worker.EmailCalendarActionRequest(
    request_id="email-no-fastapi",
    tenant_id="tenant-1",
    capability_id="email.search",
    action="email.search",
    connector_id="gmail",
    query="newer_than:1d",
)
email_response = email_calendar_worker.execute_email_calendar_request(
    email_request,
    adapter=email_calendar_worker.UnavailableEmailCalendarAdapter(),
    policy=email_calendar_worker.EmailCalendarWorkerPolicy(),
)

errors = []
for label, factory in (
    ("browser", browser_worker.create_browser_worker_app),
    ("voice", voice_worker.create_voice_worker_app),
    ("email", email_calendar_worker.create_email_calendar_worker_app),
):
    try:
        factory(signing_secret="secret")
    except RuntimeError as exc:
        errors.append(f"{label}:{exc}")

print(json.dumps({
    "browser_app_is_none": browser_worker.app is None,
    "browser_status": browser_response.status,
    "browser_receipt_status": browser_response.receipt.verification_status,
    "voice_app_is_none": voice_worker.app is None,
    "voice_status": voice_response.status,
    "voice_receipt_status": voice_response.receipt.verification_status,
    "email_app_is_none": email_calendar_worker.app is None,
    "email_status": email_response.status,
    "email_receipt_status": email_response.receipt.verification_status,
    "http_app_errors": errors,
}, sort_keys=True))
"""
    environment = os.environ.copy()
    pythonpath_parts = [str(_ROOT), str(_ROOT / "mcoi")]
    existing_pythonpath = environment.get("PYTHONPATH", "")
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    environment["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
        timeout=30,
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0, completed.stderr
    assert payload["browser_app_is_none"] is True
    assert payload["voice_app_is_none"] is True
    assert payload["email_app_is_none"] is True
    assert payload["browser_status"] == "failed"
    assert payload["browser_receipt_status"] == "failed"
    assert payload["voice_status"] == "failed"
    assert payload["voice_receipt_status"] == "failed"
    assert payload["email_status"] == "failed"
    assert payload["email_receipt_status"] == "failed"
    assert len(payload["http_app_errors"]) == 3
