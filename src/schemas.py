"""
Pydantic models shared across the non-agentic baseline, the individual tools,
and the agentic QC pipeline. Keeping one schema definition means both
approaches' outputs are directly comparable in docs/comparison.md.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    """How serious a QC finding is, from a client-facing-risk standpoint."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IssueCategory(str, Enum):
    """What kind of QC problem was found."""

    NUMERIC_MISMATCH = "numeric_mismatch"
    DATE_FORMAT_INCONSISTENCY = "date_format_inconsistency"
    TERMINOLOGY_INCONSISTENCY = "terminology_inconsistency"
    MISSING_SECTION = "missing_section"
    OTHER = "other"


class QCFinding(BaseModel):
    """A single QC issue found in a document."""

    category: IssueCategory
    severity: Severity
    description: str = Field(
        ..., description="Human-readable explanation of the issue, with specifics."
    )
    evidence: Optional[str] = Field(
        default=None,
        description="Exact quoted text / values from the document supporting the finding.",
    )
    source: str = Field(
        default="llm",
        description=(
            "What caught this finding: 'llm' for single-shot model judgment, or the "
            "tool name (e.g. 'number_verifier') for the agentic pipeline."
        ),
    )


class QCReport(BaseModel):
    """Full structured QC report for one document."""

    document_name: str
    approach: str = Field(..., description="'non_agentic' or 'agentic'")
    findings: List[QCFinding] = Field(default_factory=list)
    summary: str = Field(
        default="", description="Short overall assessment of the document's QC state."
    )
    tools_used: List[str] = Field(
        default_factory=list,
        description=(
            "Names of tools actually invoked (agentic approach only) — kept for "
            "transparency, to show the agent chose a subset rather than always "
            "calling every tool."
        ),
    )

    @property
    def issue_count(self) -> int:
        return len(self.findings)


class QCFindingsOutput(BaseModel):
    """The raw shape both the non-agentic and agentic LLM calls are asked to
    produce: just findings + a summary. document_name/approach/tools_used are
    filled in afterward by the calling code, not by the model."""

    findings: List[QCFinding] = Field(default_factory=list)
    summary: str = ""
