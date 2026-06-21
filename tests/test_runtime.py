"""Tests for checks/runtime.py."""

from agentguard.checks.runtime import detect_loop


def test_detect_loop_returns_false_below_threshold():
    history = ["tool_a", "tool_b", "tool_c", "tool_a", "tool_b"]
    assert detect_loop(history, threshold=2) is False


def test_detect_loop_triggers_at_threshold():
    history = ["tool_a"] * 4 + ["tool_b"]
    assert detect_loop(history, threshold=2) is True


def test_detect_loop_uses_last_10_calls():
    # Old repetitions outside the window should not count
    tail = [f"tool_{c}" for c in "abcdefghijk"]  # 11 unique tools
    history = ["tool_x"] * 10 + tail
    assert detect_loop(history, threshold=2) is False


def test_detect_loop_exact_threshold_boundary():
    # threshold=3 means >= 6 calls in window → loop
    history = ["tool_z"] * 6
    assert detect_loop(history, threshold=3) is True


def test_detect_loop_empty_history():
    assert detect_loop([], threshold=2) is False


def test_detect_loop_single_tool_high_threshold():
    history = ["tool_a", "tool_b"]
    assert detect_loop(history, threshold=5) is False
