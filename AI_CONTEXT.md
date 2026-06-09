# AI_CONTEXT.md

> Keep this file current. Update after each significant session.

---

## Project

**Name:** AgentGuard  
**Version:** 0.6.0  
**Repo:** github.com/MyPatric69/agentguard  
**Purpose:** Governance layer for autonomous AI agents — pre-flight
checks, runtime enforcement, concretization, and audit trail.

**Positioning:** Not an observability tool. The governance layer that
runs before, during, and after observability tools do.

**Tagline:** "Maximum instruction, minimum interpretation."

## Stack

- Python 3.11+
- Click (CLI), Rich (output), PyYAML (config), python-dotenv (env)
- Optional AI: Anthropic SDK, OpenAI SDK
- Optional Web: FastAPI + uvicorn (server), React 18 + Vite 5 (frontend)
- Build: hatchling, PyPI distribution pending

## Current State (v0.7.0)

### Commands
- `agentguard check` — pre-flight: 11 checks, CRITICAL/WARNING/INFO
- `agentguard check --ai-review` — + AI scope quality score 1-10
- `agentguard init --interactive` — basic setup, no AI required
- `agentguard init --guided` — AI-concretized 5-step governance dialog
- `agentguard enforce` — PreToolUse hook, exit 0/2, deterministic
- `agentguard watch` — native Claude Code JSONL monitoring
- `agentguard report` — post-session Markdown governance report
- `agentguard review` — interactive governance update cycle
- `agentguard review --guided` — AI-assisted field update
- `agentguard verify` — prompt-pin drift detection
- `agentguard override` — documented exception with mandatory reason
- `agentguard web` — browser-based UI (requires pip install agentguard[web])

### Key Technical Decisions
- Enforcement: deterministic, no LLM, never probabilistic
- Concretization: claude-sonnet / gpt-4o, temperature=0
- Scope review: provider default model (haiku/gpt-4o-mini)
- Validation: deterministic structural checks after every concretization
- Pinning: SHA-256 hashes of prompt+output stored in governance.yaml
- Version: single source of truth via importlib.metadata
- Terminal: PTY via Python stdlib `pty`, relayed over WebSocket to xterm.js; clean bash startup with custom PS1
- Run in Terminal: InitPanel/ReviewPanel buttons navigate to Terminal tab and execute command

### governance.yaml Schema
- scope.authorized: list of {action, reason, added}
- scope.prohibited: list of {action, reason, severity, added}
- scope.requires_confirmation: list of {action, reason, added}
- scope.unresolved_ambiguities: list of {text, added, status}
- escalation: {contact, method, trigger}
- killswitch: string
- concretization_pins: list of pin records {field, input_hash, prompt_hash, output_hash, model, provider, temperature, date}
- governance_history: list of change records {date, action, tool, version}

### Tests
- 214/214 passing (includes 9 web server API tests)
- CI: GitHub Actions, Python 3.11 + 3.12, green

## Open Items

### Before PyPI
- MindTrace as documented showcase (in progress)

### After PyPI
- v0.8.0: Intent-Aware Live Observer (drift detection via JSONL)

## Key Files

- `agentguard/web/server.py` — FastAPI bridge (/api/check, /api/governance, /api/verify, /api/health, /api/project-info, /ws/terminal)
- `web/src/App.jsx` — React shell: Check / Governance / Verify / Terminal tabs, dark theme
- `web/src/components/` — CheckPanel, GovernanceView, StatusBadge, TerminalPanel
- `agentguard/checks/preflight.py` — Layer 1
- `agentguard/enforcement/enforcer.py` — Layer 2
- `agentguard/checks/runtime.py` — Layer 3
- `agentguard/guided/concretizer.py` — AI concretization (sonnet, temperature=0)
- `agentguard/guided/validator.py` — deterministic structural validation
- `agentguard/guided/pinning.py` — SHA-256 prompt/output pinning
- `agentguard/review/reviewer.py` — governance review and update cycle
- `agentguard/ai_review.py` — provider-agnostic AI scope quality review
- `agentguard/cli.py` — all commands wired here
- `agentguard/output/renderer.py` — Rich panels, severity colors
- `agentguard/config/loader.py` — governance.yaml loading, list+string compat
- `governance.yaml.example` — reference config

## Related

- Dev.to: https://dev.to/mypatric69/the-blind-spot-of-agentic-ai-systems-when-nobody-notices-the-agent-is-stuck-1hkb
- LinkedIn: https://www.linkedin.com/posts/patric-hayna-6b7b55134_the-blind-spot-of-agentic-ai-systems-when-activity-7467668285891821568-ZXtx

---

## Last updated

2026-06-09 – Auto-synced 2 commit(s) to a047d28
