import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.schemas import IssueCategory
from src.tools.number_verifier import verify_numbers


def test_flags_mismatched_total():
    text = """
    Region          Units Sold      Net Revenue (USD)
    Northeast       12,450          1,867,500
    Midwest         8,900           1,157,000
    West Coast      6,320           948,000

    Total confirmed units across all regions for the period: 27,670
    Total net revenue for the period: $4,205,500
    """
    findings = verify_numbers(text)
    assert len(findings) == 1
    finding = findings[0]
    assert finding.category == IssueCategory.NUMERIC_MISMATCH
    assert "4,205,500.00" in finding.description
    assert "3,972,500.00" in finding.description


def test_no_findings_when_totals_match():
    text = """
    Region          Units Sold
    Northeast       100
    Midwest         200
    West Coast      300

    Total units across all regions: 600
    """
    findings = verify_numbers(text)
    assert findings == []


def test_no_findings_when_no_tables_present():
    text = "This is a plain paragraph with no tables or totals at all."
    findings = verify_numbers(text)
    assert findings == []


def test_handles_multiple_totals_some_matching_some_not():
    text = """
    Region      Units       Revenue
    North       10          100
    South       20          150

    Total units: 30
    Total revenue: 300
    """
    findings = verify_numbers(text)
    # units total (30) matches; revenue total (300) should NOT match (250)
    assert len(findings) == 1
    assert "250.00" in findings[0].description
