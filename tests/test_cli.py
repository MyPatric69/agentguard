"""Tests for cli.py — CLAUDE.md append behavior and init helpers."""


from agentguard.cli import _strip_quotes, _update_claude_md

# ── _strip_quotes ─────────────────────────────────────────────────────────────

def test_strip_quotes_leading_double_quote():
    assert _strip_quotes('"Read files') == "Read files"


def test_strip_quotes_trailing_double_quote():
    assert _strip_quotes('Read files"') == "Read files"


def test_strip_quotes_both_double_quotes():
    assert _strip_quotes('"Read files"') == "Read files"


def test_strip_quotes_no_quotes_unchanged():
    assert _strip_quotes("Read files") == "Read files"


def test_strip_quotes_single_quotes():
    assert _strip_quotes("'Read files'") == "Read files"


def test_strip_quotes_mixed_quotes():
    assert _strip_quotes("'Read files\"") == "Read files"


def test_strip_quotes_preserves_internal_quotes():
    assert _strip_quotes('"No "database" writes"') == 'No "database" writes'

# ── CLAUDE.md append behavior ─────────────────────────────────────────────────

def test_claude_md_created_when_not_exists(tmp_path):
    dest = tmp_path / "CLAUDE.md"
    template = "## AgentGuard\nGovernance content here.\n"

    action, msg = _update_claude_md(dest, template)

    assert dest.exists()
    assert dest.read_text() == template
    assert action == "created"
    assert "Created" in msg


def test_claude_md_append_preserves_original_content(tmp_path):
    dest = tmp_path / "CLAUDE.md"
    original = "# My Existing Project\n\nSome important content here.\n"
    dest.write_text(original)

    action, msg = _update_claude_md(dest, "## AgentGuard\nContent.\n")

    result = dest.read_text()
    assert original in result
    assert action == "updated"
    assert "appended" in msg.lower()


def test_claude_md_append_adds_governance_block_header(tmp_path):
    dest = tmp_path / "CLAUDE.md"
    dest.write_text("# Existing\n")

    _update_claude_md(dest, "## Governance content\n")

    result = dest.read_text()
    assert "AgentGuard Governance Block" in result
    assert "Added by: agentguard init --interactive" in result
    assert "End AgentGuard Governance Block" in result


def test_claude_md_append_includes_template_content(tmp_path):
    dest = tmp_path / "CLAUDE.md"
    dest.write_text("# Existing\n")
    template = "## Loop Detection\nStop after 2 failures.\n"

    _update_claude_md(dest, template)

    result = dest.read_text()
    assert template in result


def test_claude_md_append_does_not_overwrite_original(tmp_path):
    dest = tmp_path / "CLAUDE.md"
    original = "# DO NOT OVERWRITE\nCritical content.\n"
    dest.write_text(original)

    _update_claude_md(dest, "## New block\n")

    result = dest.read_text()
    assert result.startswith(original)


def test_claude_md_appended_multiple_times_stacks_blocks(tmp_path):
    dest = tmp_path / "CLAUDE.md"
    dest.write_text("# Base\n")

    _update_claude_md(dest, "## Block 1\n")
    _update_claude_md(dest, "## Block 2\n")

    result = dest.read_text()
    assert result.count("## AgentGuard Governance Block\n") == 2
