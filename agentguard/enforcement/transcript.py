"""
Parse Claude Code JSONL transcripts to extract full tool call details.
Tool use entries live in type="assistant" lines under message.content[].
"""

from __future__ import annotations

import json


def get_tool_call(transcript_path: str, tool_use_id: str) -> dict | None:
    """
    Parse a Claude Code JSONL transcript and return the full tool_input
    for the given tool_use_id.

    Returns a dict with:
      {
        "tool_name": str,
        "tool_input": dict,   # full, untruncated — e.g. old_string/new_string for Edit
        "tool_use_id": str,
      }
    Or None if tool_use_id is not found in the transcript.
    """
    try:
        f = open(transcript_path)
    except OSError:
        return None

    with f:
        for raw in f:
            raw = raw.strip()
            if not raw:
                continue
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if obj.get("type") != "assistant":
                continue

            content = obj.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue

            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "tool_use" and item.get("id") == tool_use_id:
                    return {
                        "tool_name": item.get("name", ""),
                        "tool_input": item.get("input", {}),
                        "tool_use_id": item["id"],
                    }

    return None
