"""Tests for AgentGuard web server API endpoints."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from agentguard.web.server import app

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
