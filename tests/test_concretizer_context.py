"""Tests for project-structure context helpers in concretizer."""
from __future__ import annotations

from agentguard.guided.concretizer import (
    _HARD_LIMITS_PROMPT,
    _MISSION_PROMPT,
    _claude_md_architecture,
    _project_tree,
)

# ── 1. _project_tree: excluded dirs are dropped ──────────────────────────────

def test_project_tree_excludes_noise_dirs(tmp_path):
    (tmp_path / "agentguard").mkdir()
    (tmp_path / "agentguard" / "__init__.py").write_text("")
    (tmp_path / "web").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "node_modules").mkdir()
    (tmp_path / ".venv").mkdir()
    (tmp_path / "dist").mkdir()
    (tmp_path / "build").mkdir()
    (tmp_path / ".agentguard").mkdir()
    (tmp_path / "mypackage.egg-info").mkdir()

    tree = _project_tree(str(tmp_path))

    assert "agentguard/" in tree
    assert "web/" in tree
    assert "tests/" in tree
    assert ".git" not in tree
    assert "__pycache__" not in tree
    assert "node_modules" not in tree
    assert ".venv" not in tree
    assert "dist" not in tree
    assert "build" not in tree
    assert ".agentguard" not in tree
    assert "egg-info" not in tree


def test_project_tree_depth_limit(tmp_path):
    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (deep / "deep_file.py").write_text("")

    tree = _project_tree(str(tmp_path))

    assert "deep_file.py" not in tree


def test_project_tree_includes_files_at_depth_2(tmp_path):
    (tmp_path / "agentguard").mkdir()
    (tmp_path / "agentguard" / "cli.py").write_text("")

    tree = _project_tree(str(tmp_path))

    assert "cli.py" in tree


# ── 2. _claude_md_architecture parsing ───────────────────────────────────────

def test_claude_md_architecture_extracts_section(tmp_path):
    (tmp_path / "CLAUDE.md").write_text(
        "# Project\n\n"
        "## Architecture Overview\n\n"
        "agentguard/\n"
        "├── cli.py\n"
        "└── checks/\n\n"
        "## Other Section\n\n"
        "Some other content.\n"
    )
    result = _claude_md_architecture(str(tmp_path))
    assert result is not None
    assert "agentguard/" in result
    assert "Other Section" not in result


def test_claude_md_architecture_returns_none_when_missing(tmp_path):
    assert _claude_md_architecture(str(tmp_path)) is None


def test_claude_md_architecture_returns_none_when_section_absent(tmp_path):
    (tmp_path / "CLAUDE.md").write_text("# Project\n\n## Some Section\n\nContent.\n")
    assert _claude_md_architecture(str(tmp_path)) is None


# ── 3. Prompt assembly: real paths injected, ./src not present ────────────────

def test_mission_prompt_contains_project_structure(tmp_path):
    (tmp_path / "agentguard").mkdir()
    (tmp_path / "web").mkdir()
    (tmp_path / "tests").mkdir()

    tree = _project_tree(str(tmp_path))
    arch = _claude_md_architecture(str(tmp_path)) or "(not available)"
    prompt = _MISSION_PROMPT.format(
        user_input="implement features in agentguard/",
        directory_tree=tree,
        claude_md_excerpt=arch,
    )

    assert "agentguard/" in prompt
    assert "web/" in prompt
    assert "tests/" in prompt
    assert "./src" not in prompt


def test_hard_limits_prompt_contains_project_structure(tmp_path):
    (tmp_path / "agentguard").mkdir()

    tree = _project_tree(str(tmp_path))
    arch = _claude_md_architecture(str(tmp_path)) or "(not available)"
    prompt = _HARD_LIMITS_PROMPT.format(
        user_input="no writes to production",
        directory_tree=tree,
        claude_md_excerpt=arch,
    )

    assert "agentguard/" in prompt
    assert "./src" not in prompt
