"""Tests for agentguard/enforcement/enforcer.py and _write_hook_config."""

from __future__ import annotations

import io
import json

import pytest

from agentguard.cli import _write_hook_config
from agentguard.enforcement.enforcer import (
    _match_confirmation_text,
    _match_path_policy,
    run_enforce,
)

# ── Shared governance configs ─────────────────────────────────────────────────

_GOV_PROHIBITED = (
    "owner: Alice\n"
    "scope:\n"
    "  authorized: read Python files in ./src only\n"
    "  prohibited: no deletion outside ./tmp, no git push, no database operations\n"
    "  requires_confirmation: ''\n"
    "escalation:\n  contact: alice@example.com\n"
    "killswitch: Ctrl+C\n"
)

_GOV_CONFIRMATION = (
    "owner: Alice\n"
    "scope:\n"
    "  authorized: read Python files in ./src only\n"
    "  prohibited: ''\n"
    "  requires_confirmation: any write operation, any git push, any file deletion\n"
    "escalation:\n  contact: alice@example.com\n"
    "killswitch: Ctrl+C\n"
)

_GOV_LEGACY_SCOPE = (
    "owner: Alice\n"
    "scope: read files\n"
    "escalation:\n  contact: alice@example.com\n"
    "killswitch: Ctrl+C\n"
)


def _hook(tool_name: str, tool_input: dict, cwd: str, session_id: str = "test") -> str:
    return json.dumps(
        {"tool_name": tool_name, "tool_input": tool_input, "cwd": cwd, "session_id": session_id}
    )


# ── 1. Allow: clean Bash command ──────────────────────────────────────────────

def test_allow_clean_command(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PROHIBITED)
    monkeypatch.setattr("sys.stdin", io.StringIO(_hook("Bash", {"command": "pytest"}, str(tmp_path))))
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0
    assert capsys.readouterr().out == ""


# ── 2. Block: rm -rf matches prohibited ───────────────────────────────────────

def test_block_rm_rf_prohibited(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PROHIBITED)
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(_hook("Bash", {"command": "rm -rf dist"}, str(tmp_path)))
    )
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "AgentGuard" in result["hookSpecificOutput"]["permissionDecisionReason"]


# ── 3. Block: git push matches prohibited ─────────────────────────────────────

def test_block_git_push_prohibited(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PROHIBITED)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(_hook("Bash", {"command": "git push origin main"}, str(tmp_path))),
    )
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


# ── 4. Allow: Write to non-core path no longer triggers write-scope confirmation

def test_write_non_core_path_not_blocked(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_CONFIRMATION)
    tool_input = {"file_path": "agentguard/output/renderer.py", "content": "key: value"}
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(_hook("Write", tool_input, str(tmp_path)))
    )
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0
    assert capsys.readouterr().out == ""


# ── 5. Allow: governance.yaml not found ───────────────────────────────────────

def test_allow_no_governance_yaml(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(_hook("Bash", {"command": "rm -rf /"}, str(tmp_path)))
    )
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0


# ── 6. Allow: malformed stdin JSON ────────────────────────────────────────────

def test_allow_malformed_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("not valid json {{{"))
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0


# ── 7. Allow: legacy string scope ────────────────────────────────────────────

def test_allow_legacy_string_scope(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_LEGACY_SCOPE)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(_hook("Bash", {"command": "rm -rf /"}, str(tmp_path))),
    )
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0


# ── 8. Logging: deny decision appended to enforcement log ────────────────────

def test_deny_logged_to_enforcement_log(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PROHIBITED)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(_hook("Bash", {"command": "rm -rf dist"}, str(tmp_path), session_id="sess-42")),
    )
    with pytest.raises(SystemExit):
        run_enforce()

    log_path = tmp_path / "agentguard-enforcement.log"
    assert log_path.exists()
    entries = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert len(entries) == 1
    entry = entries[0]
    assert entry["decision"] == "deny"
    assert entry["tool"] == "Bash"
    assert entry["session_id"] == "sess-42"
    assert "rm -rf dist" in entry["input_summary"]


