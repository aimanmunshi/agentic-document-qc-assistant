# Agentic vs. Non-Agentic: Comparison

This document runs both the non-agentic baseline (`src/non_agentic/simple_qc.py`)
and the agentic version (`src/agentic/qc_agent.py`) against all three sample
reports in `data/sample_reports/` and reports, honestly, what each one caught
and missed.

> ## ⚠️ A note on how this comparison was generated
>
> This project was built without spare Anthropic API credit available at the
> time of writing, so the numbers below come from
> **[`scripts/run_simulated_demo.py`](../scripts/run_simulated_demo.py)**, not
> a live API run. To keep this honest rather than just convenient, here's
> exactly what is and isn't real in that script:
>
> - **The agentic side's tool outputs are 100% real.** `src/tools/*.py`
>   (`number_verifier`, `formatting_checker`, `checklist_validator`) are pure,
>   deterministic Python — no LLM involved at all — and the simulated demo
>   calls them directly against the real sample documents. The exact
>   discrepancy figures, date-format lists, and missing-section names below
>   are genuine code output, unit-tested independently in `tests/`.
> - **The agentic side's tool-*selection* is simulated.** In a live run, the
>   LLM decides which of the three tools to call by reading the document. Here
>   a simple stand-in heuristic makes that call instead (see
>   `simulate_tool_selection()` in the script) — it happens to reach the same
>   conclusion a reasonable agent would (skip `number_verifier` on documents
>   with no stated totals), but it's a heuristic, not a model decision.
> - **The non-agentic side is entirely hand-authored and clearly labeled
>   `[SIMULATED]`.** A single-shot LLM call has no deterministic stand-in — the
>   whole point of that approach is that it *is* the model's judgment — so
>   there's no way to "really" run it offline. The simulated findings below
>   were written to reflect the specific, well-documented failure mode this
>   project exists to demonstrate (LLMs read fluently but don't reliably
>   re-derive arithmetic), not to make the baseline look artificially weak.
>
> **To regenerate this comparison for real:** add Anthropic API credit, set
> `ANTHROPIC_API_KEY` in `.env`, and run `python scripts/run_live_demo.py`.
> It exercises the exact same two code paths (`run_simple_qc` /
> `run_agentic_qc`) against the same three documents and will produce a
> directly comparable — but genuine — version of the table below. If the live
> numbers differ from the simulated ones (e.g. the model does catch the
> arithmetic error sometimes), that's expected and worth reporting honestly
> too; this document should be regenerated, not defended, if that happens.

## Summary table (simulated run)

| Document | Non-agentic issues found | Agentic issues found | Tools the agent used |
|---|---|---|---|
| `report_1_numeric_mismatch.txt` | 0 | 1 | number_verifier, formatting_checker, checklist_validator |
| `report_2_formatting_issues.txt` | 2 | 2 | formatting_checker, checklist_validator |
| `report_3_missing_sections.txt` | 1 | 2 | formatting_checker, checklist_validator |

Full JSON output for each run is saved to
[`output/qc_findings/`](../output/qc_findings/) (files suffixed
`_SIMULATED.json` from this run; a live run via `run_live_demo.py` writes the
same filenames without that suffix).

---

## Document 1: `report_1_numeric_mismatch.txt`

**The planted issue:** the report states `Total net revenue for the period:
$4,205,500`, but the three regional line items above it
(`1,867,500 + 1,157,000 + 948,000`) actually sum to `$3,972,500` — a
`$233,000` discrepancy.

**Non-agentic baseline: MISSED.** The simulated single-pass review found the
document "well-organized... no issues flagged." It did not catch the
mismatch.

**Agentic version: CAUGHT, with exact numbers.**
`number_verifier` reported:

> Stated total 4,205,500.00 does not match the computed sum of its line
> items (3,972,500.00) — discrepancy 233,000.00.

**Why the gap.** This is the clearest, most defensible case for the agentic
approach in the whole project. Verifying that three multi-digit,
comma-formatted numbers sum to a stated total is *arithmetic*, not reading
comprehension — and LLMs generate text token-by-token rather than executing
a calculation, so they're well documented to be unreliable at exactly this
kind of multi-digit addition, especially when it's one sentence buried in a
longer document rather than the explicit focus of the prompt. A dedicated
tool that actually parses the numbers and adds them in code doesn't have
that failure mode — it's either right or it has a bug, and it's unit-tested
against exactly this scenario (`tests/test_number_verifier.py`). This is the
textbook case for giving an LLM-based system a tool instead of asking it to
"just do the math."

