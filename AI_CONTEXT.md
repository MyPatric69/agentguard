# AI_CONTEXT.md

> Keep this file current. Update after each significant session.

---

## Project

**Name:** AgentGuard  
**Version:** 1.0.0  
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
- Click (CLI), Rich (output), PyYAML (config), python-dotenv (env), pathspec (glob path matching)
- Optional AI: Anthropic SDK, OpenAI SDK
- Optional Web: FastAPI + uvicorn, React 18 + Vite 5, xterm.js
- Build: hatchling, PyPI: agentguard-governance
- Frontend: web/vite.config.js outDir = '../agentguard/web/dist' (builds directly into package)

## Current State (v1.0.0)

### CLI Commands (15 total)
- `agentguard check` — pre-flight: governance + prompt + harness checks; validates `path_policy` if present (INFO if absent, no score impact)
- `agentguard check --ai-review` — + AI scope quality score 1-10
- `agentguard init --interactive` — basic setup, no AI required
- `agentguard init --guided` — AI-concretized 5-step governance dialog
- `agentguard enforce` — PreToolUse hook, exit 0/2, writes .agentguard/session.log
- `agentguard watch` — live feed of all tool calls, auto-discovers session.log
- `agentguard watch --loop-threshold N` — custom loop detection threshold (default: 6)
- `agentguard report` — post-session Markdown report with ROI Summary (cost, ask/deny/allow breakdown, proposals); use `--path .`
- `agentguard review` — interactive governance update cycle
- `agentguard review --guided` — AI-assisted field update
- `agentguard verify` — prompt-pin drift detection
- `agentguard verify --repair` — generate baseline pins from existing governance (no AI)
- `agentguard override` — documented exception with mandatory reason
- `agentguard propose` — create GitHub PRs for pending proposals; `--dry-run` to preview; requires `gh` CLI
- `agentguard web` — browser UI (requires pip install agentguard-governance[web])

### Web UI (v1.0.0)
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
- Header: session cost ($X.XX · model) polled every 30s via /api/session/cost
- Live Watch tab: real-time tool call feed via /ws/watch WebSocket
  - Loads last 50 historical entries on open (dimmed, separator before live)
  - Green ✓ allow / red ✗ deny per entry
  - Pulsing live status indicator
  - Allow/deny counters
- Verify Pins tab: Run Verify + Repair Pins button (brownfield baseline)
  - Repair Pins calls /api/verify-repair, then auto-runs verify
- Session Report tab: ROI Summary table (cost/ask/deny breakdown/proposals), stat cards
  (Total/Allowed/Ask/Blocked/Warnings), tool distribution bar chart, proposals section
  with per-entry status badges, blocked actions, runtime warnings
  - Reads .agentguard/session.log + agentguard.log + proposals/ via /api/report
- Terminal tab: Cost Awareness Thresholds inline editor
  - View/edit mode, levels auto-assigned (warn/alert/critical)
  - Saves via POST /api/governance/update with cost_awareness key

### Key Technical Decisions
- Enforcement: deterministic, no LLM, never probabilistic
- Concretization: claude-sonnet / gpt-4o, temperature=0
- Mission concretization: higher-capability model (sonnet/gpt-4o)
- Scope review: provider default model (haiku/gpt-4o-mini)
- Validation: deterministic structural checks, no LLM
- Pinning: SHA-256 hashes of prompt+output in governance.yaml
- Enforcer signals: prohibited/HARD_LIMIT → deny() exit 2; requires_confirmation → ask() exit 0 (per Claude Code hooks docs)
- path_policy evaluated FIRST for file-targeting tools (Write/Edit/MultiEdit/NotebookEdit) via pathspec gitignore-style patterns; denied_paths→deny, protected_paths→ask, authorized_paths→allow (then content checks still run), unmatched→default_for_unmatched. Backward compat: no path_policy key → protected_paths=CORE_ARCHITECTURE_PATHS, default="allow"
- CORE_ARCHITECTURE_PATHS constant lives in agentguard/config/loader.py (moved from enforcer to avoid circular import)
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
- cost_awareness (optional): {thresholds: [{at_usd: float, level: str}],
  repeat_last_threshold: bool (default true),
  repeat_interval_usd: float (default 2.0)}
  Old schema (warn_at_usd/alert_at_usd) auto-converted with DeprecationWarning.
- concretization_pins: list of {field, input_hash, prompt_hash,
  output_hash, model, provider, temperature, date}
- governance_history: list of {date, action, tool, version,
  changed_fields?}

### path_policy Schema (new, optional)

Top-level `governance.yaml` key for deterministic, glob-based path access control.
Patterns use gitignore syntax (via pathspec). Evaluated in order:
denied_paths → protected_paths → authorized_paths → default_for_unmatched. First match wins.
Only applies to file-editing tools (Write/Edit/MultiEdit/NotebookEdit).

