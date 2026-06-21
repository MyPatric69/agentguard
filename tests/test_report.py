"""Tests for agentguard report — generate_report_data() and generate_report()."""

from __future__ import annotations

import json

from agentguard.checks.report import generate_report, generate_report_data


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


# ── ROI fields ──────────────────────────────────────────────────────────────


def test_roi_fields_asked_and_session_cost(tmp_path):
    """asked, asked_entries, session_cost, session_id populated from session.log."""
    log_dir = tmp_path / ".agentguard"
    log_dir.mkdir()
    entries = [
        {"timestamp": "2026-06-21T10:00:00+00:00", "tool": "Bash",
         "decision": "allow", "input_summary": "ls", "session_id": "s1"},
        {"timestamp": "2026-06-21T10:01:00+00:00", "tool": "Edit",
         "decision": "ask", "input_summary": "edit file", "session_id": "s1"},
        {"timestamp": "2026-06-21T10:02:00+00:00", "tool": "Bash",
         "decision": "deny", "input_summary": "rm -rf", "reason": "prohibited",
         "session_id": "s1"},
        {"event": "session_cost", "session_id": "s1", "model": "claude-sonnet-4-6",
         "total_usd": 0.12, "input_tokens": 1000, "cache_write_5m_tokens": 0,
         "cache_write_1h_tokens": 0, "cache_read_tokens": 500, "output_tokens": 200,
         "pricing_source": "live"},
    ]
    (log_dir / "session.log").write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n"
    )
    data = generate_report_data(tmp_path)
    assert data["total"] == 3
    assert data["allowed"] == 1
    assert data["asked"] == 1
    assert data["denied"] == 1
    assert len(data["asked_entries"]) == 1
    assert data["asked_entries"][0]["tool"] == "Edit"
    assert data["session_cost"] is not None
    assert data["session_cost"]["total_usd"] == 0.12
    assert data["session_cost"]["model"] == "claude-sonnet-4-6"
    assert data["session_id"] == "s1"
    assert data["has_data"] is True


def test_session_cost_not_counted_in_total(tmp_path):
    """session_cost entries must not inflate total/allowed/denied."""
    log_dir = tmp_path / ".agentguard"
    log_dir.mkdir()
    entries = [
        {"timestamp": "2026-06-21T10:00:00+00:00", "tool": "Bash",
         "decision": "allow", "input_summary": "ls", "session_id": "s1"},
        {"event": "session_cost", "session_id": "s1", "total_usd": 0.05},
        {"event": "session_cost_notified", "session_id": "s1", "at_usd": 0.50},
        {"event": "post_tool_use", "tool_use_id": "x", "session_id": "s1"},
    ]
    (log_dir / "session.log").write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n"
    )
    data = generate_report_data(tmp_path)
    assert data["total"] == 1
    assert data["allowed"] == 1
    assert data["denied"] == 0
    assert data["asked"] == 0


def test_roi_fields_proposals(tmp_path):
    """proposals dict populated from .agentguard/proposals/*.json."""
    log_dir = tmp_path / ".agentguard"
    log_dir.mkdir()
    proposals_dir = log_dir / "proposals"
    proposals_dir.mkdir()
    (proposals_dir / "abc.json").write_text(json.dumps({
        "tool_use_id": "abc", "session_id": "s1", "tool_name": "Edit",
        "file_path": "test.py", "governance_reason": "needs review",
        "status": "pending", "timestamp": "2026-06-21T10:01:00+00:00",
        "pr_url": None,
    }))
    (proposals_dir / "def.json").write_text(json.dumps({
        "tool_use_id": "def", "session_id": "s1", "tool_name": "Write",
        "file_path": "other.py", "governance_reason": "needs review",
        "status": "pr_created", "timestamp": "2026-06-21T10:02:00+00:00",
        "pr_url": "https://github.com/x/y/pull/1",
    }))
    data = generate_report_data(tmp_path)
    assert data["proposals"]["total"] == 2
    assert data["proposals"]["pending"] == 1
    assert data["proposals"]["pr_created"] == 1
    assert len(data["proposals"]["entries"]) == 2


def test_no_session_log_roi_defaults(tmp_path):
    """Missing session.log → all ROI fields are zero/None."""
    data = generate_report_data(tmp_path)
    assert data["asked"] == 0
    assert data["asked_entries"] == []
    assert data["session_cost"] is None
    assert data["session_id"] is None
    assert data["proposals"]["total"] == 0
    assert data["proposals"]["pending"] == 0
    assert data["proposals"]["pr_created"] == 0
    assert data["proposals"]["entries"] == []
    assert data["has_data"] is False


