"""Rich-based console output: panels, tables, severity indicators."""

from __future__ import annotations

import textwrap
from datetime import datetime
from typing import Any, NamedTuple

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

SEVERITY_ICON = {
    "critical": "🔴 CRITICAL",
    "warning": "🟡 WARNING ",
    "info": "🔵 INFO    ",
    "ok": "🟢 OK      ",
}

SEVERITY_STYLE = {
    "critical": "bold red",
    "warning": "yellow",
    "info": "cyan",
    "ok": "green",
}

# Panel content width = panel width(56) - 2 borders - 2 padding = 52.
# Prefix display width = 2 leading spaces + emoji(2) + icon text(9) + 3 trailing = 16.
# Available message width = 52 - 16 = 36.
_MSG_WRAP = 36
_MSG_INDENT = " " * 16


def _wrap_message(text: str) -> str:
    """Wrap message to fit panel; indent continuation lines to align with text start."""
    lines = textwrap.wrap(text, width=_MSG_WRAP, break_long_words=True, break_on_hyphens=False)
    return ("\n" + _MSG_INDENT).join(lines) if lines else text


class Finding(NamedTuple):
    severity: str   # critical | warning | info | ok
    message: str


def render_preflight(project_path: str, findings: list[Finding]) -> None:
    """Print the pre-flight check panel to the console."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    criticals = [f for f in findings if f.severity == "critical"]
    warnings = [f for f in findings if f.severity == "warning"]

    lines: list[Text] = []

    for finding in findings:
        icon = SEVERITY_ICON.get(finding.severity, "   ")
        style = SEVERITY_STYLE.get(finding.severity, "white")
        line = Text()
        line.append(f"  {icon}   ", style=style)
        line.append(_wrap_message(finding.message))
        lines.append(line)

    lines.append(Text(""))

    if criticals:
        result_line = Text()
        result_line.append(
            f"  RESULT: BLOCKED — {len(criticals)} critical gap{'s' if len(criticals) != 1 else ''}",
            style="bold red",
        )
        lines.append(result_line)
        lines.append(Text(""))
        lines.append(Text("  This agent cannot start until governance", style="red"))
        lines.append(Text("  gaps are resolved or explicitly overridden.", style="red"))
        lines.append(Text(""))
        lines.append(Text("  agentguard init --interactive", style="bold"))
        lines.append(Text("  agentguard override --reason \"...\"", style="bold"))
    elif warnings:
        result_line = Text()
        result_line.append(
            f"  RESULT: WARNINGS — {len(warnings)} item{'s' if len(warnings) != 1 else ''} to review",
            style="bold yellow",
        )
        lines.append(result_line)
    else:
        lines.append(Text("  RESULT: ALL CLEAR — agent may proceed", style="bold green"))

    content = Text("\n").join(lines)

    header = (
        f"  Project:  {project_path}\n"
        f"  Checked:  {now}\n"
    )

    full = Text(header) + Text("\n") + content

    panel = Panel(
        full,
        title="[bold]AGENTGUARD — PRE-FLIGHT CHECK[/bold]",
        border_style="white",
        expand=False,
        width=56,
    )
    console.print(panel)


def render_json(findings: list[Finding]) -> str:
    """Return findings as a JSON string."""
    import json
    return json.dumps(
        [{"severity": f.severity, "message": f.message} for f in findings],
        indent=2,
    )


def render_watch_event(event_type: str, message: str) -> None:
    """Print a runtime watch event."""
    style_map = {
        "LOOP_WARNING": "bold red",
        "STALL_WARNING": "bold yellow",
        "BURN_WARNING": "bold magenta",
        "INFO": "cyan",
    }
    style = style_map.get(event_type, "white")
    console.print(f"[{style}][{event_type}][/{style}] {message}")


_VERDICT_ICON = {
    "STRONG": "🟢",
    "ACCEPTABLE": "🟡",
    "WEAK": "🟠",
    "INSUFFICIENT": "🔴",
}

_VERDICT_STYLE = {
    "STRONG": "bold green",
    "ACCEPTABLE": "bold yellow",
    "WEAK": "bold dark_orange",
    "INSUFFICIENT": "bold red",
}


def _short_model(model: str) -> str:
    if model.startswith("claude-"):
        parts = model.split("-")
        return f"{parts[0]}-{parts[1]}"
    return model


def render_ai_review(result: dict[str, Any]) -> None:
    """Print AI scope review panel to the console."""
    provider = result.get("_provider", "unknown")
    model = result.get("_model", "unknown")
    score = result.get("score", 0)
    verdict = result.get("verdict", "UNKNOWN")
    issues = result.get("issues", [])
    suggestion = result.get("suggestion", "")

    model_short = _short_model(model)
    icon = _VERDICT_ICON.get(verdict, "⚪")
    vstyle = _VERDICT_STYLE.get(verdict, "white")

    lines: list[Text] = [
        Text(f"   Provider:  {provider} ({model_short})"),
        Text(f"   Score:     {score}/10"),
    ]
    verdict_line = Text("   Verdict:   ")
    verdict_line.append(f"{icon} {verdict}", style=vstyle)
    lines.append(verdict_line)

    if issues:
        lines.append(Text(""))
        lines.append(Text("   Issues:"))
        for issue in issues:
            wrapped = textwrap.wrap(issue, width=40, break_long_words=True)
            for i, part in enumerate(wrapped):
                prefix = "   • " if i == 0 else "     "
                lines.append(Text(f"{prefix}{part}"))

    if suggestion:
        lines.append(Text(""))
        wrapped = textwrap.wrap(f"Suggestion: {suggestion}", width=43, break_long_words=True)
        for i, part in enumerate(wrapped):
            prefix = "   " if i == 0 else "   "
            lines.append(Text(f"{prefix}{part}"))

    content = Text("\n").join(lines)

    panel = Panel(
        content,
        title="[bold]AI SCOPE REVIEW[/bold]",
        border_style="white",
        expand=False,
        width=56,
    )
    console.print(panel)


def render_override_confirmation(reason: str, log_path: str) -> None:
    """Print override confirmation panel."""
    panel = Panel(
        f"  [bold yellow]OVERRIDE ACCEPTED[/bold yellow]\n\n"
        f"  Reason: {reason}\n"
        f"  Logged: {log_path}\n\n"
        f"  [red]Proceeding despite critical governance gaps.[/red]",
        title="[bold]AGENTGUARD — OVERRIDE[/bold]",
        border_style="yellow",
        expand=False,
        width=56,
    )
    console.print(panel)
