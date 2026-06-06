"""Tests for agentguard init --guided and agentguard/guided/concretizer.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from agentguard.cli import main
from agentguard.guided.concretizer import (
    _split_mission_concretized,
    concretize_field,
    concretize_mission,
)

# ── Shared mock AI results ────────────────────────────────────────────────────

_MOCK_MISSION = {
    "authorized": "Read and write Python files in ./src",
    "prohibited": "No database operations, no git push to main",
    "requires_confirmation": "Any file deletion outside ./tmp",
    "confidence": "HIGH",
    "ambiguities": [],
    "_provider": "anthropic",
    "_model": "claude-haiku-4-5-20251001",
}

_MOCK_FIELD = {
    "concretized": "No writes to ./production directory",
    "enforcement_notes": "Check file paths in Write tool calls",
    "confidence": "HIGH",
    "ambiguities": [],
    "_provider": "anthropic",
    "_model": "claude-haiku-4-5-20251001",
}

_HAPPY_PATH_INPUT = (
    "Jane Smith\n"        # step 1: owner
    "implement features\n"  # step 2: mission
    "1\n"                 # accept mission concretization
    "no production writes\n"  # step 3: hard limits
    "1\n"                 # accept hard limits concretization
    "owner@example.com\n"  # step 4: escalation
    "Ctrl+C\n"            # step 5: killswitch
    "1\n"                 # final review: save
)


# ── 1. Complete happy path: governance.yaml created ───────────────────────────

def test_guided_complete_flow_saves_governance_yaml():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with (
            mock.patch("agentguard.guided.concretizer._ai_available", return_value=True),
            mock.patch("agentguard.guided.concretizer.concretize_mission", return_value=_MOCK_MISSION),
            mock.patch("agentguard.guided.concretizer.concretize_field", return_value=_MOCK_FIELD),
        ):
            result = runner.invoke(main, ["init", "--guided"], input=_HAPPY_PATH_INPUT)

        assert result.exit_code == 0, result.output
        assert Path("governance.yaml").exists()
        gov = Path("governance.yaml").read_text()
        assert 'owner: "Jane Smith"' in gov


# ── 2. Concretize field: AI response is parsed correctly ─────────────────────

def test_concretize_field_parses_ai_response(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)

    mock_response = json.dumps(
        {
            "concretized": "No writes to ./production files",
            "enforcement_notes": "Check Write tool file_path argument",
            "confidence": "HIGH",
            "ambiguities": [],
        }
    )
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response):
        result = concretize_field("hard_limits", "no production writes")

    assert result["concretized"] == "No writes to ./production files"
    assert result["confidence"] == "HIGH"
    assert not result.get("_fallback")


# ── 3. Concretize mission: splits into three scope fields ────────────────────

def test_concretize_mission_returns_three_scope_fields(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)

    mock_response = json.dumps(
        {
            "authorized": "Read and write Python files in ./src",
            "prohibited": "No database operations, no git push",
            "requires_confirmation": "Any file deletion",
            "confidence": "HIGH",
            "ambiguities": [],
        }
    )
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response):
        result = concretize_mission("implement Python features")

    assert "authorized" in result
    assert "prohibited" in result
    assert "requires_confirmation" in result
    assert result["confidence"] == "HIGH"
    assert not result.get("_fallback")


# ── 4. No API key: concretize_field returns fallback ─────────────────────────

def test_concretize_field_no_api_key_returns_fallback(monkeypatch):
    monkeypatch.delenv("AGENTGUARD_AI_PROVIDER", raising=False)
    monkeypatch.delenv("AGENTGUARD_AI_API_KEY", raising=False)

    result = concretize_field("hard_limits", "no production writes")

    assert result["_fallback"] is True
    assert result["concretized"] == "no production writes"
    assert result["confidence"] == "LOW"


# ── 5. API failure: concretize_field falls back gracefully ───────────────────

def test_concretize_field_api_failure_returns_fallback(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)

    with mock.patch(
        "agentguard.guided.concretizer._call_provider", side_effect=Exception("timeout")
    ):
        result = concretize_field("hard_limits", "no production writes")

    assert result["_fallback"] is True
    assert "no production writes" in result["concretized"]


# ── 6. No API key in env: guided init shows clear error ──────────────────────

def test_guided_no_api_key_shows_error():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with mock.patch("agentguard.guided.concretizer._ai_available", return_value=False):
            result = runner.invoke(main, ["init", "--guided"])

    assert "requires an AI provider" in result.output
    assert result.exit_code == 0


# ── 7. Adjustment loop: 3 rounds max, then saved as-is ───────────────────────

def test_guided_adjustment_loop_max_3_rounds_saves_as_is():
    runner = CliRunner()
    # Input for hard_limits: enter → adjust×2 → 3rd "2" → save as-is automatically
    user_input = (
        "Jane Smith\n"             # step 1: owner
        "implement features\n"     # step 2: mission
        "1\n"                      # accept mission
        "no production writes\n"   # step 3: hard limits (round 0)
        "2\n"                      # round 0: adjust
        "be more specific\n"       # adjustment 1
        "2\n"                      # round 1: adjust
        "even more specific\n"     # adjustment 2
        "2\n"                      # round 2: max rounds → save as-is
        "owner@example.com\n"      # step 4: escalation
        "Ctrl+C kill\n"            # step 5: killswitch
        "1\n"                      # final review: save
    )
    with runner.isolated_filesystem():
        with (
            mock.patch("agentguard.guided.concretizer._ai_available", return_value=True),
            mock.patch("agentguard.guided.concretizer.concretize_mission", return_value=_MOCK_MISSION),
            mock.patch("agentguard.guided.concretizer.concretize_field", return_value=_MOCK_FIELD),
        ):
            result = runner.invoke(main, ["init", "--guided"], input=user_input)

        assert result.exit_code == 0, result.output
        assert "Maximum adjustments" in result.output
        assert Path("governance.yaml").exists()


# ── 9. Escalation: invalid contact triggers re-entry ────────────────────────

def test_guided_escalation_invalid_contact_triggers_reentry():
    runner = CliRunner()
    user_input = (
        "Jane Smith\n"             # step 1: owner
        "implement features\n"     # step 2: mission
        "1\n"                      # accept mission
        "no production writes\n"   # step 3: hard limits
        "1\n"                      # accept hard limits
        "invalidname\n"            # step 4: escalation (invalid — single word, no @)
        "n\n"                      # decline override
        "owner@example.com\n"      # step 4: escalation (valid — has @)
        "Ctrl+C\n"                 # step 5: killswitch
        "1\n"                      # final review: save
    )
    with runner.isolated_filesystem():
        with (
            mock.patch("agentguard.guided.concretizer._ai_available", return_value=True),
            mock.patch("agentguard.guided.concretizer.concretize_mission", return_value=_MOCK_MISSION),
            mock.patch("agentguard.guided.concretizer.concretize_field", return_value=_MOCK_FIELD),
        ):
            result = runner.invoke(main, ["init", "--guided"], input=user_input)

        assert result.exit_code == 0, result.output
        assert "Invalid contact" in result.output
        gov = Path("governance.yaml").read_text()

    assert 'contact: "owner@example.com"' in gov


# ── 10. Bug 4: Confirms field populated in governance.yaml ───────────────────

def test_guided_confirms_field_written_to_governance_yaml():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with (
            mock.patch("agentguard.guided.concretizer._ai_available", return_value=True),
            mock.patch("agentguard.guided.concretizer.concretize_mission", return_value=_MOCK_MISSION),
            mock.patch("agentguard.guided.concretizer.concretize_field", return_value=_MOCK_FIELD),
        ):
            result = runner.invoke(main, ["init", "--guided"], input=_HAPPY_PATH_INPUT)

        assert result.exit_code == 0, result.output
        gov = Path("governance.yaml").read_text()

    assert 'requires_confirmation: "Any file deletion outside ./tmp"' in gov


# ── 8. Ctrl+C: save-progress prompt is shown ─────────────────────────────────

def test_guided_ctrl_c_shows_save_progress_prompt():
    runner = CliRunner()
    call_count = [0]

    def step_side_effect(step, results):
        call_count[0] += 1
        if call_count[0] == 1:
            results["owner"] = "Jane Smith"
        else:
            raise KeyboardInterrupt

    with runner.isolated_filesystem():
        with (
            mock.patch("agentguard.guided.concretizer._ai_available", return_value=True),
            mock.patch("agentguard.cli._run_guided_step", side_effect=step_side_effect),
        ):
            result = runner.invoke(main, ["init", "--guided"], input="n\n")

    assert "Save progress" in result.output
    assert result.exit_code == 0


# ── 11. Mission Format A: three explicit fields mapped correctly ──────────────

def test_concretize_mission_format_a_maps_three_fields(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)

    mock_response = json.dumps({
        "authorized": "Read and write Python files in ./src",
        "prohibited": "No database writes, no git push to main",
        "requires_confirmation": "Any file deletion",
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response):
        result = concretize_mission("implement features safely")

    assert result["authorized"] == "Read and write Python files in ./src"
    assert result["prohibited"] == "No database writes, no git push to main"
    assert result["requires_confirmation"] == "Any file deletion"
    assert result["confidence"] == "HIGH"
    assert not result.get("_fallback")
    assert not result.get("_format_b")


# ── 12. Mission Format B: single concretized split into three fields ──────────

def test_concretize_mission_format_b_split_into_three_fields(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)

    mock_response = json.dumps({
        "concretized": (
            "Read and write Python files in ./src. "
            "Must never delete production data. "
            "Any deployment requires human approval."
        ),
        "confidence": "MEDIUM",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response):
        result = concretize_mission("implement features")

    assert "authorized" in result
    assert "prohibited" in result
    assert "requires_confirmation" in result
    assert result.get("_format_b") is True
    assert not result.get("_fallback")
    assert "never" in result["prohibited"].lower()
    assert "approval" in result["requires_confirmation"].lower()


# ── 13. _split_mission_concretized: prohibited sentences extracted ────────────

def test_split_mission_concretized_extracts_prohibited_sentences():
    text = (
        "May read Python files in ./src. "
        "Must never write to ./production directory. "
        "Run pytest to verify changes."
    )
    authorized, prohibited, confirmation = _split_mission_concretized(text)

    assert "Must never" in prohibited
    assert "never" not in authorized.lower()
    assert confirmation == ""


# ── 14. _split_mission_concretized: confirmation sentences extracted ──────────

def test_split_mission_concretized_extracts_confirmation_sentences():
    text = (
        "Modify Python files in ./src. "
        "Any deployment requires human approval. "
        "Run tests automatically."
    )
    authorized, prohibited, confirmation = _split_mission_concretized(text)

    assert "approval" in confirmation.lower()
    assert "approval" not in authorized.lower()
    assert prohibited == ""