# ── 9. Block: SQL DROP matches prohibited ────────────────────────────────────

def test_block_sql_drop_prohibited(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PROHIBITED)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(_hook("Bash", {"command": "DROP TABLE users"}, str(tmp_path))),
    )
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


# ── 10. init: .claude/settings.json created when not present ─────────────────

def test_write_hook_config_creates_settings_json(tmp_path):
    result = _write_hook_config(tmp_path)

    settings_file = tmp_path / ".claude" / "settings.json"
    assert settings_file.exists()
    data = json.loads(settings_file.read_text())
    pre_hooks = data["hooks"]["PreToolUse"]
    commands = [h.get("command") for entry in pre_hooks for h in entry.get("hooks", [])]
    assert "agentguard enforce" in commands
    assert "Created" in result


# ── 11. init: .claude/settings.json merged when existing without agentguard ──

def test_write_hook_config_merges_existing_settings(tmp_path):
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir()
    existing = {
        "theme": "dark",
        "hooks": {
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "other-tool"}]}
            ]
        },
    }
    (settings_dir / "settings.json").write_text(json.dumps(existing))

    result = _write_hook_config(tmp_path)

    data = json.loads((settings_dir / "settings.json").read_text())
    pre_hooks = data["hooks"]["PreToolUse"]
    commands = [h.get("command") for entry in pre_hooks for h in entry.get("hooks", [])]
    assert "other-tool" in commands
    assert "agentguard enforce" in commands
    assert data.get("theme") == "dark"
    assert "Updated" in result


# ── 12. init: .claude/settings.json skipped when agentguard already present ──

def test_write_hook_config_skips_if_already_present(tmp_path):
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir()
    existing = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash|Write|Edit|MultiEdit|NotebookEdit",
                    "hooks": [{"type": "command", "command": "agentguard enforce"}],
                }
            ]
        }
    }
    (settings_dir / "settings.json").write_text(json.dumps(existing))

    result = _write_hook_config(tmp_path)

    data = json.loads((settings_dir / "settings.json").read_text())
    pre_hooks = data["hooks"]["PreToolUse"]
    enforce_count = sum(
        1
        for entry in pre_hooks
        for h in entry.get("hooks", [])
        if h.get("command") == "agentguard enforce"
    )
    assert enforce_count == 1
    assert "Skipped" in result


# ── List format scope: new structured governance.yaml ─────────────────────────

_GOV_PROHIBITED_LIST = """\
owner: Alice
scope:
  authorized:
    - action: "Read Python files in ./src"
      reason: "Core task"
  prohibited:
    - action: "Delete files outside ./tmp"
      reason: "Prevent data loss"
      severity: "HARD_LIMIT"
    - action: "git push to main"
      reason: "Requires review"
      severity: "HARD_LIMIT"
    - action: "No database operations"
      reason: "No DB access"
      severity: "CRITICAL"
  requires_confirmation: []
escalation:
  contact: alice@example.com
killswitch: Ctrl+C
"""

_GOV_CONFIRMATION_LIST = """\
owner: Alice
scope:
  authorized:
    - action: "Read Python files in ./src"
      reason: "Core task"
  prohibited: []
  requires_confirmation:
    - action: "Any write operation or file modification"
      reason: "Needs sign-off"
    - action: "Any git push"
      reason: "Requires review"
    - action: "Any file deletion"
      reason: "Irreversible"
escalation:
  contact: alice@example.com
killswitch: Ctrl+C
"""


# ── 13. List format: rm -rf matches prohibited item ──────────────────────────

def test_block_rm_rf_prohibited_list_format(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PROHIBITED_LIST)
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(_hook("Bash", {"command": "rm -rf dist"}, str(tmp_path)))
    )
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


# ── 14. List format: git push → HARD_LIMIT prefix in denial reason ────────────

