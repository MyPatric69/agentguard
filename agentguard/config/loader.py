"""Governance.yaml loader with defaults and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class GovernanceConfigError(ValueError):
    pass


CORE_ARCHITECTURE_PATHS = (
    "agentguard/enforcement/",
    "agentguard/cli.py",
    "agentguard/guided/",
    "agentguard/review/",
    "agentguard/config/",
    ".claude/settings.json",
    "governance.yaml",
)

_VALID_UNMATCHED = frozenset({"deny", "ask", "allow"})


@dataclass
class PathPolicyEntry:
    pattern: str
    reason: str = ""


@dataclass
class PathPolicy:
    denied_paths: list[PathPolicyEntry] = field(default_factory=list)
    protected_paths: list[PathPolicyEntry] = field(default_factory=list)
    authorized_paths: list[PathPolicyEntry] = field(default_factory=list)
    default_for_unmatched: str = "allow"

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


def _parse_path_entries(
    entries: list, section: str, require_reason: bool
) -> list[PathPolicyEntry]:
    result = []
    for i, entry in enumerate(entries or []):
        if not isinstance(entry, dict):
            raise GovernanceConfigError(
                f"path_policy.{section}[{i}] must be a mapping, got {type(entry).__name__!r}"
            )
        pattern = entry.get("pattern", "")
        if not isinstance(pattern, str) or not pattern.strip():
            raise GovernanceConfigError(
                f"path_policy.{section}[{i}] missing required non-empty 'pattern'"
            )
        reason = str(entry.get("reason", "") or "")
        if require_reason and not reason:
            raise GovernanceConfigError(
                f"path_policy.{section}[{i}] missing required 'reason'"
            )
        result.append(PathPolicyEntry(pattern=pattern, reason=reason))
    return result


def load_cost_awareness(governance: dict) -> dict | None:
    """Return cost_awareness config dict, or None if absent.

    Raises GovernanceConfigError if warn_at_usd >= alert_at_usd.
    """
    raw = governance.get("cost_awareness")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise GovernanceConfigError("cost_awareness must be a mapping")
    warn_at = raw.get("warn_at_usd")
    alert_at = raw.get("alert_at_usd")
    if warn_at is not None and alert_at is not None:
        try:
            if float(warn_at) >= float(alert_at):
                raise GovernanceConfigError(
                    f"cost_awareness: warn_at_usd ({warn_at}) must be less than"
                    f" alert_at_usd ({alert_at})"
                )
        except (TypeError, ValueError) as exc:
            raise GovernanceConfigError(
                f"cost_awareness: invalid threshold value — {exc}"
            ) from exc
    return raw


def load_path_policy(governance: dict) -> PathPolicy:
    """Parse path_policy from a loaded governance dict.

    If the key is absent, returns a backward-compatible default that preserves
    existing _CORE_ARCHITECTURE_PATHS enforcement and allows all other paths.
    """
    raw = governance.get("path_policy")
    if raw is None:
        protected = [
            PathPolicyEntry(pattern=p, reason="core architecture path")
            for p in CORE_ARCHITECTURE_PATHS
        ]
        return PathPolicy(
            denied_paths=[],
            protected_paths=protected,
            authorized_paths=[],
            default_for_unmatched="allow",
        )

    default_for_unmatched = raw.get("default_for_unmatched", "ask")
    if default_for_unmatched not in _VALID_UNMATCHED:
        raise GovernanceConfigError(
            f"path_policy.default_for_unmatched must be one of"
            f" {sorted(_VALID_UNMATCHED)!r}, got {default_for_unmatched!r}"
        )

    return PathPolicy(
        denied_paths=_parse_path_entries(
            raw.get("denied_paths", []), "denied_paths", require_reason=True
        ),
        protected_paths=_parse_path_entries(
            raw.get("protected_paths", []), "protected_paths", require_reason=True
        ),
        authorized_paths=_parse_path_entries(
            raw.get("authorized_paths", []), "authorized_paths", require_reason=False
        ),
        default_for_unmatched=default_for_unmatched,
    )
