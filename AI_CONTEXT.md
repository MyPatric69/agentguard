# AI_CONTEXT.md

> Keep this file current. Update after each significant session.

---

## Project

**Name:** AgentGuard  
**Version:** 0.10.0  
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

## Current State (v0.10.0)

### CLI Commands (12 total)
- `agentguard check` — pre-flight: governance + prompt + harness checks
- `agentguard check --ai-review` — + AI scope quality score 1-10
- `agentguard init --interactive` — basic setup, no AI required
- `agentguard init --guided` — AI-concretized 5-step governance dialog
- `agentguard enforce` — PreToolUse hook, exit 0/2, writes .agentguard/session.log
- `agentguard watch` — live feed of all tool calls, auto-discovers session.log
- `agentguard watch --loop-threshold N` — custom loop detection threshold (default: 6)
- `agentguard report` — post-session Markdown governance report
- `agentguard review` — interactive governance update cycle
- `agentguard review --guided` — AI-assisted field update
- `agentguard verify` — prompt-pin drift detection
- `agentguard verify --repair` — generate baseline pins from existing governance (no AI)
- `agentguard override` — documented exception with mandatory reason
- `agentguard web` — browser UI (requires pip install agentguard-governance[web])

### Web UI (v0.9.0)
Seven tabs: Pre-Flight Check, Governance, Verify Pins, Live Watch,
Terminal, Setup Governance, Review & Update.

Key features:
- Governance Score Ring on Check panel
- Color-coded scope sections (green/red/amber)
- xterm.js terminal with WebSocket PTY — runs interactive commands
- Quick Commands bar in terminal
- Run in Terminal buttons in Setup/Review panels
- Multi-project switcher (--path flag, dropdown when >1 project)
- Project name shown in header with check status
- Live Watch tab: real-time tool call feed via /ws/watch WebSocket
  - Green ✓ allow / red ✗ deny per entry
  - Pulsing live status indicator
  - Allow/deny counters
- Verify Pins tab: Run Verify + Repair Pins button (brownfield baseline)
  - Repair Pins calls /api/verify-repair, then auto-runs verify
- Session Report tab: stat cards, tool distribution bar chart, blocked actions, runtime warnings
  - Reads .agentguard/session.log + agentguard.log via /api/report

### Key Technical Decisions
- Enforcement: deterministic, no LLM, never probabilistic
- Concretization: claude-sonnet / gpt-4o, temperature=0
- Mission concretization: higher-capability model (sonnet/gpt-4o)
- Scope review: provider default model (haiku/gpt-4o-mini)
- Validation: deterministic structural checks, no LLM
- Pinning: SHA-256 hashes of prompt+output in governance.yaml
- Enforcer signals: prohibited/HARD_LIMIT → deny() exit 2; requires_confirmation → ask() exit 0 (per Claude Code hooks docs)
- Write/edit confirmation: path-scoped to _CORE_ARCHITECTURE_PATHS — only fires for agentguard/enforcement/, agentguard/cli.py, agentguard/guided/, agentguard/review/, agentguard/config/, .claude/settings.json, governance.yaml
- Version: single source of truth via importlib.metadata
- Terminal: PTY via Python stdlib pty + WebSocket + xterm.js
- Resize: binary protocol (0x01 prefix + cols/rows uint16)
- Session logging: every tool call → .agentguard/session.log (gitignored)
- Loop threshold: 6 (configurable via --loop-threshold)
- Concretization prompts are grounded in real project structure: directory scan (depth 2) + CLAUDE.md Architecture Overview excerpt, injected before the user input

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
- 243/243 passing
- CI: GitHub Actions, Python 3.11 + 3.12, green
- Web tests: TestClient (fastapi), PTY documented as manual-test-only

## Open Items / Backlog

**Priority order (current session):**
1. Dogfooding — `init --guided` on AgentGuard repo itself
2. Governance Hard-Rules Extension (builds on dogfooding findings)
3. v0.11.0 Email Notification (pending SMTP/service decision)
4. Medium-term quick wins (PDF export, pin timestamp fix)
5. v1.0.0 Intent-Aware Live Observer
6. Outreach/Tooling (ongoing, reactive)

