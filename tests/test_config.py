"""Tests for config/loader.py."""


from agentguard.config.loader import DEFAULTS, find_config, get_severity, load_config


def test_load_config_returns_defaults_when_file_missing(tmp_path):
    config = load_config(tmp_path / "nonexistent.yaml")
    assert config["owner"] == ""
    assert config["scope"] == ""
    assert config["escalation"]["contact"] == ""
    assert config["killswitch"] == ""


def test_load_config_merges_with_defaults(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text("owner: Alice\nscope: data pipeline\n")
    config = load_config(gov)
    assert config["owner"] == "Alice"
    assert config["scope"] == "data pipeline"
    assert config["escalation"]["contact"] == ""  # default preserved


def test_load_config_nested_merge(tmp_path):
    gov = tmp_path / "governance.yaml"
    gov.write_text("escalation:\n  contact: alice@example.com\n")
    config = load_config(gov)
    assert config["escalation"]["contact"] == "alice@example.com"
    assert config["escalation"]["trigger"] == DEFAULTS["escalation"]["trigger"]


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
