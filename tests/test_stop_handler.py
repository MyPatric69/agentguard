"""Tests for the Stop hook handler (handle_stop) in enforcer.py."""

from __future__ import annotations

import io
import json

import pytest

from agentguard.enforcement.enforcer import handle_stop, run_enforce

# ── helpers ───────────────────────────────────────────────────────────────────


def _ask_entry(
    tool: str,
    tool_use_id: str,
    session_id: str = "sess-1",
    reason: str = "requires confirmation",
    timestamp: str = "2026-06-16T10:00:00+00:00",
) -> str:
    return json.dumps({
        "timestamp": timestamp,
        "tool": tool,
        "tool_use_id": tool_use_id,
        "input_summary": "some input",
        "decision": "ask",
        "reason": reason,
        "session_id": session_id,
    })


def _post_entry(tool: str, tool_use_id: str, session_id: str = "sess-1") -> str:
    return json.dumps({
        "timestamp": "2026-06-16T10:00:01+00:00",
        "event": "post_tool_use",
        "tool": tool,
        "tool_use_id": tool_use_id,
        "session_id": session_id,
        "duration_ms": 100,
    })


def _allow_entry(tool: str, session_id: str = "sess-1") -> str:
    return json.dumps({
        "timestamp": "2026-06-16T10:00:00+00:00",
        "tool": tool,
        "tool_use_id": "",
        "input_summary": "some input",
        "decision": "allow",
        "reason": None,
        "session_id": session_id,
    })


def _transcript_line(tool_name: str, tool_use_id: str, tool_input: dict) -> str:
    return json.dumps({
        "type": "assistant",
        "message": {
            "content": [
                {
                    "type": "tool_use",
                    "id": tool_use_id,
                    "name": tool_name,
                    "input": tool_input,
                }
            ]
        },
    })


def _stop_data(
    session_id: str,
    transcript_path: str,
    cwd: str,
) -> dict:
    return {
        "hook_event_name": "Stop",
        "session_id": session_id,
        "transcript_path": transcript_path,
        "cwd": cwd,
        "stop_hook_active": False,
    }


# ── 1. Unresolved ask → proposal file written with correct fields ─────────────


def test_unresolved_ask_writes_proposal(tmp_path):
    session_log = tmp_path / ".agentguard" / "session.log"
    session_log.parent.mkdir()
    session_log.write_text(
        _ask_entry("Edit", "tuid-1", reason="core enforcement layer", timestamp="2026-06-16T10:00:00+00:00")
        + "\n"
    )

    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        _transcript_line("Edit", "tuid-1", {"file_path": "agentguard/enforcement/enforcer.py", "old_string": "x", "new_string": "y"})
        + "\n"
    )

    data = _stop_data("sess-1", str(transcript), str(tmp_path))
    handle_stop(data, str(tmp_path))

    proposal_path = tmp_path / ".agentguard" / "proposals" / "tuid-1.json"
    assert proposal_path.exists()
    proposal = json.loads(proposal_path.read_text())

    assert proposal["tool_use_id"] == "tuid-1"
    assert proposal["session_id"] == "sess-1"
    assert proposal["tool_name"] == "Edit"
    assert proposal["file_path"] == "agentguard/enforcement/enforcer.py"
    assert proposal["tool_input"]["old_string"] == "x"
    assert proposal["tool_input"]["new_string"] == "y"
    assert proposal["governance_reason"] == "core enforcement layer"
    assert proposal["status"] == "pending"
    assert proposal["timestamp"] == "2026-06-16T10:00:00+00:00"


# ── 2. Resolved ask (matching PostToolUse) → no proposal written ──────────────


def test_resolved_ask_no_proposal(tmp_path):
    session_log = tmp_path / ".agentguard" / "session.log"
    session_log.parent.mkdir()
    session_log.write_text(
        _ask_entry("Edit", "tuid-resolved") + "\n" + _post_entry("Edit", "tuid-resolved") + "\n"
    )

    data = _stop_data("sess-1", "", str(tmp_path))
    handle_stop(data, str(tmp_path))

    proposals_dir = tmp_path / ".agentguard" / "proposals"
    assert not proposals_dir.exists() or not list(proposals_dir.iterdir())


# ── 3. Idempotency: Stop fires twice → pending overwritten, not duplicated ────


def test_idempotency_pending_overwritten(tmp_path):
    session_log = tmp_path / ".agentguard" / "session.log"
    session_log.parent.mkdir()
    session_log.write_text(_ask_entry("Edit", "tuid-idem") + "\n")

    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        _transcript_line("Edit", "tuid-idem", {"file_path": "pyproject.toml", "old_string": "a", "new_string": "b"})
        + "\n"
    )
    data = _stop_data("sess-1", str(transcript), str(tmp_path))

    handle_stop(data, str(tmp_path))
    handle_stop(data, str(tmp_path))

    proposals_dir = tmp_path / ".agentguard" / "proposals"
    files = list(proposals_dir.iterdir())
    assert len(files) == 1
    proposal = json.loads(files[0].read_text())
    assert proposal["status"] == "pending"


