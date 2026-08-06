# Project: Agentic Document QC & Validation Assistant

## Purpose
A portfolio project that directly demonstrates the JD's phrase "Agentic and
Non-Agentic AI Solutions" by building BOTH approaches side by side on the
same task, then documenting the difference. This is the differentiator
project — most trainee applicants won't have touched agentic AI at all, and
fewer still will be able to articulate when each approach is appropriate.

The task itself mirrors real analytics-ops QC work: reviewing a
report/document for inconsistencies, formatting issues, and completeness
before it goes to a client — directly tied to the JD's "QC, proof-reading,
validation of analytics/market access documents" line.

## Tech Stack
- Python 3.11+
- langchain, langchain-anthropic (or langchain-openai as an alternative)
- Anthropic API (or OpenAI API) — set via .env, never hardcoded
- pydantic — structured output schemas for QC findings
- pytest + unittest.mock — mocked LLM responses for tests (no API cost/key
  required to run the test suite)
- python-dotenv

## Folder Structure
```
agentic-document-qc-assistant/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .env.example
├── data/
│   └── sample_reports/
│       ├── report_1_numeric_mismatch.txt
│       ├── report_2_formatting_issues.txt
│       └── report_3_missing_sections.txt
├── src/
│   ├── non_agentic/
│   │   └── simple_qc.py          # single-shot LLM call, one prompt, no tools
│   ├── agentic/
│   │   └── qc_agent.py           # LangChain agent that decides which tools
│   │                                to call and in what order
│   ├── tools/
│   │   ├── number_verifier.py    # extracts figures, checks totals/sums
│   │   ├── formatting_checker.py # checks date format & terminology consistency
│   │   └── checklist_validator.py # checks for required sections by doc type
│   └── schemas.py                 # pydantic models for structured QC findings
├── docs/
│   └── comparison.md              # side-by-side run + written analysis
├── output/
│   └── qc_findings/                # generated findings per document, per approach
└── tests/
    ├── test_number_verifier.py
    ├── test_formatting_checker.py
    ├── test_checklist_validator.py
    └── test_agent_mocked.py        # agent logic tested with mocked LLM calls
```

## Sample Documents (data/sample_reports/)
Three short synthetic reports (300-500 words each, plain text, styled like a
business/market-access summary) with DELIBERATE, findable issues:

1. **report_1_numeric_mismatch.txt** — contains a "Total" figure that does
   not match the sum of the line items listed above it
2. **report_2_formatting_issues.txt** — mixes date formats (e.g.
   "12/05/2025" and "May 12, 2025" in the same doc) and inconsistent
   terminology (e.g. "Q1" in one place, "Quarter 1" in another, referring to
   the same period)
3. **report_3_missing_sections.txt** — styled as a standard report template
   but missing a required section (e.g. no "Methodology" or "Limitations"
   section that a checklist says should be present)

## Non-Agentic Baseline (src/non_agentic/simple_qc.py)
- One LLM call, one fixed prompt: "review this document and list any QC
  issues you find"
- No tools, no multi-step reasoning, no memory of prior steps
- Returns whatever the model finds in a single pass — this is the honest
  baseline, not a strawman. Document its actual results, don't rig it to fail.

## Tools (src/tools/) — build and test each independently first
- **number_verifier.py**: extracts numeric values from text, re-computes
  sums/totals, flags mismatches with exact numbers (e.g. "stated total 45,230
  vs computed sum 44,180 — discrepancy 1,050")
- **formatting_checker.py**: detects mixed date formats and inconsistent
  terms referring to the same concept
- **checklist_validator.py**: given a document "type," checks for presence
  of required section headers from a small config-defined checklist

## Agentic Version (src/agentic/qc_agent.py)
- Uses LangChain's agent framework (e.g. a ReAct-style agent) with the three
  tools above available to it
- The agent must DECIDE which tools to invoke based on the document content,
  not run a hardcoded fixed sequence — this is what makes it agentic rather
  than just "a script that calls three functions in order"
- Should reason step by step (visible in verbose/trace output) and produce a
  final structured QC report (via the pydantic schema) listing each issue,
  which tool caught it, and its severity

## docs/comparison.md Requirements
Run both the non-agentic baseline and the agentic version on all three sample
documents. Document, honestly:
- What each approach caught vs. missed
- Why (e.g. "the non-agentic single-shot approach caught the missing section
  by general reading, but missed the exact numeric discrepancy because
  arithmetic isn't reliable without a dedicated verification step")
- When you'd actually choose one over the other in a real ops setting (e.g.
  non-agentic = fast/cheap for a quick first-pass; agentic = more thorough
  for high-stakes client-facing documents)
- Do NOT rig this to make the agentic version look artificially superior —
  an honest, nuanced comparison is more credible in an interview than a
  one-sided one

## README.md Requirements
Must include:
- One-paragraph project summary framed for a resume/portfolio reader
- Clear plain-language explanation of "agentic vs non-agentic AI" (assume
  the reader/interviewer may not know the distinction — explain it well and
  you'll stand out in the interview itself)
- Setup instructions including .env / API key setup
- How to run both versions and where to find the comparison output
- A short "Results" section summarizing docs/comparison.md's findings

## Testing
- Each tool (number_verifier, formatting_checker, checklist_validator) gets
  unit tests with known inputs and expected outputs — no API calls needed
- Agent logic tested with MOCKED LLM responses (unittest.mock or a fake LLM)
  so the test suite runs without an API key or cost
- A separate, clearly-labeled script (not part of pytest) for running the
  real end-to-end demo against the live API when you want to generate the
  actual comparison output

## Constraints
- Never hardcode an API key — use .env, and .env.example should show the
  variable name only
- Keep sample documents short to minimize API cost when running live
- Prioritize a correct, honest agentic/non-agentic comparison over an
  impressive-looking but dishonest one — this project's credibility depends
  on being able to explain it accurately in an interview
