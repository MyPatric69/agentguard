"""Tests for agentguard init --guided and agentguard/guided/concretizer.py."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from click.testing import CliRunner

from agentguard.cli import main
from agentguard.guided.concretizer import (
    CONCRETIZATION_MODEL_OVERRIDES,
    _normalize_from_concretized,
    _split_mission_concretized,
    concretize_field,
    concretize_mission,
)

# ── Shared mock AI results ────────────────────────────────────────────────────

_MOCK_MISSION = {
    "authorized": [{"action": "Read and write Python files in ./src", "reason": "Core task"}],
    "prohibited": [{"action": "No database operations, no git push to main", "reason": "Hard limit", "severity": "HARD_LIMIT"}],
    "requires_confirmation": [{"action": "Any file deletion outside ./tmp", "reason": "Needs human sign-off"}],
    "confidence": "HIGH",
    "ambiguities": [],
    "_provider": "anthropic",
    "_model": "claude-haiku-4-5-20251001",
}

_MOCK_FIELD = {
    "prohibited": [{"action": "No writes to ./production directory", "reason": "Production writes prohibited", "severity": "HARD_LIMIT"}],
    "enforcement_notes": "Check file paths in Write tool calls",
    "confidence": "HIGH",
    "ambiguities": [],
    "_provider": "anthropic",
    "_model": "claude-haiku-4-5-20251001",
}

_HAPPY_PATH_INPUT = (
    "\n"                  # pre-inquiry screen: press ENTER
    "Jane Smith\n"        # step 1: owner
    "implement features\n"  # step 2: mission
    "1\n"                 # accept mission concretization
    "no production writes\n"  # step 3: hard limits
    "1\n"                 # accept hard limits concretization
    "owner@example.com\n"  # step 4: escalation
    "Ctrl+C\n"            # step 5: killswitch
    "n\n"                 # cost awareness: skip
    "1\n"                 # final review: save
)

_MOCK_MISSION_MEDIUM = {
    "authorized": [{"action": "Read and write Python files in ./src", "reason": "Core task"}],
    "prohibited": [{"action": "No database operations, no git push to main", "reason": "Hard limit", "severity": "HARD_LIMIT"}],
    "requires_confirmation": [{"action": "Any file deletion outside ./tmp", "reason": "Needs sign-off"}],
    "confidence": "MEDIUM",
    "ambiguities": ["Definition of 'features' is unclear", "Scope of file access not bounded"],
    "_provider": "anthropic",
    "_model": "claude-haiku-4-5-20251001",
}


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
    assert isinstance(result["prohibited"], list)
    assert result["prohibited"][0]["action"] == "no production writes"
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
    assert isinstance(result["prohibited"], list)
    assert "no production writes" in result["prohibited"][0]["action"]


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
        "\n"                       # pre-inquiry screen: press ENTER
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
        "n\n"                      # cost awareness: skip
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
        "\n"                       # pre-inquiry screen: press ENTER
        "Jane Smith\n"             # step 1: owner
        "implement features\n"     # step 2: mission
        "1\n"                      # accept mission
        "no production writes\n"   # step 3: hard limits
        "1\n"                      # accept hard limits
        "invalidname\n"            # step 4: escalation (invalid — single word, no @)
        "n\n"                      # decline override
        "owner@example.com\n"      # step 4: escalation (valid — has @)
        "Ctrl+C\n"                 # step 5: killswitch
        "n\n"                      # cost awareness: skip
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

    assert 'action: "Any file deletion outside ./tmp"' in gov


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
            result = runner.invoke(main, ["init", "--guided"], input="\nn\n")

    assert "Save progress" in result.output
    assert result.exit_code == 0


# ── 11. Mission Format A: three explicit fields mapped correctly ──────────────

def test_concretize_mission_format_a_maps_three_fields(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)

    # AI returns new structured list format
    mock_response = json.dumps({
        "authorized": [{"action": "Read and write Python files in ./src", "reason": "Core task"}],
        "prohibited": [{"action": "No database writes, no git push to main", "reason": "Hard limit", "severity": "HARD_LIMIT"}],
        "requires_confirmation": [{"action": "Any file deletion", "reason": "Needs sign-off"}],
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response):
        result = concretize_mission("implement features safely")

    assert isinstance(result["authorized"], list)
    assert result["authorized"][0]["action"] == "Read and write Python files in ./src"
    assert isinstance(result["prohibited"], list)
    assert result["prohibited"][0]["action"] == "No database writes, no git push to main"
    assert result["prohibited"][0]["severity"] == "HARD_LIMIT"
    assert isinstance(result["requires_confirmation"], list)
    assert result["requires_confirmation"][0]["action"] == "Any file deletion"
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

    assert isinstance(result["authorized"], list)
    assert isinstance(result["prohibited"], list)
    assert isinstance(result["requires_confirmation"], list)
    assert result.get("_format_b") is True
    assert not result.get("_fallback")
    assert any("never" in item.get("action", "").lower() for item in result["prohibited"])
    assert any("approval" in item.get("action", "").lower() for item in result["requires_confirmation"])


# ── 13. _split_mission_concretized: prohibited sentences extracted ────────────

def test_split_mission_concretized_extracts_prohibited_sentences():
    text = (
        "May read Python files in ./src. "
        "Must never write to ./production directory. "
        "Run pytest to verify changes."
    )
    authorized, prohibited, confirmation = _split_mission_concretized(text)

    assert isinstance(prohibited, list)
    assert any("Must never" in item.get("action", "") for item in prohibited)
    assert not any("never" in item.get("action", "").lower() for item in authorized)
    assert confirmation == []


# ── 14. _split_mission_concretized: confirmation sentences extracted ──────────

def test_split_mission_concretized_extracts_confirmation_sentences():
    text = (
        "Modify Python files in ./src. "
        "Any deployment requires human approval. "
        "Run tests automatically."
    )
    authorized, prohibited, confirmation = _split_mission_concretized(text)

    assert isinstance(confirmation, list)
    assert any("approval" in item.get("action", "").lower() for item in confirmation)
    assert not any("approval" in item.get("action", "").lower() for item in authorized)
    assert prohibited == []


# ── 15. Pre-inquiry screen shown before Step 1 ───────────────────────────────

def test_guided_shows_pre_inquiry_screen_before_step_1():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with (
            mock.patch("agentguard.guided.concretizer._ai_available", return_value=True),
            mock.patch("agentguard.guided.concretizer.concretize_mission", return_value=_MOCK_MISSION),
            mock.patch("agentguard.guided.concretizer.concretize_field", return_value=_MOCK_FIELD),
        ):
            result = runner.invoke(main, ["init", "--guided"], input=_HAPPY_PATH_INPUT)

    assert result.exit_code == 0, result.output
    assert "BEFORE YOU START" in result.output
    assert "Press ENTER to continue" in result.output
    pre_idx = result.output.index("BEFORE YOU START")
    step1_idx = result.output.index("Step 1/5")
    assert pre_idx < step1_idx


# ── 16. Ambiguity prompt shown when confidence MEDIUM + ambiguities present ───

def test_guided_ambiguity_prompt_shown_for_medium_confidence():
    runner = CliRunner()
    # After accepting [1] mission, ambiguity panel appears → choose [1] Proceed
    user_input = (
        "\n"                       # pre-inquiry ENTER
        "Jane Smith\n"             # step 1: owner
        "implement features\n"     # step 2: mission
        "1\n"                      # accept concretized mission
        "1\n"                      # ambiguity panel: [1] Proceed
        "no production writes\n"   # step 3: hard limits
        "1\n"                      # accept hard limits
        "owner@example.com\n"      # step 4: escalation
        "Ctrl+C\n"                 # step 5: killswitch
        "n\n"                      # cost awareness: skip
        "1\n"                      # final review: save
    )
    with runner.isolated_filesystem():
        with (
            mock.patch("agentguard.guided.concretizer._ai_available", return_value=True),
            mock.patch("agentguard.guided.concretizer.concretize_mission", return_value=_MOCK_MISSION_MEDIUM),
            mock.patch("agentguard.guided.concretizer.concretize_field", return_value=_MOCK_FIELD),
        ):
            result = runner.invoke(main, ["init", "--guided"], input=user_input)

    assert result.exit_code == 0, result.output
    assert "UNRESOLVED AMBIGUITIES" in result.output


# ── 17. Ambiguity prompt NOT shown when confidence HIGH + no ambiguities ──────

def test_guided_ambiguity_prompt_not_shown_for_high_confidence():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with (
            mock.patch("agentguard.guided.concretizer._ai_available", return_value=True),
            mock.patch("agentguard.guided.concretizer.concretize_mission", return_value=_MOCK_MISSION),
            mock.patch("agentguard.guided.concretizer.concretize_field", return_value=_MOCK_FIELD),
        ):
            result = runner.invoke(main, ["init", "--guided"], input=_HAPPY_PATH_INPUT)

    assert result.exit_code == 0, result.output
    assert "UNRESOLVED AMBIGUITIES" not in result.output


# ── 18. [1] Proceed: ambiguities written as structured list in governance.yaml ─

def test_guided_proceed_writes_ambiguities_as_yaml_comments():
    runner = CliRunner()
    user_input = (
        "\n"
        "Jane Smith\n"
        "implement features\n"
        "1\n"                      # accept mission
        "1\n"                      # ambiguity: [1] Proceed
        "no production writes\n"
        "1\n"                      # accept hard limits (HIGH, no ambiguity panel)
        "owner@example.com\n"
        "Ctrl+C\n"
        "n\n"                      # cost awareness: skip
        "1\n"
    )
    with runner.isolated_filesystem():
        with (
            mock.patch("agentguard.guided.concretizer._ai_available", return_value=True),
            mock.patch("agentguard.guided.concretizer.concretize_mission", return_value=_MOCK_MISSION_MEDIUM),
            mock.patch("agentguard.guided.concretizer.concretize_field", return_value=_MOCK_FIELD),
        ):
            result = runner.invoke(main, ["init", "--guided"], input=user_input)

        assert result.exit_code == 0, result.output
        gov = Path("governance.yaml").read_text()
        assert "unresolved_ambiguities" in gov
        assert "Definition of 'features' is unclear" in gov


# ── 19. [2] Address: re-concretization triggered with clarification ───────────

def test_guided_address_ambiguity_triggers_reconcretization():
    runner = CliRunner()
    user_input = (
        "\n"
        "Jane Smith\n"
        "implement features\n"
        "1\n"                      # accept mission (round 0)
        "2\n"                      # ambiguity: [2] Address
        "features means Python files in ./src only\n"  # clarification
        "1\n"                      # accept re-concretized mission (round 1)
        "1\n"                      # ambiguity panel again: [1] Proceed (MEDIUM again)
        "no production writes\n"
        "1\n"
        "owner@example.com\n"
        "Ctrl+C\n"
        "n\n"                      # cost awareness: skip
        "1\n"
    )
    concretize_call_args = []

    def tracking_concretize_mission(user_input):
        concretize_call_args.append(user_input)
        return _MOCK_MISSION_MEDIUM

    with runner.isolated_filesystem():
        with (
            mock.patch("agentguard.guided.concretizer._ai_available", return_value=True),
            mock.patch("agentguard.guided.concretizer.concretize_mission", side_effect=tracking_concretize_mission),
            mock.patch("agentguard.guided.concretizer.concretize_field", return_value=_MOCK_FIELD),
        ):
            result = runner.invoke(main, ["init", "--guided"], input=user_input)

    assert result.exit_code == 0, result.output
    assert len(concretize_call_args) >= 2, "concretize_mission should be called twice"
    assert "Clarification:" in concretize_call_args[1]


# ── 20. Structured YAML: governance.yaml contains action/reason/severity ──────

def test_guided_governance_yaml_has_structured_scope():
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

    assert "authorized:" in gov
    assert "prohibited:" in gov
    assert "requires_confirmation:" in gov
    assert 'action: "Read and write Python files in ./src"' in gov
    assert 'severity: "HARD_LIMIT"' in gov
    assert "governance_history:" in gov
    assert 'action: "Initial governance created"' in gov


# ── 21. Structured YAML: reason field present for every item ──────────────────

def test_guided_governance_yaml_has_reason_fields():
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

    assert "reason:" in gov
    assert "added:" in gov


# ── 22. Format B fallback wraps sentences with auto-generated reason ──────────

def test_concretize_mission_format_b_has_auto_reason(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)

    mock_response = json.dumps({
        "concretized": "Read Python files in ./src. Must never push to main.",
        "confidence": "MEDIUM",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response):
        result = concretize_mission("implement features")

    for item in result["authorized"] + result["prohibited"]:
        assert "reason" in item
        assert item["reason"] == "Extracted from governance definition — review and refine"


# ── 23. Two-shot prompt produces Format A correctly ───────────────────────────

def test_concretize_mission_two_shot_returns_format_a(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)

    mock_response = json.dumps({
        "authorized": [{"action": "Review performance metrics", "reason": "Core task"}],
        "prohibited": [{"action": "Deploy without approval", "reason": "Hard limit", "severity": "HARD_LIMIT"}],
        "requires_confirmation": [{"action": "Add new dependencies", "reason": "Security surface"}],
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response):
        result = concretize_mission("improve system performance")

    assert isinstance(result["authorized"], list)
    assert isinstance(result["prohibited"], list)
    assert isinstance(result["requires_confirmation"], list)
    assert result["prohibited"][0]["severity"] == "HARD_LIMIT"
    assert not result.get("_format_b")
    assert not result.get("_fallback")


# ── 24. _normalize_from_concretized: "never" → prohibited HARD_LIMIT ─────────

def test_normalize_from_concretized_hard_limit_sentence():
    text = "Read Python files in ./src. The agent must never push to main."
    parts = _normalize_from_concretized(text)

    assert any(item.get("severity") == "HARD_LIMIT" for item in parts["prohibited"])
    assert any("Read Python" in item["action"] for item in parts["authorized"])


# ── 25. _normalize_from_concretized: "must not" → prohibited WARNING ──────────

def test_normalize_from_concretized_must_not_is_warning():
    text = "Read source files in ./src. The agent must not write to ./production."
    parts = _normalize_from_concretized(text)

    prohibited = parts["prohibited"]
    assert len(prohibited) >= 1
    assert any(item.get("severity") == "WARNING" for item in prohibited)
    assert not any(item.get("severity") == "HARD_LIMIT" for item in prohibited)


# ── 26. _normalize_from_concretized: "requires confirmation" → confirmation ───

def test_normalize_from_concretized_requires_confirmation():
    text = "Run pytest suite. Any deployment requires human approval."
    parts = _normalize_from_concretized(text)

    assert len(parts["requires_confirmation"]) >= 1
    assert any("approval" in item["action"].lower() for item in parts["requires_confirmation"])


# ── 27. _normalize_from_concretized: plain sentence → authorized ──────────────

def test_normalize_from_concretized_plain_sentence_is_authorized():
    text = "Read and write Python files in ./src. Run the test suite."
    parts = _normalize_from_concretized(text)

    assert len(parts["authorized"]) >= 1
    assert parts["prohibited"] == []
    assert parts["requires_confirmation"] == []


# ── 28. concretize_mission uses max_tokens=800 ────────────────────────────────

def test_concretize_mission_uses_max_tokens_800(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)

    mock_response = json.dumps({
        "authorized": [{"action": "Read files", "reason": "Core task"}],
        "prohibited": [],
        "requires_confirmation": [],
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response) as mock_call:
        concretize_mission("implement features")

    assert mock_call.call_args.kwargs.get("max_tokens") == 800


# ── 29. Mission uses sonnet model for anthropic provider ──────────────────────

def test_concretize_mission_uses_sonnet_for_anthropic(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    monkeypatch.delenv("AGENTGUARD_MISSION_MODEL", raising=False)

    mock_response = json.dumps({
        "authorized": [{"action": "Read files", "reason": "Core task"}],
        "prohibited": [],
        "requires_confirmation": [],
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response) as mock_call:
        result = concretize_mission("implement features")

    called_model = mock_call.call_args.args[3]
    assert called_model == CONCRETIZATION_MODEL_OVERRIDES["anthropic"]
    assert result["_model"] == CONCRETIZATION_MODEL_OVERRIDES["anthropic"]
    assert not result.get("_fallback")


# ── 30. Mission uses gpt-4o for openai provider ───────────────────────────────

def test_concretize_mission_uses_gpt4o_for_openai(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "openai")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    monkeypatch.delenv("AGENTGUARD_MISSION_MODEL", raising=False)

    mock_response = json.dumps({
        "authorized": [{"action": "Read files", "reason": "Core task"}],
        "prohibited": [],
        "requires_confirmation": [],
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response) as mock_call:
        result = concretize_mission("implement features")

    called_model = mock_call.call_args.args[3]
    assert called_model == CONCRETIZATION_MODEL_OVERRIDES["openai"]
    assert result["_model"] == CONCRETIZATION_MODEL_OVERRIDES["openai"]
    assert not result.get("_fallback")


# ── 31. AGENTGUARD_MISSION_MODEL env var overrides mission model ──────────────

def test_concretize_mission_env_var_overrides_mission_model(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    monkeypatch.setenv("AGENTGUARD_MISSION_MODEL", "claude-opus-4-20250514")

    mock_response = json.dumps({
        "authorized": [{"action": "Read files", "reason": "Core task"}],
        "prohibited": [],
        "requires_confirmation": [],
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response) as mock_call:
        result = concretize_mission("implement features")

    called_model = mock_call.call_args.args[3]
    assert called_model == "claude-opus-4-20250514"
    assert result["_model"] == "claude-opus-4-20250514"
    assert not result.get("_fallback")


# ── 32. Format B fallback works even when sonnet returns it ───────────────────

def test_concretize_mission_format_b_fallback_no_error(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    monkeypatch.delenv("AGENTGUARD_MISSION_MODEL", raising=False)

    mock_response = json.dumps({
        "concretized": "Read Python files in ./src. Must never push to main. Deployments require human approval.",
        "confidence": "MEDIUM",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response):
        result = concretize_mission("implement features")

    assert result.get("_format_b") is True
    assert not result.get("_fallback")
    assert isinstance(result["authorized"], list)
    assert isinstance(result["prohibited"], list)
    assert isinstance(result["requires_confirmation"], list)
    assert result["_model"] == CONCRETIZATION_MODEL_OVERRIDES["anthropic"]


# ── 33. Empty response triggers fallback, not "Could not concretize" ─────────

def test_concretize_mission_empty_response_uses_fallback_not_invalid(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    monkeypatch.delenv("AGENTGUARD_MISSION_MODEL", raising=False)

    mock_response = json.dumps({"confidence": "LOW", "ambiguities": []})
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response):
        result = concretize_mission("implement features")

    assert result.get("_fallback") is True
    assert "empty response" in result["ambiguities"][0]
    assert result["authorized"][0]["action"] == "implement features"


# ── 34. Metadata comment uses actual mission model after save ─────────────────

def test_save_guided_metadata_shows_mission_model():
    from pathlib import Path

    from agentguard.cli import _save_guided

    results = {
        "owner": "Alice",
        "scope.authorized": [{"action": "Read files", "reason": "Core task"}],
        "scope.prohibited": [],
        "scope.requires_confirmation": [],
        "escalation": "alice@example.com",
        "killswitch": "Ctrl+C",
        "_mission_model": "claude-sonnet-4-20250514",
        "_mission_provider": "anthropic",
    }

    runner = CliRunner()
    with runner.isolated_filesystem():
        with (
            mock.patch("agentguard.cli._write_hook_config", return_value="ok"),
            mock.patch("agentguard.cli._update_claude_md", return_value=("created", "ok")),
        ):
            _save_guided(results)
        gov = Path("governance.yaml").read_text()

    assert "claude-sonnet-4-20250514" in gov
    assert "anthropic/claude-sonnet-4-20250514" in gov


# ── 35. Panel shows all items without truncation ──────────────────────────────

def test_show_concretized_no_truncation():
    from io import StringIO

    from rich.console import Console

    from agentguard.cli import _show_concretized

    step = {"splits_into": ["scope.authorized", "scope.prohibited", "scope.requires_confirmation"]}
    ai_result = {
        "authorized": [
            {"action": f"Action {i}", "reason": "Reason"} for i in range(5)
        ],
        "prohibited": [
            {"action": f"Block {i}", "reason": "Risk", "severity": "HARD_LIMIT"} for i in range(4)
        ],
        "requires_confirmation": [
            {"action": "Confirm deploy", "reason": "Needs sign-off"}
        ],
        "confidence": "HIGH",
        "ambiguities": [],
    }

    buf = StringIO()
    from agentguard import cli as cli_module
    original_console = cli_module._console
    cli_module._console = Console(file=buf, force_terminal=False)
    try:
        _show_concretized(step, ai_result)
    finally:
        cli_module._console = original_console

    output = buf.getvalue()
    for i in range(5):
        assert f"Action {i}" in output
    for i in range(4):
        assert f"Block {i}" in output
    assert "(+5 more)" not in output
    assert "(+4 more)" not in output
    assert "(+3 more)" not in output


# ── 36. Ambiguities accumulated across adjustment rounds, deduped ─────────────

def test_guided_ambiguities_accumulated_across_rounds():
    runner = CliRunner()

    _prohibited_hl = [{"action": "No production writes", "reason": "Hard limit", "severity": "HARD_LIMIT"}]
    _confirmation = [{"action": "Any file deletion", "reason": "Irreversible"}]

    round_1_result = {
        "authorized": [{"action": "Read files in ./src", "reason": "Core task"}],
        "prohibited": _prohibited_hl,
        "requires_confirmation": _confirmation,
        "confidence": "MEDIUM",
        "ambiguities": ["Round-1 ambiguity: scope of files unclear"],
        "_provider": "anthropic",
        "_model": "claude-sonnet-4-20250514",
    }
    round_2_result = {
        "authorized": [{"action": "Read Python files in ./src", "reason": "Core task"}],
        "prohibited": _prohibited_hl,
        "requires_confirmation": _confirmation,
        "confidence": "MEDIUM",
        "ambiguities": [
            "Round-2 ambiguity: time constraints not specified",
            "Round-1 ambiguity: scope of files unclear",  # duplicate — should appear once
        ],
        "_provider": "anthropic",
        "_model": "claude-sonnet-4-20250514",
    }

    calls = []
    ambiguity_panel_args = []

    def side_effect_mission(user_input):
        calls.append(user_input)
        return round_1_result if len(calls) == 1 else round_2_result

    def mock_ambiguity_panel(ambiguities):
        ambiguity_panel_args.append(list(ambiguities))
        return "1"  # Proceed

    _MOCK_FIELD_HIGH = {
        "prohibited": [{"action": "No production writes", "reason": "Hard limit", "severity": "HARD_LIMIT"}],
        "confidence": "HIGH",
        "ambiguities": [],
        "_provider": "anthropic",
        "_model": "claude-haiku-4-5-20251001",
    }

    user_input = (
        "\n"                       # pre-inquiry
        "Jane Smith\n"             # step 1: owner
        "implement features\n"     # step 2: mission (round 1 → MEDIUM)
        "2\n"                      # adjust
        "be more specific\n"       # adjustment
        "1\n"                      # accept round 2 (MEDIUM) → ambiguity panel (mocked, no prompt consumed)
        "no production writes\n"   # step 3: hard limits
        "1\n"                      # accept
        "owner@example.com\n"      # step 4: escalation
        "Ctrl+C\n"                 # step 5: killswitch
        "n\n"                      # cost awareness: skip
        "1\n"                      # final review: save
    )

    with runner.isolated_filesystem():
        with (
            mock.patch("agentguard.guided.concretizer._ai_available", return_value=True),
            mock.patch("agentguard.guided.concretizer.concretize_mission", side_effect=side_effect_mission),
            mock.patch("agentguard.guided.concretizer.concretize_field", return_value=_MOCK_FIELD_HIGH),
            mock.patch("agentguard.cli._show_ambiguity_panel", side_effect=mock_ambiguity_panel),
        ):
            result = runner.invoke(main, ["init", "--guided"], input=user_input)

    assert result.exit_code == 0, result.output
    assert len(ambiguity_panel_args) == 1
    panel_ambs = ambiguity_panel_args[0]
    assert "Round-1 ambiguity: scope of files unclear" in panel_ambs
    assert "Round-2 ambiguity: time constraints not specified" in panel_ambs
    assert panel_ambs.count("Round-1 ambiguity: scope of files unclear") == 1


# ── 37. hard_limits uses sonnet model for anthropic provider ──────────────────

def test_concretize_hard_limits_uses_sonnet_for_anthropic(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    monkeypatch.delenv("AGENTGUARD_MISSION_MODEL", raising=False)

    mock_response = json.dumps({
        "prohibited": [{"action": "No production writes", "reason": "Hard limit", "severity": "HARD_LIMIT"}],
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response) as mock_call:
        result = concretize_field("hard_limits", "no production writes")

    called_model = mock_call.call_args.args[3]
    assert called_model == CONCRETIZATION_MODEL_OVERRIDES["anthropic"]
    assert result["_model"] == CONCRETIZATION_MODEL_OVERRIDES["anthropic"]
    assert not result.get("_fallback")


# ── 38. concretize_field uses sonnet model for anthropic provider ─────────────

def test_concretize_field_non_hard_limits_uses_sonnet_for_anthropic(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    monkeypatch.delenv("AGENTGUARD_MISSION_MODEL", raising=False)

    mock_response = json.dumps({
        "concretized": "Email owner@example.com when 2+ failures occur",
        "enforcement_notes": "Check escalation trigger",
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response) as mock_call:
        result = concretize_field("escalation", "email me on failure")

    called_model = mock_call.call_args.args[3]
    assert called_model == CONCRETIZATION_MODEL_OVERRIDES["anthropic"]
    assert result["_model"] == CONCRETIZATION_MODEL_OVERRIDES["anthropic"]
    assert not result.get("_fallback")


# ── 39. AGENTGUARD_MISSION_MODEL env var overrides hard_limits and field ──────

def test_concretize_hard_limits_env_var_overrides_model(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    monkeypatch.setenv("AGENTGUARD_MISSION_MODEL", "claude-opus-4-20250514")

    mock_response = json.dumps({
        "prohibited": [{"action": "No production writes", "reason": "Hard limit", "severity": "HARD_LIMIT"}],
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response) as mock_call:
        result = concretize_field("hard_limits", "no production writes")

    called_model = mock_call.call_args.args[3]
    assert called_model == "claude-opus-4-20250514"
    assert result["_model"] == "claude-opus-4-20250514"
    assert not result.get("_fallback")


def test_concretize_field_env_var_overrides_model(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    monkeypatch.setenv("AGENTGUARD_MISSION_MODEL", "claude-opus-4-20250514")

    mock_response = json.dumps({
        "concretized": "Email owner@example.com",
        "enforcement_notes": "",
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response) as mock_call:
        result = concretize_field("escalation", "email me on failure")

    called_model = mock_call.call_args.args[3]
    assert called_model == "claude-opus-4-20250514"
    assert result["_model"] == "claude-opus-4-20250514"
    assert not result.get("_fallback")


# ── 40. hard_limits fallback returns valid prohibited list on exception ────────

def test_concretize_hard_limits_fallback_has_valid_prohibited_list(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)

    with mock.patch(
        "agentguard.guided.concretizer._call_provider",
        side_effect=Exception("network error"),
    ):
        result = concretize_field("hard_limits", "no writes to production")

    assert result["_fallback"] is True
    assert isinstance(result["prohibited"], list)
    assert len(result["prohibited"]) > 0
    assert result["prohibited"][0]["action"] == "no writes to production"
    assert result["prohibited"][0]["severity"] == "HARD_LIMIT"
    assert "network error" in result["ambiguities"][0]


# ── 41. Step 2 question text references Claude Code ───────────────────────────

def test_guided_step2_question_references_claude_code():
    from agentguard.cli import GUIDED_STEPS

    step2 = next(s for s in GUIDED_STEPS if s["step"] == 2)
    assert "Claude Code authorized" in step2["question"]
    assert "no calls to external APIs" in step2["example"]


# ── 42. temperature=0 used in all concretization calls ───────────────────────

def test_concretize_mission_uses_temperature_0(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    monkeypatch.delenv("AGENTGUARD_MISSION_MODEL", raising=False)

    mock_response = json.dumps({
        "authorized": [{"action": "Read files", "reason": "Core task"}],
        "prohibited": [{"action": "No prod", "reason": "Hard limit", "severity": "HARD_LIMIT"}],
        "requires_confirmation": [],
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response) as mock_call:
        concretize_mission("implement features")

    assert mock_call.call_args.kwargs.get("temperature") == 0


def test_concretize_hard_limits_uses_temperature_0(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    monkeypatch.delenv("AGENTGUARD_MISSION_MODEL", raising=False)

    mock_response = json.dumps({
        "prohibited": [{"action": "No production writes", "reason": "Hard limit", "severity": "HARD_LIMIT"}],
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response) as mock_call:
        concretize_field("hard_limits", "no production writes")

    assert mock_call.call_args.kwargs.get("temperature") == 0


def test_concretize_field_uses_temperature_0(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    monkeypatch.delenv("AGENTGUARD_MISSION_MODEL", raising=False)

    mock_response = json.dumps({
        "concretized": "Email owner@example.com on failure",
        "enforcement_notes": "",
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response) as mock_call:
        concretize_field("escalation", "email me on failure")

    assert mock_call.call_args.kwargs.get("temperature") == 0


# ── 48. Governance review: menu choice routing ───────────────────────────────

def _review_results() -> dict:
    return {
        "owner": "Jane Smith",
        "scope.authorized": [{"action": "Read files in ./src", "reason": "Core task"}],
        "scope.prohibited": [{"action": "No prod writes", "reason": "Hard limit", "severity": "HARD_LIMIT"}],
        "scope.requires_confirmation": [],
        "escalation": "jane@example.com",
        "killswitch": "Ctrl+C",
    }


def test_governance_review_choice_1_triggers_save(tmp_path, monkeypatch):
    """Choosing '1' at the governance review menu must route to 'save', not 'adjust'."""
    from io import StringIO

    from rich.console import Console

    from agentguard import cli as cli_module
    from agentguard.cli import _show_guided_review

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "_console", Console(file=StringIO(), force_terminal=False))

    runner = CliRunner()
    with runner.isolated_filesystem():
        with runner.isolation(input="1\n"):
            result = _show_guided_review(_review_results())

    assert result == "save", f"Expected 'save', got {repr(result)}"


def test_governance_review_default_empty_input_triggers_save(tmp_path, monkeypatch):
    """Pressing Enter (accepting default) at governance review must route to 'save'."""
    from io import StringIO

    from rich.console import Console

    from agentguard import cli as cli_module
    from agentguard.cli import _show_guided_review

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "_console", Console(file=StringIO(), force_terminal=False))

    runner = CliRunner()
    with runner.isolated_filesystem():
        with runner.isolation(input="\n"):
            result = _show_guided_review(_review_results())

    assert result == "save", f"Expected 'save' for empty/default input, got {repr(result)}"


def test_governance_review_choice_3_triggers_restart(tmp_path, monkeypatch):
    """Choosing '3' at the governance review menu must route to 'restart'."""
    from io import StringIO

    from rich.console import Console

    from agentguard import cli as cli_module
    from agentguard.cli import _show_guided_review

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "_console", Console(file=StringIO(), force_terminal=False))

    runner = CliRunner()
    with runner.isolated_filesystem():
        with runner.isolation(input="3\n"):
            result = _show_guided_review(_review_results())

    assert result == "restart", f"Expected 'restart', got {repr(result)}"


def test_governance_review_choice_2_triggers_adjust_field_submenu(tmp_path, monkeypatch):
    """Choosing '2' at governance review enters the Adjust path: _run_guided_step is called."""
    from io import StringIO

    from rich.console import Console

    from agentguard import cli as cli_module
    from agentguard.cli import _show_guided_review

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "_console", Console(file=StringIO(), force_terminal=False))

    run_step_calls = []

    def mock_run_step(step, results):
        run_step_calls.append(step["field"])

    runner = CliRunner()
    # "2" → Adjust → field submenu → "1" picks Owner field →
    # mock _run_guided_step records the call → recursive review → "1" saves
    with runner.isolated_filesystem():
        with mock.patch("agentguard.cli._run_guided_step", side_effect=mock_run_step):
            with runner.isolation(input="2\n1\n1\n"):
                result = _show_guided_review(_review_results())

    assert result == "save"
    assert run_step_calls == ["owner"], (
        f"Expected Adjust path to call _run_guided_step for 'owner', got {run_step_calls}"
    )


# ── 43. Validation error panel shown when mission has no authorized ───────────

def test_show_validation_errors_renders_panel():
    from io import StringIO

    from rich.console import Console

    from agentguard import cli as cli_module
    from agentguard.cli import _show_validation_errors
    from agentguard.guided.validator import ValidationIssue

    issues = [ValidationIssue(
        field="authorized",
        severity="error",
        message="No authorized actions defined",
        fix="Define at least one concrete authorized action",
    )]
    buf = StringIO()
    original = cli_module._console
    cli_module._console = Console(file=buf, force_terminal=False)
    try:
        _show_validation_errors(issues)
    finally:
        cli_module._console = original

    output = buf.getvalue()
    assert "VALIDATION ERRORS" in output
    assert "No authorized actions defined" in output
    assert "Define at least one concrete authorized action" in output


# ── 44. Validation warning panel shown when mission has no HARD_LIMIT ─────────

def test_show_validation_warnings_renders_panel():
    from io import StringIO

    from rich.console import Console

    from agentguard import cli as cli_module
    from agentguard.cli import _show_validation_warnings
    from agentguard.guided.validator import ValidationIssue

    issues = [ValidationIssue(
        field="prohibited",
        severity="warning",
        message="No HARD_LIMIT rules defined",
        fix="Mark your most critical prohibitions as HARD_LIMIT",
    )]
    buf = StringIO()
    original = cli_module._console
    cli_module._console = Console(file=buf, force_terminal=False)
    try:
        _show_validation_warnings(issues)
    finally:
        cli_module._console = original

    output = buf.getvalue()
    assert "VALIDATION WARNINGS" in output
    assert "No HARD_LIMIT rules defined" in output


# ── 45. concretize_mission result contains _pin dict ──────────────────────────

def test_concretize_mission_result_has_pin():
    mock_response = json.dumps({
        "authorized": [{"action": "Read Python files in ./src", "reason": "Core task"}],
        "prohibited": [{"action": "Deploy to production", "reason": "Hard limit", "severity": "HARD_LIMIT"}],
        "requires_confirmation": [{"action": "Delete files", "reason": "Irreversible"}],
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response), \
         mock.patch("agentguard.guided.concretizer._get_env", return_value=("openai", "key", None, None)):
        result = concretize_mission("Build a Python code assistant")

    assert "_pin" in result
    pin = result["_pin"]
    assert pin["field"] == "mission"
    assert pin["temperature"] == 0
    assert len(pin["prompt_hash"]) == 16
    assert len(pin["output_hash"]) == 16


# ── 46. concretize_field result contains _pin dict ────────────────────────────

def test_concretize_field_result_has_pin():
    mock_response = json.dumps({
        "concretized": "Send email via /api/notify only",
        "enforcement_notes": "Block all other email calls",
        "confidence": "HIGH",
        "ambiguities": [],
    })
    with mock.patch("agentguard.guided.concretizer._call_provider", return_value=mock_response), \
         mock.patch("agentguard.guided.concretizer._get_env", return_value=("openai", "key", None, None)):
        result = concretize_field("escalation", "Send email notifications")

    assert "_pin" in result
    pin = result["_pin"]
    assert pin["field"] == "escalation"
    assert pin["temperature"] == 0


# ── 47. _save_guided writes concretization_pins to governance.yaml ────────────

def test_save_guided_writes_concretization_pins(tmp_path, monkeypatch):
    from agentguard.cli import _save_guided

    monkeypatch.chdir(tmp_path)

    results = {
        "owner": "Test Owner",
        "scope.authorized": [{"action": "Read files in ./src", "reason": "Core task", "severity": "WARNING"}],
        "scope.prohibited": [{"action": "Deploy to production", "reason": "Hard limit", "severity": "HARD_LIMIT"}],
        "scope.requires_confirmation": [{"action": "Delete files", "reason": "Irreversible"}],
        "escalation": "owner@example.com",
        "killswitch": "Ctrl+C",
        "_mission_pin": {
            "field": "mission",
            "input_hash": "abc123def456abcd",
            "prompt_hash": "def456abc123ef01",
            "output_hash": "1234567890abcdef",
            "model": "claude-sonnet-4-20250514",
            "provider": "anthropic",
            "temperature": 0,
            "date": "2026-06-09",
        },
    }

    with mock.patch("agentguard.cli._write_hook_config", return_value="hook config written"), \
         mock.patch("agentguard.cli._update_claude_md", return_value=(True, "CLAUDE.md updated")), \
         mock.patch("agentguard.ai_review._get_env", return_value=("anthropic", "key", None, None)):
        _save_guided(results)

    gov_text = (tmp_path / "governance.yaml").read_text()
    assert "concretization_pins:" in gov_text
    assert 'field: "mission"' in gov_text
    assert "temperature: 0" in gov_text


# ── 48. review --guided: "y" to further changes loops back to menu ───────────

_MINIMAL_GOV_YAML = """\
owner: "test-owner"
scope:
  authorized:
    - action: "Read source files"
      reason: "Core development"
      added: "2026-06-13"
  prohibited: []
  requires_confirmation: []
