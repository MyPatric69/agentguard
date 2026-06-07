"""Tests for config/loader.py."""

from agentguard.config.loader import DEFAULTS, find_config, get_severity, load_config


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
