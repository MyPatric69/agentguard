const CommandCard = ({ title, description, cmd, accent, onRun }) => (
  <div style={{
    background: 'var(--bg-surface)',
    border: `1px solid ${accent || 'var(--border)'}`,
    borderRadius: '12px', padding: '20px', marginBottom: '12px'
  }}>
    <div style={{ marginBottom: '16px' }}>
      <div style={{ fontSize: '15px', fontWeight: '700',
                    marginBottom: '4px' }}>{title}</div>
      <div style={{ fontSize: '13px', color: 'var(--text-muted)',
                    lineHeight: '1.5' }}>{description}</div>
    </div>
    <div style={{
      display: 'flex', alignItems: 'center', gap: '12px'
    }}>
      <code style={{
        flex: 1, background: 'var(--bg-base)', borderRadius: '6px',
        padding: '8px 12px', fontSize: '12px', color: 'var(--accent)',
        fontFamily: 'monospace'
      }}>
        {cmd.replace('\r', '')}
      </code>
      <button onClick={onRun} style={{
        background: 'var(--accent)', color: '#fff',
        border: 'none', borderRadius: '6px',
        padding: '8px 16px', cursor: 'pointer',
        fontSize: '12px', fontWeight: '600', flexShrink: 0
      }}>
        ▶ Run in Terminal
      </button>
    </div>
  </div>
)

export default function ReviewPanel({ projectPath, runInTerminal }) {
  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '20px', fontWeight: '700', margin: '0 0 4px' }}>
          Review & Update
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
          Keep governance current as your project evolves
        </p>
      </div>

      <CommandCard
        title="🤖 AI-Assisted Review (Recommended)"
        description="Review all governance fields with AI concretization. Updates only changed fields — unchanged fields are preserved. All changes logged in governance_history."
        cmd={`cd "${projectPath}" && agentguard review --guided\r`}
        accent="rgba(59,130,246,0.3)"
        onRun={() => runInTerminal(`cd "${projectPath}" && agentguard review --guided\r`)}
      />
      <CommandCard
        title="📋 Interactive Review"
        description="Review governance fields manually. Choose which fields to keep, update, or add rules to. Mark ambiguities as resolved."
        cmd={`cd "${projectPath}" && agentguard review\r`}
        accent="rgba(16,185,129,0.2)"
        onRun={() => runInTerminal(`cd "${projectPath}" && agentguard review\r`)}
      />
      <CommandCard
        title="🎯 Review Specific Field"
        description="Update only authorized, prohibited, or requires_confirmation scope. Fastest for targeted changes."
        cmd={`cd "${projectPath}" && agentguard review --field authorized\r`}
        accent="rgba(99,102,241,0.2)"
        onRun={() => runInTerminal(`cd "${projectPath}" && agentguard review --field authorized\r`)}
      />

      <div style={{
        marginTop: '8px', padding: '14px 16px',
        background: 'rgba(59,130,246,0.08)',
        border: '1px solid rgba(59,130,246,0.2)',
        borderRadius: '10px', fontSize: '12px',
        color: 'var(--text-muted)', lineHeight: '1.6'
      }}>
        💡 <strong style={{ color: 'var(--accent)' }}>When to review:</strong>{' '}
        after significant project scope changes, team handovers,
        when unresolved ambiguities need addressing, or periodically
        as a governance audit. All changes are logged in
        <code style={{ margin: '0 4px' }}>governance_history</code>.
      </div>
    </div>
  )
}
