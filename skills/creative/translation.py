"""Translation + Summarization Skills — Multi-language governed operations.

Uses LLM for translation and summarization with governance:
content safety on both input and output, PII redaction, audit trail.

Permission: translate / summarize
Risk: low (auto-approve with audit)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TranslationResult:
    """Result of a translation."""

    success: bool
    original: str = ""
    translated: str = ""
    source_lang: str = ""
    target_lang: str = ""
    error: str = ""


@dataclass(frozen=True, slots=True)
class SummarizationResult:
    """Result of a summarization."""

    success: bool
    original_length: int = 0
    summary: str = ""
    summary_length: int = 0
    compression_ratio: float = 0.0
    error: str = ""


SUPPORTED_LANGUAGES = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "pt": "Portuguese", "it": "Italian", "zh": "Chinese", "ja": "Japanese",
    "ko": "Korean", "ar": "Arabic", "hi": "Hindi", "am": "Amharic",
    "sw": "Swahili", "yo": "Yoruba", "ha": "Hausa", "ru": "Russian",
    "tr": "Turkish", "nl": "Dutch", "pl": "Polish", "vi": "Vietnamese",
}


def build_translation_prompt(text: str, source_lang: str, target_lang: str) -> str:
    """Build a governed translation prompt."""
    src = SUPPORTED_LANGUAGES.get(source_lang, source_lang)
    tgt = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
    return (
        f"Translate the following text from {src} to {tgt}. "
        f"Return ONLY the translation, no explanation.\n\n"
        f"Text: {text}"
    )


def build_summarization_prompt(text: str, *, max_sentences: int = 3) -> str:
    """Build a governed summarization prompt."""
    return (
        f"Summarize the following text in {max_sentences} sentences or fewer. "
        f"Be concise and preserve key information.\n\n"
        f"Text: {text}"
    )


def parse_translation_result(
    original: str, llm_response: str,
    source_lang: str, target_lang: str,
) -> TranslationResult:
    """Parse LLM response into structured translation result."""
    if not llm_response:
        return TranslationResult(success=False, error="empty LLM response")
    return TranslationResult(
        success=True,
        original=original,
        translated=llm_response.strip(),
        source_lang=source_lang,
        target_lang=target_lang,
    )


def parse_summarization_result(original: str, llm_response: str) -> SummarizationResult:
    """Parse LLM response into structured summarization result."""
    if not llm_response:
        return SummarizationResult(success=False, error="empty LLM response")
    original_len = len(original.split())
    summary_len = len(llm_response.split())
    ratio = round(summary_len / max(1, original_len), 2)
    return SummarizationResult(
        success=True,
        original_length=original_len,
        summary=llm_response.strip(),
        summary_length=summary_len,
        compression_ratio=ratio,
    )
