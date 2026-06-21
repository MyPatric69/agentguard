"""Tests for agentguard.checks.cost, agentguard.notifications, and
cost-awareness integration in handle_stop."""

from __future__ import annotations

import json
import warnings

import pytest

from agentguard.checks.cost import (
    HARDCODED_PRICING,
    _display_to_key,
    _match_model_key,
    calculate_session_cost,
    fetch_pricing,
)

# ── helpers ───────────────────────────────────────────────────────────────────

SAMPLE_MARKDOWN_TABLE = """\
| Model | Base Input Tokens | 5m Cache Writes | 1h Cache Writes | Cache Hits & Refreshes | Output Tokens |
|---|---|---|---|---|---|
| Claude Sonnet 4.6 | $3 / MTok | $3.75 / MTok | $6 / MTok | $0.30 / MTok | $15 / MTok |
| Claude Opus 4.8 | $5 / MTok | $6.25 / MTok | $10 / MTok | $0.50 / MTok | $25 / MTok |
| Claude Haiku 4.5 | $1 / MTok | $1.25 / MTok | $2 / MTok | $0.10 / MTok | $5 / MTok |
| Claude Fable 5 | $10 / MTok | $12.50 / MTok | $20 / MTok | $1 / MTok | $50 / MTok |
"""


def _transcript_msg(
    msg_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_write: int = 0,
    cache_read: int = 0,
) -> str:
    """Build assistant message with legacy flat cache_creation_input_tokens."""
    return json.dumps(
        {
            "type": "assistant",
            "message": {
                "id": msg_id,
                "model": model,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cache_creation_input_tokens": cache_write,
                    "cache_read_input_tokens": cache_read,
                },
                "content": [],
            },
        }
    )


def _transcript_msg_split_cache(
    msg_id: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_write_5m: int = 0,
    cache_write_1h: int = 0,
    cache_read: int = 0,
) -> str:
    """Build assistant message with new nested cache_creation format (5m + 1h)."""
    return json.dumps(
        {
            "type": "assistant",
            "message": {
                "id": msg_id,
                "model": model,
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cache_creation": {
                        "ephemeral_5m_input_tokens": cache_write_5m,
                        "ephemeral_1h_input_tokens": cache_write_1h,
                    },
                    "cache_read_input_tokens": cache_read,
                },
                "content": [],
            },
        }
    )


# ── fetch_pricing: parse markdown table ──────────────────────────────────────


def test_fetch_pricing_parses_markdown_table(monkeypatch):
    monkeypatch.setattr("agentguard.checks.cost._fetch_text", lambda url: SAMPLE_MARKDOWN_TABLE)
    pricing = fetch_pricing()
    assert pricing["claude-sonnet-4"]["input"] == 3.0
    assert pricing["claude-sonnet-4"]["cache_write_5m"] == 3.75
    assert pricing["claude-sonnet-4"]["cache_write_1h"] == 6.0
    assert pricing["claude-sonnet-4"]["cache_read"] == 0.30
    assert pricing["claude-sonnet-4"]["output"] == 15.0
    assert pricing["claude-opus-4"]["input"] == 5.0
    assert pricing["claude-haiku-4"]["cache_read"] == 0.10
    assert pricing["claude-fable-5"]["output"] == 50.0
    assert pricing.get("_source") == "live"


# ── fetch_pricing: fallback on error ─────────────────────────────────────────


def test_fetch_pricing_fallback_on_network_error(monkeypatch):
    def _fail(url):
        raise OSError("network error")

    monkeypatch.setattr("agentguard.checks.cost._fetch_text", _fail)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        pricing = fetch_pricing()
    assert pricing["claude-sonnet-4"]["input"] == HARDCODED_PRICING["claude-sonnet-4"]["input"]
    assert pricing.get("_source") == "fallback"
    assert any("fallback" in str(warning.message).lower() for warning in w)


def test_fetch_pricing_fallback_on_empty_parse(monkeypatch):
    monkeypatch.setattr("agentguard.checks.cost._fetch_text", lambda url: "no table here")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        pricing = fetch_pricing()
    assert pricing.get("_source") == "fallback"
    assert any("fallback" in str(warning.message).lower() for warning in w)


# ── calculate_session_cost: deduplication and correct totals ─────────────────


def test_calculate_session_cost_deduplication(tmp_path):
    transcript = tmp_path / "session.jsonl"
    # msg_001 appears twice — must be counted once (legacy flat cache field)
    transcript.write_text(
        _transcript_msg("msg_001", "claude-sonnet-4-6", 1000, 200, cache_write=500, cache_read=300)
        + "\n"
        + _transcript_msg(
            "msg_001", "claude-sonnet-4-6", 1000, 200, cache_write=500, cache_read=300
        )
        + "\n"
        + _transcript_msg("msg_002", "claude-sonnet-4-6", 500, 100)
        + "\n"
    )
    pricing = {**HARDCODED_PRICING, "_source": "fallback"}
    result = calculate_session_cost(str(transcript), pricing)

    assert result is not None
    assert result["model"] == "claude-sonnet-4-6"
    assert result["input_tokens"] == 1500  # 1000 (msg_001) + 500 (msg_002)
    assert result["output_tokens"] == 300  # 200 + 100
    assert result["cache_write_5m_tokens"] == 500  # legacy field treated as 5m
    assert result["cache_write_1h_tokens"] == 0
    assert result["cache_read_tokens"] == 300
    assert result["pricing_source"] == "fallback"

    p = HARDCODED_PRICING["claude-sonnet-4"]
    expected = round(
        1500 * p["input"] / 1_000_000
        + 500 * p["cache_write_5m"] / 1_000_000
        + 300 * p["cache_read"] / 1_000_000
        + 300 * p["output"] / 1_000_000,
        6,
    )
    assert abs(result["total_usd"] - expected) < 1e-9


