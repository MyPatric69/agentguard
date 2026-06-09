# AI_CONTEXT.md

> Keep this file current. Update after each significant session.

---

## Project

**Name:** AgentGuard  
**Version:** 0.5.1  
**Repo:** github.com/MyPatric69/agentguard  
**Purpose:** Governance layer for autonomous AI agents — pre-flight checks,
runtime loop detection, and post-session reporting.

**Positioning:** Not an observability tool. The governance layer that runs
before observability tools do.

## Stack

- Python 3.11+
- Click (CLI), Rich (output), PyYAML (config)
- Optional: Anthropic / OpenAI / Anysphere API (AI-powered scope review via --ai-review flag, provider-agnostic)
- Build: hatchling, PyPI distribution planned

## Current State (v0.5.1)

- Pre-flight check: checks across 3 layers (governance, prompt, harness)
- AI-powered scope quality review via `--ai-review` flag (opt-in)
  - Provider-agnostic: Anthropic, OpenAI, Anysphere, OpenAI-compatible
  - Config via .env / environment variables (python-dotenv)
  - Graceful degradation: API failure never blocks main check
  - Score 1-10 with STRONG/ACCEPTABLE/WEAK/INSUFFICIENT verdict
- Escalation contact format validation (email/Slack/name heuristic)
- Inline examples for all `agentguard init --interactive` prompts
- Runtime watch: loop, stall, burn detection via JSON log
- Post-session report: Markdown governance summary
- agentguard enforce: PreToolUse hook handler (exit 0=allow, exit 2=block)
  - Prohibited scope matching against tool input (rm -rf, git push, SQL ops)
  - Confirmation-required detection (Write/Edit tools, git push, deletion)
  - Enforcement log: agentguard-enforcement.log (deny decisions only)
  - HARD_LIMIT severity items logged with HARD_LIMIT: prefix
- agentguard init --guided: AI-powered 5-step guided concretization
  - Transforms vague intent into enforceable rules (provider-agnostic)
  - Per-field adjustment loop (max 3 rounds) with fallback to raw input
  - Final review panel before saving; field-level re-do support
  - Writes governance.yaml (with metadata), settings.json, CLAUDE.md
  - Ctrl+C save-progress prompt; graceful on API failure
  - Pre-inquiry screen shown before Step 1 (realistic expectations)
  - Ambiguity confirmation when confidence MEDIUM/LOW
  - Metadata comment shows actual model used (not env default)
  - Ambiguities accumulated across all adjustment rounds (deduplicated)
- **New in v0.4.1: Structured governance.yaml schema**
  - scope.authorized/prohibited/requires_confirmation are lists of objects
  - Each rule has: action + reason + severity (prohibited) + added date
  - governance_history block tracks all governance changes
  - unresolved_ambiguities as structured list with status
  - Backward compatible: legacy flat-string format still supported
  - AI concretization generates reason for every rule automatically
- **New in v0.5.0: agentguard review command**
  - Interactive field-by-field governance review
  - Keep / Add / Remove / Replace rules for any scope field
  - Mark ambiguities as resolved with audit timestamp
  - --guided flag: AI-assisted rule concretization via concretize_field
  - --field flag: single field review without going through full menu
  - governance_history entry appended on every save (date, tool, changed_fields)
  - View full governance.yaml with Rich syntax highlighting
  - Module: agentguard/review/reviewer.py
- agentguard init: generates .claude/settings.json with PreToolUse hook
  - Merge-safe: existing hooks preserved when settings.json exists
  - interactive + template-only + guided modes
- agentguard override: mandatory reason, logged to agentguard-overrides.log
- security.md absence triggers INFO check in preflight
- CONCRETIZATION_MODEL_OVERRIDES: sonnet for all concretization calls (anthropic/openai/anysphere)
- temperature=0 enforced on all concretization API calls (deterministic outputs)
- Structural validation before accepting concretized governance (validator.py)
- **New in v0.5.1: Prompt-Pinning for reproducibility**
  - `agentguard/guided/pinning.py`: SHA-256 hash pins for prompt/output/model/temperature
  - `_pin` dict embedded in every concretization result
  - `concretization_pins` block written to governance.yaml on save
  - `agentguard verify`: checks pin integrity — structure + temperature=0
  - 205/205 tests passing, ruff clean
- CI: GitHub Actions, Python 3.11 + 3.12 matrix, green

## Open Items

- PyPI publish
- Homebrew formula
- OpenAI Agents + LangChain support
- SKILL.md validation improvements
- Runtime Watch via native JSONL (direct Claude Code log integration)

## Key Files

- `agentguard/guided/concretizer.py` — AI concretization logic for --guided
- `agentguard/review/reviewer.py` — Governance reviewer (load, review, save)
- `agentguard/enforcement/enforcer.py` — PreToolUse hook enforcement logic
- `agentguard/checks/preflight.py` — Layer 1 check logic
- `agentguard/checks/runtime.py` — Layer 2 loop/stall/burn detection
- `agentguard/checks/report.py` — Layer 3 governance report
- `agentguard/cli.py` — CLI entry point
- `agentguard/output/renderer.py` — Rich panel output
- `agentguard/config/loader.py` — governance.yaml loading + defaults
- `governance.yaml.example` — reference config

## Related

- Dev.to article: https://dev.to/mypatric69/the-blind-spot-of-agentic-ai-systems-when-nobody-notices-the-agent-is-stuck-1hkb

---

## Last updated

2026-06-09 – Auto-synced 1 commit(s) to 997966d