escalation:
  contact: "test@example.com"
  method: "log"
  trigger: "2+ failures"
killswitch: "stop"
governance_history: []
"""


def test_review_interactive_guided_loops_back_on_y(tmp_path):
    """Answering 'y' to 'Make further changes?' re-enters the top-level menu."""
    from agentguard.cli import _review_interactive
    from agentguard.review.reviewer import load_governance

    gov_path = tmp_path / "governance.yaml"
    gov_path.write_text(_MINIMAL_GOV_YAML)
    governance = load_governance(gov_path)

    # iter 1: specific field → authorized → add rule → saved → "y" to continue
    # iter 2: all fields → keep all three → no changes → exits (no further prompt)
    prompt_values = iter([
        "2", "1", "2", "Run unit tests", "Quality assurance",  # iter 1: specific→authorized→add
        "y",                                                     # Make further changes?
        "1", "1", "1", "1",                                     # iter 2: all fields → keep ×3
    ])
    with (
        mock.patch("click.prompt", side_effect=lambda *a, **kw: next(prompt_values)),
        mock.patch("agentguard.guided.concretizer._ai_available", return_value=False),
    ):
        _review_interactive(governance, gov_path, guided=True)

    updated = load_governance(gov_path)
    authorized = updated.get("scope", {}).get("authorized", [])
    assert any(r.get("action") == "Run unit tests" for r in authorized)


def test_review_interactive_guided_exits_on_n(tmp_path):
    """Answering 'n' to 'Make further changes?' exits the review loop."""
    from agentguard.cli import _review_interactive
    from agentguard.review.reviewer import load_governance

    gov_path = tmp_path / "governance.yaml"
    gov_path.write_text(_MINIMAL_GOV_YAML)
    governance = load_governance(gov_path)

    # specific field → authorized → add rule → saved → "n" to exit
    prompt_values = iter([
        "2", "1", "2", "Deploy to staging", "Test deployment",  # specific→authorized→add
        "n",                                                      # Make further changes?
    ])
    with (
        mock.patch("click.prompt", side_effect=lambda *a, **kw: next(prompt_values)),
        mock.patch("agentguard.guided.concretizer._ai_available", return_value=False),
    ):
        _review_interactive(governance, gov_path, guided=True)

    updated = load_governance(gov_path)
    authorized = updated.get("scope", {}).get("authorized", [])
    assert any(r.get("action") == "Deploy to staging" for r in authorized)


# ── 50. _generate_default_path_policy: authorized dirs detected ───────────────

def test_generate_default_path_policy_authorized_dirs(tmp_path):
    from agentguard.guided.concretizer import _generate_default_path_policy

    (tmp_path / "mypackage").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "web").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "README.md").write_text("# readme")

    policy = _generate_default_path_policy(str(tmp_path))

    auth_patterns = [e["pattern"] for e in policy["authorized_paths"]]
    assert "mypackage/**" in auth_patterns
    assert "tests/**" in auth_patterns
    assert "web/**" in auth_patterns
    assert "*.md" in auth_patterns
    assert ".git/**" not in auth_patterns
    assert "__pycache__/**" not in auth_patterns


# ── 51. _generate_default_path_policy: denied_paths always present ────────────

def test_generate_default_path_policy_denied_always_has_env_and_git(tmp_path):
    from agentguard.guided.concretizer import _generate_default_path_policy

    policy = _generate_default_path_policy(str(tmp_path))

    denied_patterns = [e["pattern"] for e in policy["denied_paths"]]
    assert ".env*" in denied_patterns
    assert ".git/**" in denied_patterns


# ── 52. _generate_default_path_policy: protected empty, default ask ───────────

def test_generate_default_path_policy_protected_empty_default_ask(tmp_path):
    from agentguard.guided.concretizer import _generate_default_path_policy

    policy = _generate_default_path_policy(str(tmp_path))

    assert policy["protected_paths"] == []
    assert policy["default_for_unmatched"] == "ask"


# ── 53. _generate_default_path_policy: no subdirs → only *.md ────────────────

def test_generate_default_path_policy_no_subdirectories(tmp_path):
    from agentguard.guided.concretizer import _generate_default_path_policy

    policy = _generate_default_path_policy(str(tmp_path))

    auth_patterns = [e["pattern"] for e in policy["authorized_paths"]]
    assert auth_patterns == ["*.md"]
    assert policy["denied_paths"]


# ── 54. _generate_default_path_policy: passes load_path_policy validation ─────

def test_generate_default_path_policy_passes_load_path_policy(tmp_path):
    from agentguard.config.loader import load_path_policy
    from agentguard.guided.concretizer import _generate_default_path_policy

    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()

    policy = _generate_default_path_policy(str(tmp_path))
    result = load_path_policy({"path_policy": policy})

    assert len(result.denied_paths) == 2
    assert len(result.authorized_paths) == 3  # src/**, tests/**, *.md
    assert result.default_for_unmatched == "ask"


# ── 55. init --guided: governance.yaml contains valid path_policy ─────────────

def test_guided_complete_flow_governance_yaml_has_path_policy():
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

    assert "path_policy:" in gov
    assert 'pattern: ".env*"' in gov
    assert 'pattern: ".git/**"' in gov
    assert 'default_for_unmatched: "ask"' in gov


# ── 56. init --guided: review panel shows Path Policy summary ─────────────────

def test_guided_complete_flow_review_panel_shows_path_policy_summary():
    runner = CliRunner()
    with runner.isolated_filesystem():
        with (
            mock.patch("agentguard.guided.concretizer._ai_available", return_value=True),
            mock.patch("agentguard.guided.concretizer.concretize_mission", return_value=_MOCK_MISSION),
            mock.patch("agentguard.guided.concretizer.concretize_field", return_value=_MOCK_FIELD),
        ):
            result = runner.invoke(main, ["init", "--guided"], input=_HAPPY_PATH_INPUT)

    assert result.exit_code == 0, result.output
    assert "Path Policy:" in result.output
    assert "default: ask" in result.output
