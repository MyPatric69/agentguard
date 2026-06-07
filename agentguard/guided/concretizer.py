"""
Guided Concretization — transforms vague intent into enforceable rules.
Uses AI provider (from .env) to concretize each governance field.
"""

from __future__ import annotations

import json
import re
from typing import Any

from agentguard.ai_review import (
    _DEFAULT_MODELS,
    _call_provider,
    _get_env,
    _strip_fences,
)

_AUTO_REASON = "Extracted from governance definition — review and refine"

_MISSION_PROMPT = """\
You are an AI governance expert. Split this agent mission into structured
governance rules with action/reason for each item.

User intent: "{user_input}"

You MUST respond with exactly this JSON structure, no other format:
{{
  "authorized": [
    {{"action": "concrete action description", "reason": "why this action is authorized — business or technical rationale"}}
  ],
  "prohibited": [
    {{"action": "concrete prohibition", "reason": "why this is prohibited — risk or policy rationale", "severity": "HARD_LIMIT|CRITICAL|WARNING"}}
  ],
  "requires_confirmation": [
    {{"action": "action requiring confirmation", "reason": "why human confirmation is needed"}}
  ],
  "confidence": "HIGH|MEDIUM|LOW",
  "ambiguities": ["list any unclear points"]
}}

Rules:
- Be specific: file paths, command names, patterns — no vague terms
- authorized: positive permissions only, each with a clear business reason
- prohibited: hard blocks with risk rationale; use HARD_LIMIT for absolute prohibitions
- requires_confirmation: actions allowed but need human sign-off first
- No markdown, no preamble, JSON only"""

_HARD_LIMITS_PROMPT = """\
You are an AI governance expert. Convert these hard limits into structured prohibitions.

User input: "{user_input}"

Respond in JSON only, no markdown:
{{
  "prohibited": [
    {{"action": "concrete prohibition", "reason": "why this is prohibited — risk or policy rationale", "severity": "HARD_LIMIT"}}
  ],
  "confidence": "HIGH|MEDIUM|LOW",
  "ambiguities": ["remaining ambiguities if any"]
}}

All severity values MUST be "HARD_LIMIT". Be specific and actionable."""

