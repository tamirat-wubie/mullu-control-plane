"""Tests for governed adapter worker dependency packaging.

Purpose: ensure browser, document, voice, and communication runtime
dependencies are packaged for isolated workers without making the default pilot
stack depend on them.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: mcoi/pyproject.toml, Dockerfile, and docker-compose.yml.
Invariants:
  - Worker dependencies are named in explicit optional dependency groups.
  - Playwright browser binaries are installed only when worker dependencies are installed.
  - Adapter workers are compose-profiled and do not block the default gateway startup path.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def test_worker_dependency_extras_are_declared() -> None:
    pyproject = tomllib.loads((_ROOT / "mcoi" / "pyproject.toml").read_text(encoding="utf-8"))
    optional_dependencies = pyproject["project"]["optional-dependencies"]

    assert "playwright>=1.51" in optional_dependencies["browser-worker"]
    assert "pypdf>=5.0" in optional_dependencies["document-worker"]
    assert "python-docx>=1.1" in optional_dependencies["document-worker"]
    assert "openpyxl>=3.1" in optional_dependencies["document-worker"]
    assert "python-pptx>=1.0" in optional_dependencies["document-worker"]
    assert "openai>=1.0" in optional_dependencies["voice-worker"]
    assert "playwright>=1.51" in optional_dependencies["worker"]
    assert "openai>=1.0" in optional_dependencies["all"]


def test_dockerfile_packages_worker_dependencies_with_guarded_browser_install() -> None:
    dockerfile = (_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "ARG MULLU_INSTALL_WORKER_DEPS=true" in dockerfile
    assert "ARG MULLU_INSTALL_PLAYWRIGHT_BROWSERS=true" in dockerfile
    assert 'pip install --no-cache-dir -e "mcoi[all]"' in dockerfile
    assert 'pip install --no-cache-dir -e "mcoi[persistence,encryption,gateway,voice-worker]" anthropic' in dockerfile
    assert '[ "$MULLU_INSTALL_WORKER_DEPS" = "true" ] && [ "$MULLU_INSTALL_PLAYWRIGHT_BROWSERS" = "true" ]' in dockerfile
    assert "python -m playwright install --with-deps chromium" in dockerfile
    assert "ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright" in dockerfile
    assert "EXPOSE 8000 8001 8010 8020 8030 8040 8050" in dockerfile


def test_compose_profiles_adapter_workers_without_gateway_dependency() -> None:
    compose = (_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    gateway_block = _service_block(compose, "gateway")
    gateway_worker_block = _service_block(compose, "gateway-worker")
    browser_block = _service_block(compose, "browser-worker")
    document_block = _service_block(compose, "document-worker")
    voice_block = _service_block(compose, "voice-worker")
    email_calendar_block = _service_block(compose, "email-calendar-worker")

    assert "browser-worker-net:" in compose
    assert 'profiles: ["adapter-workers"]' in browser_block
    assert 'profiles: ["adapter-workers"]' in document_block
    assert 'profiles: ["adapter-workers"]' in voice_block
    assert 'profiles: ["adapter-workers"]' in email_calendar_block
    assert '"gateway.browser_worker:app"' in browser_block
    assert '"gateway.document_worker:app"' in document_block
    assert '"gateway.voice_worker:app"' in voice_block
    assert '"gateway.email_calendar_worker:app"' in email_calendar_block
    assert "MULLU_BROWSER_WORKER_SECRET" in browser_block
    assert "MULLU_DOCUMENT_WORKER_ADAPTER: \"production\"" in document_block
    assert "MULLU_VOICE_WORKER_ADAPTER: \"openai\"" in voice_block
    assert "OPENAI_API_KEY" in voice_block
    assert "MULLU_EMAIL_CALENDAR_WORKER_SECRET" in email_calendar_block
    assert "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER: \"production\"" in email_calendar_block
    assert "GMAIL_ACCESS_TOKEN" in email_calendar_block
    assert "GOOGLE_CALENDAR_ACCESS_TOKEN" in email_calendar_block
    assert "MICROSOFT_GRAPH_ACCESS_TOKEN" in email_calendar_block
    assert 'MULLU_BROWSER_WORKER_URL: "${MULLU_BROWSER_WORKER_URL:-}"' in gateway_block
    assert 'MULLU_DOCUMENT_WORKER_URL: "${MULLU_DOCUMENT_WORKER_URL:-}"' in gateway_block
    assert 'MULLU_VOICE_WORKER_URL: "${MULLU_VOICE_WORKER_URL:-}"' in gateway_block
    assert 'MULLU_EMAIL_CALENDAR_WORKER_URL: "${MULLU_EMAIL_CALENDAR_WORKER_URL:-}"' in gateway_block
    assert 'MULLU_BROWSER_WORKER_SECRET: "${MULLU_BROWSER_WORKER_SECRET:-}"' in gateway_block
    assert 'MULLU_DOCUMENT_WORKER_SECRET: "${MULLU_DOCUMENT_WORKER_SECRET:-}"' in gateway_block
    assert 'MULLU_VOICE_WORKER_SECRET: "${MULLU_VOICE_WORKER_SECRET:-}"' in gateway_block
    assert 'MULLU_EMAIL_CALENDAR_WORKER_SECRET: "${MULLU_EMAIL_CALENDAR_WORKER_SECRET:-}"' in gateway_block
    assert "\n      browser-worker:\n" not in gateway_block
    assert "\n      document-worker:\n" not in gateway_block
    assert "\n      voice-worker:\n" not in gateway_block
    assert "\n      email-calendar-worker:\n" not in gateway_block
    assert "\n      browser-worker:\n" not in gateway_worker_block
    assert "\n      document-worker:\n" not in gateway_worker_block
    assert "\n      voice-worker:\n" not in gateway_worker_block
    assert "\n      email-calendar-worker:\n" not in gateway_worker_block


def _service_block(compose: str, service_name: str) -> str:
    lines = compose.splitlines()
    start = next(index for index, line in enumerate(lines) if line == f"  {service_name}:")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            end = index
            break
    return "\n".join(lines[start:end])
