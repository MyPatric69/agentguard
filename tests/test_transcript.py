"""Tests for agentguard/enforcement/transcript.py"""

from __future__ import annotations

import json

from agentguard.enforcement.transcript import get_tool_call

# ── helpers ───────────────────────────────────────────────────────────────────


def _assistant_line(tool_name: str, tool_use_id: str, tool_input: dict) -> str:
    """Build a minimal assistant JSONL line containing one tool_use content item."""
    return json.dumps(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "id": tool_use_id,
                        "name": tool_name,
                        "input": tool_input,
                    }
                ]
            },
        }
    )


def _other_line(line_type: str = "user") -> str:
    return json.dumps({"type": line_type, "message": {}})


# ── 1. Basic: known tool_use_id found → correct dict returned ────────────────


def test_get_tool_call_basic(tmp_path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        "\n".join(
            [
                _other_line("user"),
                _assistant_line(
                    "Bash", "tuid-A", {"command": "pytest", "description": "run tests"}
                ),
                _assistant_line("Read", "tuid-B", {"file_path": "/foo/bar.py"}),
                _other_line("user"),
            ]
        )
        + "\n"
    )

    result = get_tool_call(str(transcript), "tuid-B")
    assert result is not None
    assert result["tool_name"] == "Read"
    assert result["tool_use_id"] == "tuid-B"
    assert result["tool_input"] == {"file_path": "/foo/bar.py"}


# ── 2. Not found: tool_use_id absent → None ───────────────────────────────────


def test_get_tool_call_not_found(tmp_path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(_assistant_line("Bash", "tuid-X", {"command": "ls"}) + "\n")

    assert get_tool_call(str(transcript), "tuid-missing") is None


# ── 3. File not found → None ─────────────────────────────────────────────────


def test_get_tool_call_file_not_found(tmp_path):
    assert get_tool_call(str(tmp_path / "nonexistent.jsonl"), "tuid-X") is None


# ── 4. Malformed line skipped, rest parsed correctly ─────────────────────────


def test_get_tool_call_malformed_line_skipped(tmp_path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        "\n".join(
            [
                _assistant_line("Bash", "tuid-before", {"command": "echo hi"}),
                "{{ not valid json ~~~",
                _assistant_line("Read", "tuid-after", {"file_path": "/tmp/x.py"}),
            ]
        )
        + "\n"
    )

    result = get_tool_call(str(transcript), "tuid-after")
    assert result is not None
    assert result["tool_name"] == "Read"
    assert result["tool_input"] == {"file_path": "/tmp/x.py"}


# ── 5. Edit tool: old_string/new_string returned in full ─────────────────────


def test_get_tool_call_edit_tool(tmp_path):
    old = "def foo():\n    pass\n"
    new = "def foo():\n    return 42\n"
    tool_input = {
        "file_path": "src/main.py",
        "old_string": old,
        "new_string": new,
        "replace_all": False,
    }

    transcript = tmp_path / "session.jsonl"
    transcript.write_text(_assistant_line("Edit", "tuid-edit", tool_input) + "\n")

    result = get_tool_call(str(transcript), "tuid-edit")
    assert result is not None
    assert result["tool_name"] == "Edit"
    assert result["tool_input"]["old_string"] == old
    assert result["tool_input"]["new_string"] == new
    assert result["tool_input"]["file_path"] == "src/main.py"


# ── 6. Write tool: content field returned correctly ──────────────────────────


def test_get_tool_call_write_tool(tmp_path):
    file_content = "hello\nworld\n" * 100  # ensure full content, not truncated
    tool_input = {"file_path": "output/result.txt", "content": file_content}

    transcript = tmp_path / "session.jsonl"
    transcript.write_text(_assistant_line("Write", "tuid-write", tool_input) + "\n")

    result = get_tool_call(str(transcript), "tuid-write")
    assert result is not None
    assert result["tool_name"] == "Write"
    assert result["tool_input"]["content"] == file_content
    assert result["tool_input"]["file_path"] == "output/result.txt"
