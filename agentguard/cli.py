"""AgentGuard CLI — check, watch, report, init, override."""

from __future__ import annotations

import json
import sys
import textwrap
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.text import Text

from agentguard import __version__
from agentguard.checks.preflight import _is_invalid_contact, has_criticals, run_preflight
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


GUIDED_STEPS = [
    {
        "step": 1,
        "title": "Owner",
        "question": "Who is responsible for this agent session?",
        "example": 'e.g. "Jane Smith", "DevOps Team Lead"',
        "field": "owner",
        "concretize": False,
    },
    {
        "step": 2,
        "title": "Mission",
        "question": (
            "What is Claude Code authorized to do in this project?\n"
            "Describe the tasks, files, and systems it may work with."
        ),
        "example": 'e.g. "implement features in ./src, run tests, no calls to external APIs"',
        "field": "mission",
        "concretize": True,
        "splits_into": ["scope.authorized", "scope.prohibited", "scope.requires_confirmation"],
    },
    {
        "step": 3,
        "title": "Hard Limits",
        "question": "What should the agent NEVER do, regardless of instructions?",
        "example": 'e.g. "delete production data, push to main without me"',
        "field": "hard_limits",
        "concretize": True,
        "appends_to": "scope.prohibited",
    },
    {
        "step": 4,
        "title": "Escalation",
        "question": "How should AgentGuard reach you when something goes wrong?",
        "example": 'e.g. "email owner@example.com", "log to file"',
        "field": "escalation",
        "concretize": False,
    },
    {
        "step": 5,
        "title": "Killswitch",
        "question": "How is this agent stopped if AgentGuard detects a violation?",
        "example": 'e.g. "AgentGuard stops it automatically", "Ctrl+C"',
        "field": "killswitch",
        "concretize": False,
    },
]


_GUIDED_LINE_WIDTH = 55


def _wrap_guided_line(prefix: str, text: str) -> Text:
    """Wrap a labeled panel line to fit within the guided panel (total width 55)."""
    avail = max(_GUIDED_LINE_WIDTH - len(prefix), 10)
    parts = textwrap.wrap(text or "(empty)", width=avail, break_long_words=True, break_on_hyphens=False)
    indent = " " * len(prefix)
    return Text(prefix + ("\n" + indent).join(parts) if parts else prefix + "(empty)")


def _store_concretized(field: str, step: dict, ai_result: dict, results: dict) -> None:
    if step.get("splits_into"):
        results["scope.authorized"] = ai_result.get("authorized", [])
        results["scope.prohibited"] = ai_result.get("prohibited", [])
        results["scope.requires_confirmation"] = ai_result.get("requires_confirmation", [])
        if ai_result.get("_model"):
            results["_mission_model"] = ai_result["_model"]
        if ai_result.get("_provider"):
            results["_mission_provider"] = ai_result["_provider"]
        if ai_result.get("_pin"):
            results["_mission_pin"] = ai_result["_pin"]
    else:
        # hard_limits returns a structured prohibited list; other fields return concretized string
        prohibited = ai_result.get("prohibited")
        if isinstance(prohibited, list):
            results[field] = prohibited
        else:
            results[field] = ai_result.get("concretized", "")
        if ai_result.get("_pin"):
            results[f"_{field}_pin"] = ai_result["_pin"]


def _items_summary(items: object, max_items: int = 2) -> str:
    """Extract a short display text from a list of structured items or a plain string."""
    if isinstance(items, list):
        texts = [item.get("action", "") for item in items[:max_items] if isinstance(item, dict)]
        result = "; ".join(t for t in texts if t)
        if len(items) > max_items:
            result += f" (+{len(items) - max_items} more)"
        return result
    return str(items or "")


def _field_lines(label: str, items: object) -> list[Text]:
    """Render all items for a field label — no truncation."""
    if isinstance(items, list):
        if not items:
            return [_wrap_guided_line(f"  {label}: ", "(none)")]
        lines = []
        for i, item in enumerate(items):
            action = item.get("action", "") if isinstance(item, dict) else str(item)
            prefix = f"  {label}: " if i == 0 else "    • "
            lines.append(_wrap_guided_line(prefix, action))
        return lines
    return [_wrap_guided_line(f"  {label}: ", str(items or "(none)"))]