```yaml
path_policy:
  denied_paths:        # always block — pattern + reason required
    - pattern: "secrets/**"
      reason: "no secret access"
  protected_paths:     # require confirmation — pattern + reason required
    - pattern: "agentguard/enforcement/**"
      reason: "core layer"
  authorized_paths:    # explicitly allowed — reason optional
    - pattern: "tests/**"
  default_for_unmatched: "deny" | "ask" | "allow"  # default: "ask" if key present
```
Backward compat: if `path_policy` key is absent, `load_path_policy()` returns
`protected_paths` = CORE_ARCHITECTURE_PATHS, `default_for_unmatched="allow"` —
exactly the pre-existing enforcement behavior, no new gate for existing users.

Parsed by `load_path_policy(governance: dict) -> PathPolicy` in `agentguard/config/loader.py`.
`CORE_ARCHITECTURE_PATHS` constant lives in `loader.py` (moved from enforcer to avoid circular import).

### Tests
- 439/439 passing
- CI: GitHub Actions, Python 3.11 + 3.12, green
- Web tests: TestClient (fastapi), PTY documented as manual-test-only

## Dogfooding Session (2026-06-12/13)

Ran `agentguard init --guided` on the AgentGuard repo itself. Found and
fixed five issues in review/concretization/enforcement:

1. Concretization prompts (_MISSION_PROMPT, _HARD_LIMITS_PROMPT,
   _FIELD_PROMPT) had no real project-structure context and a biasing
   "./src" few-shot example, producing nonexistent paths. Fixed: prompts
   now include a directory-tree scan + CLAUDE.md "Architecture Overview"
   excerpt (commit 1b3d8f4).
2. `review --guided` "Replace a rule" bypassed AI concretization and
   dropped `severity` for prohibited rules. Fixed: Replace unified with
   Add flow (a0d2a82); prohibited field routed through hard-limits
   concretization (d9e60cf); severity defaults to HARD_LIMIT
   unconditionally regardless of AI fallback (e252f3e).
3. Enforcer false positive: confirmation-text matching fired on ANY
   Edit/Write call when the rule text contained generic words like
   "modif". Fixed: write/edit confirmation matching scoped to
   `_CORE_ARCHITECTURE_PATHS` (4fd5475).
4. No structural distinction between `deny` (HARD_LIMIT/prohibited) and
   `ask` (requires_confirmation) — both returned exit 2, leading an agent
   to treat a confirmation request as "forbidden" and seek a bypass via
   Bash. Fixed: separate `ask` permission decision (exit 0) for
   requires_confirmation (f61d576); CLAUDE.md now instructs not to bypass
   `deny` via alternate tools (3524223).
5. Redundant `"rm -f" in tool_str` check caused a false positive when
   source code contained that string literally. Fixed: removed, rm regex
   scoped to Bash tool only (35bbb80).

AgentGuard's own governance.yaml was created (15 authorized rules, 11
prohibited HARD_LIMIT rules, 3 requires_confirmation, escalation: log to
owner email).

## Open Items / Backlog

**Priority order (current session):**
1. Medium-term quick wins (PDF export, pin timestamp fix)
2. v1.0.0 Intent-Aware Live Observer
3. Outreach/Tooling (ongoing, reactive)

### Medium-term
- Session Report PDF export (Web UI)
- `agentguard verify --repair` — review timestamp accuracy for repaired pins

### v1.0.0 — **Complete (2026-06-21)**
All three components shipped. v1.0.0 tagged on main.

**A) Async Approval Workflow** — **Complete.**
Stage 1: v0.10.5 (2026-06-16, commits 2f7977c + 5667342 + 5f2a577).
Stage 2: `agentguard propose` (v0.10.6, 2026-06-18, commits caa9543 +
4a98d7b + c86f3cb). ANY `ask`-gated action unresolved during the
session gets a durable proposal → surfaced as a GitHub PR.
Note: `escalation.contact` in governance.yaml must be a **GitHub
username** (not an email address) for `gh pr create --reviewer` to work.

Validated facts (empirical, 2026-06-15):
- PreToolUse hook input includes `session_id`, `tool_use_id`,
  `transcript_path`, `permission_mode`, `effort`, `cwd`.
- Stop hook fires (possibly multiple times per session) with the same
  `session_id` + `transcript_path`, plus `last_assistant_message` and
  `stop_hook_active`.
- `permission_mode` is identical ("default") in interactive and `-p`
  sessions — not a usable interactive/non-interactive signal. Approach
  abandoned in favor of retroactive, log-based detection, which works
  identically for both session types.
- PreToolUse "ask" decisions do not reveal whether the user
  subsequently approved — the hook never receives that answer.
- `session.log`'s `input_summary` is truncated to ~100 chars — not
  sufficient for reconstructing a diff; `transcript_path` has the full,
  untruncated tool call.

Stage 1 design (local detection + recording, no network/git):
1. Register AgentGuard as a PostToolUse hook (new — currently
   PreToolUse only). Log `{session_id, tool_use_id, timestamp}` on
   PostToolUse — this means the tool call executed (approved, whether
   via "allow" or an interactively-confirmed "ask").
