"""
AgentGuard Governance Reviewer.
Loads existing governance.yaml, guides field-by-field review,
updates only changed fields, appends to governance_history.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from agentguard import __version__

_console = Console()


def load_governance(path: Path) -> dict:
    """Load governance.yaml. Raises FileNotFoundError if missing."""
    if not path.exists():
        raise FileNotFoundError(f"governance.yaml not found: {path}")
    return yaml.safe_load(path.read_text()) or {}


def _count_rules(items: object) -> int:
    if isinstance(items, list):
        return len(items)
    return 1 if isinstance(items, str) and str(items).strip() else 0


def _count_hard_limits(prohibited: object) -> int:
    if not isinstance(prohibited, list):
        return 0
    return sum(1 for item in prohibited if isinstance(item, dict) and item.get("severity") == "HARD_LIMIT")


def _count_open_ambiguities(governance: dict) -> int:
    ambs = governance.get("scope", {}).get("unresolved_ambiguities", [])
    if not isinstance(ambs, list):
        return 0
    return sum(1 for a in ambs if isinstance(a, dict) and a.get("status") == "open")


def show_governance_summary(governance: dict, project_path: str = ".") -> None:
    """Print Rich summary panel of current governance state."""
    scope = governance.get("scope", {}) or {}
    authorized = scope.get("authorized", [])
    prohibited = scope.get("prohibited", [])
    confirmation = scope.get("requires_confirmation", [])

    n_auth = _count_rules(authorized)
    n_proh = _count_rules(prohibited)
    n_hl = _count_hard_limits(prohibited)
    n_conf = _count_rules(confirmation)
    n_amb = _count_open_ambiguities(governance)

    history = governance.get("governance_history", [])
    last_updated = (
        history[-1].get("date", "unknown")
        if isinstance(history, list) and history
        else "unknown"
    )

    proh_label = f"{n_proh} rules ({n_hl} HARD_LIMIT)" if n_hl else f"{n_proh} rules"
    amb_label = f"{n_amb} open" if n_amb else "none"

    lines = [
        Text(""),
        Text(f"  Project:      {project_path}"),
        Text(f"  Last updated: {last_updated}"),
        Text(f"  Version:      agentguard {__version__}"),
        Text(""),
        Text("  Current governance:"),
        Text(f"  Owner:        {governance.get('owner', '(not set)')}"),
        Text(f"  Authorized:   {n_auth} rules"),
        Text(f"  Prohibited:   {proh_label}"),
        Text(f"  Confirms:     {n_conf} rules"),
        Text(f"  Ambiguities:  {amb_label}"),
        Text(""),
    ]

    _console.print(
        Panel(
            Text("\n").join(lines),
            title="[bold]AGENTGUARD — GOVERNANCE REVIEW[/bold]",
            border_style="white",
            expand=False,
            width=64,
        )
    )


def _run_add_rule(
    items: list, field_name: str, guided: bool, today: str
) -> tuple[list, bool]:
    """Prompt for a new rule, optionally concretize with AI, append to items."""
    click.echo("  Enter new rule (action):")
    action_text = click.prompt("> ", prompt_suffix="").strip().strip("\"'")
    if not action_text:
        return items, False
    click.echo("  Reason (why is this allowed?):")
    reason_text = (
        click.prompt("> ", prompt_suffix="").strip().strip("\"'") or "Added during review"
    )

    new_item: dict[str, Any] = {"action": action_text, "reason": reason_text, "added": today}

    if guided:
        from agentguard.guided.concretizer import _ai_available, concretize_field

        if _ai_available():
            _console.print("\n[dim]Concretizing with AI...[/dim]")
            ai_result = concretize_field(field_name, action_text)
            if not ai_result.get("_fallback"):
                prohibited_items = ai_result.get("prohibited")
                if isinstance(prohibited_items, list) and prohibited_items:
                    # Structured path: prohibited field returns list with severity
                    first = prohibited_items[0]
                    concretized = first.get("action", "")
                    if concretized:
                        _console.print(f"  AI suggests: {concretized}", style="cyan")
                        use_ai = click.prompt("  Use AI-concretized version? [y/n]", default="y")
                        if use_ai.lower().startswith("y"):
                            new_item = {
                                "action": concretized,
                                "reason": first.get("reason", reason_text),
                                "severity": first.get("severity", "HARD_LIMIT"),
                                "added": today,
                            }
                else:
                    # Plain string path: other fields return concretized string
                    concretized = ai_result.get("concretized", "")
                    if concretized:
                        _console.print(f"  AI suggests: {concretized}", style="cyan")
                        use_ai = click.prompt("  Use AI-concretized version? [y/n]", default="y")
                        if use_ai.lower().startswith("y"):
                            new_item["action"] = concretized

    return items + [new_item], True


def review_field(
    field_items: list,
    field_name: str,
    guided: bool = False,
) -> tuple[list, bool]:
    """Interactive review of a single scope field. Returns (updated_items, was_changed)."""
    items = list(field_items) if isinstance(field_items, list) else []

    _console.print(f"\n[bold]{field_name.title()} scope — current rules:[/bold]")
    if items:
        for i, item in enumerate(items, 1):
            action = item.get("action", str(item)) if isinstance(item, dict) else str(item)
            _console.print(f"  {i}. {action}")
    else:
        _console.print("  (none)")

    click.echo("\n  [1] Keep as-is")
    click.echo("  [2] Add new rules")
    click.echo("  [3] Remove a rule (by number)")
    click.echo("  [4] Replace a rule (by number)")
    choice = click.prompt("  Choose [1-4]", default="1")

    today = date.today().isoformat()

    if choice == "1":
        return items, False

    if choice == "2":
        return _run_add_rule(items, field_name, guided, today)

    if choice == "3":
        if not items:
            _console.print("  No rules to remove.", style="yellow")
            return items, False
        idx_str = click.prompt(f"  Remove rule number [1-{len(items)}]")
        try:
            idx = int(idx_str) - 1
            if 0 <= idx < len(items):
                removed = items[idx]
                action = removed.get("action", str(removed)) if isinstance(removed, dict) else str(removed)
                updated = items[:idx] + items[idx + 1:]
                _console.print(f"  Removed: {action}", style="dim")
                return updated, True
        except ValueError:
            pass
        _console.print("  Invalid number — no changes made.", style="yellow")
        return items, False

    if choice == "4":
        if not items:
            _console.print("  No rules to replace.", style="yellow")
            return items, False
        idx_str = click.prompt(f"  Replace rule number [1-{len(items)}]")
        try:
            idx = int(idx_str) - 1
            if 0 <= idx < len(items):
                removed = items[idx]
                action = removed.get("action", str(removed)) if isinstance(removed, dict) else str(removed)
                items = items[:idx] + items[idx + 1:]
                _console.print(f"  Removed: {action}", style="dim")
                return _run_add_rule(items, field_name, guided, today)
        except ValueError:
            pass
        _console.print("  Invalid number — no changes made.", style="yellow")
        return items, False

    return items, False


def mark_ambiguity_resolved(ambiguities: list, index: int) -> list:
    """Mark ambiguity at 0-based index as resolved. Returns updated list."""
    today = date.today().isoformat()
    updated = []
    for i, amb in enumerate(ambiguities):
        if i == index and isinstance(amb, dict) and amb.get("status") == "open":
            updated.append({**amb, "status": "resolved", "resolved": today})
        else:
            updated.append(amb)
    return updated


def _yaml_item_block(items: list, today: str) -> str:
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
        if isinstance(a, dict):
            text = str(a.get("text", "")).replace('"', '\\"')
            added = a.get("added", today)
            status = a.get("status", "open")
            lines.append(f'    - text: "{text}"')
            lines.append(f'      added: "{added}"')
            lines.append(f'      status: "{status}"')
            if "resolved" in a:
                lines.append(f'      resolved: "{a["resolved"]}"')
        else:
            text = str(a).replace('"', '\\"')
            lines.append(f'    - text: "{text}"')
            lines.append(f'      added: "{today}"')
            lines.append('      status: "open"')
    return "\n".join(lines) + "\n"


def _yaml_history_block(history: list) -> str:
    lines: list[str] = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        action = str(entry.get("action", "")).replace('"', '\\"')
        lines.append(f'  - date: "{entry.get("date", "")}"')
        lines.append(f'    action: "{action}"')
        lines.append(f'    tool: "{entry.get("tool", "")}"')
        lines.append(f'    version: "{entry.get("version", "")}"')
        cf = entry.get("changed_fields")
        if isinstance(cf, list):
            cf_str = "[" + ", ".join(f'"{f}"' for f in cf) + "]"
            lines.append(f'    changed_fields: {cf_str}')
    return "\n".join(lines) + "\n"


def save_governance(governance: dict, path: Path, changed_fields: list[str]) -> None:
    """Write governance.yaml with updated governance_history entry."""
    today = date.today().isoformat()
    scope = governance.get("scope", {}) or {}

    def _with_date(raw: object) -> list:
        if not isinstance(raw, list):
            return []
        return [
            {**item, "added": today}
            if isinstance(item, dict) and "added" not in item
            else item
            for item in raw
        ]

    authorized_items = _with_date(scope.get("authorized", []))
    prohibited_items = _with_date(scope.get("prohibited", []))
    confirmation_items = _with_date(scope.get("requires_confirmation", []))

    raw_ambs = governance.get("unresolved_ambiguities", [])
    ambiguities = raw_ambs if isinstance(raw_ambs, list) else []
    amb_section = (
        "  unresolved_ambiguities:\n" + _yaml_ambiguity_block(ambiguities, today)
        if ambiguities
        else ""
    )

    history = list(governance.get("governance_history", []) or [])
    action_desc = f"Updated: {', '.join(changed_fields)}" if changed_fields else "Reviewed via agentguard review"
    history_entry: dict[str, Any] = {
        "date": today,
        "action": action_desc,
        "tool": "agentguard review",
        "version": __version__,
    }
    if changed_fields:
        history_entry["changed_fields"] = changed_fields
    history.append(history_entry)

    escalation = governance.get("escalation", {}) or {}
    if isinstance(escalation, dict):
        contact = escalation.get("contact", "")
        method = escalation.get("method", "log")
        trigger = escalation.get("trigger", "2+ critical failures or loop detected")
    else:
        contact, method, trigger = str(escalation), "log", "2+ critical failures or loop detected"

    gov_yaml = (
        "# Generated by: agentguard\n"
        f"# Date: {today}\n"
        "# Review with: agentguard check --ai-review\n\n"
        f'owner: "{governance.get("owner", "")}"\n\n'
        "scope:\n"
        "  authorized:\n"
        + _yaml_item_block(authorized_items, today)
        + "  prohibited:\n"
        + _yaml_item_block(prohibited_items, today)
        + "  requires_confirmation:\n"
        + _yaml_item_block(confirmation_items, today)
        + amb_section
        + "\nescalation:\n"
        + f'  contact: "{contact}"\n'
        + f'  method: "{method}"\n'
        + f'  trigger: "{trigger}"\n\n'
        + f'killswitch: "{governance.get("killswitch", "")}"\n\n'
        + "governance_history:\n"
        + _yaml_history_block(history)
    )

    path.write_text(gov_yaml)