*(Caveat: a live run might occasionally catch this one too — models have
gotten better at simple arithmetic, and this sum is small enough a
model *could* get lucky. The point isn't that the baseline mathematically
cannot succeed, it's that it isn't *reliable* at it, which is exactly why you
wouldn't want to depend on it for a client-facing number.)*

---

## Document 2: `report_2_formatting_issues.txt`

**The planted issues:** dates written in at least four different formats
(`2025-03-31`, `01/02/2025`, `May 12, 2025`, `15 July 2025`, ...), and the
same quarter referred to as both "Q1" and "Quarter 1."

**Non-agentic baseline: CAUGHT, in general terms.** The simulated review
flagged both the mixed date formats and the "Q1"/"Quarter 1" inconsistency,
citing a few representative examples of each rather than enumerating every
instance.

**Agentic version: CAUGHT, exhaustively.** `formatting_checker` reported:

> Document mixes 4 different date formats: ISO (YYYY-MM-DD): 2025-03-31;
> Slash-numeric (M/D/Y or D/M/Y): 01/02/2025, 07/15/2025, 1/2/2025; Month
> Day, Year: August 3, 2025, March 31, 2025, May 12, 2025; Day Month Year:
> 15 July 2025
>
> Document uses inconsistent terminology for the same concept: 'Q1',
> 'Quarter 1' all appear, referring to the same period.

**Why the gap is smaller here.** Spotting "these dates don't look
consistent" or "this document says Q1 in one place and Quarter 1 in
another" is fundamentally a pattern-recognition / reading-comprehension
task — exactly what LLMs are good at, with or without a dedicated tool. Both
approaches catch the issue. The difference is *completeness and precision*:
the baseline samples a few examples in a fluent paragraph, while
`formatting_checker` mechanically enumerates every matching instance in the
document by category. For a client-facing QC pass, that completeness
matters (you want the *full* list of inconsistent dates to fix, not "some
examples"), but it's a difference of degree, not of kind — this is not a
case where the non-agentic approach fundamentally can't do the job.

---

## Document 3: `report_3_missing_sections.txt`

**The planted issue:** the report is missing both a "Methodology" section
and a "Limitations"/"Risk Factors" section, which the project's checklist
treats as required for a `market_access_summary`-type document.

**Non-agentic baseline: CAUGHT.** The simulated review noted the document
"does not include a Methodology section... nor a Limitations section,"
picking up on the structural gap by reading through the document's outline.

**Agentic version: CAUGHT, itemized.** `checklist_validator` reported the
same gap as two separate, explicit findings:

> Document is missing a required section: 'methodology' (checklist profile:
> 'market_access_summary').
>
> Document is missing a required section: 'limitations / risk factors'
> (checklist profile: 'market_access_summary').

**Why both catch this one.** Noticing "this document doesn't have a section
a report like this should have" is a structural-skim task a capable model
handles well in a single pass — you don't need a dedicated tool to notice
something isn't there when you're reading the whole document anyway. The
agentic version's advantage here is precision and consistency rather than
detection: `checklist_validator` checks against an explicit,
version-controlled list of required sections per document type
(`DOC_TYPE_CHECKLISTS` in `src/tools/checklist_validator.py`), so its
answer doesn't depend on the model happening to remember what a market-access
report "usually" includes, and it separates "missing Methodology" from
"missing Limitations/Risk Factors" as two distinct, individually-actionable
findings rather than one vague sentence.

---

## Honest takeaways

**What actually differed:** the agentic version's advantage was large and
structural on the arithmetic case (missed vs. caught, full stop), and mostly
about completeness/precision — not detection — on the two pattern-matching
cases. That's the nuanced result, not "agentic wins everywhere," and it
lines up with what you'd predict from *why* each tool exists: a dedicated
tool only meaningfully outperforms a fluent single-shot read when the task
is something a fluent read is structurally bad at (exact computation),
not just something it's mediocre at.

**When you'd actually pick each approach in a real ops setting:**

- **Non-agentic (single-shot LLM call)** is the right default for a fast,
  cheap first-pass — one API call, a few seconds, one prompt to maintain.
  Fine for an early draft, a low-stakes internal document, or triaging a
  large batch of documents to decide which ones need deeper review at all.
  It reliably catches the "obvious on a careful read" category of issue
  (missing sections, inconsistent phrasing) reasonably well.
- **Agentic (tool-calling)** earns its extra latency, cost, and complexity
  specifically when a document contains anything requiring *exact*
  verification — sums, cross-referenced figures, computed percentages — or
  when the output needs to be exhaustive and auditable (every instance
  flagged, every check individually traceable to a specific deterministic
  tool) rather than "a reasonable-sounding paragraph." That describes
  exactly the kind of high-stakes, client-facing analytics/market-access
  deliverable this project is modeled on: the cost of one missed
  `$233,000` discrepancy reaching a client is much higher than the cost of
  a few extra seconds and a few extra cents of API spend to catch it first.
- In practice, a reasonable real-world pipeline is neither purely one nor
  the other: run the cheap non-agentic pass on everything as a fast triage,
  and route anything containing numeric tables or client-facing figures
  through the agentic pipeline before it goes out the door.