def test_calculate_session_cost_missing_transcript(tmp_path):
    pricing = {**HARDCODED_PRICING, "_source": "fallback"}
    result = calculate_session_cost(str(tmp_path / "nonexistent.jsonl"), pricing)
    assert result is None


def test_calculate_session_cost_no_usage_returns_none(tmp_path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {"id": "msg_001", "model": "claude-sonnet-4-6", "content": []},
            }
        )
        + "\n"
    )
    pricing = {**HARDCODED_PRICING, "_source": "fallback"}
    result = calculate_session_cost(str(transcript), pricing)
    assert result is None


def test_calculate_session_cost_pricing_source_live(tmp_path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(_transcript_msg("msg_001", "claude-sonnet-4-6", 100, 50) + "\n")
    pricing = {**HARDCODED_PRICING, "_source": "live"}
    result = calculate_session_cost(str(transcript), pricing)
    assert result is not None
    assert result["pricing_source"] == "live"


# ── cache write pricing: 5m vs 1h ────────────────────────────────────────────


def test_calculate_session_cost_cache_write_5m_priced_correctly(tmp_path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        _transcript_msg_split_cache("msg_001", "claude-sonnet-4-6", 0, 0, cache_write_5m=1_000_000)
        + "\n"
    )
    pricing = {**HARDCODED_PRICING, "_source": "fallback"}
    result = calculate_session_cost(str(transcript), pricing)

    assert result is not None
    assert result["cache_write_5m_tokens"] == 1_000_000
    assert result["cache_write_1h_tokens"] == 0
    p = HARDCODED_PRICING["claude-sonnet-4"]
    expected = round(1_000_000 * p["cache_write_5m"] / 1_000_000, 6)
    assert abs(result["total_usd"] - expected) < 1e-9


def test_calculate_session_cost_cache_write_1h_priced_correctly(tmp_path):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        _transcript_msg_split_cache("msg_001", "claude-sonnet-4-6", 0, 0, cache_write_1h=1_000_000)
        + "\n"
    )
    pricing = {**HARDCODED_PRICING, "_source": "fallback"}
    result = calculate_session_cost(str(transcript), pricing)

    assert result is not None
    assert result["cache_write_5m_tokens"] == 0
    assert result["cache_write_1h_tokens"] == 1_000_000
    p = HARDCODED_PRICING["claude-sonnet-4"]
    expected = round(1_000_000 * p["cache_write_1h"] / 1_000_000, 6)
    assert abs(result["total_usd"] - expected) < 1e-9


def test_calculate_session_cost_mixed_cache_writes_summed_correctly(tmp_path):
    """5m and 1h tokens are split and priced at their respective rates."""
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        _transcript_msg_split_cache(
            "msg_001",
            "claude-sonnet-4-6",
            0,
            0,
            cache_write_5m=500_000,
            cache_write_1h=500_000,
        )
        + "\n"
    )
    pricing = {**HARDCODED_PRICING, "_source": "fallback"}
    result = calculate_session_cost(str(transcript), pricing)

    assert result is not None
    assert result["cache_write_5m_tokens"] == 500_000
    assert result["cache_write_1h_tokens"] == 500_000
    p = HARDCODED_PRICING["claude-sonnet-4"]
    expected = round(
        500_000 * p["cache_write_5m"] / 1_000_000 + 500_000 * p["cache_write_1h"] / 1_000_000,
        6,
    )
    assert abs(result["total_usd"] - expected) < 1e-9
    # 1h costs more per token — total should exceed what pure 5m pricing would give
    assert result["total_usd"] > round(1_000_000 * p["cache_write_5m"] / 1_000_000, 6)


def test_calculate_session_cost_legacy_flat_field_treated_as_5m(tmp_path):
    """Old cache_creation_input_tokens field is treated as 5m write tokens."""
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        _transcript_msg("msg_001", "claude-sonnet-4-6", 0, 0, cache_write=1_000_000) + "\n"
    )
    pricing = {**HARDCODED_PRICING, "_source": "fallback"}
    result = calculate_session_cost(str(transcript), pricing)

    assert result is not None
    assert result["cache_write_5m_tokens"] == 1_000_000
    assert result["cache_write_1h_tokens"] == 0
    p = HARDCODED_PRICING["claude-sonnet-4"]
    expected = round(1_000_000 * p["cache_write_5m"] / 1_000_000, 6)
    assert abs(result["total_usd"] - expected) < 1e-9


# ── model prefix matching ─────────────────────────────────────────────────────


def test_match_model_key_sonnet():
    pricing = {**HARDCODED_PRICING, "_source": "fallback"}
    assert _match_model_key("claude-sonnet-4-6", pricing) == "claude-sonnet-4"


def test_match_model_key_opus():
    pricing = {**HARDCODED_PRICING, "_source": "fallback"}
    assert _match_model_key("claude-opus-4-8", pricing) == "claude-opus-4"


def test_match_model_key_haiku():
    pricing = {**HARDCODED_PRICING, "_source": "fallback"}
    assert _match_model_key("claude-haiku-4-5", pricing) == "claude-haiku-4"


def test_match_model_key_no_match():
    pricing = {**HARDCODED_PRICING, "_source": "fallback"}
    assert _match_model_key("gpt-4-turbo", pricing) is None


def test_match_model_key_longest_wins():
    pricing = {
        "claude-sonnet": {
            "input": 1.0,
            "cache_write_5m": 1.0,
            "cache_write_1h": 1.0,
            "cache_read": 0.1,
            "output": 5.0,
        },
        "claude-sonnet-4": {
            "input": 3.0,
            "cache_write_5m": 3.75,
            "cache_write_1h": 6.0,
            "cache_read": 0.30,
            "output": 15.0,
        },
    }
    assert _match_model_key("claude-sonnet-4-6", pricing) == "claude-sonnet-4"


