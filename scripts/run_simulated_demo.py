"""
run_simulated_demo.py — SIMULATED demo. Makes NO live API calls.

Why this exists: docs/comparison.md needs a concrete side-by-side run, but
this project was built without spare Anthropic API credit available. Rather
than fabricate a live-looking run, this script is explicit about what's real
and what's simulated:

  AGENTIC side — REAL, not simulated. src/tools/*.py are pure deterministic
  Python (no LLM involved at all), already unit-tested. This script calls
  them directly against the real sample documents and gets real results.
  The one piece standing in for the LLM is *which* tools get called — in a
  live run, the model decides that dynamically based on the document; here
  a simple, clearly-labeled heuristic (SIMULATE_TOOL_SELECTION below) makes
  that same kind of decision instead. Everything downstream of "which tool
  fires" is genuine code execution, not text I wrote by hand.

  NON-AGENTIC side — SIMULATED. A single-shot LLM call has no deterministic
  component to substitute in; there's no way to "really" run it without a
  live model. SIMULATED_NON_AGENTIC_FINDINGS below is hand-authored to
  represent a plausible, honestly-reasoned single-pass outcome, informed by
  the well-documented failure mode this project is built to demonstrate:
  LLMs reading fluently but not reliably re-deriving arithmetic in their
  head. It is clearly labeled as such everywhere it surfaces.

To replace this entire script's output with a genuine live run once API
credit is available, run scripts/run_live_demo.py instead — same sample
documents, same output format, real model calls on both sides.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from src.schemas import IssueCategory, QCFinding, QCReport, Severity  # noqa: E402
from src.tools.checklist_validator import validate_checklist  # noqa: E402
from src.tools.formatting_checker import check_formatting  # noqa: E402
from src.tools.number_verifier import verify_numbers  # noqa: E402

SAMPLE_DOCS = [
    "report_1_numeric_mismatch.txt",
    "report_2_formatting_issues.txt",
    "report_3_missing_sections.txt",
]
DOC_TYPE = "market_access_summary"

OUTPUT_DIR = ROOT / "output" / "qc_findings"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def simulate_tool_selection(document_text: str) -> dict:
    """Stand-in for the LLM's dynamic tool-selection decision.

    A real agent reads the document and decides for itself; here a simple
    heuristic approximates the same call: only run number_verifier if the
    document actually contains something that looks like a stated total
    (the word 'total' near the end of a line), since running it on a
    document with no tables would find nothing and waste a call — exactly
    the reasoning the agent's system prompt asks it to apply.

    formatting_checker and checklist_validator are cheap and broadly
    applicable, so (like the real agent tends to in practice) they run on
    every document.
    """
    has_total_statement = bool(re.search(r"(?i)\btotal\b[^\n]*\d", document_text))
    return {
        "number_verifier": has_total_statement,
        "formatting_checker": True,
        "checklist_validator": True,
    }


def run_simulated_agentic(document_text: str, document_name: str) -> QCReport:
    decisions = simulate_tool_selection(document_text)
    findings: list[QCFinding] = []
    tools_used: list[str] = []

    if decisions["number_verifier"]:
        tools_used.append("number_verifier")
        findings.extend(verify_numbers(document_text))

    if decisions["formatting_checker"]:
        tools_used.append("formatting_checker")
        findings.extend(check_formatting(document_text))

    if decisions["checklist_validator"]:
        tools_used.append("checklist_validator")
        findings.extend(validate_checklist(document_text, doc_type=DOC_TYPE))

    if findings:
        summary = (
            f"[SIMULATED tool-selection] {len(findings)} issue(s) found via "
            f"{len(tools_used)} tool(s) called: {', '.join(tools_used)}."
        )
    else:
        summary = (
            f"[SIMULATED tool-selection] No issues found. Tools called: "
            f"{', '.join(tools_used)}."
        )

    return QCReport(
        document_name=document_name,
        approach="agentic",
        findings=findings,
        summary=summary,
        tools_used=tools_used,
    )


# Hand-authored, clearly-labeled stand-in for what a single-shot LLM pass
# would plausibly notice on each document. See module docstring for why this
# side can't be "really" run without a live API key. Reasoning per document
# is documented in docs/comparison.md.
SIMULATED_NON_AGENTIC_FINDINGS: dict[str, dict] = {
    "report_1_numeric_mismatch.txt": {
        "findings": [],
        "summary": (
            "[SIMULATED] Document appears well-organized with a clear regional "
            "breakdown, consistent formatting, and no missing sections. No "
            "issues flagged. (A single fluent read does not reliably re-add "
            "three large comma-formatted figures against a stated total — the "
            "well-documented gap this project's dedicated number_verifier tool "
            "closes; see docs/comparison.md.)"
        ),
    },
    "report_2_formatting_issues.txt": {
        "findings": [
            QCFinding(
                category=IssueCategory.DATE_FORMAT_INCONSISTENCY,
                severity=Severity.MEDIUM,
                description=(
                    "[SIMULATED] The document mixes several date formats "
                    "(e.g. 'May 12, 2025', '1/2/2025', '2025-03-31') rather "
                    "than using one consistent style throughout."
                ),
                evidence=None,
                source="llm",
            ),
            QCFinding(
                category=IssueCategory.TERMINOLOGY_INCONSISTENCY,
                severity=Severity.LOW,
                description=(
                    "[SIMULATED] The document refers to the same period as "
                    "both 'Q1' and 'Quarter 1' in different places."
                ),
                evidence=None,
                source="llm",
            ),
        ],
        "summary": (
            "[SIMULATED] A careful read surfaces the mixed date formatting and "
            "inconsistent 'Q1'/'Quarter 1' phrasing in general terms, though "
            "without exhaustively listing every instance of each — a single "
            "pass tends to sample a few examples rather than mechanically "
            "scanning the entire document the way a dedicated checker does."
        ),
    },
    "report_3_missing_sections.txt": {
        "findings": [
            QCFinding(
                category=IssueCategory.MISSING_SECTION,
                severity=Severity.HIGH,
                description=(
                    "[SIMULATED] The document does not include a Methodology "
                    "section explaining how the payer landscape data was "
                    "compiled, nor a Limitations section — both of which a "
                    "reader would expect from a report making claims like "
                    "'twelve currently indicate a favorable predisposition'."
                ),
                evidence=None,
                source="llm",
            )
        ],
        "summary": (
            "[SIMULATED] A single read-through reasonably catches the missing "
            "Methodology/Limitations section, since a structural gap like a "
            "whole absent section is the kind of thing a careful reader "
            "notices by skimming the document's outline."
        ),
    },
}


def run_simulated_non_agentic(document_name: str) -> QCReport:
    data = SIMULATED_NON_AGENTIC_FINDINGS[document_name]
    return QCReport(
        document_name=document_name,
        approach="non_agentic",
        findings=data["findings"],
        summary=data["summary"],
    )


def main():
    print(
        "NOTE: this is a SIMULATED demo — no live Anthropic API calls are "
        "made. See this script's module docstring for exactly what's real "
        "(the agentic side's tool outputs) vs simulated (tool-selection "
        "decisions and all non-agentic findings).\n"
    )

    results = []
    for filename in SAMPLE_DOCS:
        path = ROOT / "data" / "sample_reports" / filename
        text = path.read_text(encoding="utf-8")

        print(f"\n{'=' * 70}\n{filename}\n{'=' * 70}")

        non_agentic_report = run_simulated_non_agentic(filename)
        print(f"\n--- NON-AGENTIC (simulated) — {non_agentic_report.issue_count} issue(s) ---")
        for f in non_agentic_report.findings:
            print(f"  [{f.severity.value.upper()}] {f.description}")
        print(f"  summary: {non_agentic_report.summary}")

        agentic_report = run_simulated_agentic(text, filename)
        print(
            f"\n--- AGENTIC (real tool outputs, simulated tool selection) — "
            f"{agentic_report.issue_count} issue(s), tools used: {agentic_report.tools_used} ---"
        )
        for f in agentic_report.findings:
            print(f"  [{f.severity.value.upper()}] ({f.source}) {f.description}")
        print(f"  summary: {agentic_report.summary}")

        stem = filename.replace(".txt", "")
        (OUTPUT_DIR / f"{stem}_non_agentic_SIMULATED.json").write_text(
            non_agentic_report.model_dump_json(indent=2), encoding="utf-8"
        )
        (OUTPUT_DIR / f"{stem}_agentic_SIMULATED.json").write_text(
            agentic_report.model_dump_json(indent=2), encoding="utf-8"
        )

        results.append((filename, non_agentic_report, agentic_report))

    print(f"\n\n{'=' * 70}\nSUMMARY TABLE\n{'=' * 70}")
    print(f"{'Document':<38}{'Non-agentic':<14}{'Agentic':<10}{'Tools used'}")
    for filename, na, ag in results:
        print(
            f"{filename:<38}{na.issue_count:<14}{ag.issue_count:<10}"
            f"{', '.join(ag.tools_used)}"
        )

    print(f"\nSimulated structured reports written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
