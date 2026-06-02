"""Layer 3: Post-session governance report generator."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def generate_report(session_log: str | Path, output_path: str | Path = "report.md") -> str:
    """Read agentguard.log and write a Markdown governance report."""
    log = Path(session_log)
    out = Path(output_path)

    events: list[dict] = []
    if log.exists():
        for line in log.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    counts = Counter(e.get("event", "UNKNOWN") for e in events)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "# AgentGuard — Post-Session Governance Report",
        "",
        f"Generated: {now}",
        f"Session log: `{log}`",
        "",
        "## Event Summary",
        "",
        "| Event Type | Count |",
        "|---|---|",
    ]

    for event_type, count in sorted(counts.items()):
        lines.append(f"| {event_type} | {count} |")

    if not counts:
        lines.append("| (no events recorded) | — |")

    lines += [
        "",
        "## Event Detail",
        "",
    ]

    for event in events:
        event_type = event.get("event", "UNKNOWN")
        message = event.get("message", "")
        lines.append(f"- **{event_type}**: {message}")

    if not events:
        lines.append("No runtime events were recorded in this session.")

    loop_count = counts.get("LOOP_WARNING", 0)
    stall_count = counts.get("STALL_WARNING", 0)
    burn_count = counts.get("BURN_WARNING", 0)

    lines += [
        "",
        "## Governance Assessment",
        "",
    ]

    if loop_count == 0 and stall_count == 0 and burn_count == 0:
        lines.append("**PASS** — No governance events detected. Agent operated within expected parameters.")
    else:
        lines.append("**REVIEW REQUIRED** — The following issues were detected:")
        if loop_count:
            lines.append(f"- {loop_count} loop warning(s)")
        if stall_count:
            lines.append(f"- {stall_count} stall warning(s)")
        if burn_count:
            lines.append(f"- {burn_count} token burn warning(s)")

    report_text = "\n".join(lines) + "\n"
    out.write_text(report_text)
    return report_text