# ── display_to_key ────────────────────────────────────────────────────────────


def test_display_to_key_with_minor_version():
    assert _display_to_key("Claude Sonnet 4.6") == "claude-sonnet-4"
    assert _display_to_key("Claude Opus 4.8") == "claude-opus-4"
    assert _display_to_key("Claude Haiku 4.5") == "claude-haiku-4"


def test_display_to_key_major_only():
    assert _display_to_key("Claude Fable 5") == "claude-fable-5"


def test_display_to_key_strips_parenthetical():
    assert _display_to_key("Claude Opus 4.8 (deprecated)") == "claude-opus-4"


def test_display_to_key_strips_markdown_link():
    assert (
        _display_to_key("Claude Mythos 5 ([limited availability](https://example.com))")
        == "claude-mythos-5"
    )


# ── notify_cost: correct title/message/sound ──────────────────────────────────


def test_notify_cost_warn_level(monkeypatch):
    send_calls = []
    sound_calls = []
    monkeypatch.setattr(
        "agentguard.notifications._send_notification", lambda t, m: send_calls.append((t, m))
    )
    monkeypatch.setattr("agentguard.notifications._play_sound", lambda lvl: sound_calls.append(lvl))

    from agentguard.notifications import notify_cost

    notify_cost(1.23, "claude-sonnet-4-6", "warn", "MyProject")

    assert len(send_calls) == 1
    title, message = send_calls[0]
    assert title == "AgentGuard Warning"
    assert "1.23" in message
    assert "claude-sonnet-4-6" in message
    assert "warn" in message
    assert sound_calls == ["warn"]


def test_notify_cost_alert_level(monkeypatch):
    send_calls = []
    sound_calls = []
    monkeypatch.setattr(
        "agentguard.notifications._send_notification", lambda t, m: send_calls.append((t, m))
    )
    monkeypatch.setattr("agentguard.notifications._play_sound", lambda lvl: sound_calls.append(lvl))

    from agentguard.notifications import notify_cost

    notify_cost(5.50, "claude-opus-4-8", "alert", "MyProject")

    title, message = send_calls[0]
    assert title == "AgentGuard Alert"
    assert "5.50" in message
    assert "alert" in message
    assert sound_calls == ["alert"]


def test_notify_cost_critical_level(monkeypatch):
    send_calls = []
    sound_calls = []
    monkeypatch.setattr(
        "agentguard.notifications._send_notification", lambda t, m: send_calls.append((t, m))
    )
    monkeypatch.setattr("agentguard.notifications._play_sound", lambda lvl: sound_calls.append(lvl))

    from agentguard.notifications import notify_cost

    notify_cost(10.00, "claude-opus-4-8", "critical", "MyProject")

    title, message = send_calls[0]
    assert title == "AgentGuard Critical"
    assert "10.00" in message
    assert "critical" in message
    assert sound_calls == ["critical"]


# ── handle_stop integration helpers ──────────────────────────────────────────


def _make_session_log(tmp_path, session_id="s1"):
    log = tmp_path / ".agentguard" / "session.log"
    log.parent.mkdir(exist_ok=True)
    log.write_text(
        json.dumps(
            {
                "event": "post_tool_use",
                "tool": "Bash",
                "tool_use_id": "t1",
                "session_id": session_id,
            }
        )
        + "\n"
    )
    return log


def _make_transcript(tmp_path, input_tokens=100, output_tokens=50):
    transcript = tmp_path / "session.jsonl"
    transcript.write_text(
        _transcript_msg("msg_001", "claude-sonnet-4-6", input_tokens, output_tokens) + "\n"
    )
    return transcript


def _patch_cost_and_notify(monkeypatch):
    notify_calls = []
    monkeypatch.setattr("agentguard.checks.cost._fetch_text", lambda url: SAMPLE_MARKDOWN_TABLE)
    monkeypatch.setattr(
        "agentguard.notifications._send_notification", lambda t, m: notify_calls.append((t, m))
    )
    monkeypatch.setattr("agentguard.notifications._play_sound", lambda lvl: None)
    return notify_calls


def _patch_cost_fixed(monkeypatch, total_usd: float):
    """Patch calculate_session_cost to return a fixed total_usd value."""
    notify_calls = []
    monkeypatch.setattr(
        "agentguard.checks.cost.calculate_session_cost",
        lambda path, pricing: {
            "model": "claude-sonnet-4-6",
            "input_tokens": 0,
            "cache_write_5m_tokens": 0,
            "cache_write_1h_tokens": 0,
            "cache_read_tokens": 0,
            "output_tokens": 0,
            "total_usd": total_usd,
            "pricing_source": "fallback",
        },
    )
    monkeypatch.setattr("agentguard.checks.cost._fetch_text", lambda url: SAMPLE_MARKDOWN_TABLE)
    monkeypatch.setattr(
        "agentguard.notifications._send_notification", lambda t, m: notify_calls.append((t, m))
    )
    monkeypatch.setattr("agentguard.notifications._play_sound", lambda lvl: None)
    return notify_calls


def _new_schema_yaml(thresholds, repeat_last=True, repeat_interval=2.0):
    lines = ["owner: Alice", "cost_awareness:", "  thresholds:"]
    for t in thresholds:
        lines.append(f"    - at_usd: {t['at_usd']}")
        lines.append(f"      level: {t['level']}")
    lines.append(f"  repeat_last_threshold: {'true' if repeat_last else 'false'}")
    lines.append(f"  repeat_interval_usd: {repeat_interval}")
    return "\n".join(lines) + "\n"


