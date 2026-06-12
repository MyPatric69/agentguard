"""Tests for agentguard/review/reviewer.py and agentguard review CLI command."""

from __future__ import annotations

from datetime import date
from io import StringIO
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from rich.console import Console

from agentguard.cli import main
from agentguard.review import reviewer as reviewer_module
from agentguard.review.reviewer import (
    _count_hard_limits,
    _count_open_ambiguities,
    _count_rules,
    _run_add_rule,
    load_governance,
    mark_ambiguity_resolved,
    review_field,
    save_governance,
    show_governance_summary,
)

# ── Shared fixtures ───────────────────────────────────────────────────────────

_GOVERNANCE_YAML = """\
owner: "Alice"
scope:
  authorized:
    - action: "Read Python files in ./src"
      reason: "Core task"
      added: "2026-06-07"
    - action: "Run pytest suite"
      reason: "Verify changes"
      added: "2026-06-07"
  prohibited:
    - action: "Deploy to production"
      reason: "Hard limit"
      severity: "HARD_LIMIT"
      added: "2026-06-07"
    - action: "Push to main"
      reason: "Requires review"
      severity: "HARD_LIMIT"
      added: "2026-06-07"
    - action: "Database writes"
      reason: "Risk"
      added: "2026-06-07"
  requires_confirmation:
    - action: "Any file deletion"
      reason: "Irreversible"
      added: "2026-06-07"
escalation:
  contact: "alice@example.com"
  method: "log"
  trigger: "2+ failures"
killswitch: "Ctrl+C"
governance_history:
  - date: "2026-06-07"
    action: "Initial governance created"
    tool: "agentguard init --guided"
    version: "0.4.1"
"""

_VALID_GOVERNANCE = {
    "owner": "Alice",
    "scope": {
        "authorized": [
            {"action": "Read Python files in ./src", "reason": "Core task", "added": "2026-06-07"},
            {"action": "Run pytest suite", "reason": "Verify changes", "added": "2026-06-07"},
        ],
        "prohibited": [
            {"action": "Deploy to production", "reason": "Hard limit", "severity": "HARD_LIMIT", "added": "2026-06-07"},
            {"action": "Push to main", "reason": "Requires review", "severity": "HARD_LIMIT", "added": "2026-06-07"},
            {"action": "Database writes", "reason": "Risk", "added": "2026-06-07"},
        ],
        "requires_confirmation": [
            {"action": "Any file deletion", "reason": "Irreversible", "added": "2026-06-07"},
        ],
    },
    "escalation": {"contact": "alice@example.com", "method": "log", "trigger": "2+ failures"},
    "killswitch": "Ctrl+C",
    "governance_history": [
        {"date": "2026-06-07", "action": "Initial governance created", "tool": "agentguard init --guided", "version": "0.4.1"},
    ],
}


# ── 1. load_governance: valid file loaded correctly ──────────────────────────

def test_load_governance_valid(tmp_path):
    gov_file = tmp_path / "governance.yaml"
    gov_file.write_text(_GOVERNANCE_YAML)
    governance = load_governance(gov_file)
    assert governance["owner"] == "Alice"
    assert len(governance["scope"]["authorized"]) == 2
    assert len(governance["scope"]["prohibited"]) == 3


# ── 2. load_governance: missing file raises clear error ──────────────────────

def test_load_governance_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="governance.yaml not found"):
        load_governance(tmp_path / "governance.yaml")


# ── 3. show_governance_summary: rule counts correct ──────────────────────────

def test_show_governance_summary_rule_counts():
    buf = StringIO()
    original = reviewer_module._console
    reviewer_module._console = Console(file=buf, force_terminal=False)
    try:
        show_governance_summary(_VALID_GOVERNANCE)
    finally:
        reviewer_module._console = original

    output = buf.getvalue()
    assert "Alice" in output
    assert "2 rules" in output       # authorized: 2
    assert "3 rules" in output       # prohibited: 3
    assert "2 HARD_LIMIT" in output  # prohibited has 2 HARD_LIMIT
    assert "1 rules" in output       # requires_confirmation: 1


# ── 4. review_field: keep as-is returns unchanged field ──────────────────────

def test_review_field_keep_as_is():
    items = [
        {"action": "Read files in ./src", "reason": "Core task", "added": "2026-06-07"},
    ]
    with mock.patch("click.prompt", return_value="1"):
        updated, changed = review_field(items, "authorized")
    assert updated == items
    assert changed is False


# ── 5. review_field: add rule appends with today's date ──────────────────────

