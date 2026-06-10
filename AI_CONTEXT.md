# AI_CONTEXT.md

> Keep this file current. Update after each significant session.

---

## Project

**Name:** AgentGuard  
**Version:** 0.7.2  
**Repo:** github.com/MyPatric69/agentguard  
**Purpose:** Governance layer for autonomous AI agents — pre-flight
checks, runtime enforcement, concretization, and audit trail.

**Positioning:** Not an observability tool. The governance layer that
runs before, during, and after observability tools do.

**Taglines:**
- "Maximum instruction, minimum interpretation."
- "It doesn't eliminate the probability of failure. It reduces the impact."

## Stack

- Python 3.11+
- Click (CLI), Rich (output), PyYAML (config), python-dotenv (env)
- Optional AI: Anthropic SDK, OpenAI SDK
- Optional Web: FastAPI + uvicorn, React 18 + Vite 5, xterm.js
- Build: hatchling, PyPI: agentguard-governance

## Current State (v0.7.2)

### CLI Commands (12 total)
- `agentguard check` — pre-flight: governance + prompt + harness checks
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
- `agentguard web` — browser UI (requires pip install agentguard-governance[web])

### Web UI (v0.7.0)
Six tabs: Pre-Flight Check, Governance, Verify Pins, Terminal,
Setup Governance, Review & Update.

Key features:
- Governance Score Ring on Check panel
- Color-coded scope sections (green/red/amber)
- xterm.js terminal with WebSocket PTY — runs interactive commands
- Quick Commands bar in terminal
- Run in Terminal buttons in Setup/Review panels
- Multi-project switcher (--path flag, dropdown when >1 project)
- Project name shown in header with check status

### Key Technical Decisions
- Enforcement: deterministic, no LLM, never probabilistic
- Concretization: claude-sonnet / gpt-4o, temperature=0
- Mission concretization: higher-capability model (sonnet/gpt-4o)
- Scope review: provider default model (haiku/gpt-4o-mini)
- Validation: deterministic structural checks, no LLM
- Pinning: SHA-256 hashes of prompt+output in governance.yaml
- Version: single source of truth via importlib.metadata
- Terminal: PTY via Python stdlib pty + WebSocket + xterm.js
- Resize: binary protocol (0x01 prefix + cols/rows uint16)

### governance.yaml Schema
- owner: string
- scope.authorized: list of {action, reason, added}
- scope.prohibited: list of {action, reason, severity, added}
- scope.requires_confirmation: list of {action, reason, added}
- scope.unresolved_ambiguities: list of {text, added, status}
- escalation: {contact, method, trigger}
- killswitch: string
- concretization_pins: list of {field, input_hash, prompt_hash,
  output_hash, model, provider, temperature, date}
- governance_history: list of {date, action, tool, version,
  changed_fields?}

### Tests
- 217/217 passing
- CI: GitHub Actions, Python 3.11 + 3.12, green
- Web tests: TestClient (fastapi), PTY documented as manual-test-only

## Open Items

### Before PyPI
- Final documentation sync (this commit)

### After PyPI
- Dev.to / LinkedIn article: "AgentGuard is live"
- v0.8.0: Intent-Aware Live Observer (drift detection via JSONL)
- Web-UI v0.8: inline governance editor
- Homebrew formula

## Key Files

**Python backend:**
- `agentguard/web/server.py` — FastAPI + WebSocket PTY
- `agentguard/checks/preflight.py` — Layer 1
- `agentguard/enforcement/enforcer.py` — Layer 2
- `agentguard/checks/runtime.py` — Layer 3
- `agentguard/guided/concretizer.py` — AI concretization
- `agentguard/guided/validator.py` — structural validation
- `agentguard/guided/pinning.py` — SHA-256 pinning
- `agentguard/review/reviewer.py` — governance review
- `agentguard/ai_review.py` — scope quality review
- `agentguard/cli.py` — all commands
- `agentguard/output/renderer.py` — Rich output

**React frontend:**
- `web/src/App.jsx` — shell, sidebar, project switcher
- `web/src/components/CheckPanel.jsx` — score ring
- `web/src/components/GovernanceView.jsx` — scope cards
- `web/src/components/VerifyPanel.jsx` — pin cards
- `web/src/components/TerminalPanel.jsx` — xterm.js PTY
- `web/src/components/InitPanel.jsx` — setup panel
- `web/src/components/ReviewPanel.jsx` — review panel

## Related

- Dev.to: https://dev.to/mypatric69/the-blind-spot-of-agentic-ai-systems-when-nobody-notices-the-agent-is-stuck-1hkb
- LinkedIn: https://www.linkedin.com/posts/patric-hayna-6b7b55134_the-blind-spot-of-agentic-ai-systems-when-activity-7467668285891821568-ZXtx

---

## Last updated

2026-06-10
