# AgentGuard — Skills & Workflows

## Release Workflow
1. Feature commit: `feat/fix/refactor(scope): description`
2. `pytest --tb=short` — all tests green
3. `ruff check agentguard tests` — clean
4. `cd web && npm run build` (if frontend changed)
5. Release commit: `chore: release vX.Y.Z`
   - CHANGELOG.md: [Unreleased] → [X.Y.Z] - date
   - pyproject.toml: version bump
   - AI_CONTEXT.md: version + last updated
6. `git tag vX.Y.Z && git push origin vX.Y.Z`
7. Approve PyPI publish workflow on GitHub Actions
8. `pip install agentguard-governance[web] --upgrade
   --break-system-packages && pyenv rehash`

## Claude Code Prompt Format
- Single Markdown code block, no text before or after
- All git operations included in the prompt
- No version bumps without explicit owner confirmation

## Testing
- `pytest --tb=short -q` — quick pass/fail
- `pytest --tb=short` — full output on failure
- Always run before committing

## Frontend Build
- `cd web && npm run build` — builds to agentguard/web/dist/
- vite.config.js outDir: '../agentguard/web/dist'
- Always rebuild before release commit if JSX changed