def test_block_git_push_hard_limit_prefix(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PROHIBITED_LIST)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(_hook("Bash", {"command": "git push origin main"}, str(tmp_path))),
    )
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 2
    out = json.loads(capsys.readouterr().out)
    reason = out["hookSpecificOutput"]["permissionDecisionReason"]
    assert "HARD_LIMIT" in reason


# ── 15. List format: Write to non-core path not blocked ──────────────────────

def test_write_non_core_path_not_blocked_list_format(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_CONFIRMATION_LIST)
    tool_input = {"file_path": "web/src/App.jsx", "content": "key: value"}
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(_hook("Write", tool_input, str(tmp_path)))
    )
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0
    assert capsys.readouterr().out == ""


# ── 16. List format: allow clean command when no match ───────────────────────

def test_allow_clean_command_list_format(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PROHIBITED_LIST)
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(_hook("Bash", {"command": "pytest"}, str(tmp_path)))
    )
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0
    assert capsys.readouterr().out == ""


# ── 17. Session log: allow decision written to .agentguard/session.log ────────

def test_allow_logged_to_session_log(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PROHIBITED)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(_hook("Bash", {"command": "pytest"}, str(tmp_path), session_id="sess-allow")),
    )
    with pytest.raises(SystemExit):
        run_enforce()

    session_log = tmp_path / ".agentguard" / "session.log"
    assert session_log.exists()
    entries = [json.loads(line) for line in session_log.read_text().splitlines()]
    assert len(entries) == 1
    assert entries[0]["decision"] == "allow"
    assert entries[0]["tool"] == "Bash"
    assert entries[0]["session_id"] == "sess-allow"
    assert entries[0]["reason"] is None


# ── 18. Session log: deny decision written to .agentguard/session.log ─────────

def test_deny_logged_to_session_log(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PROHIBITED)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(_hook("Bash", {"command": "rm -rf dist"}, str(tmp_path), session_id="sess-deny")),
    )
    with pytest.raises(SystemExit):
        run_enforce()

    session_log = tmp_path / ".agentguard" / "session.log"
    assert session_log.exists()
    entries = [json.loads(line) for line in session_log.read_text().splitlines()]
    assert len(entries) == 1
    assert entries[0]["decision"] == "deny"
    assert entries[0]["tool"] == "Bash"
    assert entries[0]["session_id"] == "sess-deny"
    assert entries[0]["reason"] is not None


# ── 19. Session log: .agentguard/ directory created automatically ─────────────

def test_agentguard_dir_created_automatically(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PROHIBITED)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(_hook("Bash", {"command": "pytest"}, str(tmp_path))),
    )
    assert not (tmp_path / ".agentguard").exists()
    with pytest.raises(SystemExit):
        run_enforce()
    assert (tmp_path / ".agentguard").is_dir()
    assert (tmp_path / ".agentguard" / "session.log").exists()


_GOV_CORE_ARCH = """\
owner: Alice
scope:
  authorized: []
  prohibited: []
  requires_confirmation:
    - action: "Modify core architecture or design patterns"
      reason: "Structural changes have wide-reaching implications"
escalation:
  contact: alice@example.com
killswitch: Ctrl+C
"""


# ── 20. Path-aware branch removed: _match_confirmation_text no longer checks paths

def test_write_scope_no_match_core_architecture_path_via_text():
    # Path-based protection now handled by path_policy, not _match_confirmation_text.
    assert _match_confirmation_text(
        "Edit",
        "agentguard/enforcement/enforcer.py old new",
        "modify core architecture or design patterns",
        file_path="agentguard/enforcement/enforcer.py",
    ) is False


# ── 21. Path-aware: Edit to non-core path does not match ────────────────────

def test_write_scope_no_match_non_core_path():
    assert _match_confirmation_text(
        "Edit",
        "agentguard/output/renderer.py old new",
        "modify core architecture or design patterns",
        file_path="agentguard/output/renderer.py",
    ) is False


