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
