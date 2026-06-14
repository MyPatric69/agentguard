# AgentGuard — CLAUDE.md

## Project Purpose
AgentGuard is a governance layer for autonomous AI agents. It provides pre-flight checks (Layer 1), runtime enforcement (Layer 2), runtime monitoring (Layer 3), and post-session reporting and audit (Layer 4). The goal is to make AI agents safer by ensuring governance prerequisites are in place before execution begins.

## Architecture Overview

```
agentguard/
├── checks/
│   ├── preflight.py      # Layer 1: governance + prompt + harness checks
│   ├── runtime.py        # Layer 3: session log monitoring, loop/stall/burn
│   └── report.py         # Layer 4: post-session governance report
├── enforcement/
│   └── enforcer.py       # Layer 2: PreToolUse hook, exit 0/2,
│                         #          writes .agentguard/session.log
├── guided/
│   ├── concretizer.py    # AI concretization (sonnet/gpt-4o, temperature=0)
│   ├── validator.py      # Deterministic structural validation
│   └── pinning.py        # SHA-256 prompt/output pinning
├── review/
│   └── reviewer.py       # Governance review and update cycle
├── web/
│   └── server.py         # FastAPI bridge + WebSocket PTY + /ws/watch
├── config/
│   └── loader.py         # governance.yaml loading, list+string compat
├── output/
│   └── renderer.py       # Rich panels, severity colors
└── cli.py                # All commands wired here

web/                       # React/Vite frontend (built to web/dist/)
├── src/
│   ├── App.jsx            # Sidebar layout, project switcher
│   └── components/
│       ├── CheckPanel.jsx      # Pre-flight check + score ring
│       ├── GovernanceView.jsx  # Color-coded scope sections
│       ├── VerifyPanel.jsx     # Pin verification cards
│       ├── TerminalPanel.jsx   # xterm.js + WebSocket PTY
│       ├── InitPanel.jsx       # Setup governance (Run in Terminal)
│       ├── ReviewPanel.jsx     # Review & update (Run in Terminal)
│       └── WatchPanel.jsx      # Live Watch — real-time tool call feed
└── package.json

Project directory (runtime):
├── governance.yaml            # Governance definition
├── .claude/settings.json      # AgentGuard PreToolUse hook
├── CLAUDE.md                  # Governance context for Claude Code
└── .agentguard/
    └── session.log            # Auto-generated tool call log (gitignored)
```

## Key Design Principles

- `path_policy` (optional governance.yaml key): evaluated first by
  enforcer.py (Layer 2) for file-editing tools via pathspec
  (gitignore-style globs). Schema and loading in `agentguard/config/loader.py`.
  See README §path_policy and governance.yaml Reference for details.

- Enforcement layer: deterministic, no LLM, exit 0 or 2
- Concretization layer: LLM with temperature=0, human confirms
- Monitoring layer: LLM allowed, warnings only, never blocks
- Validation layer: deterministic, structural checks, no LLM

## Scope
- Python CLI tool using Click and Rich
- No external network calls in core logic (API key optional for progress scoring)
- Target: developers and teams deploying autonomous AI agents

## Code Quality Rules

**YAGNI** — Build only what is specified. No extra abstractions, no speculative features.
**KISS** — Prefer the simplest implementation that satisfies the requirement.
**DRY** — Extract shared logic when the same pattern appears 3+ times.
**Single Responsibility** — Each module does one thing. CLI wires them together.

- No debug logging (`print()` statements) in committed code
- No commented-out code
- No unused imports
- Tests must pass before commit (`pytest --tb=short`)
- One commit per logical change

## Loop Detection
If the same approach fails 2+ times in a row:
1. STOP immediately
2. Do not retry the same strategy
3. Propose a fundamentally different approach
4. After 3 failed iterations: escalate or ask

## Root Cause Analysis
- Confirm root cause before implementing any fix
- Do not patch symptoms
- If root cause is unclear, ask — do not guess

## External APIs & Documentation
- Always fetch current documentation before diagnosing API issues
- Never rely on training-data memory for external API behavior
- If a newer API version or migration guide exists, flag it first

## Testing
- All new behavior must have a corresponding test
- Tests live in `tests/` and mirror the module structure
- Use `tmp_path` pytest fixture for file system tests — never write to the real project root in tests

## Version Management
- Version is defined ONLY in `pyproject.toml`
- `agentguard/__init__.py` reads version dynamically via importlib.metadata
- Never hardcode version in __init__.py
- On release: update pyproject.toml version only


## AgentGuard Governance Block
## Added by: agentguard init --interactive
## Date: 2026-06-12 21:43:34
## ─────────────────────────────────────────

## AgentGuard Governance

This project is governed by AgentGuard. The following rules apply:

### Loop Detection
- If the same approach fails 2+ times in a row, STOP immediately.
- Do not retry the same strategy. Propose a fundamentally different approach.
- If stuck after 3 iterations, escalate to the owner defined in governance.yaml.

### Root Cause Analysis
- Confirm root cause before implementing any fix.
- Do not patch symptoms. Diagnose before acting.
- If root cause is unclear, ask — do not guess.

### External APIs & Research
- ALWAYS fetch current documentation before diagnosing API issues.
- Never rely on memory for external API behavior — APIs change.
- If a newer API version exists, flag it before recommending a fix.

### Scope
- Only take actions within the defined scope in governance.yaml.
- Do not expand scope without explicit approval from the owner.

## AgentGuard — Handling Governance Decisions
- If AgentGuard denies an action (`permissionDecision: deny`,
  HARD_LIMIT or prohibited scope): this action is forbidden. Do not
  attempt the same change via a different tool (e.g. Bash instead of
  Edit). Report the denial and propose an alternative approach that
  stays within authorized scope.
- If AgentGuard asks for confirmation (`permissionDecision: ask`):
  this requires the owner's real-time decision. Wait for the owner's
  response; do not reroute through another tool while waiting.

## ─────────────────────────────────────────
## End AgentGuard Governance Block
