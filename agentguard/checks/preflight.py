"""Layer 1: Governance, prompt, and harness pre-flight checks."""

from __future__ import annotations

import re
from pathlib import Path

from agentguard.config.loader import get_severity, load_config
from agentguard.output.renderer import Finding

LOOP_KEYWORDS = ["loop", "iteration", "attempt", "stuck", "retry"]
ROOT_CAUSE_KEYWORDS = ["root cause", "root_cause", "diagnose before", "confirm before"]
API_RESEARCH_KEYWORDS = ["fetch", "documentation", "never rely on memory", "aktuelle"]

ATTEMPT_COUNTER_PATTERNS = [r"attempt_count", r"retry_count", r"max_attempts"]
ACTION_LOG_PATTERNS = [r"action_log", r"log_action", r"append.*log"]
ERROR_PATTERN_PATTERNS = [r"same_error", r"error_pattern", r"consecutive_errors"]

_SCOPE_BOUNDARY_WORDS = ["no", "not", "never", "kein", "ohne"]
_SCOPE_MIN_AUTHORIZED_LEN = 20


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError:
        return ""


def _scan_keywords(text: str, keywords: list[str]) -> bool:
    return any(kw.lower() in text for kw in keywords)


def _scan_patterns(text: str, patterns: list[str]) -> bool:
    return any(re.search(pat, text) for pat in patterns)


def _collect_py_content(project_path: Path) -> str:
    parts: list[str] = []
    for py_file in project_path.rglob("*.py"):
        parts.append(_read_text(py_file))
    return "\n".join(parts)


def _check_scope(config: dict, findings: list[Finding]) -> None:
    """Validate structured scope fields and append findings."""
    raw_scope = config.get("scope", {})

    if isinstance(raw_scope, str):
        # Legacy single-string scope — treat as authorized only
        scope = {"authorized": raw_scope, "prohibited": "", "requires_confirmation": ""}
    else:
        scope = raw_scope

    authorized = scope.get("authorized", "").strip()
    prohibited = scope.get("prohibited", "").strip()
    requires_confirmation = scope.get("requires_confirmation", "").strip()

    # authorized
    if not authorized:
        findings.append(Finding(get_severity(config, "no_scope"), "No authorized scope defined"))
    elif len(authorized) < _SCOPE_MIN_AUTHORIZED_LEN:
        findings.append(Finding("warning", "Scope too vague — be specific (authorized field < 20 chars)"))
    else:
        findings.append(Finding("ok", "Authorized scope defined"))

    # prohibited
    if not prohibited:
        findings.append(Finding(get_severity(config, "no_scope"), "No prohibited actions defined in scope"))
    elif not any(word in prohibited.lower() for word in _SCOPE_BOUNDARY_WORDS):
        findings.append(Finding("warning", "Scope has no boundaries defined (use 'no', 'not', 'never', etc.)"))
    else:
        findings.append(Finding("ok", "Scope boundaries defined"))

    # requires_confirmation
    if not requires_confirmation:
        findings.append(Finding(
            get_severity(config, "no_scope"),
            "No confirmation-required actions defined in scope",
        ))
    else:
        findings.append(Finding("ok", "Confirmation requirements defined"))


