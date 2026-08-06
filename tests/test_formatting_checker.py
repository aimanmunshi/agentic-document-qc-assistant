import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.schemas import IssueCategory
from src.tools.formatting_checker import check_formatting


def test_flags_mixed_date_formats():
    text = (
        "Data collection began 01/02/2025 and closed on March 31, 2025. "
        "Final freeze occurred on 2025-03-31."
    )
    findings = check_formatting(text)
    date_findings = [f for f in findings if f.category == IssueCategory.DATE_FORMAT_INCONSISTENCY]
    assert len(date_findings) == 1
    assert "3 different date formats" in date_findings[0].description


def test_no_date_finding_when_single_format_used_consistently():
    text = "Kickoff was on 01/02/2025 and wrap-up was on 03/31/2025."
    findings = check_formatting(text)
    date_findings = [f for f in findings if f.category == IssueCategory.DATE_FORMAT_INCONSISTENCY]
    assert date_findings == []


def test_flags_terminology_inconsistency():
    text = "Q1 growth was strong. Quarter 1 revenue exceeded targets."
    findings = check_formatting(text)
    term_findings = [f for f in findings if f.category == IssueCategory.TERMINOLOGY_INCONSISTENCY]
    assert len(term_findings) == 1
    assert "Q1" in term_findings[0].evidence
    assert "Quarter 1" in term_findings[0].evidence


def test_no_terminology_finding_when_only_one_variant_used():
    text = "Q1 growth was strong. Q1 revenue exceeded targets."
    findings = check_formatting(text)
    term_findings = [f for f in findings if f.category == IssueCategory.TERMINOLOGY_INCONSISTENCY]
    assert term_findings == []


def test_clean_document_produces_no_findings():
    text = "All dates use ISO format: 2025-01-01 and 2025-03-31. Terms are consistent."
    findings = check_formatting(text)
    assert findings == []