# ── 4. Non-pending proposal → not overwritten ─────────────────────────────────


def test_non_pending_proposal_not_overwritten(tmp_path):
    session_log = tmp_path / ".agentguard" / "session.log"
    session_log.parent.mkdir()
    session_log.write_text(_ask_entry("Edit", "tuid-done") + "\n")

    proposals_dir = tmp_path / ".agentguard" / "proposals"
    proposals_dir.mkdir(parents=True)
    existing_proposal = {"tool_use_id": "tuid-done", "status": "pr_created", "pr_url": "https://github.com/x/y/pull/1"}
    (proposals_dir / "tuid-done.json").write_text(json.dumps(existing_proposal))

    data = _stop_data("sess-1", "", str(tmp_path))
    handle_stop(data, str(tmp_path))

    result = json.loads((proposals_dir / "tuid-done.json").read_text())
    assert result["status"] == "pr_created"
    assert result.get("pr_url") == "https://github.com/x/y/pull/1"


# ── 5. No asks in session → no proposals written ──────────────────────────────


def test_no_asks_no_proposals(tmp_path):
    session_log = tmp_path / ".agentguard" / "session.log"
    session_log.parent.mkdir()
    session_log.write_text(
        _allow_entry("Bash") + "\n" + _post_entry("Bash", "tuid-x") + "\n"
    )

    data = _stop_data("sess-1", "", str(tmp_path))
    handle_stop(data, str(tmp_path))

    proposals_dir = tmp_path / ".agentguard" / "proposals"
    assert not proposals_dir.exists() or not list(proposals_dir.iterdir())


# ── 6. Transcript missing → proposal written with tool_input: null ────────────


def test_transcript_missing_proposal_has_null_tool_input(tmp_path):
    session_log = tmp_path / ".agentguard" / "session.log"
    session_log.parent.mkdir()
    session_log.write_text(_ask_entry("Write", "tuid-notx", reason="protected path") + "\n")

    data = _stop_data("sess-1", str(tmp_path / "nonexistent.jsonl"), str(tmp_path))
    handle_stop(data, str(tmp_path))

    proposal_path = tmp_path / ".agentguard" / "proposals" / "tuid-notx.json"
    assert proposal_path.exists()
    proposal = json.loads(proposal_path.read_text())
    assert proposal["tool_input"] is None
    assert proposal["file_path"] is None
    assert proposal["tool_name"] == "Write"
    assert proposal["status"] == "pending"


# ── 7. Session log missing → handle_stop exits silently ──────────────────────


def test_no_session_log_exits_silently(tmp_path):
    data = _stop_data("sess-1", "", str(tmp_path))
    handle_stop(data, str(tmp_path))
    assert not (tmp_path / ".agentguard" / "proposals").exists()


# ── 8. Dispatch: Stop hook_event_name → handle_stop called, exit 0 ───────────


def test_stop_dispatch_exit_0(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text("owner: Alice\nscope:\n  authorized: []\n  prohibited: []\n  requires_confirmation: []\nescalation:\n  contact: alice@example.com\nkillswitch: Ctrl+C\n")
    stop_input = json.dumps({
        "hook_event_name": "Stop",
        "session_id": "sess-stop",
        "transcript_path": str(tmp_path / "t.jsonl"),
        "cwd": str(tmp_path),
        "stop_hook_active": False,
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(stop_input))
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0
    assert capsys.readouterr().out == ""


# ── 9. PreToolUse and PostToolUse dispatch unchanged (regression) ─────────────


def test_pre_and_post_dispatch_regression(tmp_path, monkeypatch, capsys):
    gov = "owner: Alice\nscope:\n  authorized: []\n  prohibited:\n    - action: 'No git push'\n      reason: 'test'\n      severity: HARD_LIMIT\n  requires_confirmation: []\nescalation:\n  contact: a@b.com\nkillswitch: x\n"
    (tmp_path / "governance.yaml").write_text(gov)

    pre_input = json.dumps({
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git push origin main"},
        "cwd": str(tmp_path),
        "session_id": "sess-r",
        "tool_use_id": "tuid-r",
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(pre_input))
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 2
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


# ── 10. tool_use_id written to PreToolUse session.log entries ────────────────


def test_pre_tool_use_logs_tool_use_id(tmp_path, monkeypatch):
    gov = "owner: Alice\nscope:\n  authorized: []\n  prohibited: []\n  requires_confirmation: []\nescalation:\n  contact: a@b.com\nkillswitch: x\n"
    (tmp_path / "governance.yaml").write_text(gov)

    pre_input = json.dumps({
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "pytest"},
        "cwd": str(tmp_path),
        "session_id": "sess-uid",
        "tool_use_id": "tuid-logged",
    })
    monkeypatch.setattr("sys.stdin", io.StringIO(pre_input))
    with pytest.raises(SystemExit):
        run_enforce()

    session_log = tmp_path / ".agentguard" / "session.log"
    entry = json.loads(session_log.read_text().strip())
    assert entry["tool_use_id"] == "tuid-logged"
    assert entry["decision"] == "allow"
