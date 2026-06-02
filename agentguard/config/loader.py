"""Governance.yaml loader with defaults and validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEFAULTS: dict[str, Any] = {
    "owner": "",
    "scope": {
        "authorized": "",
        "prohibited": "",
        "requires_confirmation": "",
    },
    "escalation": {
        "contact": "",
        "method": "log",
        "trigger": "2+ critical failures or loop detected",
    },
    "killswitch": "",
    "severity": {
        "no_owner": "critical",
        "no_scope": "critical",
        "no_escalation": "critical",
        "no_killswitch": "critical",
        "no_instruction_file": "critical",
        "no_loop_detection": "warning",
        "no_root_cause_rule": "warning",
        "no_api_research_rule": "info",
        "no_attempt_counter": "warning",
        "no_action_log": "warning",
        "no_skill_md": "warning",
    },
    "runtime": {
        "loop_threshold": 2,
        "progress_check_interval": 10,
        "token_burn_threshold": 5000,
        "progress_scoring": False,
    },
    "override": {
        "allowed": True,
        "require_reason": True,
        "log_overrides": True,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def load_config(path: str | Path) -> dict[str, Any]:
    """Load governance.yaml from path, merging with defaults."""
    config_path = Path(path)
    if not config_path.exists():
        return dict(DEFAULTS)

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    return _deep_merge(DEFAULTS, raw)


def find_config(project_path: str | Path) -> Path | None:
    """Search for governance.yaml starting at project_path."""
    base = Path(project_path).resolve()
    for candidate in [
        base / "governance.yaml",
        base / ".agentguard" / "governance.yaml",
    ]:
        if candidate.exists():
            return candidate
    return None


def get_severity(config: dict, rule: str) -> str:
    """Return normalized severity string for a given rule key."""
    return config.get("severity", {}).get(rule, "warning").lower()
