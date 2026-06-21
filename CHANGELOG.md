# Changelog

All notable changes to this project will be documented in this file.

> This changelog starts with v0.10.1. Earlier project history is not
> retroactively documented here — see AI_CONTEXT.md for prior context.

## [Unreleased]

### Changed
- Component C cost notifications refactored to multi-threshold
  escalation (Option B): configurable `thresholds` list with
  `warn`/`alert`/`critical` levels, repeat notification above last
  threshold at configurable interval (`repeat_interval_usd`).
  Old `warn_at_usd`/`alert_at_usd` schema auto-converted with
  `DeprecationWarning`.
- `agentguard init --guided` now includes an optional cost awareness
  setup step (no AI required): enter comma-separated USD thresholds
  and repeat interval; levels assigned warn/alert/critical
  automatically.

### Fixed
- Cache write tokens now correctly priced: `ephemeral_5m_input_tokens`
  at $3.75/MTok and `ephemeral_1h_input_tokens` at $6.00/MTok
  (previously all cache writes were priced at the 5m rate —
  underestimated cost by up to 37.5% for 1h cached sessions).
  Session log now records `cache_write_5m_tokens` and
  `cache_write_1h_tokens` separately for auditability.

### Added (original Component C, carried forward)
- `agentguard/checks/cost.py`: session cost calculation with live
  pricing fetch and hardcoded fallback (no new required dependencies).
- `agentguard/notifications.py`: cross-platform desktop notifications
  (macOS/Linux/Windows). No additional dependencies required on macOS.
  Now handles `critical` level (title "AgentGuard Critical",
  macOS sound "Basso").
- `agentguard check` validates `cost_awareness` schema
  (INFO if absent, PASS with threshold count + repeat interval if
  valid, FAIL if invalid).

## [0.10.6] - 2026-06-18

### Added
- `agentguard propose` command: reads pending proposals from
  `.agentguard/proposals/` and creates a GitHub PR per proposal
  via `gh` CLI, with `escalation.contact` as reviewer. Supports
  `--dry-run` to preview without creating PRs. Requires `gh` CLI
  (`https://cli.github.com`). Branches from `main` via git worktree
  for clean isolation; updates each proposal's `status` to
  `"pr_created"` and records the `pr_url` on success.

### Fixed
- `agentguard propose`: convert absolute `file_path` to relative before
  git worktree operations — absolute paths from proposal JSON were
  rejected by git as outside the worktree.
- `agentguard propose`: force push proposal branches (`--force`) to
  handle retry after partial failure when the branch already exists on
  the remote.
- `agentguard propose`: recover gracefully when a PR already exists for
  a proposal branch — looks up the existing PR URL via `gh pr list`,
  records it as `pr_created`, and continues. Re-raises only if the PR
  is no longer open.

## [0.10.5] - 2026-06-16

### Added
- AgentGuard now registers as a PostToolUse hook and logs executed
  tool calls to session.log — foundation for async approval workflow
  (Component A, v1.0.0).
- New `agentguard/enforcement/transcript.py` — parses Claude Code JSONL
  transcripts to extract full, untruncated tool call details by
  tool_use_id (used by async approval workflow, Component A).
- Stop hook handler correlates PreToolUse "ask" decisions against
  PostToolUse executions — unresolved asks (rejected or headless
  sessions) are written as proposal records to
  `.agentguard/proposals/<tool_use_id>.json` for future PR-based
  approval (Component A, Stage 2).
- PreToolUse session.log entries now include `tool_use_id` field,
  enabling correlation with PostToolUse entries.

## [0.10.4] - 2026-06-15

### Added
- `agentguard init --guided` now generates a default `path_policy`
  section deterministically from the project's directory structure
  (no AI involved).
- `agentguard check` now validates `path_policy` (if present) and
  reports its presence/absence informationally (no score impact when
  absent, for backward compatibility).

## [0.10.3] - 2026-06-14

### Added
- New `path_policy` governance.yaml section for deterministic,
  glob-pattern-based path access control (`denied_paths`, `protected_paths`,
  `authorized_paths`, `default_for_unmatched`). Evaluated before existing
  prohibited/requires_confirmation checks for file-editing tools.
  Backward compatible — configs without `path_policy` behave as before.

## [0.10.2] - 2026-06-13

### Added
- `review --guided` now prompts "Make further changes? [y/n]" after each
  saved edit, looping back to the review menu instead of exiting (commit
  6ec47c4).

### Fixed
- Enforcer false positive: any `git push` triggered `ask` for
  requires_confirmation rules that mention "git push" in their text.
  Now only tag-related push operations match (`--tags`, `refs/tags/`,
  version-like tag patterns, `git tag` commands) (commit 6222e9f).

### Docs
- Added CHANGELOG.md (this file) — release history starts at v0.10.1.
- Updated README: corrected deny/ask exit code documentation, documented
  review --guided loop, added CHANGELOG link, fixed stale version example.

## [0.10.1] - 2026-06-13

### Security
- Fixed enforcer false positive where write/edit confirmation matching
  fired on any Edit/Write call due to generic keyword matching; scoped to
  core architecture paths.
- Added a distinct `ask` permission decision (vs `deny`) for
  requires_confirmation rules, preventing agents from misinterpreting a
  confirmation request as a denial and seeking a workaround.
- Removed a redundant `rm -f` string check that caused false positives on
  source code containing that string.

### Fixed
- `review --guided` "Replace a rule" now uses the same AI concretization
  flow as "Add new rule" (previously bypassed concretization and dropped
  `severity`).
- Prohibited scope rules added via guided review now default to
  `severity: HARD_LIMIT` even when AI concretization is unavailable.
- Concretization prompts (mission, hard limits, field) now ground
  suggested paths in the real project structure instead of a generic
  "./src" example.
