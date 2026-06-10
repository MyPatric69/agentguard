"""Tests for agentguard/ai_review.py."""

from __future__ import annotations

from unittest import mock

import pytest

from agentguard.ai_review import _get_env, review_scope

# ── Provider detection ────────────────────────────────────────────────────────

def test_provider_detection_anthropic(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_BASE_URL", raising=False)
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    provider, api_key, base_url, model = _get_env()
    assert provider == "anthropic"
    assert api_key == "sk-test"
    assert base_url is None
    assert model is None


def test_provider_detection_openai(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "openai")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-openai-test")
    monkeypatch.delenv("AGENTGUARD_AI_BASE_URL", raising=False)
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    provider, api_key, _, _ = _get_env()
    assert provider == "openai"
    assert api_key == "sk-openai-test"


def test_provider_detection_with_model_override(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.setenv("AGENTGUARD_AI_MODEL", "claude-opus-4-8")
    monkeypatch.delenv("AGENTGUARD_AI_BASE_URL", raising=False)
    _, _, _, model = _get_env()
    assert model == "claude-opus-4-8"


def test_provider_detection_openai_compatible_with_base_url(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "openai-compatible")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "key")
    monkeypatch.setenv("AGENTGUARD_AI_BASE_URL", "https://my-endpoint/v1")
    monkeypatch.setenv("AGENTGUARD_AI_MODEL", "custom-model")
    provider, _, base_url, model = _get_env()
    assert provider == "openai-compatible"
    assert base_url == "https://my-endpoint/v1"
    assert model == "custom-model"


# ── No env vars — graceful skip ───────────────────────────────────────────────

def test_no_env_vars_returns_none(monkeypatch, capsys):
    monkeypatch.delenv("AGENTGUARD_AI_PROVIDER", raising=False)
    monkeypatch.delenv("AGENTGUARD_AI_API_KEY", raising=False)
    result = review_scope("read files", "no writes", "any deletion")
    assert result is None
    captured = capsys.readouterr()
    assert "No provider" in captured.out or "no provider" in captured.out.lower()


def test_no_provider_returns_none(monkeypatch, capsys):
    monkeypatch.delenv("AGENTGUARD_AI_PROVIDER", raising=False)
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    result = review_scope("authorized", "prohibited", "confirmation")
    assert result is None


def test_no_api_key_returns_none(monkeypatch, capsys):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.delenv("AGENTGUARD_AI_API_KEY", raising=False)
    result = review_scope("authorized", "prohibited", "confirmation")
    assert result is None


def test_no_env_does_not_raise(monkeypatch):
    monkeypatch.delenv("AGENTGUARD_AI_PROVIDER", raising=False)
    monkeypatch.delenv("AGENTGUARD_AI_API_KEY", raising=False)
    try:
        review_scope("authorized", "prohibited", "confirmation")
    except Exception as exc:
        pytest.fail(f"review_scope raised unexpectedly: {exc}")


# ── API failure — warning printed, returns None ───────────────────────────────

def test_api_failure_returns_none(monkeypatch, capsys):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    with mock.patch("agentguard.ai_review._call_provider", side_effect=Exception("network error")):
        result = review_scope("authorized", "prohibited", "confirmation")
    assert result is None
    captured = capsys.readouterr()
    assert "API call failed" in captured.out


def test_api_failure_does_not_raise(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    with mock.patch("agentguard.ai_review._call_provider", side_effect=RuntimeError("boom")):
        try:
            review_scope("authorized", "prohibited", "confirmation")
        except Exception as exc:
            pytest.fail(f"review_scope raised unexpectedly: {exc}")


# ── Markdown fence stripping ──────────────────────────────────────────────────

def test_strip_fences_json_fenced_response(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    fenced = '```json\n{"score": 8, "verdict": "STRONG", "issues": [], "suggestion": "Good."}\n```'
    with mock.patch("agentguard.ai_review._call_provider", return_value=fenced):
        result = review_scope("authorized", "prohibited", "confirmation")
    assert result is not None
    assert result["score"] == 8
    assert result["verdict"] == "STRONG"


def test_strip_fences_plain_json_unchanged(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    plain = '{"score": 5, "verdict": "WEAK", "issues": ["too vague"], "suggestion": "Be specific."}'
    with mock.patch("agentguard.ai_review._call_provider", return_value=plain):
        result = review_scope("authorized", "prohibited", "confirmation")
    assert result is not None
    assert result["score"] == 5
    assert result["verdict"] == "WEAK"


# ── Invalid JSON — warning printed, returns None ──────────────────────────────

def test_invalid_json_returns_none(monkeypatch, capsys):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    with mock.patch("agentguard.ai_review._call_provider", return_value="not valid json {{"):
        result = review_scope("authorized", "prohibited", "confirmation")
    assert result is None
    captured = capsys.readouterr()
    assert "Invalid JSON" in captured.out


def test_invalid_json_shows_raw_response(monkeypatch, capsys):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    with mock.patch("agentguard.ai_review._call_provider", return_value="OOPS NOT JSON"):
        review_scope("authorized", "prohibited", "confirmation")
    captured = capsys.readouterr()
    assert "OOPS NOT JSON" in captured.out


# ── Score rendering — all four verdict levels ─────────────────────────────────

@pytest.mark.parametrize(
    "verdict,score",
    [
        ("STRONG", 9),
        ("ACCEPTABLE", 7),
        ("WEAK", 4),
        ("INSUFFICIENT", 2),
    ],
)
def test_render_ai_review_all_verdicts(verdict, score):
    from agentguard.output.renderer import render_ai_review

    result = {
        "_provider": "anthropic",
        "_model": "claude-haiku-4-5-20251001",
        "score": score,
        "verdict": verdict,
        "issues": ["Issue one", "Issue two"],
        "suggestion": "Add more specific boundaries.",
    }
    try:
        render_ai_review(result)
    except Exception as exc:
        pytest.fail(f"render_ai_review raised for {verdict}: {exc}")


def test_render_ai_review_empty_issues_and_suggestion():
    from agentguard.output.renderer import render_ai_review

    result = {
        "_provider": "openai",
        "_model": "gpt-4o-mini",
        "score": 8,
        "verdict": "STRONG",
        "issues": [],
        "suggestion": "",
    }
    render_ai_review(result)  # must not raise


# ── .env loading — env vars are read from environment ─────────────────────────

def test_env_vars_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anysphere")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "cursor-key")
    monkeypatch.delenv("AGENTGUARD_AI_BASE_URL", raising=False)
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    provider, api_key, _, _ = _get_env()
    assert provider == "anysphere"
    assert api_key == "cursor-key"


def test_valid_json_response_returns_result(monkeypatch):
    monkeypatch.setenv("AGENTGUARD_AI_PROVIDER", "anthropic")
    monkeypatch.setenv("AGENTGUARD_AI_API_KEY", "sk-test")
    monkeypatch.delenv("AGENTGUARD_AI_MODEL", raising=False)
    mock_response = (
        '{"score": 7, "verdict": "ACCEPTABLE", "issues": [], "suggestion": "Good scope."}'
    )
    with mock.patch("agentguard.ai_review._call_provider", return_value=mock_response):
        result = review_scope("authorized", "prohibited", "confirmation")
    assert result is not None
    assert result["score"] == 7
    assert result["verdict"] == "ACCEPTABLE"
    assert result["_provider"] == "anthropic"
    assert result["_model"] == "claude-haiku-4-5-20251001"


# ── dotenv loading ────────────────────────────────────────────────────────────

def test_load_dotenv_called_with_usecwd_true(tmp_path):
    from pathlib import Path

    from agentguard.ai_review import _load_env

    with mock.patch("agentguard.ai_review.find_dotenv", return_value="") as mock_find:
        with mock.patch("agentguard.ai_review.load_dotenv"):
            with mock.patch.object(Path, "home", return_value=tmp_path):
                _load_env()
    mock_find.assert_called_once_with(usecwd=True)


def test_global_config_loaded_when_no_project_env(tmp_path):
    """~/.agentguard/.env is loaded when no project .env is found."""
    from pathlib import Path

    from agentguard.ai_review import _load_env

    global_dir = tmp_path / ".agentguard"
    global_dir.mkdir()
    (global_dir / ".env").write_text("AGENTGUARD_AI_PROVIDER=anthropic\n")

    load_calls = []

    def fake_load(path, override=True):
        load_calls.append((str(path), override))

    with mock.patch("agentguard.ai_review.find_dotenv", return_value=""):
        with mock.patch("agentguard.ai_review.load_dotenv", side_effect=fake_load):
            with mock.patch.object(Path, "home", return_value=tmp_path):
                _load_env()

    assert len(load_calls) == 1
    assert str(global_dir / ".env") in load_calls[0][0]
    assert load_calls[0][1] is False


def test_project_env_overrides_global_config(tmp_path):
    """Project .env is loaded first; global config cannot override it (override=False)."""
    from pathlib import Path

    from agentguard.ai_review import _load_env

    global_dir = tmp_path / ".agentguard"
    global_dir.mkdir()
    (global_dir / ".env").write_text("AGENTGUARD_AI_API_KEY=global-key\n")

    project_env = tmp_path / "project.env"
    project_env.write_text("AGENTGUARD_AI_API_KEY=project-key\n")

    load_calls = []

    def fake_load(path, override=True):
        load_calls.append((str(path), override))

    with mock.patch("agentguard.ai_review.find_dotenv", return_value=str(project_env)):
        with mock.patch("agentguard.ai_review.load_dotenv", side_effect=fake_load):
            with mock.patch.object(Path, "home", return_value=tmp_path):
                _load_env()

    assert len(load_calls) == 2
    assert str(project_env) in load_calls[0][0]
    assert str(global_dir / ".env") in load_calls[1][0]
    assert load_calls[0][1] is False
    assert load_calls[1][1] is False
