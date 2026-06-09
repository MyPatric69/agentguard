"""Tests for agentguard verify command."""

from __future__ import annotations

from click.testing import CliRunner

from agentguard.cli import main


_PINS_YAML = """\
owner: "Test Owner"
scope:
  authorized:
    - action: "Read files in ./src"
      reason: "Core task"
      added: "2026-06-09"
  prohibited:
    - action: "Deploy to production"
      reason: "Hard limit"
      severity: "HARD_LIMIT"
      added: "2026-06-09"
  requires_confirmation:
    - action: "Any file deletion"
      reason: "Irreversible"
      added: "2026-06-09"
escalation:
  contact: "owner@example.com"
  method: "log"
  trigger: "2+ critical failures or loop detected"
killswitch: "Ctrl+C"
governance_history:
  - date: "2026-06-09"
    action: "Initial governance created"
    tool: "agentguard init --guided"
    version: "0.5.1"
concretization_pins:
  - field: "mission"
    input_hash: "abc123def456abcd"
    prompt_hash: "def456abc123ef01"
    output_hash: "1234567890abcdef"
    model: "claude-sonnet-4-20250514"
    provider: "anthropic"
    temperature: 0
    date: "2026-06-09"
"""

_NO_PINS_YAML = """\
owner: "Test Owner"
scope:
  authorized: "Read files"
  prohibited: "No deploys"
  requires_confirmation: "File deletes"
escalation:
  contact: "owner@example.com"
  method: "log"
  trigger: "2+ critical failures or loop detected"
killswitch: "Ctrl+C"
"""

_BAD_TEMP_YAML = """\
owner: "Test Owner"
scope:
  authorized: "Read files"
escalation:
  contact: "owner@example.com"
  method: "log"
  trigger: "2+ critical failures or loop detected"
killswitch: "Ctrl+C"
concretization_pins:
  - field: "mission"
    input_hash: "abc123def456abcd"
    prompt_hash: "def456abc123ef01"
    output_hash: "1234567890abcdef"
    model: "gpt-4o"
    provider: "openai"
    temperature: 1
    date: "2026-06-09"
"""


# ── 1. verify exits 0 when all pins are valid ─────────────────────────────────

def test_verify_exits_0_with_valid_pins(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(_PINS_YAML)
    runner = CliRunner()
    result = runner.invoke(main, ["verify", "--config", str(gov)])
    assert result.exit_code == 0
    assert "ok" in result.output or "✅" in result.output


# ── 2. verify exits 1 when no pins found ─────────────────────────────────────

def test_verify_exits_1_when_no_pins(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(_NO_PINS_YAML)
    runner = CliRunner()
    result = runner.invoke(main, ["verify", "--config", str(gov)])
    assert result.exit_code == 1
    assert "missing" in result.output


# ── 3. verify exits 1 when temperature is not 0 ──────────────────────────────

def test_verify_exits_1_when_temperature_not_zero(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(_BAD_TEMP_YAML)
    runner = CliRunner()
    result = runner.invoke(main, ["verify", "--config", str(gov)])
    assert result.exit_code == 1
    assert "drift" in result.output


# ── 4. verify exits 2 when file not found ────────────────────────────────────

def test_verify_exits_2_when_file_not_found(tmp_path):
    runner = CliRunner()
    result = runner.invoke(main, ["verify", "--config", str(tmp_path / "nonexistent.yaml")])
    assert result.exit_code == 2