def _show_concretized(step: dict, ai_result: dict) -> None:
    from rich.panel import Panel
    from rich.text import Text

    if ai_result.get("_fallback"):
        _console.print("  ⚠️  Could not concretize — saved as-is.", style="yellow")
        return

    confidence = ai_result.get("confidence", "?")
    conf_style = {"HIGH": "green", "MEDIUM": "yellow", "LOW": "red"}.get(confidence, "white")

    if step.get("splits_into"):
        lines = (
            _field_lines("Authorized", ai_result.get("authorized", []))
            + _field_lines("Prohibited", ai_result.get("prohibited", []))
            + _field_lines("Confirmation", ai_result.get("requires_confirmation", []))
        )
    else:
        prohibited = ai_result.get("prohibited")
        if isinstance(prohibited, list):
            lines = _field_lines("Rule", prohibited)
        else:
            lines = [_wrap_guided_line("  Rule: ", ai_result.get("concretized", ""))]

    notes = ai_result.get("enforcement_notes", "")
    if notes:
        enf_line = _wrap_guided_line("  Enforcement:  ", notes)
        enf_line.stylize("dim")
        lines.append(enf_line)

    conf_text = Text()
    conf_text.append(f"  Confidence: {confidence}", style=conf_style)
    lines.append(conf_text)

    ambiguities = ai_result.get("ambiguities") or []
    if ambiguities:
        lines.append(Text("  Ambiguities:", style="yellow"))
        for a in ambiguities:
            amb_line = _wrap_guided_line("    • ", str(a))
            amb_line.stylize("yellow")
            lines.append(amb_line)

    content = Text("\n").join(lines)
    _console.print(Panel(content, title="[bold]Concretized Rule[/bold]", border_style="cyan", expand=False, width=64))


def _show_validation_errors(errors: list) -> None:
    from rich.panel import Panel
    from rich.text import Text

    lines = [Text("")]
    for issue in errors:
        lines.append(Text(f"  \U0001f534 {issue.field}: {issue.message}"))
        lines.append(Text(f"     Fix: {issue.fix}", style="dim"))
    lines.append(Text(""))
    _console.print(
        Panel(
            Text("\n").join(lines),
            title="[bold red]VALIDATION ERRORS — cannot proceed[/bold red]",
            border_style="red",
            expand=False,
            width=64,
        )
    )


def _show_validation_warnings(warnings: list) -> None:
    from rich.panel import Panel
    from rich.text import Text

    lines = [Text("")]
    for issue in warnings:
        lines.append(Text(f"  \U0001f7e1 {issue.field}: {issue.message}"))
        lines.append(Text(f"     Fix: {issue.fix}", style="dim"))
    lines.append(Text(""))
    _console.print(
        Panel(
            Text("\n").join(lines),
            title="[bold yellow]VALIDATION WARNINGS[/bold yellow]",
            border_style="yellow",
            expand=False,
            width=64,
        )
    )


def _show_ambiguity_panel(ambiguities: list) -> str:
    from rich.panel import Panel
    from rich.text import Text

    lines = [
        Text(""),
        Text("  The following points remain unclear:", style="yellow"),
    ]
    for a in ambiguities:
        line = Text(f"  • {a}", style="yellow")
        lines.append(line)
    lines += [
        Text(""),
        Text("  Unresolved ambiguities reduce enforcement precision."),
        Text("  They will be documented in governance.yaml."),
        Text(""),
    ]
    content = Text("\n").join(lines)
    _console.print(
        Panel(
            content,
            title="[bold yellow]⚠️  UNRESOLVED AMBIGUITIES[/bold yellow]",
            border_style="yellow",
            expand=False,
            width=64,
        )
    )
    click.echo("\n  [1] Proceed — document ambiguities in governance.yaml")
    click.echo("  [2] Address ambiguities — refine this field further")
    return click.prompt("  Choose [1-2]", default="1")


