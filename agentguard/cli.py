"""AgentGuard CLI — check, watch, report, init, override."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console

from agentguard import __version__
from agentguard.checks.preflight import has_criticals, run_preflight
from agentguard.checks.report import generate_report
from agentguard.checks.runtime import watch as runtime_watch
from agentguard.config.loader import find_config
from agentguard.output.renderer import (
    render_ai_review,
    render_json,
    render_override_confirmation,
    render_preflight,
)

_console = Console()


def _strip_quotes(value: str) -> str:
    return value.strip().strip('"\'')


def _write_hook_config(project_path: Path) -> str:
    """Generate .claude/settings.json with AgentGuard PreToolUse hook."""
    settings_dir = project_path / ".claude"
    settings_file = settings_dir / "settings.json"

    agentguard_hook = {
        "matcher": "Bash|Write|Edit|MultiEdit|NotebookEdit",
        "hooks": [{"type": "command", "command": "agentguard enforce"}],
    }

    if settings_file.exists():
        existing = json.loads(settings_file.read_text())
        hooks = existing.setdefault("hooks", {})
        pre = hooks.setdefault("PreToolUse", [])
        already_present = any(
            any(h.get("command") == "agentguard enforce" for h in entry.get("hooks", []))
            for entry in pre
        )
        if not already_present:
            pre.append(agentguard_hook)
            settings_file.write_text(json.dumps(existing, indent=2))
            return "Updated: .claude/settings.json (AgentGuard hook added)"
        return "Skipped: .claude/settings.json (AgentGuard hook already present)"

    settings_dir.mkdir(exist_ok=True)
    settings = {"hooks": {"PreToolUse": [agentguard_hook]}}
    settings_file.write_text(json.dumps(settings, indent=2))
    return "Created: .claude/settings.json (AgentGuard PreToolUse hook)"


def _update_claude_md(dest: Path, template_content: str) -> tuple[str, str]:
    """Write or append governance block to CLAUDE.md.

    Returns (action, message): action is 'created' or 'updated'.
    If dest exists, the original content is always preserved — only the block is appended.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sep = "## ─────────────────────────────────────────"
    append_block = (
        f"\n\n## AgentGuard Governance Block\n"
        f"## Added by: agentguard init --interactive\n"
        f"## Date: {timestamp}\n"
        f"{sep}\n"
        f"\n"
        f"{template_content}\n"
        f"{sep}\n"
        f"## End AgentGuard Governance Block\n"
    )
    if dest.exists():
        existing = dest.read_text()
        dest.write_text(existing + append_block)
        return "updated", "Updated: CLAUDE.md (AgentGuard governance block appended)"
    else:
        dest.write_text(template_content)
        return "created", "Created: CLAUDE.md"


@click.group()
@click.version_option(__version__, prog_name="agentguard")
def main() -> None:
    """AgentGuard — governance layer for autonomous AI agents."""


@main.command()
@click.option("--path", default=".", show_default=True, help="Project directory to check.")
@click.option("--config", "config_path", default=None, help="Path to governance.yaml.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    show_default=True,
    help="Output format.",
)
@click.option(
    "--ai-review",
    is_flag=True,
    default=False,
    help="Enable AI-powered scope quality review (requires API key in .env)",
)
def check(path: str, config_path: str | None, fmt: str, ai_review: bool) -> None:
    """Run pre-flight governance check."""
    resolved_config = config_path or find_config(path)

    try:
        findings = run_preflight(path, config_path=resolved_config, ai_review=ai_review)
    except Exception as exc:
        click.echo(f"[ERROR] Config error: {exc}", err=True)
        sys.exit(2)

    if fmt == "json":
        click.echo(render_json(findings))
    else:
        render_preflight(path, findings)

        if ai_review:
            from agentguard.ai_review import review_scope
            from agentguard.config.loader import DEFAULTS, _deep_merge, load_config

            cfg = load_config(resolved_config) if resolved_config else _deep_merge(DEFAULTS, {})
            raw_scope = cfg.get("scope", {})
            if isinstance(raw_scope, str):
                scope: dict = {"authorized": raw_scope, "prohibited": "", "requires_confirmation": ""}
            else:
                scope = raw_scope

            ai_result = review_scope(
                scope.get("authorized", ""),
                scope.get("prohibited", ""),
                scope.get("requires_confirmation", ""),
            )
            if ai_result:
                render_ai_review(ai_result)

    sys.exit(1 if has_criticals(findings) else 0)


@main.command()
@click.option("--log", "log_path", default="agent.log", show_default=True, help="JSON tool-call log to watch.")
@click.option("--interval", default=10.0, show_default=True, help="Poll interval in seconds.")
def watch(log_path: str, interval: float) -> None:
    """Start runtime observer — reads JSON tool-call log from agent harness."""
    click.echo(f"AgentGuard watching: {log_path} (interval={interval}s)")
    try:
        runtime_watch(log_path, interval=interval)
    except KeyboardInterrupt:
        click.echo("\nWatch stopped.")
    except FileNotFoundError:
        click.echo(f"[ERROR] Log file not found: {log_path}", err=True)
        sys.exit(2)