# ── handle_stop: basic cost logging ──────────────────────────────────────────


def test_handle_stop_cost_below_threshold_no_notification(tmp_path, monkeypatch):
    (tmp_path / "governance.yaml").write_text(
        _new_schema_yaml([{"at_usd": 100.0, "level": "warn"}])
    )
    _make_session_log(tmp_path)
    transcript = _make_transcript(tmp_path, input_tokens=10, output_tokens=5)
    notify_calls = _patch_cost_and_notify(monkeypatch)

    from agentguard.enforcement.enforcer import handle_stop

    handle_stop({"session_id": "s1", "transcript_path": str(transcript)}, str(tmp_path))

    assert notify_calls == []


def test_handle_stop_no_cost_awareness_no_notification(tmp_path, monkeypatch):
    (tmp_path / "governance.yaml").write_text("owner: Alice\n")
    _make_session_log(tmp_path)
    transcript = _make_transcript(tmp_path, input_tokens=1_000_000, output_tokens=500_000)
    notify_calls = _patch_cost_and_notify(monkeypatch)

    from agentguard.enforcement.enforcer import handle_stop

    handle_stop({"session_id": "s1", "transcript_path": str(transcript)}, str(tmp_path))

    assert notify_calls == []


def test_handle_stop_session_cost_entry_written_to_log(tmp_path, monkeypatch):
    (tmp_path / "governance.yaml").write_text("owner: Alice\n")
    session_log = _make_session_log(tmp_path)
    transcript = _make_transcript(tmp_path, input_tokens=1000, output_tokens=500)
    _patch_cost_and_notify(monkeypatch)

    from agentguard.enforcement.enforcer import handle_stop

    handle_stop({"session_id": "s1", "transcript_path": str(transcript)}, str(tmp_path))

    entries = [json.loads(line) for line in session_log.read_text().splitlines() if line.strip()]
    cost_entries = [e for e in entries if e.get("event") == "session_cost"]
    assert len(cost_entries) == 1
    entry = cost_entries[0]
    assert entry["session_id"] == "s1"
    assert entry["model"] == "claude-sonnet-4-6"
    assert entry["total_usd"] > 0
    assert "input_tokens" in entry
    assert "cache_write_5m_tokens" in entry
    assert "cache_write_1h_tokens" in entry
    assert "cache_read_tokens" in entry
    assert "output_tokens" in entry
    assert entry["pricing_source"] in ("live", "fallback")


def test_handle_stop_no_transcript_no_cost_entry(tmp_path, monkeypatch):
    (tmp_path / "governance.yaml").write_text("owner: Alice\n")
    session_log = _make_session_log(tmp_path)
    _patch_cost_and_notify(monkeypatch)

    from agentguard.enforcement.enforcer import handle_stop

    handle_stop({"session_id": "s1", "transcript_path": ""}, str(tmp_path))

    entries = [json.loads(line) for line in session_log.read_text().splitlines() if line.strip()]
    cost_entries = [e for e in entries if e.get("event") == "session_cost"]
    assert cost_entries == []


# ── handle_stop: old schema backward compat ──────────────────────────────────


def test_handle_stop_old_schema_warn_fires(tmp_path, monkeypatch):
    """Old warn_at_usd/alert_at_usd schema auto-converts; warn fires when cost exceeds it."""
    (tmp_path / "governance.yaml").write_text(
        "owner: Alice\ncost_awareness:\n  warn_at_usd: 0.00001\n  alert_at_usd: 500.00\n"
    )
    _make_session_log(tmp_path)
    transcript = _make_transcript(tmp_path, input_tokens=10_000, output_tokens=5_000)
    notify_calls = _patch_cost_and_notify(monkeypatch)

    from agentguard.enforcement.enforcer import handle_stop

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        handle_stop({"session_id": "s1", "transcript_path": str(transcript)}, str(tmp_path))

    assert len(notify_calls) == 1
    assert "Warning" in notify_calls[0][0]


def test_handle_stop_old_schema_alert_fires_both_thresholds(tmp_path, monkeypatch):
    """Old schema with both thresholds crossed fires both warn and alert notifications."""
    (tmp_path / "governance.yaml").write_text(
        "owner: Alice\ncost_awareness:\n  warn_at_usd: 0.00001\n  alert_at_usd: 0.00002\n"
    )
    _make_session_log(tmp_path)
    transcript = _make_transcript(tmp_path, input_tokens=10_000, output_tokens=5_000)
    notify_calls = _patch_cost_and_notify(monkeypatch)

    from agentguard.enforcement.enforcer import handle_stop

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        handle_stop({"session_id": "s1", "transcript_path": str(transcript)}, str(tmp_path))

    # Both warn and alert cross; multi-threshold fires both
    assert len(notify_calls) == 2
    titles = {c[0] for c in notify_calls}
    assert "AgentGuard Warning" in titles
    assert "AgentGuard Alert" in titles


# ── handle_stop: multi-threshold escalation (sentinel scenario) ───────────────


def test_handle_stop_first_crossing_warn_fires_sentinel_written(tmp_path, monkeypatch):
    """First crossing of $0.50 → warn fires; sentinel at at_usd=0.50 written to log."""
    (tmp_path / "governance.yaml").write_text(
        _new_schema_yaml(
            [
                {"at_usd": 0.50, "level": "warn"},
                {"at_usd": 2.00, "level": "alert"},
                {"at_usd": 5.00, "level": "critical"},
            ]
        )
    )
    session_log = _make_session_log(tmp_path)
    notify_calls = _patch_cost_fixed(monkeypatch, 0.60)

    from agentguard.enforcement.enforcer import handle_stop

    handle_stop({"session_id": "s1", "transcript_path": str(tmp_path / "t.jsonl")}, str(tmp_path))

    assert len(notify_calls) == 1
    assert "Warning" in notify_calls[0][0]

    entries = [json.loads(line) for line in session_log.read_text().splitlines() if line.strip()]
    sentinels = [e for e in entries if e.get("event") == "session_cost_notified"]
    assert len(sentinels) == 1
    assert sentinels[0]["at_usd"] == 0.50
    assert sentinels[0]["level"] == "warn"


