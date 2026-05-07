"""Document production parser tests.

Purpose: prove production document parser families expose deterministic parser
contracts without relying on external effects.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: gateway.document_production_parsers.
Invariants:
  - PPTX extraction is deterministic Open XML parsing.
  - PPTX parser availability does not require an external provider.
  - Parser receipts expose production parser identity.
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path


_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
_MCOI_ROOT = _ROOT / "mcoi"
if str(_MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(_MCOI_ROOT))

from gateway.document_production_parsers import ProductionPPTXParser  # noqa: E402


def test_pptx_parser_uses_stdlib_open_xml_extraction() -> None:
    parser = ProductionPPTXParser()
    content = _pptx_bytes(
        {
            "ppt/slides/slide1.xml": (
                "<p:sld xmlns:p='urn:p' xmlns:a='urn:a'>"
                "<p:cSld><p:spTree><p:sp><p:txBody>"
                "<a:p><a:r><a:t>Governed slide title</a:t></a:r></a:p>"
                "<a:p><a:r><a:t>Evidence line</a:t></a:r></a:p>"
                "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
            ),
            "ppt/slides/slide2.xml": (
                "<p:sld xmlns:p='urn:p' xmlns:a='urn:a'>"
                "<p:cSld><p:spTree><p:sp><p:txBody>"
                "<a:p><a:r><a:t>Second slide</a:t></a:r></a:p>"
                "</p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
            ),
        }
    )

    output = parser.parse(
        artifact_id="artifact-pptx-1",
        filename="deck.pptx",
        content=content,
    )

    assert parser.available is True
    assert parser.parser_id() == "production-pptx"
    assert output.parser_id == "production-pptx"
    assert output.page_count == 2
    assert output.word_count == 7
    assert "Governed slide title" in output.text_content
    assert "Evidence line" in output.text_content
    assert "Second slide" in output.text_content


def _pptx_bytes(slides: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        for name, content in slides.items():
            archive.writestr(name, content)
    return buffer.getvalue()
