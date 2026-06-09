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
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


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


# WebSocket PTY endpoint (/ws/terminal) requires a real PTY process and cannot
# be tested with TestClient. Manual test: open the web UI Terminal tab and
# verify the shell connects and agentguard commands run interactively.