def test_handle_stop_same_session_cost_same_no_repeat(tmp_path, monkeypatch):
    """Second stop with same cost → sentinel already present → no duplicate notification."""
    (tmp_path / "governance.yaml").write_text(_new_schema_yaml([{"at_usd": 0.50, "level": "warn"}]))
    log = tmp_path / ".agentguard" / "session.log"
    log.parent.mkdir(exist_ok=True)
    log.write_text(
        json.dumps(
            {"event": "post_tool_use", "tool": "Bash", "tool_use_id": "t1", "session_id": "s1"}
        )
        + "\n"
        + json.dumps(
            {"event": "session_cost_notified", "session_id": "s1", "at_usd": 0.50, "level": "warn"}
        )
        + "\n"
    )
    notify_calls = _patch_cost_fixed(monkeypatch, 0.60)

    from agentguard.enforcement.enforcer import handle_stop

    handle_stop({"session_id": "s1", "transcript_path": str(tmp_path / "t.jsonl")}, str(tmp_path))

    assert notify_calls == []


def test_handle_stop_cost_rises_to_alert(tmp_path, monkeypatch):
    """Cost rises to $2.00 → alert fires; warn already in notified."""
    (tmp_path / "governance.yaml").write_text(
        _new_schema_yaml(
            [
                {"at_usd": 0.50, "level": "warn"},
                {"at_usd": 2.00, "level": "alert"},
                {"at_usd": 5.00, "level": "critical"},
            ]
        )
    )
    log = tmp_path / ".agentguard" / "session.log"
    log.parent.mkdir(exist_ok=True)
    log.write_text(
        json.dumps(
            {"event": "post_tool_use", "tool": "Bash", "tool_use_id": "t1", "session_id": "s1"}
        )
        + "\n"
        + json.dumps(
            {"event": "session_cost_notified", "session_id": "s1", "at_usd": 0.50, "level": "warn"}
        )
        + "\n"
    )
    notify_calls = _patch_cost_fixed(monkeypatch, 2.10)

    from agentguard.enforcement.enforcer import handle_stop

    handle_stop({"session_id": "s1", "transcript_path": str(tmp_path / "t.jsonl")}, str(tmp_path))

    assert len(notify_calls) == 1
    assert "Alert" in notify_calls[0][0]


def test_handle_stop_cost_rises_to_critical(tmp_path, monkeypatch):
    """Cost rises to $5.00 → critical fires; warn + alert already notified."""
    (tmp_path / "governance.yaml").write_text(
        _new_schema_yaml(
            [
                {"at_usd": 0.50, "level": "warn"},
                {"at_usd": 2.00, "level": "alert"},
                {"at_usd": 5.00, "level": "critical"},
            ]
        )
    )
    log = tmp_path / ".agentguard" / "session.log"
    log.parent.mkdir(exist_ok=True)
    log.write_text(
        json.dumps(
            {"event": "post_tool_use", "tool": "Bash", "tool_use_id": "t1", "session_id": "s1"}
        )
        + "\n"
        + json.dumps(
            {"event": "session_cost_notified", "session_id": "s1", "at_usd": 0.50, "level": "warn"}
        )
        + "\n"
        + json.dumps(
            {"event": "session_cost_notified", "session_id": "s1", "at_usd": 2.00, "level": "alert"}
        )
        + "\n"
    )
    notify_calls = _patch_cost_fixed(monkeypatch, 5.20)

    from agentguard.enforcement.enforcer import handle_stop

    handle_stop({"session_id": "s1", "transcript_path": str(tmp_path / "t.jsonl")}, str(tmp_path))

    assert len(notify_calls) == 1
    assert "Critical" in notify_calls[0][0]


def test_handle_stop_repeat_critical_fires_at_7(tmp_path, monkeypatch):
    """Cost rises to $7.00 → repeat critical fires (5.00 + 2.00); sentinel at $7.00 written."""
    (tmp_path / "governance.yaml").write_text(
        _new_schema_yaml(
            [
                {"at_usd": 0.50, "level": "warn"},
                {"at_usd": 2.00, "level": "alert"},
                {"at_usd": 5.00, "level": "critical"},
            ],
            repeat_last=True,
            repeat_interval=2.0,
        )
    )
    log = tmp_path / ".agentguard" / "session.log"
    log.parent.mkdir(exist_ok=True)
    log.write_text(
        json.dumps(
            {"event": "post_tool_use", "tool": "Bash", "tool_use_id": "t1", "session_id": "s1"}
        )
        + "\n"
        + json.dumps(
            {"event": "session_cost_notified", "session_id": "s1", "at_usd": 0.50, "level": "warn"}
        )
        + "\n"
        + json.dumps(
            {"event": "session_cost_notified", "session_id": "s1", "at_usd": 2.00, "level": "alert"}
        )
        + "\n"
        + json.dumps(
            {
                "event": "session_cost_notified",
                "session_id": "s1",
                "at_usd": 5.00,
                "level": "critical",
            }
        )
        + "\n"
    )
    notify_calls = _patch_cost_fixed(monkeypatch, 7.10)

    from agentguard.enforcement.enforcer import handle_stop

    session_log = tmp_path / ".agentguard" / "session.log"
    handle_stop({"session_id": "s1", "transcript_path": str(tmp_path / "t.jsonl")}, str(tmp_path))

    assert len(notify_calls) == 1
    assert "Critical" in notify_calls[0][0]

    entries = [json.loads(line) for line in session_log.read_text().splitlines() if line.strip()]
    sentinels = [
        e
        for e in entries
        if e.get("event") == "session_cost_notified" and e.get("session_id") == "s1"
    ]
    new_sentinel = [s for s in sentinels if s.get("at_usd") == 7.0]
    assert len(new_sentinel) == 1


