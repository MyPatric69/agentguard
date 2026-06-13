# Changelog

All notable changes to this project will be documented in this file.

> This changelog starts with v0.10.1. Earlier project history is not
> retroactively documented here — see AI_CONTEXT.md for prior context.

## [Unreleased]

### Added
- `review --guided` now asks "Make further changes?" after each saved
  edit, looping back to the review menu instead of exiting.

### Fixed
- Fixed enforcer false positive where any `git push` triggered ask for
  requires_confirmation rules mentioning "git push" in their text — now
  only tag-related push operations match (`git push --tags`,
  `git push origin vX.Y`, `git push refs/tags/*`, `git tag`).

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
