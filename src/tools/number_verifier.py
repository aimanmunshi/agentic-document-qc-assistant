"""
number_verifier.py

Deterministic tool: extracts numeric "line item" rows and "total" statements
from a document's text, recomputes column sums, and flags any stated total
that doesn't match its computed sum. No LLM call involved — this is exactly
the kind of arithmetic check a language model is unreliable at doing purely
"in its head", which is the whole point of giving it to a tool instead.

Public API:
    verify_numbers(document_text: str) -> List[QCFinding]   # pure function, unit-testable
    number_verifier_tool                                     # LangChain @tool wrapper
"""

from __future__ import annotations

import re
from typing import Dict, List

from langchain_core.tools import tool

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.schemas import IssueCategory, QCFinding, Severity  # noqa: E402

NUMBER_RE = r"\$?\s?-?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?"
TOTAL_LINE_RE = re.compile(
    r"(?i)\btotal\b[^:\n]*?[:\-]?\s*(" + NUMBER_RE + r")\s*$"
)
ROW_NUMBERS_RE = re.compile(NUMBER_RE)
TOLERANCE = 0.5  # absolute tolerance for float rounding noise


def _clean_number(raw: str) -> float:
    cleaned = raw.strip().replace("$", "").replace(",", "").replace("%", "")
    return float(cleaned)


def _is_total_line(line: str) -> bool:
    return bool(TOTAL_LINE_RE.search(line))


FULL_NUMBER_RE = re.compile(r"^" + NUMBER_RE + r"$")


def _extract_row_numbers(line: str) -> List[float]:
    """Return numeric tokens found in a line, if it looks like a genuine
    tabular data row (a text label followed by one or more numeric columns,
    column-aligned with runs of 2+ spaces — e.g.
    'Northeast       12,450          1,867,500').

    This is deliberately strict: plain prose sentences (single spaces
    between words) never qualify, even if they happen to contain digits
    (a year, a date, a "Q1" reference, etc.) — only intentionally
    column-formatted rows do. That keeps stray numbers in narrative text
    from contaminating the recomputed sums.
    """
    stripped = line.strip()
    if not stripped or _is_total_line(stripped):
        return []

    # Column-aligned tables use runs of 2+ spaces between cells; a normal
    # sentence does not.
    cells = re.split(r"\s{2,}", stripped)
    if len(cells) < 2:
        return []

    label, number_cells = cells[0], cells[1:]
    if not label or not re.match(r"^[A-Za-z]", label):
        return []

    numbers = []
    for cell in number_cells:
        cell = cell.strip()
        if not FULL_NUMBER_RE.match(cell):
            # A non-numeric cell (e.g. a units header, a footnote) means
            # this isn't a pure numeric data row — reject the whole line.
            return []
        try:
            numbers.append(_clean_number(cell))
        except ValueError:
            return []
    return numbers


def verify_numbers(document_text: str) -> List[QCFinding]:
    """Recompute totals from line-item rows and flag mismatches.

    Algorithm:
      1. Scan lines, splitting into "data rows" (label + N numbers) and
         "total lines" (contain the word 'total' and end in a number).
      2. Group data rows by their numeric-column count (the most common
         column count is treated as "the" table; stray rows are ignored).
      3. Sum each column across the table.
      4. For each total line's stated value, check whether it matches any
         column sum within tolerance. If none match, flag a mismatch against
         the closest column sum.
    """
    lines = document_text.splitlines()

    data_rows: List[List[float]] = []
    total_statements: List[Dict] = []

    for line in lines:
        if _is_total_line(line):
            match = TOTAL_LINE_RE.search(line)
            if match:
                try:
                    stated_value = _clean_number(match.group(1))
                except ValueError:
                    continue
                total_statements.append({"line": line.strip(), "value": stated_value})
            continue

        row_numbers = _extract_row_numbers(line)
        if row_numbers:
            data_rows.append(row_numbers)

    findings: List[QCFinding] = []

    if not data_rows or not total_statements:
        return findings

    # Determine the dominant column count and only keep rows matching it.
    col_counts = [len(r) for r in data_rows]
    dominant_count = max(set(col_counts), key=col_counts.count)
    table_rows = [r for r in data_rows if len(r) == dominant_count]

    if not table_rows:
        return findings

    column_sums = [
        round(sum(row[col_idx] for row in table_rows), 2)
        for col_idx in range(dominant_count)
    ]

    for stmt in total_statements:
        stated = stmt["value"]
        matched = any(abs(stated - col_sum) <= TOLERANCE for col_sum in column_sums)
        if matched:
            continue

        closest_sum = min(column_sums, key=lambda s: abs(s - stated))
        discrepancy = round(stated - closest_sum, 2)
        findings.append(
            QCFinding(
                category=IssueCategory.NUMERIC_MISMATCH,
                severity=Severity.HIGH,
                description=(
                    f"Stated total {stated:,.2f} does not match the computed sum of "
                    f"its line items ({closest_sum:,.2f}) — discrepancy "
                    f"{discrepancy:,.2f}."
                ),
                evidence=stmt["line"],
                source="number_verifier",
            )
        )

    return findings


@tool("number_verifier")
def number_verifier_tool(document_text: str) -> str:
    """Check whether numeric totals stated in a document match the sum of their
    underlying line items. Use this on any document containing tables, sums,
    or a 'Total' figure that should reconcile with numbers listed above it.
    Returns a plain-text summary of any mismatches found (empty string if none)."""
    findings = verify_numbers(document_text)
    if not findings:
        return "No numeric mismatches found."
    lines = [f"- {f.description} (evidence: {f.evidence!r})" for f in findings]
    return "Numeric mismatches found:\n" + "\n".join(lines)