def test_handle_stop_repeat_critical_fires_at_9(tmp_path, monkeypatch):
    """Cost rises to $9.00 → repeat critical fires again ($7.00 + 2.00)."""
    (tmp_path / "governance.yaml").write_text(
        _new_schema_yaml(
            [
                {"at_usd": 0.50, "level": "warn"},
                {"at_usd": 2.00, "level": "alert"},
                {"at_usd": 5.00, "level": "critical"},
            ],
            repeat_last=True,
            repeat_interval=2.0,
        )
    )
    log = tmp_path / ".agentguard" / "session.log"
    log.parent.mkdir(exist_ok=True)
    log.write_text(
        json.dumps(
            {"event": "post_tool_use", "tool": "Bash", "tool_use_id": "t1", "session_id": "s1"}
        )
        + "\n"
        + json.dumps(
            {"event": "session_cost_notified", "session_id": "s1", "at_usd": 0.50, "level": "warn"}
        )
        + "\n"
        + json.dumps(
            {"event": "session_cost_notified", "session_id": "s1", "at_usd": 2.00, "level": "alert"}
        )
        + "\n"
        + json.dumps(
            {
                "event": "session_cost_notified",
                "session_id": "s1",
                "at_usd": 5.00,
                "level": "critical",
            }
        )
        + "\n"
        + json.dumps(
            {
                "event": "session_cost_notified",
                "session_id": "s1",
                "at_usd": 7.00,
                "level": "critical",
            }
        )
        + "\n"
    )
    notify_calls = _patch_cost_fixed(monkeypatch, 9.10)

    from agentguard.enforcement.enforcer import handle_stop

    handle_stop({"session_id": "s1", "transcript_path": str(tmp_path / "t.jsonl")}, str(tmp_path))

    assert len(notify_calls) == 1
    assert "Critical" in notify_calls[0][0]


def test_handle_stop_repeat_not_triggered_below_next_interval(tmp_path, monkeypatch):
    """Cost at $6.00 does not trigger repeat (next is $7.00 = 5.00 + 2.00)."""
    (tmp_path / "governance.yaml").write_text(
        _new_schema_yaml([{"at_usd": 5.00, "level": "critical"}], repeat_interval=2.0)
    )
    log = tmp_path / ".agentguard" / "session.log"
    log.parent.mkdir(exist_ok=True)
    log.write_text(
        json.dumps(
            {"event": "post_tool_use", "tool": "Bash", "tool_use_id": "t1", "session_id": "s1"}
        )
        + "\n"
        + json.dumps(
            {
                "event": "session_cost_notified",
                "session_id": "s1",
                "at_usd": 5.00,
                "level": "critical",
            }
        )
        + "\n"
    )
    notify_calls = _patch_cost_fixed(monkeypatch, 6.00)

    from agentguard.enforcement.enforcer import handle_stop

    handle_stop({"session_id": "s1", "transcript_path": str(tmp_path / "t.jsonl")}, str(tmp_path))

    assert notify_calls == []


def test_handle_stop_different_session_does_not_share_sentinels(tmp_path, monkeypatch):
    """Sentinels from s1 do not suppress notifications for s2."""
    (tmp_path / "governance.yaml").write_text(
        _new_schema_yaml([{"at_usd": 0.001, "level": "warn"}, {"at_usd": 500.0, "level": "alert"}])
    )
    log = tmp_path / ".agentguard" / "session.log"
    log.parent.mkdir(exist_ok=True)
    log.write_text(
        json.dumps(
            {"event": "post_tool_use", "tool": "Bash", "tool_use_id": "t1", "session_id": "s2"}
        )
        + "\n"
        + json.dumps(
            {"event": "session_cost_notified", "session_id": "s1", "at_usd": 0.001, "level": "warn"}
        )
        + "\n"
    )
    notify_calls = _patch_cost_fixed(monkeypatch, 0.10)

    from agentguard.enforcement.enforcer import handle_stop

    handle_stop({"session_id": "s2", "transcript_path": str(tmp_path / "t.jsonl")}, str(tmp_path))

    assert len(notify_calls) == 1
    assert "Warning" in notify_calls[0][0]


# ── _get_notified_thresholds ──────────────────────────────────────────────────


def test_get_notified_thresholds_empty_when_no_sentinels(tmp_path):
    from agentguard.enforcement.enforcer import _get_notified_thresholds

    log = tmp_path / ".agentguard" / "session.log"
    log.parent.mkdir()
    log.write_text(json.dumps({"event": "session_cost", "session_id": "s1"}) + "\n")
    assert _get_notified_thresholds(log, "s1") == set()


def test_get_notified_thresholds_returns_at_usd_set(tmp_path):
    from agentguard.enforcement.enforcer import _get_notified_thresholds

    log = tmp_path / ".agentguard" / "session.log"
    log.parent.mkdir()
    log.write_text(
        json.dumps(
            {"event": "session_cost_notified", "session_id": "s1", "at_usd": 0.50, "level": "warn"}
        )
        + "\n"
        + json.dumps(
            {"event": "session_cost_notified", "session_id": "s1", "at_usd": 2.00, "level": "alert"}
        )
        + "\n"
    )
    assert _get_notified_thresholds(log, "s1") == {0.50, 2.00}