# Sentence-level classifiers for Format B splitting
_PROHIBITED_RE = re.compile(r"\b(not|never|deny|block|must\s+not)\b", re.IGNORECASE)
_CONFIRMATION_RE = re.compile(r"\b(confirmation|approval|human)\b", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _ai_available() -> bool:
    provider, api_key, _, _ = _get_env()
    return bool(provider and api_key)


def _normalize_items(items: Any, default_severity: str | None = None) -> list[dict]:
    """Normalize scope items to structured list format — handles string and list inputs."""
    if isinstance(items, list):
        result = []
        for item in items:
            if isinstance(item, dict) and item.get("action"):
                result.append(item)
            elif isinstance(item, str) and item:
                entry: dict = {"action": item, "reason": _AUTO_REASON}
                if default_severity:
                    entry["severity"] = default_severity
                result.append(entry)
        return result
    if isinstance(items, str) and items:
        entry = {"action": items, "reason": _AUTO_REASON}
        if default_severity:
            entry["severity"] = default_severity
        return [entry]
    return []


def _split_mission_concretized(text: str) -> tuple[list[dict], list[dict], list[dict]]:
    """Split a single-field concretized text into structured (authorized, prohibited, confirmation) items.

    Checks confirmation keywords first so sentences like "cannot proceed without
    human confirmation" are not misclassified as prohibited.
    """
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if not sentences:
        return [{"action": text, "reason": _AUTO_REASON}], [], []

    authorized_parts: list[str] = []
    prohibited_parts: list[str] = []
    confirmation_parts: list[str] = []

    for sentence in sentences:
        if _CONFIRMATION_RE.search(sentence):
            confirmation_parts.append(sentence)
        elif _PROHIBITED_RE.search(sentence):
            prohibited_parts.append(sentence)
        else:
            authorized_parts.append(sentence)

    authorized = [{"action": s, "reason": _AUTO_REASON} for s in authorized_parts] or [{"action": text, "reason": _AUTO_REASON}]
    prohibited = [{"action": s, "reason": _AUTO_REASON, "severity": "WARNING"} for s in prohibited_parts]
    confirmation = [{"action": s, "reason": _AUTO_REASON} for s in confirmation_parts]

    return authorized, prohibited, confirmation


def concretize_mission(user_input: str) -> dict[str, Any]:
    """Concretize mission description into structured authorized/prohibited/confirmation rules."""
    provider, api_key, base_url, model_override = _get_env()
    if not provider or not api_key:
        return _mission_fallback(user_input, "No AI provider configured")

    model = model_override or _DEFAULT_MODELS.get(provider)
    if not model:
        return _mission_fallback(user_input, "No model configured")

    prompt = _MISSION_PROMPT.format(user_input=user_input)
    try:
        raw = _call_provider(provider, api_key, base_url, model, prompt)
        parsed: dict[str, Any] = json.loads(_strip_fences(raw))

        # Format A — preferred: response already has explicit three-field structure
        if "authorized" in parsed:
            parsed["authorized"] = _normalize_items(parsed.get("authorized"))
            parsed["prohibited"] = _normalize_items(parsed.get("prohibited"), "HARD_LIMIT")
            parsed["requires_confirmation"] = _normalize_items(parsed.get("requires_confirmation"))
            parsed["_provider"] = provider
            parsed["_model"] = model
            return parsed

        # Format B — fallback: response used single concretized field; split it
        concretized = parsed.get("concretized", "")
        authorized, prohibited, confirmation = _split_mission_concretized(concretized)
        return {
            "authorized": authorized,
            "prohibited": prohibited,
            "requires_confirmation": confirmation,
            "enforcement_notes": parsed.get("enforcement_notes", ""),
            "confidence": parsed.get("confidence", "MEDIUM"),
            "ambiguities": (parsed.get("ambiguities") or [])
            + ["Response used single-field format — auto-split applied"],
            "_provider": provider,
            "_model": model,
            "_format_b": True,
        }
    except Exception as exc:
        return _mission_fallback(user_input, str(exc))


def concretize_field(field_name: str, user_input: str) -> dict[str, Any]:
    """Concretize a single governance field into an enforceable rule."""
    if field_name == "hard_limits":
        return _concretize_hard_limits(user_input)

    provider, api_key, base_url, model_override = _get_env()
    if not provider or not api_key:
        return _field_fallback(user_input, "No AI provider configured")

    model = model_override or _DEFAULT_MODELS.get(provider)
    if not model:
        return _field_fallback(user_input, "No model configured")

    from agentguard.ai_review import _strip_fences as _sf

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

    prompt = _FIELD_PROMPT.format(field_name=field_name, user_input=user_input)
    try:
        raw = _call_provider(provider, api_key, base_url, model, prompt)
        result: dict[str, Any] = json.loads(_sf(raw))
        result["_provider"] = provider
        result["_model"] = model
        return result
    except Exception as exc:
        return _field_fallback(user_input, str(exc))


def _concretize_hard_limits(user_input: str) -> dict[str, Any]:
    """Concretize hard limits into a structured prohibited list."""
    provider, api_key, base_url, model_override = _get_env()
    if not provider or not api_key:
        return _hard_limits_fallback(user_input, "No AI provider configured")

    model = model_override or _DEFAULT_MODELS.get(provider)
    if not model:
        return _hard_limits_fallback(user_input, "No model configured")

    prompt = _HARD_LIMITS_PROMPT.format(user_input=user_input)
    try:
        raw = _call_provider(provider, api_key, base_url, model, prompt)
        parsed: dict[str, Any] = json.loads(_strip_fences(raw))
        parsed["prohibited"] = _normalize_items(parsed.get("prohibited"), "HARD_LIMIT")
        parsed["_provider"] = provider
        parsed["_model"] = model
        return parsed
    except Exception as exc:
        return _hard_limits_fallback(user_input, str(exc))


def _mission_fallback(user_input: str, reason: str) -> dict[str, Any]:
    return {
        "authorized": [{"action": user_input, "reason": _AUTO_REASON}],
        "prohibited": [],
        "requires_confirmation": [],
        "confidence": "LOW",
        "ambiguities": [reason],
        "_fallback": True,
    }


def _hard_limits_fallback(user_input: str, reason: str) -> dict[str, Any]:
    return {
        "prohibited": [{"action": user_input, "reason": _AUTO_REASON, "severity": "HARD_LIMIT"}],
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
