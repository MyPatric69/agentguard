"""AgentGuard CLI — check, watch, report, init, override."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import click

from agentguard import __version__
from agentguard.checks.preflight import has_criticals, run_preflight
from agentguard.checks.report import generate_report
from agentguard.checks.runtime import watch as runtime_watch
from agentguard.config.loader import find_config
from agentguard.output.renderer import (
    render_json,
    render_override_confirmation,
    render_preflight,
)


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
def check(path: str, config_path: str | None, fmt: str) -> None:
    """Run pre-flight governance check."""
    resolved_config = config_path or find_config(path)

    try:
        findings = run_preflight(path, config_path=resolved_config)
    except Exception as exc:
        click.echo(f"[ERROR] Config error: {exc}", err=True)
        sys.exit(2)

    if fmt == "json":
        click.echo(render_json(findings))
    else:
        render_preflight(path, findings)

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
    owner = click.prompt("Agent owner (name or role)")
    scope = click.prompt("Agent scope (what is this agent authorized to do)")
    escalation = click.prompt("Escalation contact (email, Slack handle, or name)")
    killswitch = click.prompt("Killswitch (e.g. 'Ctrl+C', 'kill PID', or endpoint URL)")

    gov_yaml = f"""# AgentGuard Governance Configuration
owner: "{owner}"
scope: "{scope}"
escalation:
  contact: "{escalation}"
  trigger: "2+ critical failures or loop detected"
killswitch: "{killswitch}"
"""

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

    claude_dest = Path("CLAUDE.md")
    if not claude_dest.exists():
        claude_dest.write_text(claude_template.read_text())
        click.echo("Created: CLAUDE.md")
    else:
        block_text = claude_template.read_text()
        existing = claude_dest.read_text()
        if "AgentGuard" not in existing:
            claude_dest.write_text(existing + "\n\n" + block_text)
            click.echo("Appended AgentGuard block to: CLAUDE.md")
        else:
            click.echo("[SKIP] AgentGuard block already in CLAUDE.md.")

    click.echo("\nSetup complete. Run: agentguard check")


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
