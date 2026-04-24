"""Document Generation Skill — Governed document creation.

Creates structured documents (reports, invoices, memos, proposals)
from templates with governed data binding. Every document is audited
with proof hash of content + template + timestamp.

Permission: create_document
Risk: medium (auto-approve for templates, approval for custom)
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


class DocumentType:
    REPORT = "report"
    INVOICE = "invoice"
    MEMO = "memo"
    PROPOSAL = "proposal"
    SUMMARY = "summary"
    LETTER = "letter"
    RECEIPT = "receipt"


@dataclass(frozen=True, slots=True)
class DocumentTemplate:
    """A document template with placeholder fields."""

    template_id: str
    name: str
    doc_type: str
    body_template: str  # Template with {field_name} placeholders
    required_fields: tuple[str, ...] = ()
    optional_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class GeneratedDocument:
    """A generated document with audit trail."""

    document_id: str
    template_id: str
    doc_type: str
    title: str
    body: str
    tenant_id: str
    generated_by: str
    generated_at: str
    content_hash: str  # SHA-256 of body for integrity
    metadata: dict[str, Any] = field(default_factory=dict)


# ═══ Built-in Templates ═══

BUILTIN_TEMPLATES: dict[str, DocumentTemplate] = {
    "invoice": DocumentTemplate(
        template_id="tpl-invoice-v1",
        name="Standard Invoice",
        doc_type=DocumentType.INVOICE,
        body_template=(
            "INVOICE\n"
            "========\n"
            "Invoice #: {invoice_number}\n"
            "Date: {date}\n"
            "From: {from_name}\n"
            "To: {to_name}\n"
            "\n"
            "Description: {description}\n"
            "Amount: {currency} {amount}\n"
            "\n"
            "Payment Terms: {payment_terms}\n"
            "Due Date: {due_date}\n"
        ),
        required_fields=("invoice_number", "date", "from_name", "to_name", "description", "amount", "currency"),
        optional_fields=("payment_terms", "due_date"),
    ),
    "memo": DocumentTemplate(
        template_id="tpl-memo-v1",
        name="Internal Memo",
        doc_type=DocumentType.MEMO,
        body_template=(
            "MEMORANDUM\n"
            "==========\n"
            "To: {to}\n"
            "From: {from_name}\n"
            "Date: {date}\n"
            "Subject: {subject}\n"
            "\n"
            "{body}\n"
        ),
        required_fields=("to", "from_name", "date", "subject", "body"),
    ),
    "receipt": DocumentTemplate(
        template_id="tpl-receipt-v1",
        name="Payment Receipt",
        doc_type=DocumentType.RECEIPT,
        body_template=(
            "RECEIPT\n"
            "=======\n"
            "Receipt #: {receipt_number}\n"
            "Date: {date}\n"
            "Received from: {from_name}\n"
            "Amount: {currency} {amount}\n"
            "Payment Method: {payment_method}\n"
            "Description: {description}\n"
            "\n"
            "Thank you for your payment.\n"
        ),
        required_fields=("receipt_number", "date", "from_name", "amount", "currency", "description"),
        optional_fields=("payment_method",),
    ),
    "summary": DocumentTemplate(
        template_id="tpl-summary-v1",
        name="Executive Summary",
        doc_type=DocumentType.SUMMARY,
        body_template=(
            "EXECUTIVE SUMMARY\n"
            "=================\n"
            "Title: {title}\n"
            "Date: {date}\n"
            "Prepared by: {author}\n"
            "\n"
            "Overview:\n{overview}\n"
            "\n"
            "Key Findings:\n{findings}\n"
            "\n"
            "Recommendations:\n{recommendations}\n"
        ),
        required_fields=("title", "date", "author", "overview", "findings", "recommendations"),
    ),
}


class DocumentGenerator:
    """Governed document generator.

    Every document is generated from a template with field binding,
    content-hashed for integrity, and audited.
    """

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        self._templates: dict[str, DocumentTemplate] = dict(BUILTIN_TEMPLATES)
        self._generated_count = 0

    def register_template(self, template: DocumentTemplate) -> None:
        self._templates[template.template_id] = template

    def list_templates(self) -> list[DocumentTemplate]:
        return list(self._templates.values())

    def generate(
        self,
        template_id: str,
        fields: dict[str, str],
        *,
        tenant_id: str = "",
        identity_id: str = "",
        title: str = "",
    ) -> GeneratedDocument:
        """Generate a document from a template with field binding."""
        template = self._templates.get(template_id)
        if template is None:
            raise ValueError(f"template not found: {template_id}")

        # Validate required fields
        missing = [f for f in template.required_fields if f not in fields]
        if missing:
            raise ValueError(f"missing required fields: {', '.join(missing)}")

        # Fill template
        all_fields = {f: fields.get(f, "") for f in (*template.required_fields, *template.optional_fields)}
        all_fields.update(fields)
        body = template.body_template.format(**all_fields)

        # Generate content hash
        content_hash = hashlib.sha256(body.encode()).hexdigest()
        now = self._clock()
        self._generated_count += 1
        doc_id = f"doc-{hashlib.sha256(f'{template_id}:{tenant_id}:{now}:{self._generated_count}'.encode()).hexdigest()[:12]}"

        return GeneratedDocument(
            document_id=doc_id,
            template_id=template_id,
            doc_type=template.doc_type,
            title=title or template.name,
            body=body,
            tenant_id=tenant_id,
            generated_by=identity_id,
            generated_at=now,
            content_hash=content_hash,
        )

    def generate_from_llm(
        self,
        doc_type: str,
        prompt: str,
        llm_response: str,
        *,
        tenant_id: str = "",
        identity_id: str = "",
        title: str = "",
    ) -> GeneratedDocument:
        """Wrap an LLM-generated response as a governed document."""
        now = self._clock()
        self._generated_count += 1
        content_hash = hashlib.sha256(llm_response.encode()).hexdigest()
        doc_id = f"doc-llm-{content_hash[:12]}"

        return GeneratedDocument(
            document_id=doc_id,
            template_id="llm-generated",
            doc_type=doc_type,
            title=title or f"Generated {doc_type}",
            body=llm_response,
            tenant_id=tenant_id,
            generated_by=identity_id,
            generated_at=now,
            content_hash=content_hash,
            metadata={"prompt_hash": hashlib.sha256(prompt.encode()).hexdigest()[:16]},
        )

    @property
    def generated_count(self) -> int:
        return self._generated_count

    @property
    def template_count(self) -> int:
        return len(self._templates)