def test_get_notified_thresholds_ignores_other_sessions(tmp_path):
    from agentguard.enforcement.enforcer import _get_notified_thresholds

    log = tmp_path / ".agentguard" / "session.log"
    log.parent.mkdir()
    log.write_text(
        json.dumps(
            {"event": "session_cost_notified", "session_id": "s1", "at_usd": 0.50, "level": "warn"}
        )
        + "\n"
    )
    assert _get_notified_thresholds(log, "s2") == set()


def test_get_notified_thresholds_ignores_entries_without_at_usd(tmp_path):
    from agentguard.enforcement.enforcer import _get_notified_thresholds

    log = tmp_path / ".agentguard" / "session.log"
    log.parent.mkdir()
    # Old-format sentinel without at_usd field
    log.write_text(
        json.dumps({"event": "session_cost_notified", "session_id": "s1", "level": "warn"}) + "\n"
    )
    assert _get_notified_thresholds(log, "s1") == set()


def test_get_notified_thresholds_missing_file(tmp_path):
    from agentguard.enforcement.enforcer import _get_notified_thresholds

    assert _get_notified_thresholds(tmp_path / ".agentguard" / "nonexistent.log", "s1") == set()


# ── load_cost_awareness: new schema ──────────────────────────────────────────


def test_load_cost_awareness_absent():
    from agentguard.config.loader import load_cost_awareness

    assert load_cost_awareness({}) is None


def test_load_cost_awareness_valid_new_schema():
    from agentguard.config.loader import load_cost_awareness

    result = load_cost_awareness(
        {
            "cost_awareness": {
                "thresholds": [
                    {"at_usd": 0.50, "level": "warn"},
                    {"at_usd": 2.00, "level": "alert"},
                    {"at_usd": 5.00, "level": "critical"},
                ],
                "repeat_last_threshold": True,
                "repeat_interval_usd": 2.0,
            }
        }
    )
    assert result is not None
    assert len(result["thresholds"]) == 3
    assert result["thresholds"][0] == {"at_usd": 0.50, "level": "warn"}
    assert result["thresholds"][2] == {"at_usd": 5.00, "level": "critical"}
    assert result["repeat_last_threshold"] is True
    assert result["repeat_interval_usd"] == 2.0


def test_load_cost_awareness_defaults_applied():
    from agentguard.config.loader import load_cost_awareness

    result = load_cost_awareness(
        {"cost_awareness": {"thresholds": [{"at_usd": 1.0, "level": "warn"}]}}
    )
    assert result["repeat_last_threshold"] is True
    assert result["repeat_interval_usd"] == 2.0


def test_load_cost_awareness_old_schema_auto_converted(recwarn):
    from agentguard.config.loader import load_cost_awareness

    result = load_cost_awareness({"cost_awareness": {"warn_at_usd": 1.0, "alert_at_usd": 5.0}})
    assert result is not None
    assert len(result["thresholds"]) == 2
    assert result["thresholds"][0] == {"at_usd": 1.0, "level": "warn"}
    assert result["thresholds"][1] == {"at_usd": 5.0, "level": "alert"}
    # deprecation warning must be emitted
    dep_warnings = [w for w in recwarn.list if issubclass(w.category, DeprecationWarning)]
    assert dep_warnings, "expected DeprecationWarning for old schema"


def test_load_cost_awareness_old_schema_only_warn(recwarn):
    from agentguard.config.loader import load_cost_awareness

    result = load_cost_awareness({"cost_awareness": {"warn_at_usd": 1.0}})
    assert len(result["thresholds"]) == 1
    assert result["thresholds"][0]["level"] == "warn"


def test_load_cost_awareness_old_schema_warn_gte_alert_raises():
    from agentguard.config.loader import GovernanceConfigError, load_cost_awareness

    with pytest.raises(GovernanceConfigError, match="warn_at_usd"):
        load_cost_awareness({"cost_awareness": {"warn_at_usd": 5.0, "alert_at_usd": 1.0}})


def test_load_cost_awareness_old_schema_equal_thresholds_raises():
    from agentguard.config.loader import GovernanceConfigError, load_cost_awareness

    with pytest.raises(GovernanceConfigError, match="warn_at_usd"):
        load_cost_awareness({"cost_awareness": {"warn_at_usd": 1.0, "alert_at_usd": 1.0}})


def test_load_cost_awareness_non_ascending_raises():
    from agentguard.config.loader import GovernanceConfigError, load_cost_awareness

    with pytest.raises(GovernanceConfigError, match="strictly ascending"):
        load_cost_awareness(
            {
                "cost_awareness": {
                    "thresholds": [
                        {"at_usd": 5.0, "level": "warn"},
                        {"at_usd": 1.0, "level": "alert"},
                    ]
                }
            }
        )


def test_load_cost_awareness_equal_at_usd_raises():
    from agentguard.config.loader import GovernanceConfigError, load_cost_awareness

    with pytest.raises(GovernanceConfigError, match="strictly ascending"):
        load_cost_awareness(
            {
                "cost_awareness": {
                    "thresholds": [
                        {"at_usd": 1.0, "level": "warn"},
                        {"at_usd": 1.0, "level": "alert"},
                    ]
                }
            }
        )


def test_load_cost_awareness_repeat_interval_zero_raises():
    from agentguard.config.loader import GovernanceConfigError, load_cost_awareness

    with pytest.raises(GovernanceConfigError, match="repeat_interval_usd"):
        load_cost_awareness(
            {
                "cost_awareness": {
                    "thresholds": [{"at_usd": 1.0, "level": "warn"}],
                    "repeat_last_threshold": True,
                    "repeat_interval_usd": 0,
                }
            }
        )