### v0.11.0 — planned
- Email notification when `escalation.method: "email"` is configured —
  notify owner on governance.yaml changes (e.g. via inline editor).
  SMTP/service choice still open.

### Medium-term
- Session Report PDF export (Web UI)
- `agentguard verify --repair` — review timestamp accuracy for repaired pins

### v1.0.0 — long-term
- Intent-Aware Live Observer — LLM-based drift detection via JSONL transcript analysis

### Governance Hard-Rules Extension (parked, aus Diskussion "Zuverlässigkeit & Verbindlichkeit")
- governance.yaml-Schema um deterministische, kontextunabhängige Regeln erweitern
  (z.B. scope.hard_rules oder Erweiterung von scope.prohibited um
  pattern-basierte Datei/Branch/Command-Regeln)
- Ziel: Entscheidungsklassen aus dem probabilistischen Bereich (LLM)
  in den deterministischen Bereich (Layer 2 Enforcer) verschieben
- Kein aktuelles To-Do — geparkter Ausgangspunkt für spätere Session

### Tooling / Infrastructure
- Homebrew formula for AgentGuard
- pyenv migration on M5 Air (separate topic, not AgentGuard-specific)

### Dogfooding
- Run `agentguard init --guided` on the AgentGuard repo itself
  (own governance for this project)

### Community / Outreach
- KI-Automatisierung Skool community post — check publish status
- Dev.to article — monitor and respond to comments/feedback
- LinkedIn follow-up post after one week with GitHub traffic numbers
- Demo of AgentGuard for Dev Team Lead at Pixum

### Optional
- Demo GIF v2 — could extend to show Session Report and Repair Pins
  (not required, current GIF covers core workflow)

## Key Files

**Python backend:**
- `agentguard/web/server.py` — FastAPI + WebSocket PTY + /ws/watch + /api/verify-repair + /api/report + POST /api/governance/update
- `agentguard/checks/report.py` — Layer 4, generate_report_data() + generate_report()
- `agentguard/checks/preflight.py` — Layer 1
- `agentguard/enforcement/enforcer.py` — Layer 2, session logging
- `agentguard/checks/runtime.py` — Layer 3, live watch feed
- `agentguard/guided/concretizer.py` — AI concretization
- `agentguard/guided/validator.py` — structural validation
- `agentguard/guided/pinning.py` — SHA-256 pinning + repair_pins() for brownfield
- `agentguard/review/reviewer.py` — governance review
- `agentguard/ai_review.py` — scope quality review
- `agentguard/cli.py` — all commands
- `agentguard/output/renderer.py` — Rich output

**React frontend:**
- `web/src/App.jsx` — shell, sidebar, project switcher
- `web/src/components/CheckPanel.jsx` — score ring
- `web/src/components/GovernanceView.jsx` — scope cards
- `web/src/components/VerifyPanel.jsx` — pin cards
- `web/src/components/WatchPanel.jsx` — live tool call feed
- `web/src/components/ReportPanel.jsx` — session report (stat cards, tool distribution, blocked actions)
- `web/src/components/TerminalPanel.jsx` — xterm.js PTY
- `web/src/components/InitPanel.jsx` — setup panel
- `web/src/components/ReviewPanel.jsx` — review panel

**Runtime (gitignored):**
- `.agentguard/session.log` — auto-generated tool call log

## Related

- Dev.to: https://dev.to/mypatric69/the-blind-spot-of-agentic-ai-systems-when-nobody-notices-the-agent-is-stuck-1hkb
- LinkedIn: https://www.linkedin.com/posts/patric-hayna-6b7b55134_the-blind-spot-of-agentic-ai-systems-when-activity-7467668285891821568-ZXtx

---

## Last updated

2026-06-12 – Enforcer: rm check scoped to Bash only; removed redundant "rm -f" string check
