"""Tests for AgentGuard web server API endpoints."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed — run: pip install agentguard[web]")

from fastapi.testclient import TestClient  # noqa: E402

from agentguard.web.server import app  # noqa: E402

client = TestClient(app)


def test_health():
    from agentguard import __version__

    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == __version__


def test_check_valid_path(tmp_path):
    mock_result = MagicMock()
    mock_result.stdout = json.dumps({"result": "ALL CLEAR", "checks": []})
    mock_result.stderr = ""
    with patch("agentguard.web.server.subprocess.run", return_value=mock_result):
        resp = client.get(f"/api/check?path={tmp_path}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] == "ALL CLEAR"


def test_check_subprocess_error():
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.stderr = "config not found"
    with patch("agentguard.web.server.subprocess.run", return_value=mock_result):
        resp = client.get("/api/check?path=/nonexistent")
    assert resp.status_code == 200
    assert "error" in resp.json()


def test_governance_exists(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text('owner: "Test"\nscope:\n  authorized: []\n')
    resp = client.get(f"/api/governance?path={tmp_path}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["exists"] is True
    assert data["governance"]["owner"] == "Test"


def test_governance_missing(tmp_path):
    resp = client.get(f"/api/governance?path={tmp_path}")
    assert resp.status_code == 200
    assert resp.json() == {"exists": False}


def test_verify_success(tmp_path):
    mock_result = MagicMock()
    mock_result.stdout = "All pins verified"
    mock_result.returncode = 0
    with patch("agentguard.web.server.subprocess.run", return_value=mock_result):
        resp = client.get(f"/api/verify?path={tmp_path}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "output" in data


def test_verify_failure(tmp_path):
    mock_result = MagicMock()
    mock_result.stdout = "Pin issues detected"
    mock_result.returncode = 1
    with patch("agentguard.web.server.subprocess.run", return_value=mock_result):
        resp = client.get(f"/api/verify?path={tmp_path}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False


def test_project_info_dot():
    resp = client.get("/api/project-info?path=.")
    assert resp.status_code == 200
    data = resp.json()
    assert "name" in data
    assert "path" in data
    assert data["name"] != "."
    assert data["name"] != ""
    assert data["path"].startswith("/")


def test_project_info_absolute(tmp_path):
    resp = client.get(f"/api/project-info?path={tmp_path}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == tmp_path.name
    assert data["path"] == str(tmp_path)


def test_projects_default():
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    data = resp.json()
    assert "projects" in data
    assert "count" in data
    assert isinstance(data["projects"], list)
    assert data["count"] == len(data["projects"])
    for p in data["projects"]:
        assert "name" in p
        assert "path" in p
        assert "has_governance" in p


def test_projects_with_governance(tmp_path):
    from agentguard.web.server import set_project_paths
    (tmp_path / "governance.yaml").write_text("owner: Test\n")
    set_project_paths([str(tmp_path)])
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    projects = resp.json()["projects"]
    assert len(projects) == 1
    assert projects[0]["has_governance"] is True
    assert projects[0]["name"] == tmp_path.name


def test_projects_without_governance(tmp_path):
    from agentguard.web.server import set_project_paths
    set_project_paths([str(tmp_path)])
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    projects = resp.json()["projects"]
    assert len(projects) == 1
    assert projects[0]["has_governance"] is False


def test_report_no_session_data(tmp_path):
    resp = client.get(f"/api/report?path={tmp_path}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_data"] is False
    assert data["total"] == 0


def test_report_with_session_log(tmp_path):
    import json as _json

    log_dir = tmp_path / ".agentguard"
    log_dir.mkdir()
    entries = [
        {"timestamp": "2026-06-11T10:00:00+00:00", "tool": "Bash",
         "decision": "allow", "input_summary": "ls", "reason": None,
         "session_id": "s1"},
        {"timestamp": "2026-06-11T10:01:00+00:00", "tool": "Edit",
         "decision": "deny", "input_summary": "bad file",
         "reason": "prohibited", "session_id": "s1"},
    ]
    (log_dir / "session.log").write_text(
        "\n".join(_json.dumps(e) for e in entries) + "\n"
    )
    resp = client.get(f"/api/report?path={tmp_path}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_data"] is True
    assert data["total"] == 2
    assert data["allowed"] == 1
    assert data["denied"] == 1


def test_verify_repair_no_pins(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(
        "owner: Test\nscope:\n"
        "  authorized:\n    - action: Read files\n      reason: Core task\n"
        "  prohibited:\n    - action: No deploys\n      reason: Hard limit\n"
        "      severity: HARD_LIMIT\n"
        "killswitch: Ctrl+C\n"
    )
    resp = client.get(f"/api/verify-repair?path={tmp_path}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["repaired"] >= 1
    import yaml
    updated = yaml.safe_load(gov.read_text())
    assert len(updated.get("concretization_pins", [])) >= 1


def test_verify_repair_all_pinned(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(
        "owner: Test\nscope:\n"
        "  authorized:\n    - action: Read files\n      reason: Core task\n"
        "  prohibited:\n    - action: No deploys\n      reason: Hard limit\n"
        "      severity: HARD_LIMIT\n"
        "killswitch: Ctrl+C\n"
        "concretization_pins:\n"
        "  - field: mission\n    input_hash: aaa\n    prompt_hash: bbb\n"
        "    output_hash: ccc\n    model: none (repaired)\n"
        "    provider: none (repaired)\n    temperature: 0\n"
        "    date: '2026-06-11'\n    repaired: true\n"
        "  - field: hard_limits\n    input_hash: aaa\n    prompt_hash: bbb\n"
        "    output_hash: ddd\n    model: none (repaired)\n"
        "    provider: none (repaired)\n    temperature: 0\n"
        "    date: '2026-06-11'\n    repaired: true\n"
    )
    resp = client.get(f"/api/verify-repair?path={tmp_path}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["repaired"] == 0


_EDITABLE_GOV = """\
owner: Test
scope:
  authorized:
    - action: Read files
      reason: Core task
      added: '2026-06-11'
  prohibited:
    - action: No deploys
      reason: Hard limit
      severity: HARD_LIMIT
      added: '2026-06-11'
  requires_confirmation: []
