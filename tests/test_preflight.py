"""Tests for checks/preflight.py."""

from pathlib import Path

from agentguard.checks.preflight import has_criticals, run_preflight


def _make_project(tmp_path: Path, **kwargs) -> Path:
    """Create a minimal project directory. kwargs control which files are created."""

    if kwargs.get("governance_yaml"):
        (tmp_path / "governance.yaml").write_text(kwargs["governance_yaml"])

    if kwargs.get("claude_md"):
        (tmp_path / "CLAUDE.md").write_text(kwargs["claude_md"])

    if kwargs.get("agents_md"):
        (tmp_path / "AGENTS.md").write_text(kwargs["agents_md"])

    if kwargs.get("py_content"):
        (tmp_path / "main.py").write_text(kwargs["py_content"])

    return tmp_path


def _find(findings, severity, fragment):
    return any(f.severity == severity and fragment.lower() in f.message.lower() for f in findings)


# ── Level 0 CRITICAL checks ──────────────────────────────────────────────────

def test_no_owner_triggers_critical(tmp_path):
    proj = _make_project(tmp_path)
    findings = run_preflight(proj)
    assert _find(findings, "critical", "owner")


def test_no_scope_triggers_critical(tmp_path):
    proj = _make_project(tmp_path)
    findings = run_preflight(proj)
    assert _find(findings, "critical", "scope")


def test_no_escalation_triggers_critical(tmp_path):
    proj = _make_project(tmp_path)
    findings = run_preflight(proj)
    assert _find(findings, "critical", "escalation")


def test_no_killswitch_triggers_critical(tmp_path):
    proj = _make_project(tmp_path)
    findings = run_preflight(proj)
    assert _find(findings, "critical", "killswitch")


def test_no_instruction_file_triggers_critical(tmp_path):
    proj = _make_project(tmp_path)
    findings = run_preflight(proj)
    assert _find(findings, "critical", "claude.md") or _find(findings, "critical", "agents.md")


# ── OK when conditions met ────────────────────────────────────────────────────

def test_full_governance_passes(tmp_path):
    gov = (
        "owner: Alice\n"
        "scope: data pipeline\n"
        "escalation:\n  contact: alice@example.com\n"
        "killswitch: Ctrl+C\n"
    )
    claude = (
        "# Project\nLoop detection: if stuck retry a different approach.\n"
        "Root cause: confirm before fixing.\n"
        "Fetch documentation before diagnosing API issues.\n"
    )
    proj = _make_project(tmp_path, governance_yaml=gov, claude_md=claude)
    findings = run_preflight(proj)
    assert not has_criticals(findings)


def test_agents_md_accepted_as_instruction_file(tmp_path):
    gov = (
        "owner: Bob\nscope: ETL\n"
        "escalation:\n  contact: bob@example.com\n"
        "killswitch: kill PID\n"
    )
    proj = _make_project(tmp_path, governance_yaml=gov, agents_md="# Agents\nloop detection here\n")
    findings = run_preflight(proj)
    assert not _find(findings, "critical", "no claude.md") and not _find(findings, "critical", "no agents.md")


# ── WARNING checks ────────────────────────────────────────────────────────────

def test_no_loop_detection_triggers_warning(tmp_path):
    gov = (
        "owner: Alice\nscope: data pipeline\n"
        "escalation:\n  contact: alice@example.com\n"
        "killswitch: Ctrl+C\n"
    )
    proj = _make_project(tmp_path, governance_yaml=gov, claude_md="# No relevant directives in this file\n")
    findings = run_preflight(proj)
    assert _find(findings, "warning", "loop")


def test_no_root_cause_triggers_warning(tmp_path):
    gov = (
        "owner: Alice\nscope: data pipeline\n"
        "escalation:\n  contact: alice@example.com\n"
        "killswitch: Ctrl+C\n"
    )
    proj = _make_project(tmp_path, governance_yaml=gov, claude_md="# loop detection present\n")
    findings = run_preflight(proj)
    assert _find(findings, "warning", "root")


def test_no_attempt_counter_triggers_warning(tmp_path):
    gov = (
        "owner: Alice\nscope: data pipeline\n"
        "escalation:\n  contact: alice@example.com\n"
        "killswitch: Ctrl+C\n"
    )
    proj = _make_project(
        tmp_path,
        governance_yaml=gov,
        claude_md="loop detection, root cause, fetch docs",
        py_content="def run(): pass\n",
    )
    findings = run_preflight(proj)
    assert _find(findings, "warning", "attempt")


def test_no_action_log_triggers_warning(tmp_path):
    gov = (
        "owner: Alice\nscope: data pipeline\n"
        "escalation:\n  contact: alice@example.com\n"
        "killswitch: Ctrl+C\n"
    )
    proj = _make_project(
        tmp_path,
        governance_yaml=gov,
        claude_md="loop detection, root cause, fetch docs",
        py_content="attempt_count = 0\n",
    )
    findings = run_preflight(proj)
    assert _find(findings, "warning", "action log")


# ── Severity override via config ──────────────────────────────────────────────

def test_severity_override_demotes_owner_to_warning(tmp_path):
    gov = (
        "owner: ''\n"
        "scope: pipeline\n"
        "escalation:\n  contact: x@y.com\n"
        "killswitch: Ctrl+C\n"
        "severity:\n  no_owner: warning\n"
    )
    proj = _make_project(tmp_path, governance_yaml=gov, claude_md="loop root cause fetch docs")
    findings = run_preflight(proj)
    assert _find(findings, "warning", "owner")
    assert not _find(findings, "critical", "owner")


# ── has_criticals helper ──────────────────────────────────────────────────────

def test_has_criticals_true():
    from agentguard.output.renderer import Finding
    findings = [Finding("critical", "something"), Finding("ok", "other")]
    assert has_criticals(findings) is True


def test_has_criticals_false():
    from agentguard.output.renderer import Finding
    findings = [Finding("warning", "something"), Finding("ok", "other")]
    assert has_criticals(findings) is False