def test_load_cost_awareness_repeat_interval_negative_raises():
    from agentguard.config.loader import GovernanceConfigError, load_cost_awareness

    with pytest.raises(GovernanceConfigError, match="repeat_interval_usd"):
        load_cost_awareness(
            {
                "cost_awareness": {
                    "thresholds": [{"at_usd": 1.0, "level": "warn"}],
                    "repeat_last_threshold": True,
                    "repeat_interval_usd": -1.0,
                }
            }
        )


def test_load_cost_awareness_repeat_interval_zero_allowed_when_repeat_disabled():
    from agentguard.config.loader import load_cost_awareness

    result = load_cost_awareness(
        {
            "cost_awareness": {
                "thresholds": [{"at_usd": 1.0, "level": "warn"}],
                "repeat_last_threshold": False,
                "repeat_interval_usd": 0,
            }
        }
    )
    assert result is not None
    assert result["repeat_last_threshold"] is False


def test_load_cost_awareness_not_mapping_raises():
    from agentguard.config.loader import GovernanceConfigError, load_cost_awareness

    with pytest.raises(GovernanceConfigError, match="mapping"):
        load_cost_awareness({"cost_awareness": "1.0"})


def test_load_cost_awareness_empty_thresholds_raises():
    from agentguard.config.loader import GovernanceConfigError, load_cost_awareness

    with pytest.raises(GovernanceConfigError, match="non-empty"):
        load_cost_awareness({"cost_awareness": {"thresholds": []}})


def test_load_cost_awareness_at_usd_zero_raises():
    from agentguard.config.loader import GovernanceConfigError, load_cost_awareness

    with pytest.raises(GovernanceConfigError, match="must be > 0"):
        load_cost_awareness({"cost_awareness": {"thresholds": [{"at_usd": 0.0, "level": "warn"}]}})


# ── check_cost_awareness ──────────────────────────────────────────────────────


def test_check_cost_awareness_absent():
    from agentguard.checks.preflight import check_cost_awareness

    f = check_cost_awareness({})
    assert f.severity == "info"
    assert "cost_awareness" in f.message.lower()


def test_check_cost_awareness_valid_new_schema():
    from agentguard.checks.preflight import check_cost_awareness

    f = check_cost_awareness(
        {
            "cost_awareness": {
                "thresholds": [
                    {"at_usd": 0.50, "level": "warn"},
                    {"at_usd": 2.00, "level": "alert"},
                    {"at_usd": 5.00, "level": "critical"},
                ],
                "repeat_last_threshold": True,
                "repeat_interval_usd": 2.0,
            }
        }
    )
    assert f.severity == "ok"
    assert "3 threshold" in f.message
    assert "2.00" in f.message


def test_check_cost_awareness_valid_old_schema_auto_converts():
    from agentguard.checks.preflight import check_cost_awareness

    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        f = check_cost_awareness({"cost_awareness": {"warn_at_usd": 1.0, "alert_at_usd": 5.0}})
    assert f.severity == "ok"
    assert "2 threshold" in f.message


def test_check_cost_awareness_invalid_raises_critical():
    from agentguard.checks.preflight import check_cost_awareness

    f = check_cost_awareness({"cost_awareness": {"thresholds": []}})
    assert f.severity == "critical"


def test_check_cost_awareness_warn_gt_alert_old_schema():
    from agentguard.checks.preflight import check_cost_awareness

    f = check_cost_awareness({"cost_awareness": {"warn_at_usd": 5.0, "alert_at_usd": 1.0}})
    assert f.severity == "critical"
    assert "warn_at_usd" in f.message


# ── init guided: cost awareness step ─────────────────────────────────────────


def test_run_cost_awareness_step_produces_valid_block(monkeypatch):
    """Confirming thresholds and interval produces a valid _cost_awareness entry."""
    import agentguard.cli as cli_mod

    inputs = iter(["y", "0.50, 2.00, 5.00", "2.00"])
    monkeypatch.setattr("click.prompt", lambda *a, **kw: next(inputs))

    results = {}
    cli_mod._run_cost_awareness_step(results)

    ca = results.get("_cost_awareness")
    assert ca is not None
    assert len(ca["thresholds"]) == 3
    assert ca["thresholds"][0] == {"at_usd": 0.50, "level": "warn"}
    assert ca["thresholds"][1] == {"at_usd": 2.00, "level": "alert"}
    assert ca["thresholds"][2] == {"at_usd": 5.00, "level": "critical"}
    assert ca["repeat_last_threshold"] is True
    assert ca["repeat_interval_usd"] == 2.00


def test_run_cost_awareness_step_skipped_when_no(monkeypatch):
    """Answering 'n' leaves no _cost_awareness key in results."""
    import agentguard.cli as cli_mod

    monkeypatch.setattr("click.prompt", lambda *a, **kw: "n")

    results = {}
    cli_mod._run_cost_awareness_step(results)

    assert "_cost_awareness" not in results


def test_run_cost_awareness_step_level_assignment(monkeypatch):
    """Levels are assigned: first=warn, second=alert, third+=critical."""
    import agentguard.cli as cli_mod

    inputs = iter(["y", "1.00, 3.00, 6.00, 10.00", "2.00"])
    monkeypatch.setattr("click.prompt", lambda *a, **kw: next(inputs))

    results = {}
    cli_mod._run_cost_awareness_step(results)

    ca = results["_cost_awareness"]
    levels = [t["level"] for t in ca["thresholds"]]
    assert levels == ["warn", "alert", "critical", "critical"]