# ── 22. Path-aware: Edit to frontend path does not match ────────────────────

def test_write_scope_no_match_frontend_path():
    assert _match_confirmation_text(
        "Edit",
        "web/src/app.jsx old new",
        "modify core architecture or design patterns",
        file_path="web/src/App.jsx",
    ) is False


# ── 23. requires_confirmation match → permissionDecision "ask", exit 0 ───────

def test_confirmation_match_emits_ask_exit_0(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_CORE_ARCH)
    tool_input = {"file_path": "agentguard/enforcement/enforcer.py", "old_string": "x", "new_string": "y"}
    monkeypatch.setattr("sys.stdin", io.StringIO(_hook("Edit", tool_input, str(tmp_path))))
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "AgentGuard" in result["hookSpecificOutput"]["permissionDecisionReason"]


# ── 24. prohibited match → permissionDecision "deny", exit 2 (no regression) ─

def test_prohibited_match_still_emits_deny_exit_2(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PROHIBITED)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(_hook("Bash", {"command": "rm -rf dist"}, str(tmp_path))),
    )
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


# ── 25. "rm -f" in source content does not trigger deletion-scope match ───────

def test_rm_f_in_source_content_not_blocked(tmp_path, monkeypatch, capsys):
    """Edit whose content contains literal 'rm -f' as a string in Python source
    must not trigger the deletion-scope confirmation check."""
    (tmp_path / "governance.yaml").write_text(_GOV_CONFIRMATION)
    tool_input = {
        "file_path": "agentguard/output/renderer.py",
        "old_string": "x",
        "new_string": 'if re.search(r"\\brm\\s+-\\S*[rf]", s) or "rm -f" in s:',
    }
    monkeypatch.setattr("sys.stdin", io.StringIO(_hook("Edit", tool_input, str(tmp_path))))
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0
    assert capsys.readouterr().out == ""


def test_bash_rm_f_command_still_triggers(tmp_path, monkeypatch, capsys):
    """An actual Bash 'rm -f somefile' command must still trigger the deletion-scope match."""
    (tmp_path / "governance.yaml").write_text(_GOV_CONFIRMATION)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(_hook("Bash", {"command": "rm -f somefile.txt"}, str(tmp_path))),
    )
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["hookSpecificOutput"]["permissionDecision"] == "ask"


# ── 27-32. Tag-push branch: only tag-related push operations match ────────────

# Rule text that mentions "git push" to describe tag-push patterns (like governance.yaml rule 4)
_TAG_RULE_TEXT = (
    "git tag operations require explicit user confirmation. blocked commands: "
    "git tag, git push --tags, git push with version tags, git push refs/tags/*"
)


def test_git_push_origin_main_does_not_match_tag_rule():
    """git push origin main must NOT trigger a tag-push confirmation rule."""
    assert _match_confirmation_text(
        "Bash", "git push origin main", _TAG_RULE_TEXT
    ) is False


def test_git_push_tags_flag_matches_tag_rule():
    """git push --tags must match a tag-push confirmation rule."""
    assert _match_confirmation_text(
        "Bash", "git push --tags", _TAG_RULE_TEXT
    ) is True


def test_git_push_version_tag_matches_tag_rule():
    """git push origin v0.10.1 must match a tag-push confirmation rule."""
    assert _match_confirmation_text(
        "Bash", "git push origin v0.10.1", _TAG_RULE_TEXT
    ) is True


def test_git_push_refs_tags_matches_tag_rule():
    """git push origin refs/tags/v0.10.1 must match a tag-push confirmation rule."""
    assert _match_confirmation_text(
        "Bash", "git push origin refs/tags/v0.10.1", _TAG_RULE_TEXT
    ) is True


def test_git_tag_command_matches_tag_rule():
    """git tag v0.10.1 must match a tag-push confirmation rule."""
    assert _match_confirmation_text(
        "Bash", "git tag v0.10.1", _TAG_RULE_TEXT
    ) is True


