import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.schemas import IssueCategory
from src.tools.checklist_validator import validate_checklist


COMPLETE_DOC = """
1. EXECUTIVE SUMMARY
Some summary text here.

2. METHODOLOGY
Some methodology text here.

3. RECOMMENDATIONS
Some recommendations text here.
"""

INCOMPLETE_DOC = """
1. EXECUTIVE SUMMARY
Some summary text here.

2. FINDINGS AND IMPLICATIONS
Some findings text here.

3. RECOMMENDATIONS
Some recommendations text here.
"""


def test_complete_document_has_no_missing_sections():
    findings = validate_checklist(COMPLETE_DOC, doc_type="standard_report")
    assert findings == []


def test_incomplete_document_flags_missing_methodology():
    findings = validate_checklist(INCOMPLETE_DOC, doc_type="standard_report")
    assert len(findings) == 1
    assert findings[0].category == IssueCategory.MISSING_SECTION
    assert "methodology" in findings[0].description.lower()


def test_market_access_profile_accepts_limitations_or_risk_factors():
    doc_with_risk_factors = COMPLETE_DOC + "\n4. RISK FACTORS\nSome risk text.\n"
    findings = validate_checklist(doc_with_risk_factors, doc_type="market_access_summary")
    assert findings == []

    doc_with_limitations = COMPLETE_DOC + "\n4. LIMITATIONS\nSome limitations text.\n"
    findings = validate_checklist(doc_with_limitations, doc_type="market_access_summary")
    assert findings == []


def test_unknown_doc_type_falls_back_to_default_checklist():
    findings = validate_checklist(COMPLETE_DOC, doc_type="totally_unknown_type")
    assert findings == []
