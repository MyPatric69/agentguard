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


# ── 5–7. verify --repair ──────────────────────────────────────────────────────

_STRUCTURED_NO_PINS_YAML = """\
owner: "Test Owner"
scope:
  authorized:
    - action: "Read files in ./src"
      reason: "Core task"
  prohibited:
    - action: "No deploys"
      reason: "Hard limit"
      severity: "HARD_LIMIT"
  requires_confirmation: []
escalation:
  contact: "owner@example.com"
killswitch: "Ctrl+C"
"""

_STRUCTURED_ALL_PINNED_YAML = """\
owner: "Test Owner"
scope:
  authorized:
    - action: "Read files in ./src"
      reason: "Core task"
  prohibited:
    - action: "No deploys"
      reason: "Hard limit"
      severity: "HARD_LIMIT"
  requires_confirmation: []
escalation:
  contact: "owner@example.com"
killswitch: "Ctrl+C"
concretization_pins:
  - field: "mission"
    input_hash: "aaaa"
    prompt_hash: "bbbb"
    output_hash: "cccc"
    model: "none (repaired)"
    provider: "none (repaired)"
    temperature: 0
    date: "2026-06-09"
    repaired: true
  - field: "hard_limits"
    input_hash: "aaaa"
    prompt_hash: "bbbb"
    output_hash: "dddd"
    model: "none (repaired)"
    provider: "none (repaired)"
    temperature: 0
    date: "2026-06-09"
    repaired: true
"""


def test_repair_generates_pins_when_missing(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(_STRUCTURED_NO_PINS_YAML)
    runner = CliRunner()
    result = runner.invoke(main, ["verify", "--config", str(gov), "--repair"])
    assert result.exit_code == 0
    assert "Repaired" in result.output
    import yaml

    data = yaml.safe_load(gov.read_text())
    assert len(data.get("concretization_pins", [])) >= 1


def test_repair_skips_when_all_pinned(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(_STRUCTURED_ALL_PINNED_YAML)
    runner = CliRunner()
    result = runner.invoke(main, ["verify", "--config", str(gov), "--repair"])
    assert result.exit_code == 0
    assert "nothing to repair" in result.output


def test_repair_pin_has_repaired_flag(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(_STRUCTURED_NO_PINS_YAML)
    runner = CliRunner()
    runner.invoke(main, ["verify", "--config", str(gov), "--repair"])
    import yaml

    data = yaml.safe_load(gov.read_text())
    pins = data.get("concretization_pins", [])
    assert all(p.get("repaired") is True for p in pins)