def _run_guided_step(step: dict, results: dict) -> None:
    from agentguard.guided.concretizer import concretize_field, concretize_mission

    _console.print(f"\n[bold]Step {step['step']}/5 — {step['title']}[/bold]")
    _console.print(step["question"])
    _console.print(f"  {step['example']}", style="bright_yellow")
    user_input = _strip_quotes(click.prompt("> ", prompt_suffix=""))

    if not step.get("concretize"):
        if step["field"] == "escalation":
            while _is_invalid_contact(user_input):
                _console.print(
                    "  ⚠️  Invalid contact — use an email address, @handle, or full name.",
                    style="bright_yellow",
                )
                if click.confirm("  Use as-is anyway?", default=False):
                    break
                _console.print(f"  {step['example']}", style="bright_yellow")
                user_input = _strip_quotes(click.prompt("> ", prompt_suffix=""))
        results[step["field"]] = user_input
        return

    max_rounds = 3
    current_input = user_input
    ai_result: dict = {}
    accumulated_ambiguities: list[str] = []

    for round_num in range(max_rounds):
        _console.print("\n[dim]Concretizing with AI...[/dim]")

        if step.get("splits_into"):
            ai_result = concretize_mission(current_input)
        else:
            ai_result = concretize_field(step["field"], current_input)

        _validation_errors: list = []
        if step.get("splits_into") and not ai_result.get("_fallback"):
            from agentguard.guided.validator import validate_concretized
            _issues = validate_concretized(ai_result)
            _validation_errors = [i for i in _issues if i.severity == "error"]
            _validation_warnings = [i for i in _issues if i.severity == "warning"]
            if _validation_warnings:
                _show_validation_warnings(_validation_warnings)

        _show_concretized(step, ai_result)

        if ai_result.get("_fallback"):
            _store_concretized(step["field"], step, ai_result, results)
            return

        if _validation_errors:
            _show_validation_errors(_validation_errors)

        for a in (ai_result.get("ambiguities") or []):
            a_str = str(a)
            if a_str and a_str not in accumulated_ambiguities:
                accumulated_ambiguities.append(a_str)

        if _validation_errors:
            click.echo("\n  [2] Adjust — I want to change something")
            click.echo("  [3] Re-enter — start over")
            choice = click.prompt("  Choose [2-3]", default="2")
            if choice not in ("2", "3"):
                choice = "2"
        else:
            click.echo("\n  [1] Yes — use this")
            click.echo("  [2] Adjust — I want to change something")
            click.echo("  [3] Re-enter — start over")
            choice = click.prompt("  Choose [1-3]", default="1")

            if choice == "1":
                confidence = ai_result.get("confidence", "HIGH")
                if confidence in ("MEDIUM", "LOW") and accumulated_ambiguities:
                    amb_choice = _show_ambiguity_panel(accumulated_ambiguities)
                    if amb_choice == "2":
                        _console.print("  What would you like to clarify?", style="bright_yellow")
                        clarification = _strip_quotes(click.prompt("> ", prompt_suffix=""))
                        current_input = f"{current_input}. Clarification: {clarification}"
                        continue
                    results.setdefault("_ambiguities", []).extend(accumulated_ambiguities)
                _store_concretized(step["field"], step, ai_result, results)
                return

        if choice == "3":
            accumulated_ambiguities = []
            _console.print(f"  {step['example']}", style="bright_yellow")
            current_input = _strip_quotes(click.prompt("> ", prompt_suffix=""))
            continue

        # choice == "2" (adjust)
        if round_num < max_rounds - 1:
            _console.print("  What would you like to change?", style="bright_yellow")
            adjustment = _strip_quotes(click.prompt("> ", prompt_suffix=""))
            current_input = f"{current_input}. Adjustment: {adjustment}"
        else:
            _console.print(
                "  ⚠️  Maximum adjustments reached — saved as-is. Run --ai-review to check quality.",
                style="yellow",
            )
            _store_concretized(step["field"], step, ai_result, results)
            return

    _store_concretized(step["field"], step, ai_result, results)


