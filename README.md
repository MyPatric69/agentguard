# AgentGuard

**Governance layer for autonomous AI agents — pre-flight checks, runtime monitoring, and post-session reporting.**

> "You wouldn't launch a rocket without a pre-launch checklist. Why run an autonomous agent without one?"

[![CI](https://github.com/MyPatric69/agentguard/actions/workflows/ci.yml/badge.svg)](https://github.com/MyPatric69/agentguard/actions/workflows/ci.yml)
![PyPI — coming soon](https://img.shields.io/badge/PyPI-coming%20soon-lightgrey)
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
pip install agentguard
cd my-agent-project
agentguard check
```

If your project lacks governance prerequisites, you'll see:

```
╔══════════════════════════════════════════════════╗
║           AGENTGUARD — PRE-FLIGHT CHECK          ║
╠══════════════════════════════════════════════════╣
║  Project:  ./my-agent-project                    ║
║  Checked:  2026-06-02 21:14:33                   ║
╠══════════════════════════════════════════════════╣
║  🔴 CRITICAL   No agent owner defined            ║
║  🔴 CRITICAL   No escalation path configured     ║
║  🟡 WARNING    No loop detection in CLAUDE.md    ║
║  🟡 WARNING    No attempt counter in harness     ║
║  🟢 OK         CLAUDE.md present                 ║
║  🟢 OK         Scope defined                     ║
╠══════════════════════════════════════════════════╣
║  RESULT: BLOCKED — 2 critical gaps               ║
║                                                  ║
║  This agent cannot start until governance        ║
║  gaps are resolved or explicitly overridden.     ║
║                                                  ║
║  agentguard init --interactive                   ║
║  agentguard override --reason "..."              ║
╚══════════════════════════════════════════════════╝
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
```

**Exit codes:**
- `0` — OK or warnings only
- `1` — CRITICAL findings found
- `2` — Config error

---

### `agentguard init`

Initialize governance for a project.

```bash
agentguard init --interactive   # guided Q&A, generates governance.yaml + CLAUDE.md block
agentguard init --template-only # copies governance.yaml.example to ./governance.yaml
```

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

### `agentguard override`

Override CRITICAL findings and proceed. The `--reason` flag is mandatory and the override is logged.

```bash
agentguard override --reason "Emergency hotfix — owner notified verbally"
agentguard override --reason "Demo environment — no real escalation needed" --path ./demo
```

Override log is written to `agentguard-overrides.log`.

---

## governance.yaml Reference

```yaml
# Required (CRITICAL if missing)
owner: "Jane Smith"
scope:
  authorized: "Refactor authentication module — read/write Python files only"
  prohibited: "No database operations, no deletions outside ./src"
  requires_confirmation: "Any git push, any file deletion"
escalation:
  contact: "jane@example.com"
  trigger: "2+ critical failures or loop detected"
killswitch: "Ctrl+C"

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

## Regulatory Alignment

AgentGuard is designed to be compatible with:

- **Singapore IMDA Model Governance Framework** — human oversight, accountability, and documentation requirements
- **Anthropic — Building Effective Agents** — loop detection, progress monitoring, and controlled escalation
- **EU AI Act GPAI provisions** (effective August 2, 2026) — transparency, human oversight, and risk management for general-purpose AI systems

AgentGuard does not provide legal compliance. It provides the **technical prerequisites** that compliance frameworks require.

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