def test_review_field_add_rule_appends_with_date():
    items = [
        {"action": "Read files in ./src", "reason": "Core task", "added": "2026-06-07"},
    ]
    today = date.today().isoformat()
    prompt_values = iter(["2", "Run tests", "Verify quality"])
    with mock.patch("click.prompt", side_effect=lambda *a, **kw: next(prompt_values)):
        updated, changed = review_field(items, "authorized")
    assert changed is True
    assert len(updated) == 2
    assert updated[-1]["action"] == "Run tests"
    assert updated[-1]["reason"] == "Verify quality"
    assert updated[-1]["added"] == today


# ── 6. review_field: remove rule by index works correctly ────────────────────

def test_review_field_remove_rule_by_index():
    items = [
        {"action": "Rule A", "reason": "Reason A", "added": "2026-06-07"},
        {"action": "Rule B", "reason": "Reason B", "added": "2026-06-07"},
        {"action": "Rule C", "reason": "Reason C", "added": "2026-06-07"},
    ]
    prompt_values = iter(["3", "2"])  # [3] Remove, then item 2
    with mock.patch("click.prompt", side_effect=lambda *a, **kw: next(prompt_values)):
        updated, changed = review_field(items, "authorized")
    assert changed is True
    assert len(updated) == 2
    assert all(item["action"] != "Rule B" for item in updated)
    assert updated[0]["action"] == "Rule A"
    assert updated[1]["action"] == "Rule C"


# ── 7. mark_ambiguity_resolved: status changes, resolved date added ──────────

def test_mark_ambiguity_resolved_changes_status():
    ambiguities = [
        {"text": "First ambiguity", "added": "2026-06-07", "status": "open"},
        {"text": "Second ambiguity", "added": "2026-06-07", "status": "open"},
    ]
    today = date.today().isoformat()
    updated = mark_ambiguity_resolved(ambiguities, 0)
    assert updated[0]["status"] == "resolved"
    assert updated[0]["resolved"] == today
    assert updated[1]["status"] == "open"
    assert "resolved" not in updated[1]


def test_mark_ambiguity_resolved_skips_already_resolved():
    ambiguities = [
        {"text": "Done", "added": "2026-06-06", "status": "resolved", "resolved": "2026-06-07"},
        {"text": "Pending", "added": "2026-06-07", "status": "open"},
    ]
    updated = mark_ambiguity_resolved(ambiguities, 0)
    assert updated[0]["status"] == "resolved"
    assert updated[0].get("resolved") == "2026-06-07"  # unchanged


# ── 8. save_governance: governance_history entry appended ────────────────────

def test_save_governance_history_appended(tmp_path):
    gov_file = tmp_path / "governance.yaml"
    governance = {
        "owner": "Alice",
        "scope": {
            "authorized": [{"action": "Read files", "reason": "Core task", "added": "2026-06-07"}],
            "prohibited": [],
            "requires_confirmation": [],
        },
        "escalation": {"contact": "alice@example.com", "method": "log", "trigger": "2+ failures"},
        "killswitch": "Ctrl+C",
        "governance_history": [
            {"date": "2026-06-07", "action": "Initial governance created", "tool": "agentguard init --guided", "version": "0.4.1"},
        ],
    }
    save_governance(governance, gov_file, ["scope.authorized"])
    content = gov_file.read_text()
    assert "agentguard review" in content
    assert "Updated: scope.authorized" in content
    assert content.count("tool:") == 2  # original + new entry


# ── 9. save_governance: unchanged fields preserved ───────────────────────────

def test_save_governance_unchanged_fields_preserved(tmp_path):
    gov_file = tmp_path / "governance.yaml"
    governance = {
        "owner": "Bob",
        "scope": {
            "authorized": [{"action": "Read files", "reason": "Core task", "added": "2026-06-07"}],
            "prohibited": [{"action": "No production", "reason": "Hard limit", "severity": "HARD_LIMIT", "added": "2026-06-07"}],
            "requires_confirmation": [],
        },
        "escalation": {"contact": "bob@example.com", "method": "log", "trigger": "2+ failures"},
        "killswitch": "kill PID",
        "governance_history": [
            {"date": "2026-06-07", "action": "Initial governance created", "tool": "agentguard init", "version": "0.4.1"},
        ],
    }
    save_governance(governance, gov_file, ["scope.authorized"])
    content = gov_file.read_text()
    assert 'owner: "Bob"' in content
    assert 'contact: "bob@example.com"' in content
    assert 'killswitch: "kill PID"' in content
    assert "No production" in content


# ── 10. review --field: only specified field reviewed ────────────────────────