def _show_guided_review(results: dict) -> str:
    from rich.panel import Panel
    from rich.text import Text

    def _short(value: object, n: int = 50) -> str:
        text = _items_summary(value) if isinstance(value, list) else str(value or "(not set)")
        if not text:
            text = "(not set)"
        return text[:n] + "…" if len(text) > n else text

    prohibited_raw = results.get("scope.prohibited", [])
    hard_limits_raw = results.get("hard_limits", [])
    all_prohibited: list = (prohibited_raw if isinstance(prohibited_raw, list) else []) + (
        hard_limits_raw if isinstance(hard_limits_raw, list) else []
    )

    lines = [
        Text(""),
        Text(f"  Owner:      {_short(results.get('owner', '(not set)'))}"),
        Text(f"  Authorized: {_short(results.get('scope.authorized', '(not set)'))}"),
        Text(f"  Prohibited: {_short(all_prohibited or '(not set)')}"),
        Text(f"  Confirms:   {_short(results.get('scope.requires_confirmation', '(not set)'))}"),
        Text(f"  Escalation: {_short(results.get('escalation', '(not set)'))}"),
        Text(f"  Killswitch: {_short(results.get('killswitch', '(not set)'))}"),
        Text(""),
        Text("  [1] Save — generate governance.yaml + hook config"),
        Text("  [2] Adjust — review individual fields"),
        Text("  [3] Start over"),
    ]

    content = Text("\n").join(lines)
    _console.print(
        Panel(
            content,
            title="[bold]GOVERNANCE REVIEW — confirm before saving[/bold]",
            border_style="white",
            expand=False,
            width=64,
        )
    )

    choice = click.prompt("  Choose [1-3]", default="1")

    if choice == "1":
        return "save"
    if choice == "3":
        return "restart"

    # choice == "2": let user pick a field to redo
    _adjustable = [
        ("owner", "Owner", 0),
        ("scope.authorized", "Authorized scope", 1),
        ("scope.prohibited", "Prohibited scope", 2),
        ("scope.requires_confirmation", "Requires confirmation", 1),
        ("escalation", "Escalation", 3),
        ("killswitch", "Killswitch", 4),
    ]
    for i, (_, label, _step_idx) in enumerate(_adjustable, 1):
        click.echo(f"    [{i}] {label}")
    field_choice = click.prompt("  Which field to adjust?", default="1")
    try:
        idx = int(field_choice) - 1
        _key, _label, step_idx = _adjustable[idx]
    except (ValueError, IndexError):
        return "save"

    _run_guided_step(GUIDED_STEPS[step_idx], results)
    return _show_guided_review(results)


def _yaml_item_block(items: list, today: str) -> str:
    """Render a list of structured scope items as YAML block lines."""
    if not items:
        return "    []\n"
    lines: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action", "")).replace('"', '\\"')
        reason = str(item.get("reason", "")).replace('"', '\\"')
        added = item.get("added", today)
        lines.append(f'    - action: "{action}"')
        lines.append(f'      reason: "{reason}"')
        if "severity" in item:
            lines.append(f'      severity: "{item["severity"]}"')
        lines.append(f'      added: "{added}"')
    return "\n".join(lines) + "\n"


def _yaml_ambiguity_block(ambiguities: list, today: str) -> str:
    lines: list[str] = []
    for a in ambiguities:
        text = str(a).replace('"', '\\"')
        lines.append(f'    - text: "{text}"')
        lines.append(f'      added: "{today}"')
        lines.append('      status: "open"')
    return "\n".join(lines) + "\n"


def _yaml_pins_block(pins: list[dict]) -> str:
    lines: list[str] = ["concretization_pins:"]
    for p in pins:
        lines.append(f'  - field: "{p.get("field", "")}"')
        lines.append(f'    input_hash: "{p.get("input_hash", "")}"')
        lines.append(f'    prompt_hash: "{p.get("prompt_hash", "")}"')
        lines.append(f'    output_hash: "{p.get("output_hash", "")}"')
        lines.append(f'    model: "{p.get("model", "")}"')
        lines.append(f'    provider: "{p.get("provider", "")}"')
        lines.append(f'    temperature: {p.get("temperature", 0)}')
        lines.append(f'    date: "{p.get("date", "")}"')
    return "\n".join(lines) + "\n"


