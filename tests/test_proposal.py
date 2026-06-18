"""Tests for agentguard/proposal.py and the propose CLI command."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agentguard.proposal import (
    _apply_file_change,
    create_pr_for_proposal,
    format_proposal_summary,
    get_pending_proposals,
)

# ── helpers ───────────────────────────────────────────────────────────────────

PROPOSAL = {
    "tool_use_id": "tooluseabcd1234",
    "session_id": "sess-1",
    "timestamp": "2026-06-18T10:00:00+00:00",
    "tool_name": "Write",
    "file_path": "agentguard/foo.py",
    "tool_input": {"file_path": "agentguard/foo.py", "content": "print('hello')"},
    "governance_reason": "core enforcement layer",
    "status": "pending",
}

PR_URL = "https://github.com/MyPatric69/agentguard/pull/42"


def _git_side_effect(args, cwd, check=True):
    if args[0] == "rev-parse":
        return "abc1234abc1234\n"
    if args[0] == "branch" and "--list" in args:
        return ""
    return ""


# ── get_pending_proposals ──────────────────────────────────────────────────────


def test_get_pending_returns_only_pending(tmp_path):
    proposals_dir = tmp_path / ".agentguard" / "proposals"
    proposals_dir.mkdir(parents=True)
    (proposals_dir / "a.json").write_text(
        json.dumps({"status": "pending", "tool_use_id": "aaa"})
    )
    (proposals_dir / "b.json").write_text(
        json.dumps({"status": "pr_created", "tool_use_id": "bbb"})
    )

    result = get_pending_proposals(str(tmp_path))

    assert len(result) == 1
    assert result[0]["tool_use_id"] == "aaa"


def test_get_pending_ignores_malformed_json(tmp_path):
    proposals_dir = tmp_path / ".agentguard" / "proposals"
    proposals_dir.mkdir(parents=True)
    (proposals_dir / "bad.json").write_text("not json{{{")
    (proposals_dir / "good.json").write_text(
        json.dumps({"status": "pending", "tool_use_id": "ggg"})
    )

    result = get_pending_proposals(str(tmp_path))

    assert len(result) == 1
    assert result[0]["tool_use_id"] == "ggg"


def test_get_pending_missing_directory(tmp_path):
    result = get_pending_proposals(str(tmp_path))
    assert result == []


def test_get_pending_empty_directory(tmp_path):
    (tmp_path / ".agentguard" / "proposals").mkdir(parents=True)
    assert get_pending_proposals(str(tmp_path)) == []


# ── create_pr_for_proposal ─────────────────────────────────────────────────────


@patch("agentguard.proposal._apply_file_change")
@patch("agentguard.proposal._ensure_gh_label")
@patch("agentguard.proposal._run_subprocess")
@patch("agentguard.proposal._run_git")
@patch("agentguard.proposal.os.path.exists", return_value=False)
def test_create_pr_branch_name_and_commit(
    mock_exists, mock_git, mock_sub, mock_label, mock_apply, tmp_path
):
    mock_git.side_effect = _git_side_effect
    mock_sub.return_value = PR_URL + "\n"

    proposals_dir = tmp_path / ".agentguard" / "proposals"
    proposals_dir.mkdir(parents=True)
    proposal = dict(PROPOSAL)
    proposal_file = proposals_dir / "tooluseabcd1234.json"
    proposal_file.write_text(json.dumps(proposal))

    pr_url = create_pr_for_proposal(proposal, "patric@hayna.net", str(tmp_path))

    assert pr_url == PR_URL

    git_arg_lists = [c.args[0] for c in mock_git.call_args_list]

    # Branch name: agentguard/proposal/<first 8 chars of tool_use_id = "toolusea">
    checkout_args = next(a for a in git_arg_lists if "checkout" in a)
    assert "agentguard/proposal/toolusea" in checkout_args

    # Commit message contains tool_name and file_path
    commit_args = next(a for a in git_arg_lists if "commit" in a)
    commit_msg = " ".join(commit_args)
    assert "Write" in commit_msg
    assert "agentguard/foo.py" in commit_msg
    assert "agentguard" in commit_msg

    # Push targets the proposal branch with --force
    push_args = next(a for a in git_arg_lists if "push" in a)
    assert "--force" in push_args
    assert "agentguard/proposal/toolusea" in " ".join(push_args)


@patch("agentguard.proposal._apply_file_change")
@patch("agentguard.proposal._ensure_gh_label")
@patch("agentguard.proposal._run_subprocess")
@patch("agentguard.proposal._run_git")
@patch("agentguard.proposal.os.path.exists", return_value=False)
def test_create_pr_title_body_reviewer_label(
    mock_exists, mock_git, mock_sub, mock_label, mock_apply, tmp_path
):
    mock_git.side_effect = _git_side_effect
    mock_sub.return_value = PR_URL + "\n"

    proposals_dir = tmp_path / ".agentguard" / "proposals"
    proposals_dir.mkdir(parents=True)
    proposal = dict(PROPOSAL)
    (proposals_dir / "tooluseabcd1234.json").write_text(json.dumps(proposal))

    create_pr_for_proposal(proposal, "patric@hayna.net", str(tmp_path))

    gh_args = mock_sub.call_args.args[0]
    assert "gh" in gh_args
    assert "pr" in gh_args
    assert "create" in gh_args
    assert "--title" in gh_args
    title_idx = gh_args.index("--title")
    assert "AgentGuard Proposal" in gh_args[title_idx + 1]
    assert "Write" in gh_args[title_idx + 1]
    assert "agentguard/foo.py" in gh_args[title_idx + 1]
    assert "--reviewer" in gh_args
    rev_idx = gh_args.index("--reviewer")
    assert gh_args[rev_idx + 1] == "patric@hayna.net"
    assert "--label" in gh_args
    label_idx = gh_args.index("--label")
    assert gh_args[label_idx + 1] == "agentguard-proposal"

    # Body contains key fields
    body_idx = gh_args.index("--body")
    body = gh_args[body_idx + 1]
    assert "tooluseabcd1234" in body
    assert "core enforcement layer" in body
    assert "2026-06-18" in body


@patch("agentguard.proposal._apply_file_change")
@patch("agentguard.proposal._ensure_gh_label")
@patch("agentguard.proposal._run_subprocess")
@patch("agentguard.proposal._run_git")
@patch("agentguard.proposal.os.path.exists", return_value=False)
def test_create_pr_updates_proposal_status(
    mock_exists, mock_git, mock_sub, mock_label, mock_apply, tmp_path
):
    mock_git.side_effect = _git_side_effect
    mock_sub.return_value = PR_URL + "\n"

    proposals_dir = tmp_path / ".agentguard" / "proposals"
    proposals_dir.mkdir(parents=True)
    proposal = dict(PROPOSAL)
    proposal_file = proposals_dir / "tooluseabcd1234.json"
    proposal_file.write_text(json.dumps(proposal))

    create_pr_for_proposal(proposal, "patric@hayna.net", str(tmp_path))

    updated = json.loads(proposal_file.read_text())
    assert updated["status"] == "pr_created"
    assert updated["pr_url"] == PR_URL


@patch("agentguard.proposal._apply_file_change")
@patch("agentguard.proposal._ensure_gh_label")
@patch("agentguard.proposal._run_subprocess")
@patch("agentguard.proposal._run_git")
@patch("agentguard.proposal.os.path.exists", return_value=False)
def test_create_pr_idempotency_deletes_existing_branch(
    mock_exists, mock_git, mock_sub, mock_label, mock_apply, tmp_path
):
    """If branch already exists, it is deleted before recreation."""
    def _git_with_branch(args, cwd, check=True):
        if args[0] == "rev-parse":
            return "abc1234\n"
        if args[0] == "branch" and "--list" in args:
            return "  agentguard/proposal/tooluseab\n"
        return ""

    mock_git.side_effect = _git_with_branch
    mock_sub.return_value = PR_URL + "\n"

    proposals_dir = tmp_path / ".agentguard" / "proposals"
    proposals_dir.mkdir(parents=True)
    proposal = dict(PROPOSAL)
    (proposals_dir / "tooluseabcd1234.json").write_text(json.dumps(proposal))

    create_pr_for_proposal(proposal, "reviewer@example.com", str(tmp_path))

    git_arg_lists = [c.args[0] for c in mock_git.call_args_list]
    delete_branch = next(
        (a for a in git_arg_lists if a[0] == "branch" and "-D" in a), None
    )
    assert delete_branch is not None
    assert "agentguard/proposal/toolusea" in " ".join(delete_branch)


@patch("agentguard.proposal._apply_file_change")
@patch("agentguard.proposal._ensure_gh_label")
@patch("agentguard.proposal._run_subprocess")
@patch("agentguard.proposal._run_git")
@patch("agentguard.proposal.os.path.exists", return_value=False)
def test_create_pr_absolute_file_path_converted_to_relative(
    mock_exists, mock_git, mock_sub, mock_label, mock_apply, tmp_path
):
    """Absolute file_path in proposal is converted to relative for git add and _apply_file_change."""
    mock_git.side_effect = _git_side_effect
    mock_sub.return_value = PR_URL + "\n"

    proposals_dir = tmp_path / ".agentguard" / "proposals"
    proposals_dir.mkdir(parents=True)

    cwd_resolved = Path(str(tmp_path)).resolve()
    abs_file_path = str(cwd_resolved / "agentguard" / "foo.py")
    proposal = dict(PROPOSAL, file_path=abs_file_path)
    proposal_file = proposals_dir / "tooluseabcd1234.json"
    proposal_file.write_text(json.dumps(proposal))

    create_pr_for_proposal(proposal, "patric@hayna.net", str(tmp_path))

    # _apply_file_change must receive the relative path
    assert mock_apply.call_args.args[1] == "agentguard/foo.py"

    # git add must receive the relative path, not the absolute one
    git_arg_lists = [c.args[0] for c in mock_git.call_args_list]
    add_args = next(a for a in git_arg_lists if a[0] == "add" and len(a) == 2)
    assert add_args[1] == "agentguard/foo.py"
    assert not Path(add_args[1]).is_absolute()


@patch("agentguard.proposal._lookup_existing_pr")
@patch("agentguard.proposal._apply_file_change")
@patch("agentguard.proposal._ensure_gh_label")
@patch("agentguard.proposal._run_subprocess")
@patch("agentguard.proposal._run_git")
@patch("agentguard.proposal.os.path.exists", return_value=False)
def test_create_pr_recovers_when_pr_already_exists(
    mock_exists, mock_git, mock_sub, mock_label, mock_apply, mock_lookup, tmp_path
):
    """gh pr create 'already exists' error → look up existing PR URL and recover."""
    mock_git.side_effect = _git_side_effect
    mock_sub.side_effect = RuntimeError(
        "Command failed: gh pr create\na pull request for branch already exists"
    )
    mock_lookup.return_value = PR_URL

    proposals_dir = tmp_path / ".agentguard" / "proposals"
    proposals_dir.mkdir(parents=True)
    proposal = dict(PROPOSAL)
    proposal_file = proposals_dir / "tooluseabcd1234.json"
    proposal_file.write_text(json.dumps(proposal))

    pr_url = create_pr_for_proposal(proposal, "patric@hayna.net", str(tmp_path))

    assert pr_url == PR_URL
    updated = json.loads(proposal_file.read_text())
    assert updated["status"] == "pr_created"
    assert updated["pr_url"] == PR_URL
    mock_lookup.assert_called_once()


@patch("agentguard.proposal._lookup_existing_pr")
@patch("agentguard.proposal._apply_file_change")
@patch("agentguard.proposal._ensure_gh_label")
@patch("agentguard.proposal._run_subprocess")
@patch("agentguard.proposal._run_git")
@patch("agentguard.proposal.os.path.exists", return_value=False)
def test_create_pr_reraises_when_pr_already_exists_but_not_found(
    mock_exists, mock_git, mock_sub, mock_label, mock_apply, mock_lookup, tmp_path
):
    """gh pr create 'already exists' but gh pr list returns empty → re-raise original error."""
    mock_git.side_effect = _git_side_effect
    original_error = RuntimeError(
        "Command failed: gh pr create\na pull request for branch already exists"
    )
    mock_sub.side_effect = original_error
    mock_lookup.return_value = ""

    proposals_dir = tmp_path / ".agentguard" / "proposals"
    proposals_dir.mkdir(parents=True)
    proposal = dict(PROPOSAL)
    proposal_file = proposals_dir / "tooluseabcd1234.json"
    proposal_file.write_text(json.dumps(proposal))

    with pytest.raises(RuntimeError, match="already exists"):
        create_pr_for_proposal(proposal, "patric@hayna.net", str(tmp_path))

    # Status must remain pending
    assert json.loads(proposal_file.read_text())["status"] == "pending"


def test_create_pr_raises_for_null_tool_input(tmp_path):
    proposal = dict(PROPOSAL)
    proposal["tool_input"] = None

    with pytest.raises(ValueError, match="has no tool_input"):
        create_pr_for_proposal(proposal, "reviewer@example.com", str(tmp_path))


def test_create_pr_status_unchanged_on_null_tool_input(tmp_path):
    """Proposal file is not modified when tool_input is None."""
    proposals_dir = tmp_path / ".agentguard" / "proposals"
    proposals_dir.mkdir(parents=True)
    proposal = dict(PROPOSAL)
    proposal["tool_input"] = None
    proposal_file = proposals_dir / "tooluseabcd1234.json"
    proposal_file.write_text(json.dumps(proposal))

    with pytest.raises(ValueError):
        create_pr_for_proposal(proposal, "reviewer@example.com", str(tmp_path))

    on_disk = json.loads(proposal_file.read_text())
    assert on_disk["status"] == "pending"
    assert "pr_url" not in on_disk


# ── _apply_file_change ─────────────────────────────────────────────────────────


def test_apply_write(tmp_path):
    _apply_file_change(
        "Write", "src/foo.py", {"content": "print('hello')"}, tmp_path
    )
    assert (tmp_path / "src" / "foo.py").read_text() == "print('hello')"


def test_apply_edit(tmp_path):
    target = tmp_path / "src" / "foo.py"
    target.parent.mkdir()
    target.write_text("x = 1\ny = 2\n")
    _apply_file_change(
        "Edit", "src/foo.py", {"old_string": "x = 1", "new_string": "x = 99"}, tmp_path
    )
    assert target.read_text() == "x = 99\ny = 2\n"


def test_apply_edit_old_string_not_found(tmp_path):
    target = tmp_path / "foo.py"
    target.write_text("nothing here\n")
    with pytest.raises(ValueError, match="old_string not found"):
        _apply_file_change(
            "Edit", "foo.py", {"old_string": "missing", "new_string": "x"}, tmp_path
        )


def test_apply_multiedit(tmp_path):
    target = tmp_path / "foo.py"
    target.write_text("a = 1\nb = 2\n")
    _apply_file_change(
        "MultiEdit",
        "foo.py",
        {"edits": [{"old_string": "a = 1", "new_string": "a = 10"},
                   {"old_string": "b = 2", "new_string": "b = 20"}]},
        tmp_path,
    )
    assert target.read_text() == "a = 10\nb = 20\n"


def test_apply_multiedit_old_string_not_found(tmp_path):
    target = tmp_path / "foo.py"
    target.write_text("a = 1\n")
    with pytest.raises(ValueError, match="old_string not found"):
        _apply_file_change(
            "MultiEdit",
            "foo.py",
            {"edits": [{"old_string": "missing", "new_string": "x"}]},
            tmp_path,
        )


# ── format_proposal_summary ────────────────────────────────────────────────────


def test_format_proposal_summary():
    summary = format_proposal_summary(PROPOSAL)
    assert "Write" in summary
    assert "agentguard/foo.py" in summary
    assert "core enforcement layer" in summary
    assert "2026-06-18 10:00:00" in summary


def test_format_proposal_summary_no_file():
    p = dict(PROPOSAL, file_path=None, tool_name="Bash")
    summary = format_proposal_summary(p)
    assert "(no file)" in summary


# ── propose CLI command ────────────────────────────────────────────────────────


def test_propose_no_pending(tmp_path):
    from click.testing import CliRunner

    from agentguard.cli import main

    runner = CliRunner()
    with patch("shutil.which", return_value="/usr/bin/gh"):
        result = runner.invoke(main, ["propose", "--path", str(tmp_path)])
    assert "No pending proposals found" in result.output


def test_propose_dry_run_lists_proposals(tmp_path):
    from click.testing import CliRunner

    from agentguard.cli import main

    proposals_dir = tmp_path / ".agentguard" / "proposals"
    proposals_dir.mkdir(parents=True)
    (proposals_dir / "tooluseabcd1234.json").write_text(json.dumps(PROPOSAL))

    runner = CliRunner()
    with patch("agentguard.proposal._run_git") as mock_git:
        result = runner.invoke(
            main, ["propose", "--path", str(tmp_path), "--dry-run"]
        )
        mock_git.assert_not_called()

    assert "Write" in result.output
    assert "agentguard/foo.py" in result.output
    assert "pending proposal" in result.output


def test_propose_gh_not_installed(tmp_path):
    from click.testing import CliRunner

    from agentguard.cli import main

    proposals_dir = tmp_path / ".agentguard" / "proposals"
    proposals_dir.mkdir(parents=True)
    (proposals_dir / "tooluseabcd1234.json").write_text(json.dumps(PROPOSAL))

    runner = CliRunner()
    with patch("shutil.which", return_value=None):
        result = runner.invoke(main, ["propose", "--path", str(tmp_path)])

    assert "gh CLI required" in result.output
    assert result.exit_code == 1


def test_propose_skips_null_tool_input(tmp_path):
    from click.testing import CliRunner

    from agentguard.cli import main

    proposals_dir = tmp_path / ".agentguard" / "proposals"
    proposals_dir.mkdir(parents=True)
    proposal = dict(PROPOSAL, tool_input=None)
    proposal_file = proposals_dir / "tooluseabcd1234.json"
    proposal_file.write_text(json.dumps(proposal))

    runner = CliRunner()
    with patch("shutil.which", return_value="/usr/bin/gh"):
        with patch("agentguard.proposal._run_git"):
            result = runner.invoke(main, ["propose", "--path", str(tmp_path)])

    assert "has no tool_input" in result.output
    assert "skipping" in result.output
    # Status remains pending
    assert json.loads(proposal_file.read_text())["status"] == "pending"


@patch("agentguard.proposal._apply_file_change")
@patch("agentguard.proposal._ensure_gh_label")
@patch("agentguard.proposal._run_subprocess")
@patch("agentguard.proposal._run_git")
@patch("agentguard.proposal.os.path.exists", return_value=False)
def test_propose_cli_success_output(
    mock_exists, mock_git, mock_sub, mock_label, mock_apply, tmp_path
):
    from click.testing import CliRunner

    from agentguard.cli import main

    mock_git.side_effect = _git_side_effect
    mock_sub.return_value = PR_URL + "\n"

    proposals_dir = tmp_path / ".agentguard" / "proposals"
    proposals_dir.mkdir(parents=True)
    (proposals_dir / "tooluseabcd1234.json").write_text(json.dumps(dict(PROPOSAL)))

    runner = CliRunner()
    with patch("shutil.which", return_value="/usr/bin/gh"):
        result = runner.invoke(main, ["propose", "--path", str(tmp_path)])

    assert PR_URL in result.output
    assert "1 PR(s) created" in result.output
    assert "0 skipped" in result.output
