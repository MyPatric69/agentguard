"""
AgentGuard PreToolUse Hook Enforcer.
Called by Claude Code as a PreToolUse hook.
Input: JSON on stdin (Claude Code hook format)
Output: JSON on stdout if denied, nothing if allowed
Exit: 0 = allow, 2 = block
Must be fast — no Rich, no panels, plain JSON only.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentguard.config.loader import load_config

PROHIBITED_PATTERNS = [
    (r"\bno\s+(\w+(?:\s+\w+)?)\b", 1),
    (r"\bnever\s+(\w+(?:\s+\w+)?)\b", 1),
]

_DB_OPS = frozenset({"insert", "update", "delete", "drop", "truncate", "alter"})
_DB_SCOPE_WORDS = ("database", "sql", "db", "table", "schema")
_DELETION_SCOPE_WORDS = ("deletion", "delete", "remov")
_WRITE_SCOPE_WORDS = ("write", "edit", "modif")


def run_enforce() -> None:
    try:
        hook_input: dict[str, Any] = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    tool_name: str = hook_input.get("tool_name", "")
    tool_input: dict = hook_input.get("tool_input", {})
    cwd = Path(hook_input.get("cwd", "."))
    session_id: str = hook_input.get("session_id", "")

    config_path = cwd / "governance.yaml"
    if not config_path.exists():
        sys.exit(0)

    config = load_config(config_path)

    scope = config.get("scope", {})
    if not isinstance(scope, dict):
        sys.exit(0)

    reason = check_prohibited(tool_name, tool_input, scope)
    if reason:
        _log_denial(cwd, tool_name, tool_input, reason, session_id)
        deny(reason)

    reason = check_confirmation(tool_name, tool_input, scope)
    if reason:
        _log_denial(cwd, tool_name, tool_input, reason, session_id)
        deny(reason)

    sys.exit(0)


def _flatten_input(tool_input: dict) -> str:
    return " ".join(str(v) for v in tool_input.values())


def _extract_keywords(text: str) -> list[str]:
    keywords = []
    for pattern, group in PROHIBITED_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            keywords.append(match.group(group).lower().strip())
    return keywords


def check_prohibited(tool_name: str, tool_input: dict, scope: dict) -> str | None:
    prohibited_text = scope.get("prohibited", "").lower()
    if not prohibited_text:
        return None

    tool_str = _flatten_input(tool_input).lower()
    input_summary = tool_str[:100]
    prohibited_full = scope.get("prohibited", "")

    # rm -rf / recursive deletion
    if re.search(r"\brm\s+-\S*[rf]", tool_str):
        if any(kw in prohibited_text for kw in _DELETION_SCOPE_WORDS):
            return (
                f"Action '{tool_name}: {input_summary}' violates prohibited scope:"
                f" {prohibited_full}"
            )

    # git push
    if "git push" in tool_str and "git push" in prohibited_text:
        return (
            f"Action '{tool_name}: {input_summary}' violates prohibited scope:"
            f" {prohibited_full}"
        )

    # SQL / database operations
    words = set(re.findall(r"\b\w+\b", tool_str))
    if words & _DB_OPS and any(kw in prohibited_text for kw in _DB_SCOPE_WORDS):
        return (
            f"Action '{tool_name}: {input_summary}' violates prohibited scope:"
            f" {prohibited_full}"
        )

    # General keyword matching extracted from prohibited text
    for keyword in _extract_keywords(prohibited_text):
        if len(keyword) > 3 and keyword in tool_str:
            return (
                f"Action '{tool_name}: {input_summary}' violates prohibited scope:"
                f" {prohibited_full}"
            )

    return None


def check_confirmation(tool_name: str, tool_input: dict, scope: dict) -> str | None:
    confirmation_text = scope.get("requires_confirmation", "").lower()
    if not confirmation_text:
        return None

    tool_str = _flatten_input(tool_input).lower()
    input_summary = tool_str[:100]

    # rm -rf / deletion commands
    if re.search(r"\brm\s+-\S*[rf]", tool_str) or "rm -f" in tool_str:
        if any(kw in confirmation_text for kw in _DELETION_SCOPE_WORDS):
            return (
                f"Action '{tool_name}: {input_summary}' requires human confirmation"
                " per governance.yaml"
            )

    # git push
    if "git push" in tool_str and "git push" in confirmation_text:
        return (
            f"Action '{tool_name}: {input_summary}' requires human confirmation"
            " per governance.yaml"
        )

    # Write / Edit tools — check for write-related confirmation keywords
    if tool_name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        if any(kw in confirmation_text for kw in _WRITE_SCOPE_WORDS):
            return (
                f"Action '{tool_name}: {input_summary}' requires human confirmation"
                " per governance.yaml"
            )

    # General keyword matching extracted from requires_confirmation
    for keyword in _extract_keywords(confirmation_text):
        if len(keyword) > 3 and keyword in tool_str:
            return (
                f"Action '{tool_name}: {input_summary}' requires human confirmation"
                " per governance.yaml"
            )

    return None


def deny(reason: str) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"AgentGuard: {reason}",
        }
    }
    print(json.dumps(output))
    sys.exit(2)


def _log_denial(
    cwd: Path,
    tool: str,
    tool_input: dict,
    reason: str,
    session_id: str,
) -> None:
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "tool": tool,
        "input_summary": _flatten_input(tool_input)[:100],
        "decision": "deny",
        "reason": reason,
        "session_id": session_id,
    }
    log_path = cwd / "agentguard-enforcement.log"
    try:
        with open(log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass
