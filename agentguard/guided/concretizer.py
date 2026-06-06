"""
Guided Concretization — transforms vague intent into enforceable rules.
Uses AI provider (from .env) to concretize each governance field.
"""

from __future__ import annotations

import json
from typing import Any

from agentguard.ai_review import (
    _DEFAULT_MODELS,
    _call_provider,
    _get_env,
    _strip_fences,
)

_MISSION_PROMPT = """\
You are an AI governance expert helping define enforceable rules for an
autonomous AI agent. The user described the agent's mission:

"{user_input}"

Transform this into concrete, machine-enforceable governance rules.
Rules must be specific, measurable, and actionable — no vague terms.

Respond in JSON only, no markdown:
{{
  "authorized": "concrete text for scope.authorized — what the agent may do",
  "prohibited": "concrete text for scope.prohibited — what the agent must never do, using no/never language",
  "requires_confirmation": "concrete text for scope.requires_confirmation — actions needing human confirmation before execution",
  "enforcement_notes": "how AgentGuard enforces these rules technically",
  "confidence": "HIGH|MEDIUM|LOW",
  "ambiguities": ["remaining ambiguities if any"]
}}

Confidence: HIGH = fully concrete, MEDIUM = mostly concrete, LOW = still vague."""

_FIELD_PROMPT = """\
You are an AI governance expert helping define enforceable rules for an
autonomous AI agent. The user provided this intent:

Field: {field_name}
Input: "{user_input}"

Transform this into a concrete, machine-enforceable rule.
Rules must be specific, measurable, and actionable — no vague terms.

Respond in JSON only, no markdown:
{{
  "concretized": "concrete rule text ready for governance.yaml",
  "enforcement_notes": "how AgentGuard enforces this technically",
  "confidence": "HIGH|MEDIUM|LOW",
  "ambiguities": ["remaining ambiguities if any"]
}}

Confidence: HIGH = fully concrete, MEDIUM = mostly concrete, LOW = still vague."""


def _ai_available() -> bool:
    provider, api_key, _, _ = _get_env()
    return bool(provider and api_key)


def concretize_mission(user_input: str) -> dict[str, Any]:
    """Concretize mission description into authorized/prohibited/confirmation rules."""
    provider, api_key, base_url, model_override = _get_env()
    if not provider or not api_key:
        return _mission_fallback(user_input, "No AI provider configured")

    model = model_override or _DEFAULT_MODELS.get(provider)
    if not model:
        return _mission_fallback(user_input, "No model configured")

    prompt = _MISSION_PROMPT.format(user_input=user_input)
    try:
        raw = _call_provider(provider, api_key, base_url, model, prompt)
        result: dict[str, Any] = json.loads(_strip_fences(raw))
        result["_provider"] = provider
        result["_model"] = model
        return result
    except Exception as exc:
        return _mission_fallback(user_input, str(exc))


def concretize_field(field_name: str, user_input: str) -> dict[str, Any]:
    """Concretize a single governance field into an enforceable rule."""
    provider, api_key, base_url, model_override = _get_env()
    if not provider or not api_key:
        return _field_fallback(user_input, "No AI provider configured")

    model = model_override or _DEFAULT_MODELS.get(provider)
    if not model:
        return _field_fallback(user_input, "No model configured")

    prompt = _FIELD_PROMPT.format(field_name=field_name, user_input=user_input)
    try:
        raw = _call_provider(provider, api_key, base_url, model, prompt)
        result: dict[str, Any] = json.loads(_strip_fences(raw))
        result["_provider"] = provider
        result["_model"] = model
        return result
    except Exception as exc:
        return _field_fallback(user_input, str(exc))


def _mission_fallback(user_input: str, reason: str) -> dict[str, Any]:
    return {
        "authorized": user_input,
        "prohibited": "",
        "requires_confirmation": "",
        "confidence": "LOW",
        "ambiguities": [reason],
        "_fallback": True,
    }


def _field_fallback(user_input: str, reason: str) -> dict[str, Any]:
    return {
        "concretized": user_input,
        "enforcement_notes": "",
        "confidence": "LOW",
        "ambiguities": [reason],
        "_fallback": True,
    }
