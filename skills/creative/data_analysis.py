"""Data Analysis Skill — Governed data processing and insights.

Analyzes structured data (CSV, key-value, lists) with governed access.
All input data is PII-scanned before analysis. Results are audited.

Permission: analyze_data
Risk: medium (auto-approve with audit)
"""

from __future__ import annotations

import csv
import io
import statistics
from collections import Counter
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ColumnStats:
    """Statistics for a single data column."""

    name: str
    count: int
    unique: int
    data_type: str  # "numeric", "text", "mixed"
    mean: float | None = None
    median: float | None = None
    min_val: str = ""
    max_val: str = ""
    top_values: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Result of data analysis."""

    success: bool
    row_count: int = 0
    column_count: int = 0
    columns: tuple[ColumnStats, ...] = ()
    summary: str = ""
    insights: tuple[str, ...] = ()
    error: str = ""


def analyze_csv(csv_text: str, *, max_rows: int = 10_000) -> AnalysisResult:
    """Analyze CSV data and produce column statistics + insights."""
    if not csv_text.strip():
        return AnalysisResult(success=False, error="empty data")

    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        fieldnames = reader.fieldnames or []
        if not fieldnames:
            return AnalysisResult(success=False, error="no columns found")

        rows: list[dict[str, str]] = []
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            rows.append(row)

        if not rows:
            return AnalysisResult(success=False, error="no data rows")

        columns: list[ColumnStats] = []
        insights: list[str] = []

        for col_name in fieldnames:
            values = [row.get(col_name, "").strip() for row in rows]
            non_empty = [v for v in values if v]

            # Determine data type
            numeric_values: list[float] = []
            for v in non_empty:
                try:
                    numeric_values.append(float(v.replace(",", "")))
                except ValueError:
                    pass

            is_numeric = len(numeric_values) > len(non_empty) * 0.8
            data_type = "numeric" if is_numeric else "text"

            # Compute stats
            unique_count = len(set(non_empty))
            top_values = tuple(Counter(non_empty).most_common(5))

            col_stats = ColumnStats(
                name=col_name,
                count=len(non_empty),
                unique=unique_count,
                data_type=data_type,
                mean=round(statistics.mean(numeric_values), 2) if numeric_values else None,
                median=round(statistics.median(numeric_values), 2) if numeric_values else None,
                min_val=str(min(numeric_values)) if numeric_values else (min(non_empty) if non_empty else ""),
                max_val=str(max(numeric_values)) if numeric_values else (max(non_empty) if non_empty else ""),
                top_values=top_values,
            )
            columns.append(col_stats)

            # Generate insights
            if is_numeric and numeric_values:
                if len(numeric_values) > 1:
                    std = statistics.stdev(numeric_values)
                    if std > col_stats.mean * 0.5:
                        insights.append(f"'{col_name}' has high variance (std={std:.2f}, mean={col_stats.mean})")
            if unique_count == 1 and len(non_empty) > 5:
                insights.append(f"'{col_name}' has only one unique value — may be constant")
            if unique_count == len(non_empty) and len(non_empty) > 5:
                insights.append(f"'{col_name}' has all unique values — possible ID column")

        # Summary
        summary_parts = [
            f"{len(rows)} rows, {len(fieldnames)} columns",
            f"Numeric columns: {sum(1 for c in columns if c.data_type == 'numeric')}",
            f"Text columns: {sum(1 for c in columns if c.data_type == 'text')}",
        ]

        return AnalysisResult(
            success=True,
            row_count=len(rows),
            column_count=len(fieldnames),
            columns=tuple(columns),
            summary=". ".join(summary_parts),
            insights=tuple(insights),
        )
    except Exception as exc:
        return AnalysisResult(success=False, error=f"analysis failed ({type(exc).__name__})")


def analyze_key_value(data: dict[str, Any]) -> AnalysisResult:
    """Analyze key-value data and produce summary."""
    if not data:
        return AnalysisResult(success=False, error="empty data")

    columns: list[ColumnStats] = []
    for key, value in data.items():
        val_str = str(value)
        is_numeric = False
        try:
            float(val_str.replace(",", ""))
            is_numeric = True
        except ValueError:
            pass

        columns.append(ColumnStats(
            name=key,
            count=1,
            unique=1,
            data_type="numeric" if is_numeric else "text",
            min_val=val_str,
            max_val=val_str,
        ))

    return AnalysisResult(
        success=True,
        row_count=1,
        column_count=len(data),
        columns=tuple(columns),
        summary=f"Key-value data with {len(data)} fields",
    )
