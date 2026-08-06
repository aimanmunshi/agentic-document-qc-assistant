"""
checklist_validator.py

Deterministic tool: extracts section headers from a document and checks them
against a small config-defined checklist of sections required for that
document "type". Catches the case where a document reads fine sentence-by-
sentence but is missing a whole required section — easy for a single LLM
pass to miss when skimming, easy for a targeted structural check to catch.

Public API:
    validate_checklist(document_text: str, doc_type: str = "standard_report") -> List[QCFinding]
    checklist_validator_tool                                     # LangChain @tool wrapper
"""

from __future__ import annotations

import re
from typing import List, Set

from langchain_core.tools import tool

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.schemas import IssueCategory, QCFinding, Severity  # noqa: E402

# Each required "slot" is a set of acceptable synonyms — the section counts as
# present if ANY term in the set is found as a header in the document.
DOC_TYPE_CHECKLISTS = {
    "standard_report": [
        {"executive summary"},
        {"methodology"},
        {"recommendations"},
    ],
    "market_access_summary": [
        {"executive summary"},
        {"methodology"},
        {"risk factors", "limitations"},
        {"recommendations"},
    ],
}

DEFAULT_DOC_TYPE = "standard_report"

# Matches lines like "2. METHODOLOGY", "3.1 Brand-Level Detail", or a bare
# "RISK FACTORS" heading — i.e. short lines that read as section titles.
HEADER_LINE_RE = re.compile(r"^\s*(?:\d+(?:\.\d+)*\.?\s*)?([A-Za-z][A-Za-z &/\-]{2,60})\s*$")


def _extract_headers(document_text: str) -> Set[str]:
    headers = set()
    for line in document_text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) > 70:
            continue
        match = HEADER_LINE_RE.match(stripped)
        if not match:
            continue
        title = match.group(1).strip()
        # Heuristic: treat as a header if it's short and either ALL CAPS or
        # Title Case (as opposed to a normal prose sentence).
        words = title.split()
        if not words:
            continue
        is_all_caps = title.upper() == title and any(c.isalpha() for c in title)
        is_title_case = all(w[0].isupper() for w in words if w[0].isalpha())
        if is_all_caps or is_title_case:
            headers.add(title.lower())
    return headers


def validate_checklist(
    document_text: str, doc_type: str = DEFAULT_DOC_TYPE
) -> List[QCFinding]:
    """Check document_text's section headers against the checklist for doc_type."""
    checklist = DOC_TYPE_CHECKLISTS.get(doc_type, DOC_TYPE_CHECKLISTS[DEFAULT_DOC_TYPE])
    headers = _extract_headers(document_text)

    findings: List[QCFinding] = []
    for required_slot in checklist:
        present = any(
            any(syn in header for header in headers) for syn in required_slot
        )
        if not present:
            slot_desc = " / ".join(sorted(required_slot))
            findings.append(
                QCFinding(
                    category=IssueCategory.MISSING_SECTION,
                    severity=Severity.HIGH,
                    description=(
                        f"Document is missing a required section: '{slot_desc}' "
                        f"(checklist profile: '{doc_type}')."
                    ),
                    evidence=None,
                    source="checklist_validator",
                )
            )
    return findings


@tool("checklist_validator")
def checklist_validator_tool(document_text: str, doc_type: str = DEFAULT_DOC_TYPE) -> str:
    """Check whether a document contains all required section headers for its
    type (e.g. 'Executive Summary', 'Methodology', 'Recommendations'). Use
    doc_type='market_access_summary' for market-access/reimbursement reports,
    otherwise the 'standard_report' default checklist applies. Returns a
    plain-text summary of any missing sections."""
    findings = validate_checklist(document_text, doc_type)
    if not findings:
        return "No missing sections found."
    lines = [f"- {f.description}" for f in findings]
    return "Missing sections found:\n" + "\n".join(lines)
