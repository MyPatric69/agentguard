"""Layer 4: Post-session governance report generator."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def generate_report_data(project_path: str | Path) -> dict:
    """
    Read .agentguard/session.log, agentguard.log, and .agentguard/proposals/,
    return structured report data as dict.
    """
    path = Path(project_path)
    session_log = path / ".agentguard" / "session.log"
    watch_log = path / "agentguard.log"

    session_entries: list[dict] = []
    if session_log.exists():
        for line in session_log.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    session_entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    watch_events: list[dict] = []
    if watch_log.exists():
        for line in watch_log.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    watch_events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    decision_entries = [e for e in session_entries if "decision" in e]
    total = len(decision_entries)
    allowed = sum(1 for e in decision_entries if e.get("decision") == "allow")
    denied = sum(1 for e in decision_entries if e.get("decision") == "deny")
    asked = sum(1 for e in decision_entries if e.get("decision") == "ask")
    tool_counts = Counter(e.get("tool", "?") for e in decision_entries)
    denied_entries = [e for e in decision_entries if e.get("decision") == "deny"]
    asked_entries = [e for e in decision_entries if e.get("decision") == "ask"]
    watch_counts = Counter(e.get("event", "?") for e in watch_events)

    cost_entries = [e for e in session_entries if e.get("event") == "session_cost"]
    session_cost = cost_entries[-1] if cost_entries else None

    session_ids = [e.get("session_id") for e in decision_entries if e.get("session_id")]
    session_id = Counter(session_ids).most_common(1)[0][0] if session_ids else None

    duration = None
    if len(decision_entries) >= 2:
        try:
            t1 = datetime.fromisoformat(decision_entries[0]["timestamp"])
            t2 = datetime.fromisoformat(decision_entries[-1]["timestamp"])
            diff = t2 - t1
            minutes = int(diff.total_seconds() // 60)
            seconds = int(diff.total_seconds() % 60)
            duration = f"{minutes}m {seconds}s"
        except Exception:
            pass

    proposals_dir = path / ".agentguard" / "proposals"
    proposal_entries: list[dict] = []
    if proposals_dir.exists():
        for p in sorted(proposals_dir.glob("*.json")):
            try:
                proposal_entries.append(json.loads(p.read_text()))
            except (json.JSONDecodeError, OSError):
                pass
    proposals = {
        "total": len(proposal_entries),
        "pending": sum(1 for e in proposal_entries if e.get("status") == "pending"),
        "pr_created": sum(1 for e in proposal_entries if e.get("status") == "pr_created"),
        "entries": proposal_entries,
    }

    return {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "project": str(path.resolve()),
        "total": total,
        "allowed": allowed,
        "denied": denied,
        "asked": asked,
        "duration": duration,
        "tool_counts": dict(tool_counts.most_common()),
        "denied_entries": denied_entries,
        "asked_entries": asked_entries,
        "watch_events": watch_events,
        "watch_counts": dict(watch_counts),
        "session_cost": session_cost,
        "session_id": session_id,
        "proposals": proposals,
        "has_data": total > 0 or len(watch_events) > 0 or session_cost is not None,
    }


def generate_report(project_path: str | Path, output_path: str | Path = "report.md") -> str:
    """Generate a Markdown governance report from project session data."""
    data = generate_report_data(project_path)
    out = Path(output_path)

    total = data["total"]
    allowed = data["allowed"]
    denied = data["denied"]
    asked = data["asked"]
    duration = data["duration"] or "N/A"
    proposals = data["proposals"]

    def pct(n: int) -> str:
        return f"{round(n / total * 100)}%" if total > 0 else "0%"

    cost = data["session_cost"]
    if cost:
        cost_str = f"${cost['total_usd']:.4f} ({cost.get('model', '?')})"
        pricing_str = cost.get("pricing_source", "?")
    else:
        cost_str = "N/A"
        pricing_str = "N/A"

    lines = [
        "# AgentGuard — Post-Session Governance Report",
        "",
        f"Generated: {data['generated']}",
        f"Project: {data['project']}",
        "",
        "## ROI Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Session Duration | {duration} |",
        f"| Session Cost | {cost_str} |",
        f"| Pricing Source | {pricing_str} |",
        f"| Total Tool Calls | {total} |",
        f"| → Allowed | {allowed} ({pct(allowed)}) |",
        f"| → Ask (confirmed/unresolved) | {asked} ({pct(asked)}) |",
        f"| → Denied | {denied} ({pct(denied)}) |",
        f"| Unresolved Proposals | {proposals['pending']} |",
        f"| PRs Created | {proposals['pr_created']} |",
        "",
        "## Tool Distribution",
        "",
        "| Tool | Calls |",
        "|---|---|",
    ]

    for tool, count in data["tool_counts"].items():
        lines.append(f"| {tool} | {count} |")
    if not data["tool_counts"]:
        lines.append("| (no tool calls) | — |")

    lines += ["", "## Blocked Actions (deny)", ""]
    if denied_entries := data["denied_entries"]:
        for e in denied_entries:
            ts = e.get("timestamp", "")[:19]
            lines.append(f"- {ts} {e.get('tool', '?')}: {e.get('reason', '')}")
    else:
        lines.append("No actions were blocked.")

    lines += ["", "## Unresolved Proposals", ""]
    if proposal_entries := proposals["entries"]:
        for p in proposal_entries:
            ts = p.get("timestamp", "")[:19]
            status = p.get("status", "unknown")
            lines.append(
                f"- {ts} {p.get('tool_name', '?')} on `{p.get('file_path', '?')}`: "
                f"{p.get('governance_reason', '')} — **{status}**"
            )
    else:
        lines.append("No proposals recorded.")

    lines += ["", "## Runtime Events (agentguard watch)", ""]
    if data["watch_counts"]:
        lines += ["| Event | Count |", "|---|---|"]
        for event_type, count in data["watch_counts"].items():
            lines.append(f"| {event_type} | {count} |")
    else:
        lines.append("No runtime events recorded.")

    loop_count = data["watch_counts"].get("LOOP_WARNING", 0)
    stall_count = data["watch_counts"].get("STALL_WARNING", 0)
    burn_count = data["watch_counts"].get("BURN_WARNING", 0)

    lines += ["", "## Governance Assessment", ""]

    issues = []
    if denied:
        issues.append(f"{denied} action(s) blocked")
    if proposals["pending"]:
        issues.append(f"{proposals['pending']} unresolved proposal(s)")
    if loop_count:
        issues.append(f"{loop_count} loop warning(s)")
    if stall_count:
        issues.append(f"{stall_count} stall warning(s)")
    if burn_count:
        issues.append(f"{burn_count} token burn warning(s)")

    if not issues:
        lines.append("**PASS** — No governance violations or runtime anomalies detected.")
    else:
        lines.append("**REVIEW REQUIRED** — The following issues were detected:")
        for issue in issues:
            lines.append(f"- {issue}")

    report_text = "\n".join(lines) + "\n"
    out.write_text(report_text)
    return report_text