def _save_guided(results: dict) -> None:
    from datetime import date

    from agentguard import __version__
    from agentguard.ai_review import _DEFAULT_MODELS, _get_env

    mission_model = results.get("_mission_model")
    mission_provider = results.get("_mission_provider")
    if mission_provider and mission_model:
        concretization_note = f"AI-assisted ({mission_provider}/{mission_model})"
    else:
        provider, _, _, model_override = _get_env()
        model = (model_override or _DEFAULT_MODELS.get(provider or "")) if provider else "unknown"
        concretization_note = f"AI-assisted ({provider}/{model})" if provider else "manual"
    today = date.today().isoformat()

    def _with_date(items: object) -> list:
        if not isinstance(items, list):
            return []
        return [{**item, "added": today} if "added" not in item else item for item in items if isinstance(item, dict)]

    authorized_items = _with_date(results.get("scope.authorized", []))
    prohibited_items = _with_date(results.get("scope.prohibited", []))
    confirmation_items = _with_date(results.get("scope.requires_confirmation", []))

    hard_limits = results.get("hard_limits", [])
    if isinstance(hard_limits, list):
        prohibited_items = prohibited_items + _with_date(hard_limits)
    elif hard_limits:
        prohibited_items.append({
            "action": str(hard_limits),
            "reason": "Hard limit — manually specified",
            "severity": "HARD_LIMIT",
            "added": today,
        })

    accumulated_ambiguities = results.get("_ambiguities", [])
    amb_section = (
        "  unresolved_ambiguities:\n" + _yaml_ambiguity_block(accumulated_ambiguities, today)
        if accumulated_ambiguities
        else ""
    )

    pins: list[dict] = []
    if results.get("_mission_pin"):
        pins.append(results["_mission_pin"])
    for key, val in results.items():
        if key.endswith("_pin") and key != "_mission_pin" and isinstance(val, dict):
            pins.append(val)

    pins_section = "\n" + _yaml_pins_block(pins) if pins else ""

    gov_yaml = (
        "# Generated by: agentguard init --guided\n"
        f"# Date: {today}\n"
        f"# Concretization: {concretization_note}\n"
        "# Review with: agentguard check --ai-review\n\n"
        f'owner: "{results.get("owner", "")}"\n\n'
        "scope:\n"
        "  authorized:\n"
        + _yaml_item_block(authorized_items, today)
        + "  prohibited:\n"
        + _yaml_item_block(prohibited_items, today)
        + "  requires_confirmation:\n"
        + _yaml_item_block(confirmation_items, today)
        + amb_section
        + "\nescalation:\n"
        + f'  contact: "{results.get("escalation", "")}"\n'
        + '  method: "log"\n'
        + '  trigger: "2+ critical failures or loop detected"\n\n'
        + f'killswitch: "{results.get("killswitch", "")}"\n\n'
        + "governance_history:\n"
        + f'  - date: "{today}"\n'
        + '    action: "Initial governance created"\n'
        + '    tool: "agentguard init --guided"\n'
        + f'    version: "{__version__}"\n'
        + pins_section
    )

    Path("governance.yaml").write_text(gov_yaml)
    _console.print("✅ governance.yaml — AI-concretized, ready for enforcement", style="green")
    _console.print(f"✅ {_write_hook_config(Path('.'))}", style="green")

    templates_dir = Path(__file__).parent / "templates"
    _, msg = _update_claude_md(Path("CLAUDE.md"), (templates_dir / "claude_md_block.md").read_text())
    _console.print(f"✅ {msg}", style="green")

    _console.print("\nRun: agentguard check --ai-review to validate quality", style="dim")


def _run_guided_init() -> None:
    from rich.panel import Panel
    from rich.text import Text

    from agentguard.guided.concretizer import _ai_available

    if not _ai_available():
        click.echo(
            "agentguard init --guided requires an AI provider.\n"
            "Set AGENTGUARD_AI_PROVIDER and AGENTGUARD_AI_API_KEY in .env\n"
            "or use: agentguard init --interactive",
            err=True,
        )
        return

    _console.print("[bold]AgentGuard — Guided Governance Setup[/bold]\n")
    _console.print(
        "Answer 5 questions. AgentGuard translates your intent into enforceable rules.\n",
        style="dim",
    )

    inquiry_lines = [
        Text(""),
        Text("  This tool translates your intent into enforceable"),
        Text("  governance rules. It cannot fill knowledge gaps —"),
        Text("  it exposes them."),
        Text(""),
        Text("  For best results, know:"),
        Text("  • What Claude Code is allowed to touch (paths, APIs, systems)"),
        Text("  • What success looks like (measurable outcome)"),
        Text("  • Who is accountable when something goes wrong"),
        Text(""),
        Text("  Ambiguities will be flagged. You decide how to handle"),
        Text("  them — AgentGuard documents your decision."),
        Text(""),
        Text("  Press ENTER to continue."),
        Text(""),
    ]
    _console.print(
        Panel(
            Text("\n").join(inquiry_lines),
            title="[bold]BEFORE YOU START — AgentGuard Guided Setup[/bold]",
            border_style="white",
            expand=False,
            width=64,
        )
    )
    click.prompt("", default="", prompt_suffix="", show_default=False)

    results: dict = {}

    try:
        for step in GUIDED_STEPS:
            _run_guided_step(step, results)

        decision = _show_guided_review(results)

        if decision == "save":
            _save_guided(results)
        elif decision == "restart":
            _run_guided_init()

    except KeyboardInterrupt:
        click.echo("\n")
        if results and click.confirm("Save progress so far?", default=False):
            _save_guided(results)


