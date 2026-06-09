"""Tests for agentguard/guided/pinning.py"""

from __future__ import annotations

import json

from agentguard.guided.pinning import hash_content, pin_concretization, verify_pin


# ── 1. hash_content returns 16-char hex string ───────────────────────────────

def test_hash_content_returns_16_char_hex():
    result = hash_content("hello world")
    assert len(result) == 16
    assert all(c in "0123456789abcdef" for c in result)


# ── 2. hash_content is deterministic ─────────────────────────────────────────

def test_hash_content_is_deterministic():
    assert hash_content("test input") == hash_content("test input")


# ── 3. hash_content differs for different inputs ──────────────────────────────

def test_hash_content_differs_for_different_inputs():
    assert hash_content("abc") != hash_content("xyz")


# ── 4. pin_concretization returns expected keys ───────────────────────────────

def test_pin_concretization_returns_expected_keys():
    output = {"authorized": [], "prohibited": [], "requires_confirmation": []}
    pin = pin_concretization("mission", "my input", "my prompt", "gpt-4o", "openai", output)
    assert set(pin.keys()) == {"field", "input_hash", "prompt_hash", "output_hash", "model", "provider", "temperature", "date"}


# ── 5. pin_concretization stores temperature=0 ───────────────────────────────

def test_pin_concretization_temperature_is_zero():
    output = {"concretized": "some rule"}
    pin = pin_concretization("escalation", "input", "prompt", "claude-sonnet", "anthropic", output)
    assert pin["temperature"] == 0


# ── 6. verify_pin returns valid=True for correct hashes ──────────────────────

def test_verify_pin_valid_for_matching_hashes():
    prompt = "my governance prompt"
    output = {"authorized": [{"action": "Read files", "reason": "core task"}]}
    pin = pin_concretization("mission", "input", prompt, "gpt-4o", "openai", output)
    result = verify_pin(pin, prompt, output)
    assert result["valid"] is True
    assert result["drifted"] == []


# ── 7. verify_pin detects prompt drift ───────────────────────────────────────

def test_verify_pin_detects_prompt_drift():
    prompt = "original prompt"
    output = {"authorized": []}
    pin = pin_concretization("mission", "input", prompt, "gpt-4o", "openai", output)
    result = verify_pin(pin, "modified prompt", output)
    assert result["valid"] is False
    assert "prompt" in result["drifted"]


# ── 8. verify_pin detects output drift ───────────────────────────────────────

def test_verify_pin_detects_output_drift():
    prompt = "original prompt"
    output = {"authorized": [{"action": "original action", "reason": "r"}]}
    pin = pin_concretization("mission", "input", prompt, "gpt-4o", "openai", output)
    modified_output = {"authorized": [{"action": "modified action", "reason": "r"}]}
    result = verify_pin(pin, prompt, modified_output)
    assert result["valid"] is False
    assert "output" in result["drifted"]


# ── 9. verify_pin detects temperature drift ──────────────────────────────────

def test_verify_pin_detects_temperature_drift():
    output = {"concretized": "rule"}
    pin = pin_concretization("field", "input", "prompt", "gpt-4o", "openai", output)
    pin_modified = {**pin, "temperature": 1}
    result = verify_pin(pin_modified, "prompt", output)
    assert result["valid"] is False
    assert "temperature" in result["drifted"]