def run_preflight(project_path: str | Path, config_path: str | Path | None = None) -> list[Finding]:
    """Run all pre-flight checks and return a list of Findings."""
    base = Path(project_path).resolve()

    if config_path is not None:
        config = load_config(config_path)
    else:
        candidate = base / "governance.yaml"
        config = load_config(candidate) if candidate.exists() else {}

    from agentguard.config.loader import DEFAULTS, _deep_merge
    config = _deep_merge(DEFAULTS, config)

    findings: list[Finding] = []

    # ── Level 0: Required governance fields ──────────────────────────────────

    if not config.get("owner", "").strip():
        findings.append(Finding(get_severity(config, "no_owner"), "No agent owner defined"))
    else:
        findings.append(Finding("ok", "Owner defined"))

    _check_scope(config, findings)

    escalation = config.get("escalation", {})
    if not escalation.get("contact", "").strip():
        findings.append(Finding(get_severity(config, "no_escalation"), "No escalation path configured"))
    else:
        findings.append(Finding("ok", "Escalation path configured"))

    if not config.get("killswitch", "").strip():
        findings.append(Finding(get_severity(config, "no_killswitch"), "No killswitch defined"))
    else:
        findings.append(Finding("ok", "Killswitch defined"))

    # ── Instruction file checks ───────────────────────────────────────────────

    claude_md = base / "CLAUDE.md"
    agents_md = base / "AGENTS.md"

    if claude_md.exists():
        findings.append(Finding("ok", "CLAUDE.md present"))
        instruction_text = _read_text(claude_md)
    elif agents_md.exists():
        findings.append(Finding("ok", "AGENTS.md present"))
        instruction_text = _read_text(agents_md)
    else:
        findings.append(Finding(
            get_severity(config, "no_instruction_file"),
            "No CLAUDE.md or AGENTS.md found — one is required",
        ))
        instruction_text = ""

    # ── SKILL.md check ────────────────────────────────────────────────────────

    skill_md = base / "SKILL.md"
    py_content = _collect_py_content(base)

    has_workflow_patterns = bool(
        re.search(r"(workflow|pipeline|chain|orchestrat)", py_content)
    )
    if has_workflow_patterns and not skill_md.exists():
        findings.append(Finding(
            get_severity(config, "no_skill_md"),
            "Project appears to use specialized workflows — consider documenting them in SKILL.md",
        ))

    # ── Prompt quality checks (from instruction file) ────────────────────────

    if instruction_text:
        if _scan_keywords(instruction_text, LOOP_KEYWORDS):
            findings.append(Finding("ok", "Loop-detection directive found"))
        else:
            findings.append(Finding(
                get_severity(config, "no_loop_detection"),
                "No loop detection directive in CLAUDE.md/AGENTS.md",
            ))

        if _scan_keywords(instruction_text, ROOT_CAUSE_KEYWORDS):
            findings.append(Finding("ok", "Root-cause directive found"))
        else:
            findings.append(Finding(
                get_severity(config, "no_root_cause_rule"),
                "No root-cause analysis rule in CLAUDE.md/AGENTS.md",
            ))

        if _scan_keywords(instruction_text, API_RESEARCH_KEYWORDS):
            findings.append(Finding("ok", "External API research rule found"))
        else:
            findings.append(Finding(
                get_severity(config, "no_api_research_rule"),
                "No external API research rule in CLAUDE.md/AGENTS.md",
            ))
    else:
        findings.append(Finding(
            get_severity(config, "no_loop_detection"),
            "No loop detection directive (fix: create CLAUDE.md first)",
        ))
        findings.append(Finding(
            get_severity(config, "no_root_cause_rule"),
            "No root-cause analysis rule (fix: create CLAUDE.md first)",
        ))
        findings.append(Finding(
            get_severity(config, "no_api_research_rule"),
            "No external API research rule (fix: create CLAUDE.md first)",
        ))

    # ── Harness checks (scan Python source) ──────────────────────────────────

    if py_content:
        if _scan_patterns(py_content, ATTEMPT_COUNTER_PATTERNS):
            findings.append(Finding("ok", "Attempt counter found in harness"))
        else:
            findings.append(Finding(
                get_severity(config, "no_attempt_counter"),
                "No attempt counter in harness (attempt_count / retry_count / max_attempts)",
            ))

        if _scan_patterns(py_content, ACTION_LOG_PATTERNS):
            findings.append(Finding("ok", "Action log found in harness"))
        else:
            findings.append(Finding(
                get_severity(config, "no_action_log"),
                "No action log in harness (action_log / log_action / append.*log)",
            ))

        if _scan_patterns(py_content, ERROR_PATTERN_PATTERNS):
            findings.append(Finding("ok", "Error pattern detection found in harness"))

    return findings


def has_criticals(findings: list[Finding]) -> bool:
    return any(f.severity == "critical" for f in findings)
