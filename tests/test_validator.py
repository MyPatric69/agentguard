"""Tests for agentguard/guided/validator.py"""

from __future__ import annotations

from agentguard.guided.validator import ValidationIssue, validate_concretized

_VALID_RESULT = {
    "authorized": [
        {"action": "Read Python files in ./src", "reason": "Core task"},
        {"action": "Run pytest test suite", "reason": "Verify changes"},
    ],
    "prohibited": [
        {"action": "Deploy to production", "reason": "Hard limit", "severity": "HARD_LIMIT"},
        {"action": "Push to main branch", "reason": "Requires review", "severity": "HARD_LIMIT"},
    ],
    "requires_confirmation": [
        {"action": "Any file deletion", "reason": "Irreversible"},
    ],
    "confidence": "HIGH",
    "ambiguities": [],
}


# ── 1. Valid output: empty issues list ───────────────────────────────────────

def test_validate_concretized_valid_returns_no_issues():
    issues = validate_concretized(_VALID_RESULT)
    assert issues == []


# ── 2. Empty authorized → error ──────────────────────────────────────────────

def test_validate_concretized_empty_authorized_returns_error():
    result = {**_VALID_RESULT, "authorized": []}
    issues = validate_concretized(result)
    errors = [i for i in issues if i.severity == "error"]
    assert any(i.field == "authorized" for i in errors)
    assert any("No authorized actions defined" in i.message for i in errors)


# ── 3. Empty prohibited → error ──────────────────────────────────────────────

def test_validate_concretized_empty_prohibited_returns_error():
    result = {**_VALID_RESULT, "prohibited": []}
    issues = validate_concretized(result)
    errors = [i for i in issues if i.severity == "error"]
    assert any(i.field == "prohibited" for i in errors)
    assert any("No prohibited actions defined" in i.message for i in errors)


# ── 4. No HARD_LIMIT rules → warning ─────────────────────────────────────────

def test_validate_concretized_no_hard_limit_returns_warning():
    prohibited_no_hl = [{"action": "No database writes", "reason": "Risk", "severity": "WARNING"}]
    result = {**_VALID_RESULT, "prohibited": prohibited_no_hl}
    issues = validate_concretized(result)
    warnings = [i for i in issues if i.severity == "warning"]
    assert any("No HARD_LIMIT rules defined" in i.message for i in warnings)


# ── 5. Empty requires_confirmation → warning ─────────────────────────────────

def test_validate_concretized_empty_confirmation_returns_warning():
    result = {**_VALID_RESULT, "requires_confirmation": []}
    issues = validate_concretized(result)
    warnings = [i for i in issues if i.severity == "warning"]
    assert any(i.field == "requires_confirmation" for i in warnings)
    assert any("No confirmation requirements defined" in i.message for i in warnings)


# ── 6. Action < 10 chars → warning ───────────────────────────────────────────

def test_validate_concretized_short_action_returns_warning():
    result = {**_VALID_RESULT, "authorized": [{"action": "Read", "reason": "Core task"}]}
    issues = validate_concretized(result)
    warnings = [i for i in issues if i.severity == "warning"]
    assert any("too vague" in i.message for i in warnings)
    assert any("Read" in i.message for i in warnings)


# ── 7. Action > 300 chars → warning ──────────────────────────────────────────

def test_validate_concretized_long_action_returns_warning():
    long_action = "Read Python files in ./src" + " and verify them" * 20
    result = {**_VALID_RESULT, "authorized": [{"action": long_action, "reason": "Core task"}]}
    issues = validate_concretized(result)
    warnings = [i for i in issues if i.severity == "warning"]
    assert any("too complex" in i.message for i in warnings)


# ── 8. All fields valid → no issues ──────────────────────────────────────────

def test_validate_concretized_all_fields_valid_no_issues():
    result = {
        "authorized": [{"action": "Read and write Python files in ./src", "reason": "Core task"}],
        "prohibited": [{"action": "Deploy to production without approval", "reason": "Hard limit", "severity": "HARD_LIMIT"}],
        "requires_confirmation": [{"action": "Delete files outside ./tmp directory", "reason": "Irreversible"}],
        "confidence": "HIGH",
        "ambiguities": [],
    }
    issues = validate_concretized(result)
    assert issues == []


# ── 9. ValidationIssue dataclass has expected fields ─────────────────────────

def test_validation_issue_dataclass_fields():
    issue = ValidationIssue(
        field="authorized",
        severity="error",
        message="No authorized actions defined",
        fix="Define at least one concrete authorized action",
    )
    assert issue.field == "authorized"
    assert issue.severity == "error"
    assert issue.message == "No authorized actions defined"
    assert issue.fix == "Define at least one concrete authorized action"
