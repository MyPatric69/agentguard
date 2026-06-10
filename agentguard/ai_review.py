"""
AI-powered scope quality review.
Supports: Anthropic, OpenAI, Anysphere (Cursor), and any OpenAI-compatible API.
Config via .env file or environment variables.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import find_dotenv, load_dotenv


def _load_env() -> None:
    project_env = find_dotenv(usecwd=True)
    if project_env:
        load_dotenv(project_env, override=False)

    global_env = Path.home() / ".agentguard" / ".env"
    if global_env.exists():
        load_dotenv(global_env, override=False)


_load_env()

_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-haiku-4-5-20251001",
    "openai": "gpt-4o-mini",
    "anysphere": "cursor-small",
}

_REVIEW_PROMPT = """\
You are an AI governance expert reviewing an agentic AI system's scope definition.
Evaluate the following scope for quality, specificity, and governance completeness.

Authorized actions: {authorized}
Prohibited actions: {prohibited}
Requires confirmation: {requires_confirmation}

Respond in JSON only, no markdown, no preamble:
{{
  "score": <1-10>,
  "verdict": "STRONG" | "ACCEPTABLE" | "WEAK" | "INSUFFICIENT",
  "issues": ["issue 1", "issue 2"],
  "suggestion": "one concrete improvement suggestion"
}}

Scoring guide:
1-3: INSUFFICIENT — too vague, missing boundaries, not actionable
4-5: WEAK — partial definition, significant gaps
6-7: ACCEPTABLE — usable but could be more specific
8-10: STRONG — clear, bounded, actionable"""


def _get_env() -> tuple[str | None, str | None, str | None, str | None]:
    provider = os.environ.get("AGENTGUARD_AI_PROVIDER")
    api_key = os.environ.get("AGENTGUARD_AI_API_KEY")
    base_url = os.environ.get("AGENTGUARD_AI_BASE_URL")
    model = os.environ.get("AGENTGUARD_AI_MODEL")
    return provider, api_key, base_url, model


def review_scope(authorized: str, prohibited: str, requires_confirmation: str) -> dict[str, Any] | None:
    """Run AI scope quality review. Returns result dict or None on failure/skip."""
    provider, api_key, base_url, model_override = _get_env()

    if not provider or not api_key:
        print("[AgentGuard AI Review] No provider/API key configured — skipping AI review.")
        print("  Set AGENTGUARD_AI_PROVIDER and AGENTGUARD_AI_API_KEY in .env or environment.")
        return None

    model = model_override or _DEFAULT_MODELS.get(provider)
    if not model:
        print(
            f"[AgentGuard AI Review] No model configured for provider '{provider}'"
            " — set AGENTGUARD_AI_MODEL."
        )
        return None

    prompt = _REVIEW_PROMPT.format(
        authorized=authorized or "(empty)",
        prohibited=prohibited or "(empty)",
        requires_confirmation=requires_confirmation or "(empty)",
    )

    try:
        raw = _call_provider(provider, api_key, base_url, model, prompt)
    except Exception as exc:
        print(f"[AgentGuard AI Review] API call failed: {exc}")
        return None

    text = _strip_fences(raw)
    try:
        result: dict[str, Any] = json.loads(text)
    except json.JSONDecodeError:
        print(f"[AgentGuard AI Review] Invalid JSON response: {raw[:200]}")
        return None

    result["_provider"] = provider
    result["_model"] = model
    return result


def _strip_fences(text: str) -> str:
    """Remove markdown code fences a model may wrap JSON in despite instructions."""
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def _call_provider(
    provider: str,
    api_key: str,
    base_url: str | None,
    model: str,
    prompt: str,
    max_tokens: int = 500,
    temperature: float | None = None,
) -> str:
    if provider == "anthropic":
        return _call_anthropic(api_key, model, prompt, max_tokens=max_tokens, temperature=temperature)
    if provider in ("openai", "anysphere", "openai-compatible"):
        return _call_openai_compat(api_key, base_url, model, prompt, max_tokens=max_tokens, temperature=temperature)
    raise ValueError(f"Unknown provider: {provider}")


def _call_anthropic(
    api_key: str, model: str, prompt: str, max_tokens: int = 500, temperature: float | None = None
) -> str:
    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic package not installed — run: pip install agentguard[ai]")

    client = anthropic.Anthropic(api_key=api_key)
    create_kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if temperature is not None:
        create_kwargs["temperature"] = temperature
    message = client.messages.create(**create_kwargs)
    return message.content[0].text


def _call_openai_compat(
    api_key: str,
    base_url: str | None,
    model: str,
    prompt: str,
    max_tokens: int = 500,
    temperature: float | None = None,
) -> str:
    try:
        import openai
    except ImportError:
        raise ImportError("openai package not installed — run: pip install agentguard[ai]")

    client_kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url

    client = openai.OpenAI(**client_kwargs)
    create_kwargs: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
    }
    if temperature is not None:
        create_kwargs["temperature"] = temperature
    response = client.chat.completions.create(**create_kwargs)
    return response.choices[0].message.content
