# Agentic Document QC & Validation Assistant

A portfolio project that builds the same task two ways — **agentic** and
**non-agentic** AI — side by side, so the difference between the two isn't
just a definition, it's something you can run and see.

The task: reviewing a report before it goes to a client for the kind of
issues a QC/proof-reading pass is meant to catch — numbers that don't add
up, inconsistent formatting, and missing required sections. This mirrors
real analytics-ops QC work (reviewing market-access/analytics documents for
inconsistencies, formatting issues, and completeness before client
delivery), and it's a task where the agentic-vs-non-agentic distinction
actually shows up in the results, not just in the architecture diagram.

## What "agentic" vs "non-agentic" actually means

It's easy to nod along to "agentic AI" without a concrete sense of what
changes in practice. Here's the plain-language version, using this project
as the example:

**Non-agentic** ([`src/non_agentic/simple_qc.py`](src/non_agentic/simple_qc.py))
is one LLM call with one fixed prompt: "here's a document, list any QC
issues you find." The model reads the whole thing once and reports back
whatever it notices. There's no tool use, no multi-step reasoning, and no
opportunity for the model to say "let me actually check that number" — it
either notices something is off on the read, or it doesn't. This is what
most people mean when they say "I asked ChatGPT to review my document."

**Agentic** ([`src/agentic/qc_agent.py`](src/agentic/qc_agent.py)) gives the
model three specialized tools — a number verifier, a date/terminology
consistency checker, and a section-completeness checklist — and lets it
**decide for itself** which ones are relevant to the document in front of
it, call them, read their results, and only then produce a final report.
The model isn't running a fixed "call tool 1, then 2, then 3" script; on a
document with no numeric tables, it can (and does) skip the number
verifier entirely. That decision-making — reasoning about what checks
this specific document needs, rather than following a hardcoded sequence —
is what makes it agentic rather than just "a script that calls three
functions in order."

The practical payoff of the agentic approach isn't that the model gets
smarter. It's that for tasks a language model is structurally unreliable
at — like exact arithmetic — a tool that actually computes the answer in
code doesn't share that weakness. See [`docs/comparison.md`](docs/comparison.md)
for exactly where that mattered and where it didn't.

## Project structure

```
agentic-document-qc-assistant/
├── data/sample_reports/       # 3 synthetic reports, each with a planted QC issue
├── src/
│   ├── non_agentic/simple_qc.py   # single-shot baseline
│   ├── agentic/qc_agent.py        # LangChain tool-calling agent
│   ├── tools/                     # the 3 deterministic tools, independently unit-tested
│   └── schemas.py                 # shared pydantic models for QC findings
├── scripts/
│   ├── run_live_demo.py           # real API calls — needs a funded ANTHROPIC_API_KEY
│   └── run_simulated_demo.py      # no API needed — see docs/comparison.md for why
├── docs/comparison.md         # side-by-side results + honest analysis
├── tests/                     # pytest suite — fully mocked, no API key needed
└── output/qc_findings/        # generated structured reports land here
```

## Setup

**Requirements:** Python 3.11+

```bash
python -m venv .venv
```

Activate it, then install dependencies:

```bash
pip install -r requirements.txt
```

### API key

This project uses the Anthropic API via `langchain-anthropic`. Copy the
example env file and fill in your key:

```bash
cp .env.example .env
```

Then edit `.env`:

```
ANTHROPIC_API_KEY=sk-ant-your-real-key-here
```

Get a key at [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)
— note that a new account needs some credit balance under **Settings →
Billing** before API calls will succeed. **You only need a key for live runs**
(`scripts/run_live_demo.py`) — the entire test suite and
`scripts/run_simulated_demo.py` run without one, at zero cost.

## Running it

**Run the tests** (mocked, no API key, no cost):

```bash
pytest
```

**Run each tool independently** (also no API key needed — they're pure
deterministic Python):

```python
from src.tools.number_verifier import verify_numbers
from src.tools.formatting_checker import check_formatting
from src.tools.checklist_validator import validate_checklist
```

**Run the non-agentic baseline on one document** (needs a funded API key):

```bash
python -m src.non_agentic.simple_qc data/sample_reports/report_1_numeric_mismatch.txt
```

**Run the agentic version on one document** (needs a funded API key; prints
its tool-call reasoning trace as it goes):

```bash
python -m src.agentic.qc_agent data/sample_reports/report_1_numeric_mismatch.txt
```

**Run the full comparison across all 3 sample documents:**

```bash
# Real API calls — needs credit on your Anthropic account
python scripts/run_live_demo.py

# No API calls at all — see docs/comparison.md for exactly what this
# simulates and why
python scripts/run_simulated_demo.py
```

Either script writes structured JSON reports to `output/qc_findings/` and
prints a summary table.

## Results

Full write-up with per-document reasoning: [`docs/comparison.md`](docs/comparison.md).

> **Note:** at the time of writing, these results come from the *simulated*
> demo, not a live API run — see the disclaimer at the top of
> `docs/comparison.md` for exactly what that means and how to regenerate a
> genuine live comparison.

| Document | Non-agentic found | Agentic found | Takeaway |
|---|---|---|---|
| Numeric mismatch (stated total doesn't match line items) | **Missed it** | **Caught it**, with the exact discrepancy (`$233,000`) | The clear win for agentic: exact arithmetic is a known LLM weak spot; a tool that actually computes the sum doesn't share that weakness. |
| Mixed date formats + inconsistent terminology | Caught it, in general terms | Caught it, with every instance itemized | Both approaches detect this fine — a fluent read is genuinely good at spotting inconsistent style. Agentic wins on completeness, not detection. |
| Missing required section | Caught it by reading the outline | Caught it, as two explicit itemized findings | Both catch a whole-section gap easily. Agentic's edge is consistency (checked against an explicit list) rather than the baseline being blind to it. |

The honest conclusion: **agentic isn't universally better — it's better
specifically at the things a single LLM pass is structurally unreliable at**
(exact computation, exhaustive enumeration, consistent rule-checking). For
tasks well within a fluent read's comfort zone, the extra tool-calling
machinery buys precision and auditability, not detection power. In a real
ops setting, that argues for a hybrid: cheap non-agentic triage on
everything, agentic verification specifically for documents with numeric
tables or other client-facing figures before they go out the door.

## Testing philosophy

- `src/tools/*.py` are pure Python with no LLM dependency — each has direct
  unit tests with known inputs/expected outputs (`tests/test_number_verifier.py`,
  `tests/test_formatting_checker.py`, `tests/test_checklist_validator.py`).
- The agent's logic (`tests/test_agent_mocked.py`) is tested by mocking the
  LangChain executor itself, so JSON-parsing robustness, tool-selection
  reporting, and error handling are all exercised without a live model call.
- `scripts/run_live_demo.py` is intentionally kept outside pytest — it's the
  one place that spends real money, and it's clearly labeled as such.