def _verify_pin_integrity(gov_path: Path) -> list[dict]:
    """Check concretization_pins in governance.yaml for structural completeness."""
    import yaml

    text = gov_path.read_text()
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        return [{"field": "governance.yaml", "status": "error", "detail": "Could not parse YAML"}]

    pins = data.get("concretization_pins")
    if not pins:
        return [{"field": "concretization_pins", "status": "missing", "detail": "No pins found in governance.yaml"}]

    results = []
    required_keys = {"field", "input_hash", "prompt_hash", "output_hash", "model", "provider", "temperature", "date"}
    for pin in pins:
        field = pin.get("field", "<unknown>")
        missing = required_keys - set(pin.keys())
        if missing:
            results.append({"field": field, "status": "incomplete", "detail": f"Missing keys: {sorted(missing)}"})
        elif pin.get("temperature") != 0:
            results.append({"field": field, "status": "drift", "detail": f"temperature={pin['temperature']} (expected 0)"})
        else:
            results.append({"field": field, "status": "ok", "detail": ""})
    return results


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
@click.option(
    "--guided",
    is_flag=True,
    default=False,
    help="AI-powered guided concretization (requires API key in .env).",
)
def init_cmd(interactive: bool, template_only: bool, guided: bool) -> None:
    """Initialize AgentGuard in the current project."""
    if guided:
        _run_guided_init()
        return

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


@main.command("verify")
@click.option("--config", "config_path", default="governance.yaml", show_default=True, help="Path to governance.yaml.")
def verify_cmd(config_path: str) -> None:
    """Verify concretization pin integrity in governance.yaml."""
    from rich.table import Table

    gov_path = Path(config_path)
    if not gov_path.exists():
        click.echo(f"[ERROR] Not found: {config_path}", err=True)
        sys.exit(2)

    pin_results = _verify_pin_integrity(gov_path)

    table = Table(title="Concretization Pin Verification", show_header=True, header_style="bold")
    table.add_column("Field", style="cyan")
    table.add_column("Status", style="bold")
    table.add_column("Detail")

    all_ok = True
    for r in pin_results:
        status = r["status"]
        if status == "ok":
            status_display = "[green]✓ ok[/green]"
        elif status == "missing":
            status_display = "[yellow]⚠ missing[/yellow]"
            all_ok = False
        else:
            status_display = f"[red]✗ {status}[/red]"
            all_ok = False
        table.add_row(r["field"], status_display, r.get("detail", ""))

    _console.print(table)

    if all_ok:
        _console.print("\n✅ All pins verified — governance is reproducible", style="green")
        sys.exit(0)
    else:
        _console.print("\n⚠  Pin issues detected — re-run agentguard init --guided to regenerate", style="yellow")
        sys.exit(1)


