"""
Deterministic validation of concretized governance output.
No LLM calls — pure structural and content checks.
Runs after every concretization before presenting to user.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationIssue:
    field: str
    severity: str  # "error" | "warning"
    message: str
    fix: str


def validate_concretized(result: dict) -> list[ValidationIssue]:
    """
    Validate concretized governance output.
    Returns list of issues — empty list means valid.
    """
    issues: list[ValidationIssue] = []

    authorized = result.get("authorized", [])
    if not authorized:
        issues.append(ValidationIssue(
            field="authorized",
            severity="error",
            message="No authorized actions defined",
            fix="Define at least one concrete authorized action",
        ))
    for item in authorized:
        action = item.get("action", "") if isinstance(item, dict) else str(item)
        if len(action) < 10:
            issues.append(ValidationIssue(
                field="authorized",
                severity="warning",
                message=f"Action too vague: '{action}'",
                fix="Be more specific — include paths, tools, or conditions",
            ))
        if len(action) > 300:
            issues.append(ValidationIssue(
                field="authorized",
                severity="warning",
                message="Action too complex for reliable enforcement",
                fix="Split into multiple specific actions",
            ))

    prohibited = result.get("prohibited", [])
    if not prohibited:
        issues.append(ValidationIssue(
            field="prohibited",
            severity="error",
            message="No prohibited actions defined",
            fix="Define at least one hard limit",
        ))

    hard_limits = [
        item for item in prohibited
        if isinstance(item, dict) and item.get("severity") == "HARD_LIMIT"
    ]
    if not hard_limits:
        issues.append(ValidationIssue(
            field="prohibited",
            severity="warning",
            message="No HARD_LIMIT rules defined",
            fix="Mark your most critical prohibitions as HARD_LIMIT",
        ))

    confirmation = result.get("requires_confirmation", [])
    if not confirmation:
        issues.append(ValidationIssue(
            field="requires_confirmation",
            severity="warning",
            message="No confirmation requirements defined",
            fix="Define which actions require human approval before execution",
        ))

    return issues