def test_review_field_option_invokes_correct_field(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("governance.yaml").write_text(_GOVERNANCE_YAML)
        with (
            mock.patch("agentguard.review.reviewer.review_field", return_value=([], False)) as mock_rf,
            mock.patch("agentguard.review.reviewer.save_governance"),
            mock.patch("agentguard.review.reviewer.show_governance_summary"),
        ):
            result = runner.invoke(main, ["review", "--field", "authorized"])

    assert result.exit_code == 0, result.output
    assert mock_rf.called
    assert mock_rf.call_args.args[1] == "authorized"


# ── 11. review --field: invalid field name exits with error ──────────────────

def test_review_invalid_field_exits_with_error(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem():
        Path("governance.yaml").write_text(_GOVERNANCE_YAML)
        result = runner.invoke(main, ["review", "--field", "invalid_field"])
    assert result.exit_code != 0 or "ERROR" in result.output


# ── 12. review: missing governance.yaml exits with error ─────────────────────

def test_review_missing_governance_yaml_exits_with_error(tmp_path):
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["review"])
    assert result.exit_code != 0 or "ERROR" in (result.output + (result.stderr or ""))


# ── 13. Helper: _count_rules handles list and string ─────────────────────────

def test_count_rules_list():
    assert _count_rules([{"action": "a"}, {"action": "b"}]) == 2


def test_count_rules_string():
    assert _count_rules("do something") == 1


def test_count_rules_empty_list():
    assert _count_rules([]) == 0


# ── 14. Helper: _count_hard_limits counts HARD_LIMIT severity ────────────────

def test_count_hard_limits():
    prohibited = [
        {"action": "a", "severity": "HARD_LIMIT"},
        {"action": "b", "severity": "WARNING"},
        {"action": "c", "severity": "HARD_LIMIT"},
        {"action": "d"},
    ]
    assert _count_hard_limits(prohibited) == 2


# ── 15. Helper: _count_open_ambiguities counts only open status ───────────────

def test_count_open_ambiguities():
    governance = {
        "scope": {
            "unresolved_ambiguities": [
                {"text": "Open 1", "status": "open"},
                {"text": "Open 2", "status": "open"},
                {"text": "Resolved", "status": "resolved"},
            ]
        }
    }
    assert _count_open_ambiguities(governance) == 2


# ── 16. show_governance_summary: ambiguity display ───────────────────────────

def _capture_summary(governance: dict) -> str:
    buf = StringIO()
    original = reviewer_module._console
    reviewer_module._console = Console(file=buf, force_terminal=False)
    try:
        show_governance_summary(governance)
    finally:
        reviewer_module._console = original
    return buf.getvalue()


def test_show_governance_summary_three_open_ambiguities():
    governance = {
        "owner": "Alice",
        "scope": {
            "authorized": [],
            "prohibited": [],
            "requires_confirmation": [],
            "unresolved_ambiguities": [
                {"text": "Amb 1", "status": "open"},
                {"text": "Amb 2", "status": "open"},
                {"text": "Amb 3", "status": "open"},
            ],
        },
    }
    assert "3 open" in _capture_summary(governance)


def test_show_governance_summary_no_ambiguities_shows_none():
    governance = {
        "owner": "Alice",
        "scope": {
            "authorized": [],
            "prohibited": [],
            "requires_confirmation": [],
        },
    }
    assert "none" in _capture_summary(governance)


def test_show_governance_summary_all_resolved_shows_none():
    governance = {
        "owner": "Alice",
        "scope": {
            "authorized": [],
            "prohibited": [],
            "requires_confirmation": [],
            "unresolved_ambiguities": [
                {"text": "Amb 1", "status": "resolved"},
                {"text": "Amb 2", "status": "resolved"},
            ],
        },
    }
    assert "none" in _capture_summary(governance)


# ── 17. review_field: Replace uses same concretization path as Add ───────────

def test_review_field_replace_uses_same_path_as_add():
    items = [
        {"action": "Old prohibited rule", "reason": "Old reason", "severity": "HARD_LIMIT", "added": "2026-06-07"},
    ]
    mock_ai = {
        "concretized": "No writes to ./production directory",
        "enforcement_notes": "Check Write tool file_path",
        "confidence": "HIGH",
        "ambiguities": [],
    }
    prompt_values = iter(["4", "1", "no production writes", "prevent data loss", "y"])
    with (
        mock.patch("click.prompt", side_effect=lambda *a, **kw: next(prompt_values)),
        mock.patch("agentguard.guided.concretizer._ai_available", return_value=True),
        mock.patch("agentguard.guided.concretizer.concretize_field", return_value=mock_ai),
    ):
        updated, changed = review_field(items, "prohibited", guided=True)
    assert changed is True
    assert len(updated) == 1  # old removed, new appended (net = 1)
    new_rule = updated[0]
    assert new_rule["action"] == "No writes to ./production directory"
