"""
run_live_demo.py — LIVE END-TO-END DEMO. Calls the real Anthropic API.

Not part of the pytest suite (the test suite runs entirely on mocked LLM
responses and never needs a key). Run this script explicitly, and only once
ANTHROPIC_API_KEY is set in .env with an account that has API credit — it
will incur a small real cost (a handful of short document reviews; each
sample report is a few hundred words).

Usage:
    python scripts/run_live_demo.py

For each sample report in data/sample_reports/, this runs BOTH the
non-agentic baseline and the agentic version, saves each structured report
to output/qc_findings/, and prints a side-by-side summary table.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

import os  # noqa: E402

if not os.environ.get("ANTHROPIC_API_KEY"):
    print(
        "ERROR: ANTHROPIC_API_KEY is not set. Copy .env.example to .env and "
        "fill in a real key with available credit before running this script."
    )
    sys.exit(1)

from src.agentic.qc_agent import run_agentic_qc  # noqa: E402
from src.non_agentic.simple_qc import run_simple_qc  # noqa: E402

SAMPLE_DOCS = [
    ("report_1_numeric_mismatch.txt", "market_access_summary"),
    ("report_2_formatting_issues.txt", "market_access_summary"),
    ("report_3_missing_sections.txt", "market_access_summary"),
]

OUTPUT_DIR = ROOT / "output" / "qc_findings"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    results = []

    for filename, doc_type in SAMPLE_DOCS:
        path = ROOT / "data" / "sample_reports" / filename
        text = path.read_text(encoding="utf-8")

        print(f"\n{'=' * 70}\n{filename}\n{'=' * 70}")

        print("\n--- Running NON-AGENTIC baseline (single LLM call) ---")
        t0 = time.time()
        non_agentic_report = run_simple_qc(text, document_name=filename)
        non_agentic_elapsed = time.time() - t0
        print(f"Done in {non_agentic_elapsed:.1f}s — {non_agentic_report.issue_count} issue(s) found")

        print("\n--- Running AGENTIC version (LangChain tool-calling agent) ---")
        t0 = time.time()
        agentic_report = run_agentic_qc(text, document_name=filename, doc_type=doc_type, verbose=True)
        agentic_elapsed = time.time() - t0
        print(f"Done in {agentic_elapsed:.1f}s — {agentic_report.issue_count} issue(s) found — tools used: {agentic_report.tools_used}")

        stem = filename.replace(".txt", "")
        (OUTPUT_DIR / f"{stem}_non_agentic.json").write_text(
            non_agentic_report.model_dump_json(indent=2), encoding="utf-8"
        )
        (OUTPUT_DIR / f"{stem}_agentic.json").write_text(
            agentic_report.model_dump_json(indent=2), encoding="utf-8"
        )

        results.append(
            {
                "filename": filename,
                "non_agentic": non_agentic_report,
                "agentic": agentic_report,
                "non_agentic_time": non_agentic_elapsed,
                "agentic_time": agentic_elapsed,
            }
        )

    print(f"\n\n{'=' * 70}\nSUMMARY\n{'=' * 70}")
    for r in results:
        print(f"\n{r['filename']}")
        print(
            f"  non-agentic: {r['non_agentic'].issue_count} issue(s) in "
            f"{r['non_agentic_time']:.1f}s"
        )
        print(
            f"  agentic:     {r['agentic'].issue_count} issue(s) in "
            f"{r['agentic_time']:.1f}s (tools used: {r['agentic'].tools_used})"
        )

    print(f"\nFull structured reports written to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
