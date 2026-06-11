"""Tests for agentguard report — generate_report_data()."""

from __future__ import annotations

import json

from agentguard.checks.report import generate_report_data


def _write_session_log(tmp_path, entries):
    log_dir = tmp_path / ".agentguard"
    log_dir.mkdir()
    log_file = log_dir / "session.log"
    log_file.write_text("\n".join(json.dumps(e) for e in entries) + "\n")


def test_no_session_log_returns_empty(tmp_path):
    data = generate_report_data(tmp_path)
    assert data["total"] == 0
    assert data["allowed"] == 0
    assert data["denied"] == 0
    assert data["has_data"] is False
    assert data["duration"] is None


def test_reads_session_log_counts(tmp_path):
    entries = [
        {"timestamp": "2026-06-11T10:00:00+00:00", "tool": "Bash",
         "decision": "allow", "input_summary": "ls", "reason": None,
         "session_id": "s1"},
        {"timestamp": "2026-06-11T10:01:00+00:00", "tool": "Bash",
         "decision": "allow", "input_summary": "pwd", "reason": None,
         "session_id": "s1"},
        {"timestamp": "2026-06-11T10:02:00+00:00", "tool": "Edit",
         "decision": "deny", "input_summary": "rm -rf /",
         "reason": "prohibited", "session_id": "s1"},
    ]
    _write_session_log(tmp_path, entries)
    data = generate_report_data(tmp_path)
    assert data["total"] == 3
    assert data["allowed"] == 2
    assert data["denied"] == 1
    assert data["has_data"] is True


def test_calculates_duration(tmp_path):
    entries = [
        {"timestamp": "2026-06-11T10:00:00+00:00", "tool": "Bash",
         "decision": "allow", "input_summary": "a", "reason": None,
         "session_id": "s1"},
        {"timestamp": "2026-06-11T10:03:30+00:00", "tool": "Bash",
         "decision": "allow", "input_summary": "b", "reason": None,
         "session_id": "s1"},
    ]
    _write_session_log(tmp_path, entries)
    data = generate_report_data(tmp_path)
    assert data["duration"] == "3m 30s"


def test_denied_entries_populated(tmp_path):
    entries = [
        {"timestamp": "2026-06-11T10:00:00+00:00", "tool": "Bash",
         "decision": "allow", "input_summary": "ok", "reason": None,
         "session_id": "s1"},
        {"timestamp": "2026-06-11T10:01:00+00:00", "tool": "Edit",
         "decision": "deny", "input_summary": "bad",
         "reason": "prohibited", "session_id": "s1"},
    ]
    _write_session_log(tmp_path, entries)
    data = generate_report_data(tmp_path)
    assert len(data["denied_entries"]) == 1
    assert data["denied_entries"][0]["tool"] == "Edit"
    assert data["denied_entries"][0]["reason"] == "prohibited"


def test_tool_counts_ordered(tmp_path):
    entries = [
        {"timestamp": "2026-06-11T10:00:00+00:00", "tool": "Bash",
         "decision": "allow", "input_summary": "a", "reason": None,
         "session_id": "s1"},
        {"timestamp": "2026-06-11T10:01:00+00:00", "tool": "Bash",
         "decision": "allow", "input_summary": "b", "reason": None,
         "session_id": "s1"},
        {"timestamp": "2026-06-11T10:02:00+00:00", "tool": "Read",
         "decision": "allow", "input_summary": "c", "reason": None,
         "session_id": "s1"},
    ]
    _write_session_log(tmp_path, entries)
    data = generate_report_data(tmp_path)
    tools = list(data["tool_counts"].keys())
    assert tools[0] == "Bash"
    assert data["tool_counts"]["Bash"] == 2
    assert data["tool_counts"]["Read"] == 1


def test_single_entry_no_duration(tmp_path):
    entries = [
        {"timestamp": "2026-06-11T10:00:00+00:00", "tool": "Bash",
         "decision": "allow", "input_summary": "x", "reason": None,
         "session_id": "s1"},
    ]
    _write_session_log(tmp_path, entries)
    data = generate_report_data(tmp_path)
    assert data["duration"] is None


def test_reads_watch_events(tmp_path):
    watch_entries = [
        {"event": "LOOP_WARNING", "message": "loop detected"},
        {"event": "LOOP_WARNING", "message": "loop again"},
        {"event": "STALL_WARNING", "message": "stall detected"},
    ]
    watch_log = tmp_path / "agentguard.log"
    watch_log.write_text("\n".join(json.dumps(e) for e in watch_entries) + "\n")
    data = generate_report_data(tmp_path)
    assert len(data["watch_events"]) == 3
    assert data["watch_counts"]["LOOP_WARNING"] == 2
    assert data["watch_counts"]["STALL_WARNING"] == 1
    assert data["has_data"] is True
