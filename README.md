# AgentGuard

**Governance layer for autonomous AI agents — pre-flight checks, runtime monitoring, and post-session reporting.**

> "You wouldn't launch a rocket without a pre-launch checklist. Why run an autonomous agent without one?"

**Maximum instruction, minimum interpretation.**

**AgentGuard doesn't eliminate the probability of failure. It reduces the impact.**

[![CI](https://github.com/MyPatric69/agentguard/actions/workflows/ci.yml/badge.svg)](https://github.com/MyPatric69/agentguard/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/agentguard-governance.svg)](https://badge.fury.io/py/agentguard-governance)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## The Problem: Observability vs Governance — the Gap

The AI agent tooling landscape is rich with **observability** tools — LangSmith, Langfuse, Helicone, Arize. They answer: *"What did the agent do?"*

But they don't answer: *"Should the agent have started at all?"*

AgentGuard fills the gap **before** execution: it checks that governance prerequisites are in place, monitors for loops and stalls at runtime, and produces a post-session governance report.

Read the full context: [The Blind Spot of Agentic AI Systems](https://dev.to/mypatric69/the-blind-spot-of-agentic-ai-systems-when-nobody-notices-the-agent-is-stuck-1hkb)

---

## AgentGuard vs Observability Tools

| Feature | LangSmith | Langfuse | Helicone | Arize | **AgentGuard** |
|---|---|---|---|---|---|
| Pre-flight governance check | — | — | — | — | **Yes** |
| Owner / scope / escalation enforcement | — | — | — | — | **Yes** |
| Killswitch verification | — | — | — | — | **Yes** |
| Instruction file validation | — | — | — | — | **Yes** |
| Runtime loop detection | Partial | — | — | Partial | **Yes** |
| Post-session governance report | — | Partial | — | — | **Yes** |
| Token / cost monitoring | Yes | Yes | Yes | Yes | Threshold |
| Trace visualization | Yes | Yes | — | Yes | — |
| Prompt replay / debugging | Yes | Yes | — | — | — |
| Works with any agent framework | — | — | — | — | **Yes** |

AgentGuard is not a replacement for observability tools — it is the layer that runs **before** they do.

---

## Prerequisite Level 0: The "Fuel in the Car" Metaphor

Before you drive, you check: fuel, seatbelt, mirrors. These are non-negotiable prerequisites — you don't skip them because you're in a hurry.

AgentGuard's Level 0 checks are the equivalent for autonomous agents:

| Check | What it verifies |
|---|---|
| **OWNER** | Someone is responsible for this agent |
| **SCOPE** | The agent knows what it's allowed to do |
| **ESCALATION** | There is a human to contact when things go wrong |
| **KILLSWITCH** | There is a documented way to stop the agent |

These are CRITICAL by default. An agent without an owner is an unaccountable system. An agent without a killswitch is a runaway process waiting to happen.

---

## Quick Start

```bash
pip install agentguard-governance
cd my-agent-project
agentguard check
```

If your project lacks governance prerequisites, you'll see:

```
╭─────────── AGENTGUARD — PRE-FLIGHT CHECK ────────────╮
│   Project:  ./my-agent-project                       │
│   Checked:  2026-06-06 15:00:00                      │
│                                                      │
│   🔴 CRITICAL   No agent owner defined               │
│   🔴 CRITICAL   No authorized scope defined          │
│   🔴 CRITICAL   No prohibited actions defined        │
│   🔴 CRITICAL   No escalation path configured        │
│   🔴 CRITICAL   No killswitch defined                │
│   🔴 CRITICAL   No CLAUDE.md or AGENTS.md found      │
│                 (fix: create CLAUDE.md first)        │
│                                                      │
│   RESULT: BLOCKED — 6 critical gaps                  │
│                                                      │
│   This agent cannot start until governance           │
│   gaps are resolved or explicitly overridden.        │
│                                                      │
│   agentguard init --interactive                      │
│   agentguard override --reason "..."                 │
╰──────────────────────────────────────────────────────╯
```

Fix it interactively:

```bash
agentguard init --interactive
```

---

## CLI Commands

### `agentguard check`

Run a pre-flight governance check.

```bash
agentguard check                          # check current directory
agentguard check --path ./my-project      # check a specific path
agentguard check --config ./gov.yaml      # use a specific governance.yaml
agentguard check --format json            # machine-readable output
agentguard check --ai-review              # include AI-powered scope quality review
```

**Exit codes:**
- `0` — OK or warnings only (with or without AI review)
- `1` — CRITICAL findings found
- `2` — Config error

> `--ai-review` requires `AGENTGUARD_AI_PROVIDER` and `AGENTGUARD_AI_API_KEY`
> in `.env` or environment. Without them, AI review is silently skipped.

---

### `agentguard init`

Initialize governance for a project.

```bash
agentguard init --guided        # AI-powered 5-step concretization (requires API key)
agentguard init --interactive   # guided Q&A with inline examples,
                                # generates governance.yaml + CLAUDE.md block
agentguard init --template-only # copies governance.yaml.example to ./governance.yaml
```

Interactive mode guides you through:
- Agent owner, scope (authorized / prohibited / confirmation-required)
- Escalation contact with format validation
- Escalation method (log / terminal / file)
- Killswitch definition

All free-text inputs are sanitized — quote characters are stripped
automatically to prevent YAML parse errors.

---

### `agentguard init --guided`

AI-powered 5-step guided concretization. Answer 5 questions in plain language —
AgentGuard uses an AI provider to transform your intent into enforceable rules.

```bash
agentguard init --guided
```

**Requires** `AGENTGUARD_AI_PROVIDER` and `AGENTGUARD_AI_API_KEY` in `.env`.
Without them, use `agentguard init --interactive` instead.

**What it does:**

1. **Owner** — who is responsible for this session
2. **Mission** — free-text description → AI splits into authorized / prohibited / confirmation scope
3. **Hard Limits** — things the agent must never do → AI adds to prohibited scope
4. **Escalation** — how to reach you when something goes wrong
5. **Killswitch** — how to stop the agent

After all 5 steps, a **review panel** shows the full governance before saving.
You can adjust individual fields or start over.

**Adjustment loop:** Each AI-concretized field offers up to 3 rounds of
refinement. If the AI cannot improve further, your raw input is saved with a
warning.

**What gets written:**

- `governance.yaml` — with metadata comment block (`Generated by: agentguard init --guided`)
- `.claude/settings.json` — PreToolUse hook (merge-safe)
- `CLAUDE.md` — AgentGuard governance block appended

**Graceful degradation:** API failure → raw input saved, flow continues.
Ctrl+C → prompted to save progress before exiting.

---

### `agentguard watch`

Start runtime observer. Reads a JSON tool-call log from the agent harness.

```bash
agentguard watch                          # watch agent.log (default)
agentguard watch --log ./my-agent.log     # watch a specific log file
agentguard watch --interval 5             # poll every 5 seconds
```

Emits `LOOP_WARNING`, `STALL_WARNING`, and `BURN_WARNING` events to console and appends to `agentguard.log`.

**Expected log format (one JSON object per line):**

```json
{"tool": "bash", "tokens": 150}
{"tool": "bash", "tokens": 150}
{"tool": "read_file", "tokens": 80}
```

---

### `agentguard report`

Generate a post-session Markdown governance report.

```bash
agentguard report                                      # reads agentguard.log, writes report.md
agentguard report --session ./run1.log --output r.md   # custom paths
```

---

### `agentguard review`

Review and update existing governance.yaml interactively.

```bash
agentguard review                          # interactive field-by-field review
agentguard review --guided                 # AI-assisted rule concretization
agentguard review --field authorized       # review a specific field only
agentguard review --path ./my-project      # review a project in another directory
```

Shows a summary of current governance, then offers:
- **Review all fields** — walk through each scope field, keep/add/remove/replace rules
- **Review specific field** — focus on one field
- **Add new rules** — append to an existing field
- **Mark ambiguities as resolved** — close open ambiguities with an audit timestamp
- **View full governance.yaml** — Rich syntax-highlighted display

All changes are logged in `governance_history` with the date, tool, and changed fields.

---

### `agentguard override`

Override CRITICAL findings and proceed. The `--reason` flag is mandatory and the override is logged.

```bash
agentguard override --reason "Emergency hotfix — owner notified verbally"
agentguard override --reason "Demo environment — no real escalation needed" --path ./demo
```

Override log is written to `agentguard-overrides.log`.

---

### `agentguard verify`

Verify governance.yaml was generated consistently.
Detects drift if prompts or outputs changed since last pin.

```bash
agentguard verify                              # verify current directory
agentguard verify --config path/to/governance.yaml
```

After `agentguard init --guided`, a `concretization_pins` block is written to
`governance.yaml`. Each pin records the SHA-256 hashes of the prompt, output,
model, provider, and temperature used during AI concretization.

`agentguard verify` checks:
- All required pin fields are present
- `temperature` is `0` (deterministic output guaranteed)

| Exit code | Meaning |
|---|---|
| `0` | All pins verified — governance is reproducible |
| `1` | Pin issues found (missing, incomplete, or temperature drift) |
| `2` | governance.yaml not found |

---

## Consistency & Reproducibility

When `agentguard init --guided` generates governance rules, it records
**prompt-pins** alongside each concretized field:

```yaml
concretization_pins:
  - field: "mission"
    input_hash: "abc123def456abcd"
    prompt_hash: "def456abc123ef01"
    output_hash: "1234567890abcdef"
    model: "claude-sonnet-4-20250514"
    provider: "anthropic"
    temperature: 0
    date: "2026-06-09"
```

This answers: *"How were these governance rules generated — and can we reproduce them?"*

The hashes are SHA-256 truncated to 16 chars for readability. They don't
re-verify the AI output automatically (the AI is non-deterministic even at
temperature=0 across versions), but they document the exact conditions under
which governance was created. Use `agentguard verify` to check structural
integrity.

---

## How AgentGuard Works — Four Layers

### Layer 1 — Before the agent starts (Pre-Flight)
`agentguard check` validates governance prerequisites.
`agentguard check --ai-review` adds AI-powered scope quality scoring.

### Layer 2 — While the agent runs (Enforcement)
`agentguard enforce` runs as a Claude Code PreToolUse hook.
Deterministic — no LLM. Checks every tool call against governance.yaml.
Exit 2 = blocked. Exit 0 = allowed.

### Layer 3 — Monitoring (Runtime Watch)
`agentguard watch` reads native Claude Code JSONL transcripts.
Detects loops, stalls, and token burn in real time.

### Layer 4 — After the session (Reporting & Audit)
`agentguard report` generates a Markdown governance report.
`agentguard verify` checks governance consistency via prompt pins.
`agentguard review` updates governance for changed projects.

---

## Complete Command Reference

| Command | Purpose | Requires API Key |
|---|---|---|
| `agentguard check` | Pre-flight governance validation | No |
| `agentguard check --ai-review` | + AI scope quality scoring | Yes |
| `agentguard init --interactive` | Basic guided setup | No |
| `agentguard init --guided` | AI-concretized governance setup | Yes |
| `agentguard enforce` | PreToolUse hook handler | No |
| `agentguard watch` | Runtime JSONL monitoring | No |
| `agentguard report` | Post-session governance report | No |
| `agentguard review` | Update existing governance | No |
| `agentguard review --guided` | AI-assisted governance update | Yes |
| `agentguard verify` | Check governance consistency/drift | No |
| `agentguard override` | Proceed despite critical gaps | No |
| `agentguard web` | Browser UI — check, governance, terminal | No (API key optional) |
| `agentguard web --path p1 --path p2` | Multi-project browser UI | No |

---

## AI-Powered Scope Review (Optional)

AgentGuard can use an AI provider to assess the quality of your governance
scope — catching vague, incomplete, or ungovernable definitions that
string-based checks miss.

**Model selection:** AgentGuard uses different models for different tasks:
- Scope review (`--ai-review`): provider default (e.g. claude-haiku, gpt-4o-mini)
- Governance concretization (`--guided`): higher-capability model
  (claude-sonnet for Anthropic, gpt-4o for OpenAI) for schema reliability
- All concretization calls use `temperature=0` for consistency

### API Key Setup

**Option 1: Project-level .env (recommended for per-project keys)**
```bash
cd my-agent-project
cat > .env << 'EOF'
AGENTGUARD_AI_PROVIDER=anthropic
AGENTGUARD_AI_API_KEY=your-api-key-here
EOF
```

**Option 2: Global config (works across all projects)**
```bash
mkdir -p ~/.agentguard
cat > ~/.agentguard/.env << 'EOF'
AGENTGUARD_AI_PROVIDER=anthropic
AGENTGUARD_AI_API_KEY=your-api-key-here
EOF
```

**Option 3: Environment variables**
```bash
# Add to ~/.zshrc
export AGENTGUARD_AI_PROVIDER=anthropic
export AGENTGUARD_AI_API_KEY=your-api-key-here
```

Priority: environment variables → project .env → global config.
Project-level always overrides global — local settings win.

### Setup

Supported providers:

| Provider | Value | Default Model |
|---|---|---|
| Anthropic | `anthropic` | claude-haiku-4-5-20251001 |
| OpenAI | `openai` | gpt-4o-mini |
| Anysphere (Cursor) | `anysphere` | cursor-small |
| OpenAI-compatible | `openai-compatible` | set `AGENTGUARD_AI_MODEL` |

### Model Selection for Concretization

AgentGuard uses different models for different tasks:

| Task | Default Model | Override |
|---|---|---|
| Scope quality review (`--ai-review`) | `claude-haiku-4-5` | `AGENTGUARD_AI_MODEL` |
| Governance concretization (`--guided`) | `claude-sonnet-4-6` | `AGENTGUARD_MISSION_MODEL` |

**Upgrade to Claude Fable 5** for maximum concretization quality:

```bash
# In .env
AGENTGUARD_MISSION_MODEL=claude-fable-5
```

Claude Fable 5 (June 9, 2026) is Anthropic's first publicly available
Mythos-class model — the tier above Opus. It delivers significantly
better results on complex, multi-step governance definitions.
Priced at $10/$50 per million tokens (2× Sonnet).

Free on Anthropic Pro/Max/Team plans until June 22, 2026.

### Usage

```bash
agentguard check --ai-review
```

AI review is always opt-in. Without `--ai-review`, AgentGuard runs fully
offline with no API calls and no external dependencies.

---

## How AgentGuard Enforces — Layer 2

After `agentguard init`, your project contains `.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [{
      "matcher": "Bash|Write|Edit|MultiEdit|NotebookEdit",
      "hooks": [{"type": "command", "command": "agentguard enforce"}]
    }]
  }
}
```

Every tool call Claude Code attempts fires `agentguard enforce` first.
AgentGuard reads your `governance.yaml` and checks:

- Does this action violate the **prohibited scope**?
- Does this action require **human confirmation**?

If yes → `exit 2`. Claude Code receives the denial reason and cannot
proceed with that action. This is deterministic — it fires every time,
regardless of model behavior or context length.

All enforcement decisions are logged to `agentguard-enforcement.log`.

### What AgentGuard cannot do

AgentGuard enforces at the tool execution layer. It cannot prevent
Claude from *reasoning* toward a blocked action — only from *executing* it.
For production systems, combine with OS-level sandboxing.

See [What AgentGuard Cannot Do](#what-agentguard-cannot-do) for the full list.

---

## governance.yaml Reference

```yaml
# Required (CRITICAL if missing)
owner: "Jane Smith"

scope:
  authorized:
    - action: "Read and write Python files in ./src"
      reason: "Core task — agent must modify source files"
      added: "2026-06-07"

  prohibited:
    - action: "No database schema changes or production writes"
      reason: "Production data changes require human review — no exceptions"
      severity: "HARD_LIMIT"
      added: "2026-06-07"
    - action: "No git push to main branch"
      reason: "All changes must go through pull request review"
      severity: "HARD_LIMIT"
      added: "2026-06-07"

  requires_confirmation:
    - action: "Any file deletion outside ./tmp"
      reason: "File deletion is irreversible — requires explicit sign-off"
      added: "2026-06-07"

escalation:
  contact: "jane@example.com"
  method: "log"              # log | terminal | file
  trigger: "2+ critical failures or loop detected"

killswitch: "Ctrl+C"

governance_history:
  - date: "2026-06-09"
    action: "Initial governance created"
    tool: "agentguard init --guided"
    version: "0.5.1"

# Concretization consistency (added by agentguard init --guided)
concretization_pins:
  - field: "mission"
    input_hash: "a1b2c3d4e5f6g7h8"
    prompt_hash: "b2c3d4e5f6g7h8i9"
    output_hash: "c3d4e5f6g7h8i9j0"
    model: "claude-sonnet-4-20250514"
    provider: "anthropic"
    temperature: 0
    date: "2026-06-09"

# Severity overrides (critical | warning | info)
severity:
  no_owner: critical
  no_scope: critical
  no_escalation: critical
  no_killswitch: critical
  no_instruction_file: critical
  no_loop_detection: warning
  no_root_cause_rule: warning
  no_api_research_rule: info
  no_attempt_counter: warning
  no_action_log: warning
  no_skill_md: warning

# Runtime thresholds
runtime:
  loop_threshold: 2
  progress_check_interval: 10
  token_burn_threshold: 5000
  progress_scoring: false        # requires ANTHROPIC_API_KEY

# Override policy
override:
  allowed: true
  require_reason: true
  log_overrides: true
```

### Why structured governance matters

Each governance rule includes:
- **action** — what is allowed, prohibited, or requires confirmation
- **reason** — why this decision was made (critical for future reference)
- **severity** — `HARD_LIMIT`, `CRITICAL`, or `WARNING` (prohibited rules only)
- **added** — when the rule was created

Six months from now — after staff changes, project handovers, or
simply forgetting — the `reason` field answers: "What did we mean by this?"

Governance without context is a checklist. Governance with context
is institutional memory.

> Legacy flat-string format is still supported for backward compatibility.

---

## What AgentGuard Checks

### Level 0 — Governance Prerequisites (CRITICAL)

| Check | Rule |
|---|---|
| Owner | `governance.yaml` has non-empty `owner` field |
| Scope | `governance.yaml` has non-empty `scope` field |
| Escalation | `governance.yaml` has `escalation.contact` field |
| Killswitch | `governance.yaml` has `killswitch` field |
| Instruction file | `CLAUDE.md` or `AGENTS.md` present in project root |
| security.md absent | INFO — consider documenting security policies |

### Prompt Quality (WARNING)

| Check | Keywords scanned in CLAUDE.md / AGENTS.md |
|---|---|
| Loop detection | loop, iteration, attempt, stuck, retry |
| Root-cause analysis | root cause, root_cause, diagnose before, confirm before |
| External API research | fetch, documentation, never rely on memory, aktuelle |

### Harness Quality (WARNING)

| Check | Patterns scanned in `*.py` files |
|---|---|
| Attempt counter | `attempt_count`, `retry_count`, `max_attempts` |
| Action log | `action_log`, `log_action`, `append.*log` |
| Error pattern detection | `same_error`, `error_pattern`, `consecutive_errors` |

---

## Governance Review Cycle

Governance defined today may not fit your project in three months.
`agentguard review` ensures governance stays current.

```bash
# Review all governance fields interactively
agentguard review

# Review with AI-assisted concretization
agentguard review --guided

# Review a specific field only
agentguard review --field authorized

# Review a project in another directory
agentguard review --path ./my-project
```

Use `agentguard review` when:
- The project scope has changed significantly
- Team members have changed (handover situation)
- Unresolved ambiguities need to be addressed
- A governance audit is due
- The agent produced unexpected results

All changes are logged in `governance_history` — full audit trail
of when governance changed, what changed, and which tool was used.

---

## Pre-Inquiry — Quality In, Quality Out

The quality of your governance is directly proportional to the
quality of your preparation.

AgentGuard cannot fill knowledge gaps — it exposes them.
The owner bears responsibility for what they define.

Before running `agentguard init --guided`, know:
- Which directories and files the agent may touch
- Which external APIs or services are involved
- What success looks like — in measurable terms
- Who is accountable when something goes wrong
- What the agent must never do — without exceptions

Vague input produces vague governance. Vague governance produces
unenforceable rules. Unenforceable rules produce incidents.

---

## What AgentGuard Cannot Do

- **Guarantee model behavior** — AgentGuard enforces at the tool
  execution layer. It cannot prevent Claude from reasoning toward
  a blocked action, only from executing it.
- **Fill knowledge gaps** — Ambiguities in your governance definition
  reflect real gaps in your understanding of the agent's scope.
  AgentGuard documents them; you must resolve them.
- **Replace security practices** — For production systems, combine
  AgentGuard with OS-level sandboxing (Docker, seccomp, file ACLs).
- **Enforce on non-hook frameworks** — Enforcement requires Claude
  Code hooks. For other frameworks, use `agentguard enforce`
  manually in your own harness.

---

## Regulatory Alignment

AgentGuard is designed to be compatible with:

- **Singapore IMDA Model Governance Framework** — human oversight, accountability, and documentation requirements
- **Anthropic — Building Effective Agents** — loop detection, progress monitoring, and controlled escalation
- **EU AI Act GPAI provisions** (effective August 2, 2026) — transparency, human oversight, and risk management for general-purpose AI systems

AgentGuard does not provide legal compliance. It provides the **technical prerequisites** that compliance frameworks require.

---

## Web Interface

```bash
pip install "agentguard-governance[web]"
agentguard web
```

Opens `http://localhost:8767` with:

| Tab | Purpose |
|---|---|
| Pre-Flight Check | Run governance validation, see results visually |
| Governance | View all governance rules with color-coded sections |
| Verify Pins | Check concretization consistency |
| Terminal | Run any agentguard command interactively |
| Setup Governance | Guided, interactive, or template setup |
| Review & Update | Update governance as project evolves |

All commands including interactive ones (`init --guided`,
`review --guided`) run directly in the browser terminal.
Click "▶ Run in Terminal" in Setup or Review to launch
any command without leaving the browser.

```bash
agentguard web                                    # single project (current dir)
agentguard web --path ./my-project                # specific project
agentguard web --path ./proj1 --path ./proj2      # multiple projects
agentguard web --port 8888                        # custom port
agentguard web --no-browser                       # don't auto-open browser
```

**Multiple projects:** pass `--path` multiple times. The sidebar shows
a project switcher — all panels update when you switch projects.
Projects with governance.yaml show ✓, projects without show ⚠.

> Requires macOS or Linux (Python `pty` module).

### Building the web frontend

Before packaging or running from source, build the frontend:

```bash
bash scripts/build_web.sh
```

This builds the React app and copies it to `agentguard/web/dist/`
where FastAPI can serve it.

For hot-reload development:

```bash
cd web
npm install
npm run build   # builds to web/dist/ — served by FastAPI
npm run dev     # hot-reload dev server (proxies API to :8767)
```

---

## Development

```bash
git clone https://github.com/MyPatric69/agentguard
cd agentguard
pip install -e ".[dev]"
pytest --tb=short
ruff check agentguard tests
```

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

*Built for developers who believe that governance should be a first-class concern, not an afterthought.*
