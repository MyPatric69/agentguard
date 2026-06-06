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

_MISSION_PROMPT = """\
You are an AI governance expert. Split this agent mission into three
enforceable governance fields.

User intent: "{user_input}"

You MUST respond with exactly this JSON structure, no other format:
{{
  "authorized": "concrete list of what the agent MAY do",
  "prohibited": "concrete list of what the agent MUST NOT do",
  "requires_confirmation": "concrete list of actions needing human approval",
  "confidence": "HIGH|MEDIUM|LOW",
  "ambiguities": ["list any unclear points"]
}}

Rules:
- Be specific: file paths, command names, patterns — no vague terms
- authorized: positive permissions only
- prohibited: hard blocks, no exceptions
- requires_confirmation: actions allowed but need human sign-off first
- No markdown, no preamble, JSON only"""

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

# Sentence-level classifiers for Format B splitting
_PROHIBITED_RE = re.compile(r"\b(not|never|deny|block|must\s+not)\b", re.IGNORECASE)
_CONFIRMATION_RE = re.compile(r"\b(confirmation|approval|human)\b", re.IGNORECASE)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _ai_available() -> bool:
    provider, api_key, _, _ = _get_env()
    return bool(provider and api_key)


def _split_mission_concretized(text: str) -> tuple[str, str, str]:
    """Split a single-field concretized text into (authorized, prohibited, confirmation).

    Checks confirmation keywords first so sentences like "cannot proceed without
    human confirmation" are not misclassified as prohibited.
    """
    sentences = [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if not sentences:
        return text, "", ""

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

    authorized = " ".join(authorized_parts) if authorized_parts else text
    prohibited = " ".join(prohibited_parts)
    confirmation = " ".join(confirmation_parts)

    return authorized, prohibited, confirmation


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
        parsed: dict[str, Any] = json.loads(_strip_fences(raw))

        # Format A — preferred: response already has explicit three-field structure
        if "authorized" in parsed:
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
