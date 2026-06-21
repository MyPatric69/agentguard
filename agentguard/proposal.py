"""Stage 2 async approval workflow: read proposals and create GitHub PRs."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def get_pending_proposals(cwd: str) -> list[dict]:
    """Read all .agentguard/proposals/*.json with status='pending'."""
    proposals_dir = Path(cwd) / ".agentguard" / "proposals"
    if not proposals_dir.exists():
        return []
    results = []
    for path in sorted(proposals_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if data.get("status") == "pending":
            results.append(data)
    return results


def create_pr_for_proposal(proposal: dict, reviewer: str, cwd: str) -> str:
    """Create a git branch + GitHub PR for a single proposal. Returns the PR URL."""
    tool_use_id = proposal["tool_use_id"]
    tool_name = proposal.get("tool_name", "unknown")
    file_path = proposal.get("file_path")
    tool_input = proposal.get("tool_input")

    if tool_input is None:
        raise ValueError(f"proposal {tool_use_id} has no tool_input — cannot create PR, skipping")

    branch_name = f"agentguard/proposal/{tool_use_id[:8]}"
    main_sha = _run_git(["rev-parse", "main"], cwd=cwd).strip()

    worktree_dir = os.path.join(tempfile.gettempdir(), f"agentguard-proposal-{tool_use_id[:8]}")

    if os.path.exists(worktree_dir):
        _run_git(["worktree", "remove", "--force", worktree_dir], cwd=cwd, check=False)
        shutil.rmtree(worktree_dir, ignore_errors=True)

    existing = _run_git(["branch", "--list", branch_name], cwd=cwd, check=False).strip()
    if existing:
        _run_git(["branch", "-D", branch_name], cwd=cwd)

    try:
        _run_git(["worktree", "add", "--detach", worktree_dir, main_sha], cwd=cwd)
        _run_git(["checkout", "-b", branch_name], cwd=worktree_dir)

        if file_path and tool_name in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            fp = Path(file_path)
            if fp.is_absolute():
                relative_path = fp.relative_to(Path(cwd).resolve())
            else:
                relative_path = fp
            _apply_file_change(tool_name, str(relative_path), tool_input, Path(worktree_dir))
            _run_git(["add", str(relative_path)], cwd=worktree_dir)
        else:
            notes_file = f".agentguard-proposal-{tool_use_id[:8]}.md"
            (Path(worktree_dir) / notes_file).write_text(_format_proposal_notes(proposal))
            _run_git(["add", notes_file], cwd=worktree_dir)

        commit_msg = f"proposal: {tool_name} {file_path or '(no file)'} (agentguard)"
        _run_git(["commit", "-m", commit_msg], cwd=worktree_dir)
        _run_git(["push", "--force", "origin", branch_name], cwd=worktree_dir)

        _ensure_gh_label(cwd)

        pr_title = f"AgentGuard Proposal: {tool_name} on {file_path or 'session'}"
        pr_body = _format_pr_body(proposal)
        gh_cmd = [
            "gh",
            "pr",
            "create",
            "--title",
            pr_title,
            "--body",
            pr_body,
            "--label",
            "agentguard-proposal",
        ]
        if reviewer:
            gh_cmd.extend(["--reviewer", reviewer])

        try:
            pr_url = _run_subprocess(gh_cmd, cwd=worktree_dir).strip()
        except RuntimeError as exc:
            if "already exists" not in str(exc):
                raise
            pr_url = _lookup_existing_pr(branch_name, worktree_dir)
            if not pr_url:
                raise

        proposal["status"] = "pr_created"
        proposal["pr_url"] = pr_url
        proposal_path = Path(cwd) / ".agentguard" / "proposals" / f"{tool_use_id}.json"
        proposal_path.write_text(json.dumps(proposal, indent=2))

        return pr_url

    finally:
        _run_git(["worktree", "remove", "--force", worktree_dir], cwd=cwd, check=False)


def format_proposal_summary(proposal: dict) -> str:
    """One-line summary for CLI output."""
    tool_name = proposal.get("tool_name", "unknown")
    file_path = proposal.get("file_path") or "(no file)"
    timestamp = proposal.get("timestamp", "")[:19].replace("T", " ")
    reason = (proposal.get("governance_reason") or "")[:60]
    return f"{tool_name} on {file_path} — {reason} [{timestamp}]"


def _run_git(args: list[str], cwd: str, check: bool = True) -> str:
    result = subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{result.stderr.strip()}")
    return result.stdout


def _run_subprocess(cmd: list[str], cwd: str) -> str:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr.strip()}")
    return result.stdout


def _ensure_gh_label(cwd: str) -> None:
    """Create 'agentguard-proposal' label if it doesn't exist; ignore errors."""
    subprocess.run(
        [
            "gh",
            "label",
            "create",
            "agentguard-proposal",
            "--color",
            "0075ca",
            "--description",
            "AgentGuard pending proposal",
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _apply_file_change(tool_name: str, file_path: str, tool_input: dict, worktree: Path) -> None:
    target = worktree / file_path
    target.parent.mkdir(parents=True, exist_ok=True)

    if tool_name == "Write":
        target.write_text(tool_input.get("content", ""))
    elif tool_name == "Edit":
        old_string = tool_input.get("old_string", "")
        new_string = tool_input.get("new_string", "")
        text = target.read_text() if target.exists() else ""
        if old_string and old_string not in text:
            raise ValueError(f"old_string not found in {file_path} on main — cannot apply Edit")
        target.write_text(text.replace(old_string, new_string, 1))
    elif tool_name == "MultiEdit":
        text = target.read_text() if target.exists() else ""
        for edit in tool_input.get("edits", []):
            old_s = edit.get("old_string", "")
            new_s = edit.get("new_string", "")
            if old_s and old_s not in text:
                raise ValueError(
                    f"old_string not found in {file_path} on main — cannot apply MultiEdit"
                )
            text = text.replace(old_s, new_s, 1)
        target.write_text(text)
    elif tool_name == "NotebookEdit":
        target.write_text(json.dumps(tool_input, indent=2))


def _lookup_existing_pr(branch_name: str, cwd: str) -> str:
    """Return the URL of the open PR for branch_name, or empty string if none."""
    result = subprocess.run(
        ["gh", "pr", "list", "--head", branch_name, "--json", "url", "--jq", ".[0].url"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _format_pr_body(proposal: dict) -> str:
    tool_name = proposal.get("tool_name", "unknown")
    file_path = proposal.get("file_path") or "(no file)"
    tool_use_id = proposal.get("tool_use_id", "")
    timestamp = proposal.get("timestamp", "")
    governance_reason = proposal.get("governance_reason", "")

    return (
        "## AgentGuard Unresolved Proposal\n\n"
        "This PR was created by `agentguard propose` for an ask-gated action "
        "that was not resolved during the agent session.\n\n"
        f"**Tool:** `{tool_name}`  \n"
        f"**File:** `{file_path}`  \n"
        f"**Timestamp:** {timestamp}  \n"
        f"**Tool Use ID:** `{tool_use_id}`  \n\n"
        f"**Governance reason:**  \n{governance_reason}\n\n"
        "---\n"
        "_Review the diff, approve if the change is acceptable, or close to reject._"
    )


def _format_proposal_notes(proposal: dict) -> str:
    """Markdown notes file for non-file-tool proposals."""
    tool_name = proposal.get("tool_name", "unknown")
    tool_use_id = proposal.get("tool_use_id", "")
    timestamp = proposal.get("timestamp", "")
    governance_reason = proposal.get("governance_reason", "")
    tool_input = proposal.get("tool_input") or {}

    return (
        f"# AgentGuard Proposal — {tool_name}\n\n"
        f"**Tool Use ID:** `{tool_use_id}`  \n"
        f"**Timestamp:** {timestamp}  \n"
        f"**Governance reason:** {governance_reason}  \n\n"
        "## Proposed Input\n\n"
        f"```json\n{json.dumps(tool_input, indent=2)}\n```\n"
    )