def test_has_data_true_from_session_cost_only(tmp_path):
    """has_data is True even when the only entry is a session_cost event."""
    log_dir = tmp_path / ".agentguard"
    log_dir.mkdir()
    (log_dir / "session.log").write_text(
        json.dumps({"event": "session_cost", "total_usd": 0.01}) + "\n"
    )
    data = generate_report_data(tmp_path)
    assert data["total"] == 0
    assert data["has_data"] is True


# ── generate_report() ────────────────────────────────────────────────────────


def test_generate_report_creates_file_and_sections(tmp_path):
    """generate_report() writes a file with all required Markdown sections."""
    log_dir = tmp_path / ".agentguard"
    log_dir.mkdir()
    entries = [
        {"timestamp": "2026-06-21T10:00:00+00:00", "tool": "Bash",
         "decision": "allow", "input_summary": "ls", "session_id": "s1"},
        {"timestamp": "2026-06-21T10:02:00+00:00", "tool": "Edit",
         "decision": "deny", "input_summary": "bad file", "reason": "prohibited",
         "session_id": "s1"},
        {"event": "session_cost", "session_id": "s1", "model": "claude-sonnet-4-6",
         "total_usd": 0.05, "pricing_source": "fallback"},
    ]
    (log_dir / "session.log").write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n"
    )
    out = tmp_path / "report.md"
    text = generate_report(tmp_path, out)

    assert out.exists()
    assert "## ROI Summary" in text
    assert "## Tool Distribution" in text
    assert "## Blocked Actions" in text
    assert "## Unresolved Proposals" in text
    assert "## Runtime Events" in text
    assert "## Governance Assessment" in text
    assert "$0.0500" in text
    assert "claude-sonnet-4-6" in text
    assert "fallback" in text
    assert "REVIEW REQUIRED" in text
    assert "1 action(s) blocked" in text


def test_generate_report_no_cost_shows_na(tmp_path):
    """generate_report() with no session_cost entry shows N/A for cost."""
    log_dir = tmp_path / ".agentguard"
    log_dir.mkdir()
    (log_dir / "session.log").write_text(
        json.dumps({"timestamp": "2026-06-21T10:00:00+00:00", "tool": "Bash",
                    "decision": "allow", "input_summary": "ls", "session_id": "s1"}) + "\n"
    )
    out = tmp_path / "report.md"
    text = generate_report(tmp_path, out)
    assert "N/A" in text
    assert "PASS" in text


def test_generate_report_cli_path_flag(tmp_path):
    """agentguard report --path <dir> generates a report in the working dir."""
    from click.testing import CliRunner

    from agentguard.cli import main

    log_dir = tmp_path / ".agentguard"
    log_dir.mkdir()
    (log_dir / "session.log").write_text(
        json.dumps({"timestamp": "2026-06-21T10:00:00+00:00", "tool": "Bash",
                    "decision": "allow", "input_summary": "ls", "session_id": "s1"}) + "\n"
    )
    out = tmp_path / "out.md"
    runner = CliRunner()
    result = runner.invoke(
        main, ["report", "--path", str(tmp_path), "--output", str(out)]
    )
    assert result.exit_code == 0
    assert out.exists()
    assert "## ROI Summary" in out.read_text()


# ── Executive Summary ────────────────────────────────────────────────────────


def _make_session_log(tmp_path, entries):
    log_dir = tmp_path / ".agentguard"
    log_dir.mkdir(exist_ok=True)
    (log_dir / "session.log").write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n"
    )


def _allow(tool="Bash", ts="2026-06-21T10:00:00+00:00"):
    return {"timestamp": ts, "tool": tool, "decision": "allow",
            "input_summary": "ok", "session_id": "s1"}


def _deny(tool="Edit", ts="2026-06-21T10:01:00+00:00"):
    return {"timestamp": ts, "tool": tool, "decision": "deny",
            "input_summary": "bad", "reason": "prohibited", "session_id": "s1"}