def test_commit_and_push_main_does_not_match_tag_rule():
    """git commit && git push origin main must NOT trigger a tag-push confirmation rule."""
    assert _match_confirmation_text(
        "Bash",
        'git commit -m "x" && git push origin main',
        _TAG_RULE_TEXT,
    ) is False


# ── path_policy integration tests ─────────────────────────────────────────────

_GOV_PATH_POLICY_DENIED = """\
owner: Alice
scope:
  authorized: []
  prohibited: []
  requires_confirmation: []
escalation:
  contact: alice@example.com
killswitch: Ctrl+C
path_policy:
  denied_paths:
    - pattern: "secrets/**"
      reason: "no secret access allowed"
  default_for_unmatched: allow
"""

_GOV_PATH_POLICY_PROTECTED = """\
owner: Alice
scope:
  authorized: []
  prohibited: []
  requires_confirmation: []
escalation:
  contact: alice@example.com
killswitch: Ctrl+C
path_policy:
  protected_paths:
    - pattern: "agentguard/enforcement/**"
      reason: "core enforcement layer"
  default_for_unmatched: allow
"""

_GOV_PATH_POLICY_AUTHORIZED_WITH_PROHIBITED = """\
owner: Alice
scope:
  authorized: []
  prohibited:
    - action: "No database operations"
      reason: "No DB access"
      severity: "HARD_LIMIT"
  requires_confirmation: []
escalation:
  contact: alice@example.com
killswitch: Ctrl+C
path_policy:
  authorized_paths:
    - pattern: "tests/**"
      reason: "test files are authorized"
  default_for_unmatched: allow
"""

_GOV_PATH_POLICY_DEFAULT_DENY = """\
owner: Alice
scope:
  authorized: []
  prohibited: []
  requires_confirmation: []
escalation:
  contact: alice@example.com
killswitch: Ctrl+C
path_policy:
  denied_paths: []
  default_for_unmatched: deny
"""

_GOV_PATH_POLICY_DEFAULT_ASK = """\
owner: Alice
scope:
  authorized: []
  prohibited: []
  requires_confirmation: []
escalation:
  contact: alice@example.com
killswitch: Ctrl+C
path_policy:
  denied_paths: []
  default_for_unmatched: ask
"""

_GOV_PATH_POLICY_PRECEDENCE = """\
owner: Alice
scope:
  authorized: []
  prohibited: []
  requires_confirmation: []
escalation:
  contact: alice@example.com
killswitch: Ctrl+C
path_policy:
  denied_paths:
    - pattern: "agentguard/**"
      reason: "deny all agentguard files"
  protected_paths:
    - pattern: "agentguard/enforcement/**"
      reason: "would be ask if denied did not win"
  default_for_unmatched: allow
"""

_GOV_NO_PATH_POLICY = """\
owner: Alice
scope:
  authorized: []
  prohibited: []
  requires_confirmation: []
escalation:
  contact: alice@example.com
killswitch: Ctrl+C
"""


# ── 28. denied_paths match → deny (exit 2) ────────────────────────────────────

def test_path_policy_denied_paths_blocks_file(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PATH_POLICY_DENIED)
    tool_input = {"file_path": "secrets/api_key.txt", "content": "key: value"}
    monkeypatch.setattr("sys.stdin", io.StringIO(_hook("Write", tool_input, str(tmp_path))))
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "no secret access allowed" in result["hookSpecificOutput"]["permissionDecisionReason"]


# ── 29. protected_paths match → ask (exit 0, permissionDecision="ask") ────────

def test_path_policy_protected_paths_asks_for_file(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PATH_POLICY_PROTECTED)
    tool_input = {"file_path": "agentguard/enforcement/enforcer.py", "old_string": "x", "new_string": "y"}
    monkeypatch.setattr("sys.stdin", io.StringIO(_hook("Edit", tool_input, str(tmp_path))))
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "core enforcement layer" in result["hookSpecificOutput"]["permissionDecisionReason"]


