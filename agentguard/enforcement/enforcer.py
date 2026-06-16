"""
AgentGuard Hook Enforcer.
Called by Claude Code as a PreToolUse and PostToolUse hook.
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

import pathspec

from agentguard.config.loader import PathPolicy, load_config, load_path_policy
from agentguard.enforcement.transcript import get_tool_call

PROHIBITED_PATTERNS = [
    (r"\bno\s+(\w+(?:\s+\w+)?)\b", 1),
    (r"\bnever\s+(\w+(?:\s+\w+)?)\b", 1),
]

_DB_OPS = frozenset({"insert", "update", "delete", "drop", "truncate", "alter"})
_DB_SCOPE_WORDS = ("database", "sql", "db", "table", "schema")
_DELETION_SCOPE_WORDS = ("deletion", "delete", "remov")
_WRITE_SCOPE_WORDS = ("write", "edit", "modif")
_FILE_TOOL_NAMES = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})


def run_enforce() -> None:
    try:
        hook_input: dict[str, Any] = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    try:
        with open("/tmp/agentguard_hook_debug.jsonl", "a") as _dbg:
            _dbg.write(json.dumps(hook_input) + "\n")
    except OSError:
        pass

    hook_event_name: str = hook_input.get("hook_event_name", "PreToolUse")

    if hook_event_name == "PostToolUse":
        log_post_tool_use(hook_input)
        sys.exit(0)
    elif hook_event_name == "Stop":
        handle_stop(hook_input, hook_input.get("cwd", "."))
        sys.exit(0)
    elif hook_event_name != "PreToolUse":
        sys.exit(0)

    tool_name: str = hook_input.get("tool_name", "")
    tool_input: dict = hook_input.get("tool_input", {})
    cwd = Path(hook_input.get("cwd", "."))
    session_id: str = hook_input.get("session_id", "")
    tool_use_id: str = hook_input.get("tool_use_id", "")

    config_path = cwd / "governance.yaml"
    if not config_path.exists():
        sys.exit(0)

    config = load_config(config_path)

    scope = config.get("scope", {})
    if not isinstance(scope, dict):
        sys.exit(0)

    # Path-policy check: evaluated first for file-targeting tools
    if tool_name in _FILE_TOOL_NAMES:
        rel_path = _to_rel_path(_extract_file_path(tool_name, tool_input), cwd)
        pp_result = _match_path_policy(tool_name, rel_path, load_path_policy(config))
        if pp_result is not None:
            pp_decision, pp_reason = pp_result
            if pp_decision == "deny":
                _log_denial(cwd, tool_name, tool_input, pp_reason, session_id)
                _log_tool_call(cwd, tool_name, tool_input, "deny", pp_reason, session_id, tool_use_id)
                deny(pp_reason)
            elif pp_decision == "ask":
                _log_tool_call(cwd, tool_name, tool_input, "ask", pp_reason, session_id, tool_use_id)
                ask(pp_reason)
            # "allow": fall through to content-based prohibited/confirmation checks

    reason = check_prohibited(tool_name, tool_input, scope)
    if reason:
        _log_denial(cwd, tool_name, tool_input, reason, session_id)
        _log_tool_call(cwd, tool_name, tool_input, "deny", reason, session_id, tool_use_id)
        deny(reason)

    reason = check_confirmation(tool_name, tool_input, scope)
    if reason:
        _log_tool_call(cwd, tool_name, tool_input, "ask", reason, session_id, tool_use_id)
        ask(reason)

    _log_tool_call(cwd, tool_name, tool_input, "allow", None, session_id, tool_use_id)
    sys.exit(0)


def _write_session_log(cwd: Path, entry: dict) -> None:
    log_dir = cwd / ".agentguard"
    try:
        log_dir.mkdir(exist_ok=True)
        with open(log_dir / "session.log", "a") as f:
            f.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def log_post_tool_use(data: dict) -> None:
    cwd = Path(data.get("cwd", "."))
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": "post_tool_use",
        "tool": data.get("tool_name", ""),
        "tool_use_id": data.get("tool_use_id", ""),
        "session_id": data.get("session_id", ""),
        "duration_ms": data.get("duration_ms"),
    }
    _write_session_log(cwd, entry)


def handle_stop(data: dict, cwd_str: str) -> None:
    session_id = data.get("session_id", "")
    transcript_path = data.get("transcript_path", "")
    cwd = Path(cwd_str)
    session_log_path = cwd / ".agentguard" / "session.log"

    if not session_log_path.exists():
        return

    ask_entries: list[dict] = []
    executed_ids: set[str] = set()

    try:
        with open(session_log_path) as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    entry = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if entry.get("session_id") != session_id:
                    continue
                if entry.get("event") == "post_tool_use":
                    tid = entry.get("tool_use_id", "")
                    if tid:
                        executed_ids.add(tid)
                elif entry.get("decision") == "ask":
                    ask_entries.append(entry)
    except OSError:
        return

    proposals_dir = cwd / ".agentguard" / "proposals"

    for ask in ask_entries:
        tool_use_id = ask.get("tool_use_id", "")
        if not tool_use_id or tool_use_id in executed_ids:
            continue

        proposal_path = proposals_dir / f"{tool_use_id}.json"

        if proposal_path.exists():
            try:
                existing = json.loads(proposal_path.read_text())
                if existing.get("status") != "pending":
                    continue
            except (json.JSONDecodeError, OSError):
                pass

        tool_call = get_tool_call(transcript_path, tool_use_id) if transcript_path else None
        tool_input = tool_call["tool_input"] if tool_call else None
        tool_name = tool_call["tool_name"] if tool_call else ask.get("tool", "")
        file_path: str | None = None
        if tool_input:
            file_path = tool_input.get("file_path") or tool_input.get("notebook_path")

        proposal = {
            "tool_use_id": tool_use_id,
            "session_id": session_id,
            "timestamp": ask.get("timestamp", ""),
            "tool_name": tool_name,
            "file_path": file_path,
            "tool_input": tool_input,
            "governance_reason": ask.get("reason", ""),
            "status": "pending",
        }

        try:
            proposals_dir.mkdir(parents=True, exist_ok=True)
            proposal_path.write_text(json.dumps(proposal, indent=2))
        except OSError:
            pass


def _log_tool_call(
    cwd: Path,
    tool: str,
    tool_input: dict,
    decision: str,
    reason: str | None,
    session_id: str,
    tool_use_id: str = "",
) -> None:
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "tool": tool,
        "tool_use_id": tool_use_id,
        "input_summary": _flatten_input(tool_input)[:100],
        "decision": decision,
        "reason": reason,
        "session_id": session_id,
    }
    _write_session_log(cwd, entry)


def _flatten_input(tool_input: dict) -> str:
    return " ".join(str(v) for v in tool_input.values())


def _extract_file_path(tool_name: str, tool_input: dict) -> str:
    if tool_name == "NotebookEdit":
        return str(tool_input.get("notebook_path", "") or "")
    return str(tool_input.get("file_path", "") or tool_input.get("path", "") or "")


def _to_rel_path(file_path_raw: str, cwd: Path) -> str | None:
    if not file_path_raw:
        return None
    p = Path(file_path_raw)
    if p.is_absolute():
        try:
            return str(p.relative_to(cwd))
        except ValueError:
            return None  # outside project root — no path_policy rule applies
    return file_path_raw


def _match_path_policy(
    tool_name: str,
    file_path: str | None,
    path_policy: PathPolicy,
) -> tuple[str, str] | None:
    """Return (decision, reason) for file-targeting tools, or None if not applicable."""
    if tool_name not in _FILE_TOOL_NAMES:
        return None
    if not file_path:
        return None
    for decision, entries in (
        ("deny", path_policy.denied_paths),
        ("ask", path_policy.protected_paths),
        ("allow", path_policy.authorized_paths),
    ):
        spec = pathspec.PathSpec.from_lines("gitignore", [e.pattern for e in entries])
        if spec.match_file(file_path):
            for entry in entries:
                single = pathspec.PathSpec.from_lines("gitignore", [entry.pattern])
                if single.match_file(file_path):
                    return (decision, entry.reason)
    return (
        path_policy.default_for_unmatched,
        "No path_policy rule matched; default_for_unmatched applies",
    )


def _extract_keywords(text: str) -> list[str]:
    keywords = []
    for pattern, group in PROHIBITED_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            keywords.append(match.group(group).lower().strip())
    return keywords


def _match_prohibited_text(tool_name: str, tool_str: str, prohibited_text: str) -> bool:
    """Return True if tool_str matches the given prohibited text string."""
    if re.search(r"\brm\s+-\S*[rf]", tool_str):
        if any(kw in prohibited_text for kw in _DELETION_SCOPE_WORDS):
            return True
    if "git push" in tool_str and "git push" in prohibited_text:
        return True
    words = set(re.findall(r"\b\w+\b", tool_str))
    if words & _DB_OPS and any(kw in prohibited_text for kw in _DB_SCOPE_WORDS):
        return True
    for keyword in _extract_keywords(prohibited_text):
        if len(keyword) > 3 and keyword in tool_str:
            return True
    return False


def _is_tag_push(tool_str: str) -> bool:
    """Return True only for tag-related push operations, not all git push commands."""
    if re.search(r"\bgit\s+push\b.*--tags", tool_str):
        return True
    if re.search(r"\bgit\s+push\b.*\brefs/tags/", tool_str):
        return True
    if re.search(r"\bgit\s+push\b.*\bv\d+\.\d+", tool_str):
        return True
    if re.search(r"\bgit\s+tag\b", tool_str):
        return True
    return False


def _match_confirmation_text(
    tool_name: str, tool_str: str, confirmation_text: str, file_path: str = ""
) -> bool:
    """Return True if tool_str matches the given confirmation text string."""
    if tool_name == "Bash" and re.search(r"\brm\s+-\S*[rf]", tool_str):
        if any(kw in confirmation_text for kw in _DELETION_SCOPE_WORDS):
            return True
    # only tag-related push operations, not all git push commands
    if _is_tag_push(tool_str) and "git push" in confirmation_text:
        return True
    for keyword in _extract_keywords(confirmation_text):
        if len(keyword) > 3 and keyword in tool_str:
            return True
    return False


def check_prohibited(tool_name: str, tool_input: dict, scope: dict) -> str | None:
    prohibited = scope.get("prohibited", "")
    tool_str = _flatten_input(tool_input).lower()
    input_summary = tool_str[:100]

    if isinstance(prohibited, list):
        for item in prohibited:
            if not isinstance(item, dict):
                continue
            action = item.get("action", "")
            severity = item.get("severity", "")
            if _match_prohibited_text(tool_name, tool_str, action.lower()):
                prefix = "HARD_LIMIT: " if severity == "HARD_LIMIT" else ""
                return (
                    f"{prefix}Action '{tool_name}: {input_summary}' violates prohibited scope:"
                    f" {action}"
                )
        return None

    # Legacy string path
    prohibited_text = str(prohibited or "").lower()
    if not prohibited_text:
        return None
    prohibited_full = str(prohibited or "")

    if _match_prohibited_text(tool_name, tool_str, prohibited_text):
        return (
            f"Action '{tool_name}: {input_summary}' violates prohibited scope:"
            f" {prohibited_full}"
        )
    return None


def check_confirmation(tool_name: str, tool_input: dict, scope: dict) -> str | None:
    confirmation = scope.get("requires_confirmation", "")
    tool_str = _flatten_input(tool_input).lower()
    input_summary = tool_str[:100]
    file_path = _extract_file_path(tool_name, tool_input)

    if isinstance(confirmation, list):
        for item in confirmation:
            if not isinstance(item, dict):
                continue
            action = item.get("action", "")
            if _match_confirmation_text(tool_name, tool_str, action.lower(), file_path):
                return (
                    f"Action '{tool_name}: {input_summary}' requires human confirmation"
                    " per governance.yaml"
                )
        return None

    # Legacy string path
    confirmation_text = str(confirmation or "").lower()
    if not confirmation_text:
        return None

    if _match_confirmation_text(tool_name, tool_str, confirmation_text, file_path):
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


def ask(reason: str) -> None:
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": f"AgentGuard: {reason}",
        }
    }
    print(json.dumps(output))
    sys.exit(0)


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
