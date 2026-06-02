"""Tests for output/renderer.py."""

import json

from agentguard.output.renderer import SEVERITY_ICON, SEVERITY_STYLE, Finding, render_json


def test_finding_namedtuple():
    f = Finding("critical", "No owner")
    assert f.severity == "critical"
    assert f.message == "No owner"


def test_render_json_produces_valid_json():
    findings = [
        Finding("critical", "No owner"),
        Finding("warning", "No loop detection"),
        Finding("ok", "CLAUDE.md present"),
    ]
    output = render_json(findings)
    parsed = json.loads(output)
    assert len(parsed) == 3
    assert parsed[0]["severity"] == "critical"
    assert parsed[0]["message"] == "No owner"
    assert parsed[2]["severity"] == "ok"


def test_render_json_empty_findings():
    output = render_json([])
    assert json.loads(output) == []


def test_severity_icons_defined():
    for level in ["critical", "warning", "info", "ok"]:
        assert level in SEVERITY_ICON
        assert level in SEVERITY_STYLE


def test_render_preflight_no_exception():
    from agentguard.output.renderer import render_preflight
    findings = [
        Finding("critical", "No owner defined"),
        Finding("warning", "No loop detection"),
        Finding("ok", "CLAUDE.md present"),
    ]
    # Should not raise
    render_preflight("./test-project", findings)


def test_render_watch_event_no_exception():
    from agentguard.output.renderer import render_watch_event
    render_watch_event("LOOP_WARNING", "tool_x called 4x in last 10 calls")
    render_watch_event("STALL_WARNING", "low diversity")
    render_watch_event("BURN_WARNING", "token threshold reached")