killswitch: Ctrl+C
"""


def test_governance_update_update_action(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(_EDITABLE_GOV)
    resp = client.post("/api/governance/update", json={
        "path": str(tmp_path),
        "section": "authorized",
        "action": "update",
        "index": 0,
        "item": {"action": "Read and write files", "reason": "Updated reason"}
    })
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    import yaml
    data = yaml.safe_load(gov.read_text())
    assert data["scope"]["authorized"][0]["action"] == "Read and write files"
    assert data["scope"]["authorized"][0]["reason"] == "Updated reason"


def test_governance_update_add_action(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(_EDITABLE_GOV)
    resp = client.post("/api/governance/update", json={
        "path": str(tmp_path),
        "section": "authorized",
        "action": "add",
        "item": {"action": "Write tests", "reason": "New rule"}
    })
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    import yaml
    data = yaml.safe_load(gov.read_text())
    authorized = data["scope"]["authorized"]
    assert len(authorized) == 2
    assert authorized[1]["action"] == "Write tests"


def test_governance_update_delete_action(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(_EDITABLE_GOV)
    resp = client.post("/api/governance/update", json={
        "path": str(tmp_path),
        "section": "prohibited",
        "action": "delete",
        "index": 0
    })
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    import yaml
    data = yaml.safe_load(gov.read_text())
    assert len(data["scope"]["prohibited"]) == 0


def test_governance_update_appends_history(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(_EDITABLE_GOV)
    client.post("/api/governance/update", json={
        "path": str(tmp_path),
        "section": "authorized",
        "action": "add",
        "item": {"action": "New rule", "reason": "Test"}
    })
    import yaml
    data = yaml.safe_load(gov.read_text())
    history = data.get("governance_history", [])
    assert len(history) >= 1
    assert history[-1]["tool"] == "agentguard web (inline editor)"


def test_watch_history_missing_log(tmp_path):
    resp = client.get(f"/api/watch/history?path={tmp_path}")
    assert resp.status_code == 200
    assert resp.json() == []


def test_watch_history_filters_and_limits(tmp_path):
    import json as _json

    log_dir = tmp_path / ".agentguard"
    log_dir.mkdir()
    entries = []
    for i in range(55):
        entries.append({
            "timestamp": "2026-06-21T10:00:00+00:00", "tool": "Bash",
            "decision": "allow", "input_summary": f"cmd{i}", "session_id": "s1",
        })
    entries.append({"event": "session_cost", "total_usd": 0.12, "session_id": "s1"})
    entries.append({"event": "post_tool_use", "tool_use_id": "x", "session_id": "s1"})
    entries.append({"event": "session_cost_notified", "at_usd": 0.50, "session_id": "s1"})
    (log_dir / "session.log").write_text(
        "\n".join(_json.dumps(e) for e in entries) + "\n"
    )
    resp = client.get(f"/api/watch/history?path={tmp_path}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 50
    assert all("decision" in e for e in data)
    skip = {"session_cost", "session_cost_notified", "post_tool_use"}
    assert all(e.get("event") not in skip for e in data)


def test_session_cost_missing_log(tmp_path):
    resp = client.get(f"/api/session/cost?path={tmp_path}")
    assert resp.status_code == 200
    assert resp.json() == {"session_cost": None}


def test_session_cost_returns_latest(tmp_path):
    import json as _json

    log_dir = tmp_path / ".agentguard"
    log_dir.mkdir()
    entries = [
        {"event": "session_cost", "session_id": "s1", "model": "claude-sonnet-4-6",
         "total_usd": 0.05, "input_tokens": 100},
        {"event": "session_cost", "session_id": "s2", "model": "claude-sonnet-4-6",
         "total_usd": 0.12, "input_tokens": 200},
    ]
    (log_dir / "session.log").write_text(
        "\n".join(_json.dumps(e) for e in entries) + "\n"
    )
    resp = client.get(f"/api/session/cost?path={tmp_path}")
    data = resp.json()["session_cost"]
    assert data is not None
    assert data["total_usd"] == 0.12
    assert data["session_id"] == "s2"


def test_cost_awareness_absent(tmp_path):
    (tmp_path / "governance.yaml").write_text("owner: Test\n")
    resp = client.get(f"/api/cost-awareness?path={tmp_path}")
    assert resp.status_code == 200
    assert resp.json() == {"cost_awareness": None}


def test_cost_awareness_returns_block(tmp_path):
    (tmp_path / "governance.yaml").write_text(
        "owner: Test\n"
        "cost_awareness:\n"
        "  thresholds:\n"
        "    - at_usd: 0.50\n"
        "      level: warn\n"
        "    - at_usd: 2.00\n"
        "      level: alert\n"
        "  repeat_last_threshold: true\n"
        "  repeat_interval_usd: 2.0\n"
    )
    resp = client.get(f"/api/cost-awareness?path={tmp_path}")
    assert resp.status_code == 200
    ca = resp.json()["cost_awareness"]
    assert ca is not None
    assert len(ca["thresholds"]) == 2
    assert ca["thresholds"][0]["at_usd"] == 0.5
    assert ca["thresholds"][0]["level"] == "warn"
    assert ca["repeat_last_threshold"] is True


def test_governance_update_cost_awareness(tmp_path):
    import yaml

    gov = tmp_path / "governance.yaml"
    gov.write_text("owner: Test\nscope:\n  authorized: []\n")
    new_ca = {
        "thresholds": [
            {"at_usd": 1.0, "level": "warn"},
            {"at_usd": 3.0, "level": "alert"},
        ],
        "repeat_last_threshold": True,
        "repeat_interval_usd": 2.0,
    }
    resp = client.post("/api/governance/update", json={
        "path": str(tmp_path),
        "cost_awareness": new_ca,
    })
    assert resp.status_code == 200
    assert resp.json()["success"] is True
    data = yaml.safe_load(gov.read_text())
    assert data["cost_awareness"]["thresholds"][0]["at_usd"] == 1.0
    assert data["cost_awareness"]["thresholds"][1]["level"] == "alert"
    history = data.get("governance_history", [])
    assert len(history) >= 1
    assert "cost_awareness" in history[-1]["action"]


def test_report_returns_roi_fields(tmp_path):
    """GET /api/report returns asked, session_cost, proposals after ROI refactor."""
    import json as _json

    log_dir = tmp_path / ".agentguard"
    log_dir.mkdir()
    proposals_dir = log_dir / "proposals"
    proposals_dir.mkdir()
    entries = [
        {"timestamp": "2026-06-21T10:00:00+00:00", "tool": "Bash",
         "decision": "allow", "input_summary": "ls", "session_id": "s1"},
        {"timestamp": "2026-06-21T10:01:00+00:00", "tool": "Edit",
         "decision": "ask", "input_summary": "edit file", "session_id": "s1"},
        {"event": "session_cost", "session_id": "s1", "model": "claude-sonnet-4-6",
         "total_usd": 0.07, "pricing_source": "live"},
    ]
    (log_dir / "session.log").write_text(
        "\n".join(_json.dumps(e) for e in entries) + "\n"
    )
    (proposals_dir / "abc.json").write_text(_json.dumps({
        "tool_use_id": "abc", "session_id": "s1", "tool_name": "Edit",
        "file_path": "test.py", "governance_reason": "review needed",
        "status": "pending", "timestamp": "2026-06-21T10:01:00+00:00", "pr_url": None,
    }))
    resp = client.get(f"/api/report?path={tmp_path}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["asked"] == 1
    assert data["session_cost"]["total_usd"] == 0.07
    assert data["session_cost"]["model"] == "claude-sonnet-4-6"
    assert data["proposals"]["total"] == 1
    assert data["proposals"]["pending"] == 1
    assert data["session_id"] == "s1"
    assert data["total"] == 2


# WebSocket PTY endpoint (/ws/terminal) requires a real PTY process and cannot
# be tested with TestClient. Manual test: open the web UI Terminal tab and
# verify the shell connects and agentguard commands run interactively.
