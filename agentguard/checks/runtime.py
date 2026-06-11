"""Layer 2: Runtime loop detection and progress monitoring."""

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Iterator
from pathlib import Path

from agentguard.output.renderer import render_watch_event


def _iter_log_lines(log_path: Path, poll_interval: float) -> Iterator[dict]:
    """Yield new JSON lines from a growing log file."""
    with open(log_path) as f:
        while True:
            line = f.readline()
            if line:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        pass
            else:
                time.sleep(poll_interval)


def watch(
    log_path: str | Path | None = None,
    interval: float = 10.0,
    loop_threshold: int = 6,
    token_burn_threshold: int = 5000,
    output_log: str | Path = "agentguard.log",
) -> None:
    """Watch session log for loop, stall, and burn events.

    Auto-discovers .agentguard/session.log in current directory
    if no log_path provided.
    """
    if log_path is None:
        auto_path = Path.cwd() / ".agentguard" / "session.log"
        if auto_path.exists():
            log_path = auto_path
        else:
            print("Waiting for .agentguard/session.log (start a Claude Code session first)...")
            while not auto_path.exists():
                time.sleep(1.0)
            log_path = auto_path
    log = Path(log_path)
    out = Path(output_log)

    print("  DEC  TIME      TOOL                 INPUT")
    print("  " + "─" * 53)

    tool_calls: list[str] = []
    total_tokens: int = 0
    last_progress_check: int = 0

    def _emit(event_type: str, message: str) -> None:
        render_watch_event(event_type, message)
        with open(out, "a") as f:
            f.write(json.dumps({"event": event_type, "message": message}) + "\n")

    for entry in _iter_log_lines(log, poll_interval=1.0):
        tool = entry.get("tool", "?")
        decision = entry.get("decision", "?")
        summary = entry.get("input_summary", "")[:60]
        ts = entry.get("timestamp", "")
        try:
            timestamp = ts[11:19]  # HH:MM:SS from ISO format
        except (IndexError, TypeError):
            timestamp = ts[:8]
        reason = entry.get("reason", "")

        if decision == "allow":
            symbol = "✓"
            color = "\033[32m"
        else:
            symbol = "✗"
            color = "\033[31m"

        reset = "\033[0m"
        reason_str = f" → {reason}" if reason else ""
        print(
            f"{color}{symbol}{reset} {timestamp}  "
            f"\033[36m{tool:<20}{reset} {summary}{reason_str}"
        )

        tokens = entry.get("tokens", 0)
        if tool:
            tool_calls.append(tool)
            total_tokens += tokens

        window = tool_calls[-10:]
        counts = Counter(window)
        for name, count in counts.items():
            if count >= loop_threshold * 2:
                _emit("LOOP_WARNING", f"Tool '{name}' called {count}x in last 10 calls — possible loop")

        if total_tokens >= token_burn_threshold:
            _emit("BURN_WARNING", f"Token usage reached {total_tokens} (threshold: {token_burn_threshold})")
            total_tokens = 0

        if len(tool_calls) - last_progress_check >= 10:
            last_progress_check = len(tool_calls)
            unique_recent = len(set(tool_calls[-10:]))
            if unique_recent <= 2:
                _emit("STALL_WARNING", f"Low tool diversity in last 10 calls ({unique_recent} unique) — possible stall")


def detect_loop(tool_call_history: list[str], threshold: int = 2) -> bool:
    """Return True if any tool appears >= threshold*2 times in the last 10 calls."""
    window = tool_call_history[-10:]
    counts = Counter(window)
    return any(count >= threshold * 2 for count in counts.values())
