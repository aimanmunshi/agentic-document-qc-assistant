"""
qc_agent.py — the AGENTIC version.

Uses LangChain's tool-calling agent framework with the three deterministic
tools in src/tools/ (number_verifier, formatting_checker, checklist_validator)
made available to the model. The key difference from the non-agentic
baseline: the agent DECIDES which tools to call, in what order, and how many
times, based on what it actually observes in the document. Nothing here runs
a hardcoded "call tool 1, then tool 2, then tool 3" sequence — that would
just be a script wearing an agent costume.

The system prompt explicitly tells the model it does NOT have to call every
tool on every document, so on a document with no tables the model can (and,
in practice, does) skip number_verifier entirely — that's the agentic
decision-making the comparison in docs/comparison.md points to.

The reasoning trace (which tools were called, with what arguments, and what
they returned) is visible via AgentExecutor's verbose output and is also
captured programmatically in QCReport.tools_used for docs/comparison.md.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).resolve().parents[2]))
from src.schemas import QCFindingsOutput, QCReport  # noqa: E402
from src.tools.checklist_validator import checklist_validator_tool  # noqa: E402
from src.tools.formatting_checker import formatting_checker_tool  # noqa: E402
from src.tools.number_verifier import number_verifier_tool  # noqa: E402

load_dotenv()

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

TOOLS = [number_verifier_tool, formatting_checker_tool, checklist_validator_tool]

AGENT_SYSTEM_PROMPT = """You are a meticulous QC (quality control) reviewer for analytics and \
market-access client deliverables. You have access to three tools:

- number_verifier: recomputes totals from numeric line items and flags \
mismatches. Only useful on documents that actually contain tables or stated \
totals/sums.
- formatting_checker: detects mixed date formats and inconsistent \
terminology for the same concept. Useful on most documents that contain \
dates or recurring named concepts (like quarters/periods).
- checklist_validator: checks whether a document has all the section \
headers expected for its type. Pass doc_type='market_access_summary' for \
market-access/reimbursement-style reports, otherwise omit it to use the \
default 'standard_report' checklist. Useful on any structured report.

Decide which tools are actually relevant to THIS document based on its \
content — you do not need to call every tool on every document. For \
example, a document with no numeric tables gains nothing from \
number_verifier, so skip it. Call each tool at most once. You may also \
rely on your own reading to catch issues the tools aren't designed to \
detect (e.g. unclear writing, factual implausibility), but for anything a \
tool can check precisely (arithmetic, date formats, section completeness), \
prefer the tool's result over your own eyeballing — tools are exact, you \
are not, especially for arithmetic.

Once you've gathered what you need, respond with ONLY a single JSON object \
(no markdown code fences, no extra commentary before or after it) matching \
this shape:

{{"findings": [{{"category": "numeric_mismatch|date_format_inconsistency|terminology_inconsistency|missing_section|other", \
"severity": "low|medium|high", "description": "...", "evidence": "... or null", \
"source": "number_verifier|formatting_checker|checklist_validator|llm"}}], \
"summary": "..."}}

Set "source" to the tool name that caught the issue, or "llm" if you \
noticed it yourself through reading rather than via a tool. Do not invent \
issues that aren't actually present in the document."""


def _extract_json_object(raw_text: str) -> dict:
    """Best-effort extraction of a single JSON object from the agent's final
    text output, tolerating stray markdown fences or commentary around it."""
    text = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    return json.loads(text)


def build_agent_executor(model: str = DEFAULT_MODEL, verbose: bool = True):
    """Construct the LangChain tool-calling AgentExecutor."""
    from langchain.agents import AgentExecutor, create_tool_calling_agent
    from langchain_anthropic import ChatAnthropic
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

    llm = ChatAnthropic(model=model, temperature=0)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", AGENT_SYSTEM_PROMPT),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )
    agent = create_tool_calling_agent(llm, TOOLS, prompt)
    return AgentExecutor(
        agent=agent,
        tools=TOOLS,
        verbose=verbose,
        return_intermediate_steps=True,
        max_iterations=6,
    )


def run_agentic_qc(
    document_text: str,
    document_name: str = "document",
    doc_type: Optional[str] = "market_access_summary",
    model: str = DEFAULT_MODEL,
    verbose: bool = True,
) -> QCReport:
    """Run the agentic QC review and return a QCReport.

    Requires ANTHROPIC_API_KEY to be set (via .env or the environment).
    """
    executor = build_agent_executor(model=model, verbose=verbose)

    doc_type_hint = f" (document type hint: '{doc_type}')" if doc_type else ""
    input_text = (
        f"Review the following document for QC issues{doc_type_hint}. Decide "
        f"which of your tools are relevant given what the document actually "
        f"contains, call them as needed, then respond with the final JSON "
        f"object as instructed.\n\nDocument name: {document_name}\n\n"
        f"Document text:\n\n{document_text}"
    )

    result = executor.invoke({"input": input_text})

    tools_used = sorted(
        {step[0].tool for step in result.get("intermediate_steps", [])}
    )

    try:
        parsed = _extract_json_object(result["output"])
        llm_output = QCFindingsOutput.model_validate(parsed)
        findings = llm_output.findings
        summary = llm_output.summary
    except (json.JSONDecodeError, ValueError) as exc:
        # Fail soft rather than crashing the whole comparison run — surface
        # the parse failure as a visible artifact instead of hiding it.
        findings = []
        summary = (
            f"[WARNING: failed to parse agent's final output as structured "
            f"JSON: {exc}] Raw output: {result.get('output', '')[:500]}"
        )

    return QCReport(
        document_name=document_name,
        approach="agentic",
        findings=findings,
        summary=summary,
        tools_used=tools_used,
    )


if __name__ == "__main__":
    # Quick manual run: python -m src.agentic.qc_agent path/to/report.txt [doc_type]
    if len(sys.argv) < 2:
        print("Usage: python -m src.agentic.qc_agent <path_to_document.txt> [doc_type]")
        sys.exit(1)

    path = Path(sys.argv[1])
    doc_type_arg = sys.argv[2] if len(sys.argv) > 2 else "market_access_summary"
    text = path.read_text(encoding="utf-8")
    report = run_agentic_qc(text, document_name=path.name, doc_type=doc_type_arg)
    print("\n=== FINAL STRUCTURED REPORT ===")
    print(report.model_dump_json(indent=2))
