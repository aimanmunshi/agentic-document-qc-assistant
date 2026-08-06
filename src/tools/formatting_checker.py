"""
formatting_checker.py

Deterministic tool: scans a document for (a) dates written in more than one
format, and (b) known synonym pairs (e.g. "Q1" vs "Quarter 1") used
interchangeably to refer to the same concept. Both are the kind of surface
inconsistency a human proofreader catches by eye but which a single LLM pass
may skim past, especially in a longer document.

Public API:
    check_formatting(document_text: str) -> List[QCFinding]   # pure function
    formatting_checker_tool                                    # LangChain @tool wrapper
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List

from langchain_core.tools import tool

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.schemas import IssueCategory, QCFinding, Severity  # noqa: E402

MONTHS = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)

DATE_PATTERNS = {
    "ISO (YYYY-MM-DD)": re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    "Slash-numeric (M/D/Y or D/M/Y)": re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    "Month Day, Year": re.compile(
        rf"\b(?:{MONTHS})\.?\s+\d{{1,2}},\s+\d{{4}}\b", re.IGNORECASE
    ),
    "Day Month Year": re.compile(
        rf"\b\d{{1,2}}\s+(?:{MONTHS})\.?\s+\d{{4}}\b", re.IGNORECASE
    ),
}

# Groups of terms considered synonyms referring to the same underlying
# concept. If 2+ variants from the same group appear in one document, that's
# an inconsistency worth flagging.
TERMINOLOGY_GROUPS: List[List[str]] = [
    ["Q1", "Quarter 1"],
    ["Q2", "Quarter 2"],
    ["Q3", "Quarter 3"],
    ["Q4", "Quarter 4"],
]


def _find_date_formats(document_text: str) -> Dict[str, List[str]]:
    found: Dict[str, List[str]] = {}
    for label, pattern in DATE_PATTERNS.items():
        matches = pattern.findall(document_text)
        if matches:
            found[label] = sorted(set(matches))
    return found


def _find_terminology_inconsistencies(document_text: str) -> List[Dict]:
    issues = []
    for group in TERMINOLOGY_GROUPS:
        present = []
        for term in group:
            pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
            if pattern.search(document_text):
                present.append(term)
        if len(present) > 1:
            issues.append({"group": group, "found": present})
    return issues


def check_formatting(document_text: str) -> List[QCFinding]:
    """Detect mixed date formats and inconsistent terminology in a document."""
    findings: List[QCFinding] = []

    date_formats = _find_date_formats(document_text)
    if len(date_formats) > 1:
        examples = "; ".join(
            f"{label}: {', '.join(vals[:3])}" for label, vals in date_formats.items()
        )
        findings.append(
            QCFinding(
                category=IssueCategory.DATE_FORMAT_INCONSISTENCY,
                severity=Severity.MEDIUM,
                description=(
                    f"Document mixes {len(date_formats)} different date formats: "
                    f"{examples}"
                ),
                evidence=examples,
                source="formatting_checker",
            )
        )

    for issue in _find_terminology_inconsistencies(document_text):
        findings.append(
            QCFinding(
                category=IssueCategory.TERMINOLOGY_INCONSISTENCY,
                severity=Severity.LOW,
                description=(
                    "Document uses inconsistent terminology for the same concept: "
                    f"{', '.join(repr(t) for t in issue['found'])} all appear, "
                    "referring to the same period."
                ),
                evidence=", ".join(issue["found"]),
                source="formatting_checker",
            )
        )

    return findings


@tool("formatting_checker")
def formatting_checker_tool(document_text: str) -> str:
    """Check a document for inconsistent date formatting (e.g. mixing
    MM/DD/YYYY, 'Month Day, Year', and ISO dates in the same doc) and
    inconsistent terminology for the same concept (e.g. 'Q1' vs 'Quarter 1').
    Returns a plain-text summary of any inconsistencies found."""
    findings = check_formatting(document_text)
    if not findings:
        return "No formatting or terminology inconsistencies found."
    lines = [f"- {f.description}" for f in findings]
    return "Formatting/terminology inconsistencies found:\n" + "\n".join(lines)
