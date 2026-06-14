"""Tests for config/loader.py."""

import pytest

from agentguard.config.loader import (
    CORE_ARCHITECTURE_PATHS,
    DEFAULTS,
    GovernanceConfigError,
    find_config,
    get_severity,
    load_config,
    load_path_policy,
)


def test_load_config_returns_defaults_when_file_missing(tmp_path):
    config = load_config(tmp_path / "nonexistent.yaml")
    assert config["owner"] == ""
    assert config["scope"] == {"authorized": "", "prohibited": "", "requires_confirmation": ""}
    assert config["escalation"]["contact"] == ""
    assert config["escalation"]["method"] == "log"
    assert config["killswitch"] == ""


def test_load_config_merges_with_defaults(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(
        "owner: Alice\n"
        "scope:\n"
        "  authorized: read and modify Python files in ./src\n"
        "  prohibited: no database operations\n"
        "  requires_confirmation: any file deletion\n"
    )
    config = load_config(gov)
    assert config["owner"] == "Alice"
    assert config["scope"]["authorized"] == "read and modify Python files in ./src"
    assert config["scope"]["prohibited"] == "no database operations"
    assert config["escalation"]["contact"] == ""  # default preserved


def test_load_config_nested_merge(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text("escalation:\n  contact: alice@example.com\n")
    config = load_config(gov)
    assert config["escalation"]["contact"] == "alice@example.com"
    assert config["escalation"]["trigger"] == DEFAULTS["escalation"]["trigger"]
    assert config["escalation"]["method"] == "log"  # default preserved


def test_load_config_severity_override(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text("severity:\n  no_owner: warning\n")
    config = load_config(gov)
    assert config["severity"]["no_owner"] == "warning"
    assert config["severity"]["no_scope"] == "critical"  # default preserved


def test_find_config_finds_governance_yaml(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text("owner: Bob\n")
    found = find_config(tmp_path)
    assert found == gov


def test_find_config_returns_none_when_missing(tmp_path):
    assert find_config(tmp_path) is None


def test_get_severity_returns_correct_level(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text("severity:\n  no_owner: warning\n")
    config = load_config(gov)
    assert get_severity(config, "no_owner") == "warning"
    assert get_severity(config, "no_scope") == "critical"


def test_get_severity_unknown_key_returns_warning():
    config = dict(DEFAULTS)
    assert get_severity(config, "completely_unknown_key") == "warning"


# ── Escalation method tests ───────────────────────────────────────────────────

def test_escalation_method_defaults_to_log():
    config = dict(DEFAULTS)
    assert config["escalation"]["method"] == "log"


def test_escalation_method_terminal(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text("escalation:\n  contact: alice@example.com\n  method: terminal\n")
    config = load_config(gov)
    assert config["escalation"]["method"] == "terminal"


def test_escalation_method_file(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text("escalation:\n  contact: alice@example.com\n  method: file\n")
    config = load_config(gov)
    assert config["escalation"]["method"] == "file"


# ── New structured scope format ───────────────────────────────────────────────

def test_load_config_list_scope_format(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(
        "owner: Alice\n"
        "scope:\n"
        "  authorized:\n"
        '    - action: "Read Python files"\n'
        '      reason: "Core task"\n'
        "  prohibited:\n"
        '    - action: "No git push"\n'
        '      reason: "Hard limit"\n'
        '      severity: "HARD_LIMIT"\n'
        "  requires_confirmation:\n"
        '    - action: "Any deletion"\n'
        '      reason: "Irreversible"\n'
    )
    config = load_config(gov)
    assert config["owner"] == "Alice"
    authorized = config["scope"]["authorized"]
    assert isinstance(authorized, list)
    assert authorized[0]["action"] == "Read Python files"
    prohibited = config["scope"]["prohibited"]
    assert isinstance(prohibited, list)
    assert prohibited[0]["severity"] == "HARD_LIMIT"


def test_load_config_legacy_string_scope_preserved(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(
        "owner: Alice\n"
        "scope:\n"
        "  authorized: read and modify Python files in ./src\n"
        "  prohibited: no database operations\n"
        "  requires_confirmation: any file deletion\n"
    )
    config = load_config(gov)
    assert config["scope"]["authorized"] == "read and modify Python files in ./src"
    assert config["scope"]["prohibited"] == "no database operations"


# ── path_policy loading ───────────────────────────────────────────────────────

def test_load_path_policy_full_section(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(
        "path_policy:\n"
        "  denied_paths:\n"
        "    - pattern: 'secrets/**'\n"
        "      reason: 'no secret access'\n"
        "  protected_paths:\n"
        "    - pattern: 'agentguard/enforcement/**'\n"
        "      reason: 'core layer'\n"
        "  authorized_paths:\n"
        "    - pattern: 'tests/**'\n"
        "      reason: 'test files'\n"
        "  default_for_unmatched: deny\n"
    )
    raw = load_config(gov)
    policy = load_path_policy(raw)
    assert len(policy.denied_paths) == 1
    assert policy.denied_paths[0].pattern == "secrets/**"
    assert policy.denied_paths[0].reason == "no secret access"
    assert len(policy.protected_paths) == 1
    assert policy.protected_paths[0].pattern == "agentguard/enforcement/**"
    assert len(policy.authorized_paths) == 1
    assert policy.authorized_paths[0].pattern == "tests/**"
    assert policy.default_for_unmatched == "deny"


def test_load_path_policy_absent_returns_backward_compat_defaults(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text("owner: Alice\n")
    raw = load_config(gov)
    policy = load_path_policy(raw)
    assert policy.denied_paths == []
    assert policy.authorized_paths == []
    assert policy.default_for_unmatched == "allow"
    protected_patterns = [e.pattern for e in policy.protected_paths]
    for path in CORE_ARCHITECTURE_PATHS:
        assert path in protected_patterns


def test_load_path_policy_default_for_unmatched_omitted_defaults_to_ask(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(
        "path_policy:\n"
        "  denied_paths:\n"
        "    - pattern: 'secrets/**'\n"
        "      reason: 'sensitive'\n"
    )
    raw = load_config(gov)
    policy = load_path_policy(raw)
    assert policy.default_for_unmatched == "ask"


def test_load_path_policy_invalid_default_for_unmatched_raises(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(
        "path_policy:\n"
        "  default_for_unmatched: maybe\n"
    )
    raw = load_config(gov)
    with pytest.raises(GovernanceConfigError, match="default_for_unmatched"):
        load_path_policy(raw)


def test_load_path_policy_missing_pattern_raises(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text(
        "path_policy:\n"
        "  denied_paths:\n"
        "    - reason: 'forgot the pattern'\n"
    )
    raw = load_config(gov)
    with pytest.raises(GovernanceConfigError, match="pattern"):
        load_path_policy(raw)