2. On Stop: for each PreToolUse "ask" entry with this `session_id`,
   check whether a PostToolUse entry with the same `tool_use_id`
   exists.
   - Exists → approved+executed, no proposal needed (optional audit
     log only).
   - Missing → unresolved → create/update a proposal record.
3. Proposal record at `.agentguard/proposals/<tool_use_id>.json`
   (local, gitignored, consumed by Stage 2):
   - `tool_use_id`, `session_id`, `timestamp`, `tool_name`, `file_path`
   - full diff/content (old_string/new_string or full file content),
     sourced from `transcript_path` (not session.log's truncated
     `input_summary`)
   - the governance `reason` that triggered "ask"
   - `status: "pending"` (Stage 2 updates on PR creation)
4. Idempotency: `tool_use_id` as filename — Stop firing multiple times
   per session does not create duplicates.

Stage 2 preview (not yet designed in detail): a command
(`agentguard propose` or similar) reads `.agentguard/proposals/*.json`
with `status: "pending"`, creates a branch + PR per proposal (grouping
strategy TBD), sets `escalation.contact` as reviewer, updates `status`
to `"pr_created"` with the PR URL. New optional dependency: `gh` CLI or
GitHub API client (itself subject to "Add new external dependencies" —
requires_confirmation).

**B) Web UI Enhancements** — **Complete (v0.10.8, 2026-06-21).**
Live Watch tab with 50-entry history + real-time feed; session cost
header (polled every 30s); Cost Awareness Thresholds inline editor
in Terminal tab (reads/writes `governance.yaml` via `/api/governance/update`).

**C) Cost-Awareness Notification** — **Complete (v0.10.7, 2026-06-21).**
Commits: 2c15b8a (feat: Component C initial), c8060c3 (fix: browser
User-Agent + cache token split), b2fdc73 (fix: dedup per session),
141474b (feat: multi-threshold escalation + 1h cache pricing fix).

`agentguard/checks/cost.py` calculates session cost from JSONL transcript
(live pricing via urllib from Anthropic docs, hardcoded fallback). Desktop
notifications fired on Stop for each crossed threshold (warn/alert/critical),
with optional repeat above last threshold every `repeat_interval_usd`.
Old `warn_at_usd`/`alert_at_usd` schema auto-converted. Cache writes
correctly split into 5m and 1h tokens and priced separately. Cost always
logged to session.log as `event: session_cost`. `agentguard check` validates
`cost_awareness` schema. `agentguard init --guided` includes optional cost
awareness setup step (no AI required). 415 tests, ruff clean.

Original C (Intent-Aware Live Observer) remains open as a separate
future track: LLM-based drift detection via JSONL transcript analysis
(Layer 3: LLM allowed, warnings only, never blocks). Open question:
what defines "intent" (user's initial prompt? `--intent` flag?
governance.yaml's authorized scope?)

### path_policy tooling (future)
- `agentguard init --guided` generates a default `path_policy` (commit 130a877).
- `agentguard check` validates `path_policy` if present (this commit).
- Remaining future work: `agentguard review --guided` editing support.

### Optional / future
- `agentguard watch` could optionally fire a local desktop notification
  (OS-native, no new dependency) on loop/critical-failure detection —
  independent of the v1.0.0 components above.
- KI-erkannte Governance-Use-Cases: während einer Session erkennt
  AgentGuard (via Stop-Hook oder Observer) potenzielle neue
  governance.yaml-Regeln und schreibt diese als Proposals
  (.agentguard/proposals/) — Owner freigibt via PR. Erweiterung
  von Component A, nicht Component B.
### Tooling / Infrastructure
- Homebrew formula for AgentGuard
- pyenv migration on M5 Air (separate topic, not AgentGuard-specific)

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
- `agentguard/checks/cost.py` — session cost calculation, live pricing fetch, hardcoded fallback
- `agentguard/notifications.py` — cross-platform desktop notifications (macOS/Linux/Windows)
- `agentguard/web/server.py` — FastAPI + WebSocket PTY + /ws/watch + /api/verify-repair + /api/report + POST /api/governance/update + GET /api/watch/history + GET /api/session/cost + GET /api/cost-awareness
- `agentguard/checks/report.py` — Layer 4, generate_report_data() + generate_report()
- `agentguard/checks/preflight.py` — Layer 1
- `agentguard/enforcement/enforcer.py` — Layer 2, session logging
- `agentguard/enforcement/transcript.py` — JSONL transcript parser, get_tool_call() for full tool input by tool_use_id
- `agentguard/proposal.py` — Stage 2: get_pending_proposals(), create_pr_for_proposal(), format_proposal_summary()
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
- `web/src/components/ReportPanel.jsx` — session report: Executive Summary card, ROI Summary table, stat cards, tool distribution, proposals, blocked actions
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

2026-06-21 – v1.0.0 release