# ── 30. authorized_paths allow, but content-based prohibited still fires ───────

def test_path_policy_authorized_allows_but_prohibited_still_fires(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PATH_POLICY_AUTHORIZED_WITH_PROHIBITED)
    tool_input = {"file_path": "tests/test_db.py", "new_string": "DROP TABLE users"}
    monkeypatch.setattr("sys.stdin", io.StringIO(_hook("Edit", tool_input, str(tmp_path))))
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


# ── 31. no path_policy match → default_for_unmatched=deny blocks ──────────────

def test_path_policy_default_deny_blocks_unmatched_file(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PATH_POLICY_DEFAULT_DENY)
    tool_input = {"file_path": "web/src/App.jsx", "content": "x"}
    monkeypatch.setattr("sys.stdin", io.StringIO(_hook("Write", tool_input, str(tmp_path))))
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"


# ── 32. no path_policy match → default_for_unmatched=ask gates ────────────────

def test_path_policy_default_ask_gates_unmatched_file(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PATH_POLICY_DEFAULT_ASK)
    tool_input = {"file_path": "web/src/App.jsx", "content": "x"}
    monkeypatch.setattr("sys.stdin", io.StringIO(_hook("Write", tool_input, str(tmp_path))))
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["hookSpecificOutput"]["permissionDecision"] == "ask"


# ── 33. backward compat: no path_policy key, core path → ask ─────────────────

def test_path_policy_backward_compat_core_path_asks(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_NO_PATH_POLICY)
    tool_input = {"file_path": "agentguard/enforcement/enforcer.py", "old_string": "x", "new_string": "y"}
    monkeypatch.setattr("sys.stdin", io.StringIO(_hook("Edit", tool_input, str(tmp_path))))
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0
    result = json.loads(capsys.readouterr().out)
    assert result["hookSpecificOutput"]["permissionDecision"] == "ask"


# ── 34. backward compat: no path_policy key, unrelated new file → allow ───────

def test_path_policy_backward_compat_unrelated_file_falls_through(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_NO_PATH_POLICY)
    tool_input = {"file_path": "tests/new_test.py", "content": "def test_x(): pass"}
    monkeypatch.setattr("sys.stdin", io.StringIO(_hook("Write", tool_input, str(tmp_path))))
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0
    assert capsys.readouterr().out == ""


# ── 35. Bash tool: path_policy never applies ──────────────────────────────────

def test_path_policy_bash_tool_unaffected(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PATH_POLICY_DENIED)
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO(_hook("Bash", {"command": "cat secrets/api_key.txt"}, str(tmp_path))),
    )
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 0
    assert capsys.readouterr().out == ""


# ── 36. precedence: denied_paths wins over protected_paths ───────────────────

def test_path_policy_precedence_denied_beats_protected(tmp_path, monkeypatch, capsys):
    (tmp_path / "governance.yaml").write_text(_GOV_PATH_POLICY_PRECEDENCE)
    tool_input = {"file_path": "agentguard/enforcement/enforcer.py", "old_string": "x", "new_string": "y"}
    monkeypatch.setattr("sys.stdin", io.StringIO(_hook("Edit", tool_input, str(tmp_path))))
    with pytest.raises(SystemExit) as exc:
        run_enforce()
    assert exc.value.code == 2
    result = json.loads(capsys.readouterr().out)
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "deny all agentguard files" in result["hookSpecificOutput"]["permissionDecisionReason"]


# ── _match_path_policy unit tests ─────────────────────────────────────────────

def test_match_path_policy_returns_none_for_bash():
    from agentguard.config.loader import PathPolicy
    assert _match_path_policy("Bash", "secrets/key.txt", PathPolicy()) is None


def test_match_path_policy_returns_none_for_empty_path():
    from agentguard.config.loader import PathPolicy
    assert _match_path_policy("Edit", None, PathPolicy()) is None
