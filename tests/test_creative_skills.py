"""Creative Skills Tests — Document gen, data analysis, image gen, translation."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pytest  # noqa: E402
from skills.creative.document_gen import (  # noqa: E402
    DocumentGenerator, DocumentTemplate, DocumentType,
    BUILTIN_TEMPLATES, GeneratedDocument,
)
from skills.creative.data_analysis import analyze_csv, analyze_key_value  # noqa: E402
from skills.creative.image_gen import (  # noqa: E402
    GovernedImageGenerator, StubImageProvider,
)
from skills.creative.translation import (  # noqa: E402
    build_translation_prompt, build_summarization_prompt,
    parse_translation_result, parse_summarization_result,
    SUPPORTED_LANGUAGES,
)


# ═══ Document Generation ═══


class TestDocumentGenerator:
    def test_generate_invoice(self):
        gen = DocumentGenerator()
        doc = gen.generate("invoice", {
            "invoice_number": "INV-001",
            "date": "2026-04-01",
            "from_name": "Mullu Corp",
            "to_name": "Client Inc",
            "description": "Consulting services",
            "amount": "5,000.00",
            "currency": "USD",
        }, tenant_id="t1", identity_id="u1")
        assert isinstance(doc, GeneratedDocument)
        assert "INV-001" in doc.body
        assert "Mullu Corp" in doc.body
        assert doc.content_hash != ""
        assert doc.tenant_id == "t1"

    def test_generate_memo(self):
        gen = DocumentGenerator()
        doc = gen.generate("memo", {
            "to": "Engineering Team",
            "from_name": "CTO",
            "date": "2026-04-01",
            "subject": "Q2 Priorities",
            "body": "Focus on governance and financial features.",
        })
        assert "Q2 Priorities" in doc.body
        assert doc.doc_type == DocumentType.MEMO

    def test_missing_required_field_raises(self):
        gen = DocumentGenerator()
        with pytest.raises(ValueError, match="missing required"):
            gen.generate("invoice", {"invoice_number": "1"})

    def test_unknown_template_raises(self):
        gen = DocumentGenerator()
        with pytest.raises(ValueError, match="template not found"):
            gen.generate("nonexistent", {})

    def test_builtin_templates_exist(self):
        assert "invoice" in BUILTIN_TEMPLATES
        assert "memo" in BUILTIN_TEMPLATES
        assert "receipt" in BUILTIN_TEMPLATES
        assert "summary" in BUILTIN_TEMPLATES

    def test_content_hash_deterministic(self):
        gen = DocumentGenerator()
        fields = {"to": "A", "from_name": "B", "date": "C", "subject": "D", "body": "E"}
        d1 = gen.generate("memo", fields)
        d2 = gen.generate("memo", fields)
        assert d1.content_hash == d2.content_hash

    def test_generate_from_llm(self):
        gen = DocumentGenerator()
        doc = gen.generate_from_llm(
            DocumentType.REPORT, "write a report",
            "This is the AI-generated report content.",
            tenant_id="t1",
        )
        assert doc.template_id == "llm-generated"
        assert "AI-generated" in doc.body

    def test_generated_count(self):
        gen = DocumentGenerator()
        assert gen.generated_count == 0
        gen.generate("memo", {"to": "A", "from_name": "B", "date": "C", "subject": "D", "body": "E"})
        assert gen.generated_count == 1

    def test_custom_template(self):
        gen = DocumentGenerator()
        gen.register_template(DocumentTemplate(
            template_id="custom", name="Custom", doc_type="custom",
            body_template="Hello {name}!", required_fields=("name",),
        ))
        doc = gen.generate("custom", {"name": "World"})
        assert doc.body == "Hello World!"


# ═══ Data Analysis ═══


class TestDataAnalysis:
    def test_analyze_simple_csv(self):
        csv_data = "name,age,score\nAlice,30,95\nBob,25,88\nCarol,35,92\n"
        result = analyze_csv(csv_data)
        assert result.success
        assert result.row_count == 3
        assert result.column_count == 3

    def test_numeric_detection(self):
        csv_data = "id,value\n1,100\n2,200\n3,300\n"
        result = analyze_csv(csv_data)
        value_col = next(c for c in result.columns if c.name == "value")
        assert value_col.data_type == "numeric"
        assert value_col.mean == 200.0

    def test_text_detection(self):
        csv_data = "name,city\nAlice,NYC\nBob,LA\n"
        result = analyze_csv(csv_data)
        name_col = next(c for c in result.columns if c.name == "name")
        assert name_col.data_type == "text"

    def test_insights_generated(self):
        csv_data = "id,status\n1,active\n2,active\n3,active\n4,active\n5,active\n6,active\n"
        result = analyze_csv(csv_data)
        assert len(result.insights) >= 1  # "status has only one unique value"

    def test_empty_csv(self):
        result = analyze_csv("")
        assert not result.success

    def test_key_value_analysis(self):
        result = analyze_key_value({"name": "Alice", "age": "30", "balance": "1234.56"})
        assert result.success
        assert result.column_count == 3

    def test_summary_present(self):
        csv_data = "a,b\n1,2\n3,4\n"
        result = analyze_csv(csv_data)
        assert "rows" in result.summary


# ═══ Image Generation ═══


class TestImageGeneration:
    def test_stub_provider(self):
        provider = StubImageProvider()
        result = provider.generate("A sunset over mountains")
        assert result.success
        assert result.image_url.startswith("https://")
        assert result.cost > 0

    def test_governed_generator(self):
        gen = GovernedImageGenerator(provider=StubImageProvider())
        result = gen.generate("A happy cat")
        assert result.success
        assert gen.generated_count == 1
        assert gen.total_cost > 0

    def test_content_safety_blocks_prompt(self):
        class MockSafety:
            def evaluate(self, text):
                return type("R", (), {"verdict": type("V", (), {"value": "blocked"})(), "reason": "unsafe"})()
        gen = GovernedImageGenerator(provider=StubImageProvider(), content_safety=MockSafety())
        result = gen.generate("Generate something unsafe")
        assert not result.success
        assert "content safety" in result.error

    def test_prompt_hash_in_result(self):
        provider = StubImageProvider()
        result = provider.generate("Test prompt")
        assert result.prompt_hash != ""
        assert len(result.prompt_hash) == 16


# ═══ Translation + Summarization ═══


class TestTranslation:
    def test_build_translation_prompt(self):
        prompt = build_translation_prompt("Hello", "en", "es")
        assert "English" in prompt
        assert "Spanish" in prompt
        assert "Hello" in prompt

    def test_parse_translation_result(self):
        result = parse_translation_result("Hello", "Hola", "en", "es")
        assert result.success
        assert result.translated == "Hola"
        assert result.source_lang == "en"

    def test_empty_response(self):
        result = parse_translation_result("Hello", "", "en", "es")
        assert not result.success

    def test_supported_languages(self):
        assert "en" in SUPPORTED_LANGUAGES
        assert "am" in SUPPORTED_LANGUAGES  # Amharic
        assert "sw" in SUPPORTED_LANGUAGES  # Swahili


class TestSummarization:
    def test_build_prompt(self):
        prompt = build_summarization_prompt("Long text here", max_sentences=2)
        assert "2 sentences" in prompt
        assert "Long text" in prompt

    def test_parse_result(self):
        original = "This is a very long text. " * 20
        summary = "This text is about something."
        result = parse_summarization_result(original, summary)
        assert result.success
        assert result.compression_ratio < 1.0
        assert result.summary_length < result.original_length

    def test_empty_summary(self):
        result = parse_summarization_result("text", "")
        assert not result.success
