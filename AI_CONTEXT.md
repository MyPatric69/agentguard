# AI_CONTEXT.md

> Keep this file current. Update after each significant session.

---

## Project

**Name:** AgentGuard  
**Version:** 0.3.0  
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

## Current State (v0.3.0)

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
- agentguard init: generates .claude/settings.json with PreToolUse hook
  - Merge-safe: existing hooks preserved when settings.json exists
  - interactive + template-only modes
- agentguard override: mandatory reason, logged to agentguard-overrides.log
- 95/95 tests passing, ruff clean
- CI: GitHub Actions, Python 3.11 + 3.12 matrix, green

## Open Items (v0.3.0 Part B)

- PyPI publish
- Homebrew formula
- OpenAI Agents + LangChain support
- SKILL.md validation improvements
- Runtime Watch via native JSONL (direct Claude Code log integration)

## Key Files

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
- LinkedIn: https://www.linkedin.com/posts/patric-hayna-6b7b55134_the-blind-spot-of-agentic-ai-systems-when-activity-7467668285891821568-ZXtx

---

## Last updated

2026-06-06 – Auto-synced 1 commit(s) to 48cc8b2
