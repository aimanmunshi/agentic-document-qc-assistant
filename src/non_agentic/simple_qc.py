"""
simple_qc.py — the NON-AGENTIC baseline.

One LLM call. One fixed prompt: "review this document and list any QC
issues you find." No tools, no multi-step reasoning, no memory of prior
steps, no decision-making about what to check next. Whatever the model
notices in a single pass is what you get.

This is the honest baseline the agentic version is compared against in
docs/comparison.md — it is not rigged to fail. A capable model asked to
proofread a document in one shot genuinely catches a lot (missing sections,
obvious phrasing issues, some inconsistencies). What it structurally cannot
do reliably is exact arithmetic re-verification, because "does 12,450 +
8,900 + 6,320 actually equal the stated total" is a computation, not a
judgment call, and LLMs generating token-by-token are not reliable
calculators.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.schemas import QCFindingsOutput, QCReport  # noqa: E402

load_dotenv()

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

SYSTEM_PROMPT = """You are a meticulous QC (quality control) reviewer for analytics and \
market-access client deliverables (the kind of reports a pharma/health-data \
consulting team sends to clients). You will be given the full text of one \
document. Review it carefully and list every QC issue you can find, such as:

- numeric figures (totals, sums) that don't add up correctly
- inconsistent formatting, e.g. dates written in more than one style, or \
inconsistent terminology referring to the same concept (e.g. "Q1" vs \
"Quarter 1")
- missing sections that a document of this type would normally be expected \
to have (e.g. Methodology, Limitations)
- any other inconsistency, error, or quality issue a careful human \
proofreader would flag before this went to a client

For each issue found, classify it into one of these categories: \
numeric_mismatch, date_format_inconsistency, terminology_inconsistency, \
missing_section, other. Assign a severity: low, medium, or high. Quote the \
relevant evidence from the document where applicable. Also write a short \
one-to-two sentence overall summary of the document's QC state.

Only report issues you are reasonably confident are real. Do not invent \
issues that aren't actually present in the text."""


def run_simple_qc(
    document_text: str,
    document_name: str = "document",
    model: str = DEFAULT_MODEL,
) -> QCReport:
    """Run the single-shot, no-tools QC review and return a QCReport.

    Requires ANTHROPIC_API_KEY to be set (via .env or the environment).
    """
    # Imported lazily so the rest of the module (and anything importing it,
    # like the schemas) stays usable without langchain-anthropic installed
    # in minimal test environments.
    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(model=model, temperature=0)
    structured_llm = llm.with_structured_output(QCFindingsOutput)

    result: QCFindingsOutput = structured_llm.invoke(
        [
            ("system", SYSTEM_PROMPT),
            ("human", f"Document to review:\n\n{document_text}"),
        ]
    )

    # The model isn't given a "source" to fill in for each finding — this is
    # the single-shot baseline, so every finding it produces came from raw
    # LLM judgment rather than a dedicated tool.
    findings = [f.model_copy(update={"source": "llm"}) for f in result.findings]

    return QCReport(
        document_name=document_name,
        approach="non_agentic",
        findings=findings,
        summary=result.summary,
    )


if __name__ == "__main__":
    # Quick manual run: python -m src.non_agentic.simple_qc path/to/report.txt
    if len(sys.argv) < 2:
        print("Usage: python -m src.non_agentic.simple_qc <path_to_document.txt>")
        sys.exit(1)

    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    report = run_simple_qc(text, document_name=path.name)
    print(report.model_dump_json(indent=2))
