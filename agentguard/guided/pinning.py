"""
Prompt-Pinning — records prompts and outputs used during concretization.
Enables reproducibility verification and drift detection.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date


def _today() -> str:
    return date.today().isoformat()


def hash_content(content: str) -> str:
    """SHA-256 hash of content, first 16 chars for readability."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def pin_concretization(
    field: str,
    user_input: str,
    prompt: str,
    model: str,
    provider: str,
    output: dict,
) -> dict:
    """
    Create a pin record for a concretization call.
    Stored in governance.yaml under concretization_pins.
    """
    return {
        "field": field,
        "input_hash": hash_content(user_input),
        "prompt_hash": hash_content(prompt),
        "output_hash": hash_content(json.dumps(output, sort_keys=True)),
        "model": model,
        "provider": provider,
        "temperature": 0,
        "date": _today(),
    }


def verify_pin(pin: dict, prompt: str, output: dict) -> dict:
    """
    Verify a stored pin against current prompt and output.
    Returns: {"valid": bool, "drifted": list[str]}
    """
    drifted = []
    current_prompt_hash = hash_content(prompt)
    current_output_hash = hash_content(json.dumps(output, sort_keys=True))

    if pin.get("prompt_hash") != current_prompt_hash:
        drifted.append("prompt")
    if pin.get("output_hash") != current_output_hash:
        drifted.append("output")
    if pin.get("temperature") != 0:
        drifted.append("temperature")

    return {
        "valid": len(drifted) == 0,
        "drifted": drifted,
    }
