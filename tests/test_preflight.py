"""Tests for checks/preflight.py."""

from pathlib import Path

from agentguard.checks.preflight import has_criticals, run_preflight

# ── Shared fixtures ───────────────────────────────────────────────────────────

_VALID_SCOPE = (
    "scope:\n"
    "  authorized: read and modify Python files in ./src directory only\n"
    "  prohibited: no database operations, no external API calls\n"
    "  requires_confirmation: any file deletion or git push\n"
)

_VALID_GOV = (
    "owner: Alice\n"
    + _VALID_SCOPE
    + "escalation:\n  contact: alice@example.com\n"
    + "killswitch: Ctrl+C\n"
)

_FULL_CLAUDE = (
    "# Project\n"
    "Loop detection: if stuck, retry a different approach.\n"
    "Root cause: confirm before fixing.\n"
    "Fetch documentation before diagnosing API issues.\n"
)


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


# ── OK when all conditions met ────────────────────────────────────────────────

def test_full_governance_passes(tmp_path):
    proj = _make_project(tmp_path, governance_yaml=_VALID_GOV, claude_md=_FULL_CLAUDE)
    findings = run_preflight(proj)
    assert not has_criticals(findings)


def test_agents_md_accepted_as_instruction_file(tmp_path):
    gov = (
        "owner: Bob\n"
        "scope:\n"
        "  authorized: run ETL pipelines in the ./etl directory only\n"
        "  prohibited: no schema changes, not allowed to modify production data\n"
        "  requires_confirmation: any pipeline run against production\n"
        "escalation:\n  contact: bob@example.com\n"
        "killswitch: kill PID\n"
    )
    proj = _make_project(tmp_path, governance_yaml=gov, agents_md="# Agents\nloop detection here\n")
    findings = run_preflight(proj)
    assert not _find(findings, "critical", "no claude.md")
    assert not _find(findings, "critical", "no agents.md")


# ── Scope quality validation ──────────────────────────────────────────────────

def test_scope_authorized_too_short_triggers_warning(tmp_path):
    gov = (
        "owner: Alice\n"
        "scope:\n"
        "  authorized: read files\n"  # < 20 chars
        "  prohibited: no database operations\n"
        "  requires_confirmation: any deletion\n"
        "escalation:\n  contact: alice@example.com\n"
        "killswitch: Ctrl+C\n"
    )
    proj = _make_project(tmp_path, governance_yaml=gov, claude_md=_FULL_CLAUDE)
    findings = run_preflight(proj)
    assert _find(findings, "warning", "vague")


def test_scope_no_boundary_words_triggers_warning(tmp_path):
    gov = (
        "owner: Alice\n"
        "scope:\n"
        "  authorized: read and modify Python files in ./src directory\n"
        "  prohibited: delete files from the production database\n"  # no boundary words
        "  requires_confirmation: any file deletion\n"
        "escalation:\n  contact: alice@example.com\n"
        "killswitch: Ctrl+C\n"
    )
    proj = _make_project(tmp_path, governance_yaml=gov, claude_md=_FULL_CLAUDE)
    findings = run_preflight(proj)
    assert _find(findings, "warning", "boundaries")


def test_scope_all_three_fields_empty_trigger_critical(tmp_path):
    gov = (
        "owner: Alice\n"
        "scope:\n"
        "  authorized: ''\n"
        "  prohibited: ''\n"
        "  requires_confirmation: ''\n"
        "escalation:\n  contact: alice@example.com\n"
        "killswitch: Ctrl+C\n"
    )
    proj = _make_project(tmp_path, governance_yaml=gov, claude_md=_FULL_CLAUDE)
    findings = run_preflight(proj)
    scope_criticals = [f for f in findings if f.severity == "critical" and "scope" in f.message.lower()]
    assert len(scope_criticals) == 3


def test_scope_missing_prohibited_triggers_critical(tmp_path):
    gov = (
        "owner: Alice\n"
        "scope:\n"
        "  authorized: read and modify Python files in ./src directory\n"
        "  prohibited: ''\n"
        "  requires_confirmation: any file deletion\n"
        "escalation:\n  contact: alice@example.com\n"
        "killswitch: Ctrl+C\n"
    )
    proj = _make_project(tmp_path, governance_yaml=gov, claude_md=_FULL_CLAUDE)
    findings = run_preflight(proj)
    assert _find(findings, "critical", "prohibited")


# ── WARNING checks ────────────────────────────────────────────────────────────

def test_no_loop_detection_triggers_warning(tmp_path):
    proj = _make_project(tmp_path, governance_yaml=_VALID_GOV, claude_md="# No relevant directives in this file\n")
    findings = run_preflight(proj)
    assert _find(findings, "warning", "loop")


def test_no_root_cause_triggers_warning(tmp_path):
    proj = _make_project(tmp_path, governance_yaml=_VALID_GOV, claude_md="# loop detection present\n")
    findings = run_preflight(proj)
    assert _find(findings, "warning", "root")


def test_no_attempt_counter_triggers_warning(tmp_path):
    proj = _make_project(
        tmp_path,
        governance_yaml=_VALID_GOV,
        claude_md="loop detection, root cause, fetch docs",
        py_content="def run(): pass\n",
    )
    findings = run_preflight(proj)
    assert _find(findings, "warning", "attempt")


def test_no_action_log_triggers_warning(tmp_path):
    proj = _make_project(
        tmp_path,
        governance_yaml=_VALID_GOV,
        claude_md="loop detection, root cause, fetch docs",
        py_content="attempt_count = 0\n",
    )
    findings = run_preflight(proj)
    assert _find(findings, "warning", "action log")


# ── Hint text for missing instruction file ────────────────────────────────────

def test_hint_text_says_create_claude_md_when_no_instruction_file(tmp_path):
    proj = _make_project(tmp_path, governance_yaml=_VALID_GOV)
    findings = run_preflight(proj)
    hint_findings = [f for f in findings if "fix: create claude.md first" in f.message.lower()]
    assert len(hint_findings) >= 2  # loop + root-cause at minimum


# ── Severity override via config ──────────────────────────────────────────────

def test_severity_override_demotes_owner_to_warning(tmp_path):
    gov = (
        "owner: ''\n"
        "scope:\n"
        "  authorized: read and modify files in ./src directory only\n"
        "  prohibited: no database operations, no writes outside ./src\n"
        "  requires_confirmation: any file modification or deletion\n"
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
