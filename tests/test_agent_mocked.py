"""
Agent logic tests using a MOCKED executor — no ANTHROPIC_API_KEY, no live
API calls, no cost. We patch build_agent_executor so run_agentic_qc's own
logic (JSON parsing, tools_used extraction, QCReport assembly, error
handling) is exercised against controlled fake LLM/tool output.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.agentic.qc_agent import _extract_json_object, run_agentic_qc


def test_extract_json_object_handles_plain_json():
    raw = '{"findings": [], "summary": "clean"}'
    assert _extract_json_object(raw) == {"findings": [], "summary": "clean"}


def test_extract_json_object_handles_markdown_fences():
    raw = 'Here you go:\n```json\n{"findings": [], "summary": "clean"}\n```'
    assert _extract_json_object(raw) == {"findings": [], "summary": "clean"}


def test_extract_json_object_handles_stray_surrounding_text():
    raw = 'Sure, here\'s the report: {"findings": [], "summary": "ok"} Hope that helps!'
    assert _extract_json_object(raw) == {"findings": [], "summary": "ok"}


class _FakeAction:
    """Stand-in for langchain_core.agents.AgentAction — only .tool is read."""

    def __init__(self, tool_name):
        self.tool = tool_name


def _make_fake_executor(output_text, tools_called):
    intermediate_steps = [(_FakeAction(t), "fake observation") for t in tools_called]

    def fake_invoke(inputs):
        return {"output": output_text, "intermediate_steps": intermediate_steps}

    return SimpleNamespace(invoke=fake_invoke)


@patch("src.agentic.qc_agent.build_agent_executor")
def test_run_agentic_qc_selects_only_relevant_tools(mock_build):
    """The agent should only report having used the tool(s) it actually
    called — proving tool selection is dynamic, not a fixed sequence of all
    three every time."""
    output_json = (
        '{"findings": [{"category": "missing_section", "severity": "high", '
        '"description": "Missing Methodology section.", "evidence": null, '
        '"source": "checklist_validator"}], "summary": "One issue found."}'
    )
    mock_build.return_value = _make_fake_executor(output_json, ["checklist_validator"])

    report = run_agentic_qc("some document text", document_name="doc.txt", verbose=False)

    assert report.approach == "agentic"
    assert report.document_name == "doc.txt"
    assert report.tools_used == ["checklist_validator"]
    assert len(report.findings) == 1
    assert report.findings[0].source == "checklist_validator"
    assert report.findings[0].category.value == "missing_section"
    assert report.summary == "One issue found."
    # number_verifier / formatting_checker were never called in this fake run.
    assert "number_verifier" not in report.tools_used
    assert "formatting_checker" not in report.tools_used


@patch("src.agentic.qc_agent.build_agent_executor")
def test_run_agentic_qc_can_report_multiple_tools_used(mock_build):
    output_json = (
        '{"findings": [], "summary": "No issues found after checking numbers and dates."}'
    )
    mock_build.return_value = _make_fake_executor(
        output_json, ["number_verifier", "formatting_checker"]
    )

    report = run_agentic_qc("some document text", verbose=False)

    assert report.tools_used == ["formatting_checker", "number_verifier"]  # sorted
    assert report.findings == []


@patch("src.agentic.qc_agent.build_agent_executor")
def test_run_agentic_qc_handles_malformed_output_gracefully(mock_build):
    """If the model doesn't produce valid JSON, we should fail soft (empty
    findings + a warning in the summary) rather than raising and crashing
    the whole comparison run."""
    mock_build.return_value = _make_fake_executor("not valid json at all", [])

    report = run_agentic_qc("some document text", verbose=False)

    assert report.findings == []
    assert "WARNING" in report.summary


@patch("src.agentic.qc_agent.build_agent_executor")
def test_run_agentic_qc_passes_document_text_and_type_hint_to_executor(mock_build):
    """Sanity check that the input handed to the executor actually contains
    the document text and doc_type hint, so a real agent would have what it
    needs to decide which tools apply."""
    captured = {}

    def fake_invoke(inputs):
        captured["input"] = inputs["input"]
        return {"output": '{"findings": [], "summary": "ok"}', "intermediate_steps": []}

    mock_build.return_value = SimpleNamespace(invoke=fake_invoke)

    run_agentic_qc(
        "UNIQUE_MARKER_TEXT_12345",
        document_name="doc.txt",
        doc_type="market_access_summary",
        verbose=False,
    )

    assert "UNIQUE_MARKER_TEXT_12345" in captured["input"]
    assert "market_access_summary" in captured["input"]
