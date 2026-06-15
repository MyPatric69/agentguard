# Changelog

All notable changes to this project will be documented in this file.

> This changelog starts with v0.10.1. Earlier project history is not
> retroactively documented here — see AI_CONTEXT.md for prior context.

## [Unreleased]

### Added
- `agentguard init --guided` now generates a default `path_policy`
  section deterministically from the project's directory structure
  (no AI involved).

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