def _review_interactive(governance: dict, gov_path: Path, guided: bool) -> None:
    from agentguard.review.reviewer import (
        mark_ambiguity_resolved,
        review_field,
        save_governance,
    )

    click.echo("\n  What would you like to review?")
    click.echo("  [1] Review all fields")
    click.echo("  [2] Review specific field")
    click.echo("  [3] Add new rules to existing fields")
    click.echo("  [4] Mark ambiguities as resolved")
    click.echo("  [5] View full governance.yaml")
    choice = click.prompt("  Choose [1-5]", default="1")

    scope = governance.setdefault("scope", {})
    changed_fields: list[str] = []
    today = __import__("datetime").date.today().isoformat()

    if choice == "1":
        for fname in ("authorized", "prohibited", "requires_confirmation"):
            items = scope.get(fname, []) or []
            updated, changed = review_field(items, fname, guided=guided)
            if changed:
                scope[fname] = updated
                changed_fields.append(f"scope.{fname}")

    elif choice == "2":
        click.echo("  [1] Authorized scope")
        click.echo("  [2] Prohibited scope")
        click.echo("  [3] Requires confirmation")
        field_choice = click.prompt("  Choose [1-3]", default="1")
        fname = {"1": "authorized", "2": "prohibited", "3": "requires_confirmation"}.get(field_choice, "authorized")
        items = scope.get(fname, []) or []
        updated, changed = review_field(items, fname, guided=guided)
        if changed:
            scope[fname] = updated
            changed_fields.append(f"scope.{fname}")

    elif choice == "3":
        click.echo("  [1] Authorized scope")
        click.echo("  [2] Prohibited scope")
        click.echo("  [3] Requires confirmation")
        field_choice = click.prompt("  Choose [1-3]", default="1")
        fname = {"1": "authorized", "2": "prohibited", "3": "requires_confirmation"}.get(field_choice, "authorized")
        items = list(scope.get(fname, []) or [])
        click.echo(f"  Enter new rule for {fname}:")
        action_text = _strip_quotes(click.prompt("> ", prompt_suffix=""))
        reason_text = _strip_quotes(click.prompt("  Reason: ", prompt_suffix="")) or "Added during review"
        new_item = {"action": action_text, "reason": reason_text, "added": today}
        scope[fname] = items + [new_item]
        changed_fields.append(f"scope.{fname}")

    elif choice == "4":
        ambiguities = governance.get("unresolved_ambiguities", [])
        if not isinstance(ambiguities, list) or not ambiguities:
            _console.print("  No ambiguities recorded.", style="dim")
        else:
            click.echo("\n  Open ambiguities:")
            open_indices = [
                i for i, a in enumerate(ambiguities)
                if isinstance(a, dict) and a.get("status") == "open"
            ]
            for i in open_indices:
                click.echo(f"    {i + 1}. {ambiguities[i].get('text', '')} [open]")
            if not open_indices:
                _console.print("  All ambiguities are already resolved.", style="dim")
            else:
                idx_str = click.prompt("  Mark as resolved (enter number, or 'all')")
                if idx_str.strip().lower() == "all":
                    for i in open_indices:
                        ambiguities = mark_ambiguity_resolved(ambiguities, i)
                    governance["unresolved_ambiguities"] = ambiguities
                    changed_fields.append("unresolved_ambiguities")
                else:
                    try:
                        idx = int(idx_str) - 1
                        if 0 <= idx < len(ambiguities):
                            governance["unresolved_ambiguities"] = mark_ambiguity_resolved(ambiguities, idx)
                            changed_fields.append("unresolved_ambiguities")
                    except ValueError:
                        _console.print("  Invalid input — no changes made.", style="yellow")

    elif choice == "5":
        from rich.syntax import Syntax
        content = gov_path.read_text() if gov_path.exists() else "# governance.yaml not found"
        _console.print(Syntax(content, "yaml", theme="monokai", line_numbers=True, word_wrap=True))
        return

    if changed_fields:
        save_governance(governance, gov_path, changed_fields)
        _console.print(f"✅ governance.yaml updated — {', '.join(changed_fields)}", style="green")
    else:
        _console.print("No changes made.", style="dim")


@main.command("review")
@click.option("--path", default=".", show_default=True, help="Project directory.")
@click.option(
    "--guided",
    is_flag=True,
    default=False,
    help="AI-assisted rule concretization (requires API key in .env).",
)
@click.option(
    "--field",
    "field_filter",
    default=None,
    help="Review a specific field only (authorized/prohibited/requires_confirmation).",
)
def review_cmd(path: str, guided: bool, field_filter: str | None) -> None:
    """Review and update existing governance.yaml."""
    from agentguard.review.reviewer import (
        load_governance,
        review_field,
        save_governance,
        show_governance_summary,
    )

    gov_path = Path(path) / "governance.yaml"
    try:
        governance = load_governance(gov_path)
    except FileNotFoundError as exc:
        click.echo(f"[ERROR] {exc}", err=True)
        sys.exit(2)

    show_governance_summary(governance, project_path=path)

    if field_filter:
        valid_fields = ("authorized", "prohibited", "requires_confirmation")
        if field_filter not in valid_fields:
            click.echo(
                f"[ERROR] Unknown field: {field_filter}. Use: {', '.join(valid_fields)}",
                err=True,
            )
            sys.exit(2)
        scope = governance.setdefault("scope", {})
        items = scope.get(field_filter, []) or []
        updated_items, changed = review_field(items, field_filter, guided=guided)
        if changed:
            scope[field_filter] = updated_items
            save_governance(governance, gov_path, [f"scope.{field_filter}"])
            _console.print(f"✅ governance.yaml updated — {field_filter} revised", style="green")
        else:
            _console.print("No changes made.", style="dim")
        return

    _review_interactive(governance, gov_path, guided)


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