def test_executive_summary_productive_yes(tmp_path):
    """Clean session (low deny, no proposals) → ✅ Yes."""
    _make_session_log(tmp_path, [_allow(), _allow(ts="2026-06-21T10:01:00+00:00")])
    data = generate_report_data(tmp_path)
    assert data["executive_summary"]["productive"] == "✅ Yes"
    assert data["executive_summary"]["governance_status"] == "All rules enforced — 0 violations"
    assert data["executive_summary"]["open_items"] == "0 proposal(s) pending owner review"


def test_executive_summary_review_needed_deny(tmp_path):
    """deny >= 20% of total → ⚠️ Review needed (not ❌)."""
    # 3 allow + 1 deny = 25% deny rate → Review needed
    entries = [
        _allow(ts="2026-06-21T10:00:00+00:00"),
        _allow(ts="2026-06-21T10:01:00+00:00"),
        _allow(ts="2026-06-21T10:02:00+00:00"),
        _deny(ts="2026-06-21T10:03:00+00:00"),
    ]
    _make_session_log(tmp_path, entries)
    data = generate_report_data(tmp_path)
    assert data["executive_summary"]["productive"] == "⚠️ Review needed"


def test_executive_summary_issues_detected_high_deny(tmp_path):
    """deny >= 50% of total → ❌ Issues detected."""
    # 1 allow + 1 deny = 50% deny rate → Issues detected
    _make_session_log(tmp_path, [_allow(), _deny(ts="2026-06-21T10:01:00+00:00")])
    data = generate_report_data(tmp_path)
    assert data["executive_summary"]["productive"] == "❌ Issues detected"


def test_executive_summary_issues_detected_burn(tmp_path):
    """BURN_WARNING in watch log → ❌ Issues detected regardless of deny rate."""
    _make_session_log(tmp_path, [_allow()])
    (tmp_path / "agentguard.log").write_text(
        json.dumps({"event": "BURN_WARNING", "message": "token burn"}) + "\n"
    )
    data = generate_report_data(tmp_path)
    assert data["executive_summary"]["productive"] == "❌ Issues detected"
    assert "runtime violation" in data["executive_summary"]["governance_status"]


def test_executive_summary_cost_within_budget(tmp_path):
    """Cost below all thresholds → '$X.XX — within budget'."""
    _make_session_log(tmp_path, [
        _allow(),
        {"event": "session_cost", "session_id": "s1", "model": "claude-sonnet-4-6",
         "total_usd": 0.25, "pricing_source": "live"},
    ])
    (tmp_path / "governance.yaml").write_text(
        "owner: Test\ncost_awareness:\n  thresholds:\n"
        "    - at_usd: 0.50\n      level: warn\n"
        "    - at_usd: 2.00\n      level: alert\n"
    )
    data = generate_report_data(tmp_path)
    assert data["executive_summary"]["cost_label"] == "$0.2500 — within budget"


def test_executive_summary_cost_above_alert(tmp_path):
    """Cost above alert threshold → correct label with ⚠️."""
    _make_session_log(tmp_path, [
        _allow(),
        {"event": "session_cost", "session_id": "s1", "model": "claude-sonnet-4-6",
         "total_usd": 1.50, "pricing_source": "live"},
    ])
    (tmp_path / "governance.yaml").write_text(
        "owner: Test\ncost_awareness:\n  thresholds:\n"
        "    - at_usd: 0.50\n      level: warn\n"
        "    - at_usd: 1.00\n      level: alert\n"
    )
    data = generate_report_data(tmp_path)
    assert data["executive_summary"]["cost_label"] == "$1.5000 — above alert threshold ⚠️"


def test_executive_summary_no_cost_awareness(tmp_path):
    """No cost_awareness in governance.yaml → plain '$X.XX' with no threshold label."""
    _make_session_log(tmp_path, [
        _allow(),
        {"event": "session_cost", "session_id": "s1", "model": "claude-sonnet-4-6",
         "total_usd": 0.42, "pricing_source": "live"},
    ])
    (tmp_path / "governance.yaml").write_text("owner: Test\n")
    data = generate_report_data(tmp_path)
    assert data["executive_summary"]["cost_label"] == "$0.4200"


def test_executive_summary_appears_first_in_markdown(tmp_path):
    """## Executive Summary section must appear before ## ROI Summary."""
    _make_session_log(tmp_path, [_allow()])
    out = tmp_path / "report.md"
    text = generate_report(tmp_path, out)
    exec_idx = text.index("## Executive Summary")
    roi_idx = text.index("## ROI Summary")
    assert exec_idx < roi_idx
    assert "✅ Yes" in text