@main.command()
@click.option("--session", "session_log", default="agentguard.log", show_default=True)
@click.option("--output", "output_path", default="report.md", show_default=True)
def report(session_log: str, output_path: str) -> None:
    """Generate post-session governance report."""
    text = generate_report(session_log, output_path)
    click.echo(text)
    click.echo(f"\nReport written to: {output_path}")


@main.command("init")
@click.option("--interactive", is_flag=True, default=False, help="Guided Q&A setup.")
@click.option("--template-only", is_flag=True, default=False, help="Copy template governance.yaml only.")
def init_cmd(interactive: bool, template_only: bool) -> None:
    """Initialize AgentGuard in the current project."""
    templates_dir = Path(__file__).parent / "templates"
    gov_template = templates_dir / "governance.yaml"
    claude_template = templates_dir / "claude_md_block.md"

    if template_only or not interactive:
        dest = Path("governance.yaml")
        if dest.exists():
            click.echo("[SKIP] governance.yaml already exists.")
        else:
            dest.write_text(gov_template.read_text())
            click.echo("Created: governance.yaml")
        return

    click.echo("AgentGuard — Interactive Setup\n")
    _console.print("Agent owner (name or role):")
    _console.print('  e.g. "Jane Smith", "DevOps Team Lead", "AI Platform Team"', style="bright_yellow")
    owner = _strip_quotes(click.prompt("> ", prompt_suffix=""))

    click.echo("\nAgent scope — answer these three questions:")
    _console.print("  What tasks is this agent authorized to perform?")
    _console.print('  e.g. "Read and modify Python files in ./src, run pytest suite"', style="bright_yellow")
    scope_authorized = _strip_quotes(click.prompt("> ", prompt_suffix=""))
    _console.print("  What is explicitly NOT allowed?")
    _console.print('  e.g. "No database writes, no deletion outside ./tmp, no git push"', style="bright_yellow")
    scope_prohibited = _strip_quotes(click.prompt("> ", prompt_suffix=""))
    _console.print("  What requires human confirmation before execution?")
    _console.print(
        '  e.g. "Any file deletion, any production deployment, any git push"', style="bright_yellow"
    )
    scope_confirmation = _strip_quotes(click.prompt("> ", prompt_suffix=""))

    _console.print("\nEscalation contact (email, Slack handle, or full name):")
    _console.print('  e.g. "jane@example.com", "@jane-smith (Slack)", "Jane Smith"', style="bright_yellow")
    escalation_contact = _strip_quotes(click.prompt("> ", prompt_suffix=""))

    click.echo("\nEscalation method:")
    click.echo("  [1] Log to agentguard.log only (default)")
    click.echo("  [2] Print to terminal")
    click.echo("  [3] Write to escalation.txt")
    method_choice = click.prompt("  Choose [1-3]", default="1")
    method_map = {"1": "log", "2": "terminal", "3": "file"}
    escalation_method = method_map.get(method_choice, "log")

    _console.print("\nKillswitch (how to stop this agent):")
    _console.print(
        '  e.g. "Ctrl+C", "kill $(pgrep -f agent.py)", "POST /api/agent/stop"', style="bright_yellow"
    )
    killswitch = _strip_quotes(click.prompt("> ", prompt_suffix=""))

    gov_yaml = (
        "# AgentGuard Governance Configuration\n"
        f'owner: "{owner}"\n'
        "scope:\n"
        f'  authorized: "{scope_authorized}"\n'
        f'  prohibited: "{scope_prohibited}"\n'
        f'  requires_confirmation: "{scope_confirmation}"\n'
        "escalation:\n"
        f'  contact: "{escalation_contact}"\n'
        f'  method: "{escalation_method}"\n'
        '  trigger: "2+ critical failures or loop detected"\n'
        f'killswitch: "{killswitch}"\n'
    )

    gov_dest = Path("governance.yaml")
    if gov_dest.exists():
        overwrite = click.confirm("governance.yaml already exists. Overwrite?", default=False)
        if not overwrite:
            click.echo("Skipped governance.yaml.")
        else:
            gov_dest.write_text(gov_yaml)
            click.echo("Created: governance.yaml")
    else:
        gov_dest.write_text(gov_yaml)
        click.echo("Created: governance.yaml")

    _, msg = _update_claude_md(Path("CLAUDE.md"), claude_template.read_text())
    click.echo(msg)

    click.echo(_write_hook_config(Path(".")))

    click.echo("\nSetup complete. Run: agentguard check")


@main.command("enforce")
def enforce_cmd() -> None:
    """PreToolUse hook handler — called by Claude Code automatically.

    Do not call this manually. Configure via agentguard init.
    Reads JSON from stdin, checks against governance.yaml, exits 0 (allow)
    or 2 (block) with JSON denial reason on stdout.
    """
    from agentguard.enforcement.enforcer import run_enforce

    run_enforce()


@main.command()
@click.option("--reason", required=True, help="Mandatory reason for overriding CRITICAL findings.")
@click.option("--path", default=".", show_default=True, help="Project directory.")
def override(reason: str, path: str) -> None:
    """Override CRITICAL findings and proceed. Reason is mandatory and logged."""
    log_path = Path("agentguard-overrides.log")
    timestamp = datetime.now().isoformat()
    entry = json.dumps({"timestamp": timestamp, "reason": reason, "path": path})

    with open(log_path, "a") as f:
        f.write(entry + "\n")

    render_override_confirmation(reason, str(log_path))
