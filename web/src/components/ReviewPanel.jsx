import { useState } from 'react'

export default function ReviewPanel({ projectPath }) {
  const [copied, setCopied] = useState(null)

  const copy = (text, key) => {
    navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(null), 2000)
  }

  const CommandCard = ({ title, description, command, id, accent }) => (
    <div style={{
      background: 'var(--bg-surface)',
      border: `1px solid ${accent || 'var(--border)'}`,
      borderRadius: '12px', padding: '20px', marginBottom: '12px'
    }}>
      <div style={{ marginBottom: '12px' }}>
        <div style={{ fontSize: '15px', fontWeight: '700',
                      marginBottom: '4px' }}>{title}</div>
        <div style={{ fontSize: '13px', color: 'var(--text-muted)',
                      lineHeight: '1.5' }}>{description}</div>
      </div>
      <div style={{
        background: 'var(--bg-base)', borderRadius: '8px',
        padding: '12px 14px', display: 'flex',
        alignItems: 'center', justifyContent: 'space-between',
        fontFamily: 'monospace', fontSize: '13px', color: 'var(--accent)'
      }}>
        <span>{command}</span>
        <button onClick={() => copy(command, id)} style={{
          background: copied === id ? 'var(--ok)' : 'var(--bg-elevated)',
          color: copied === id ? '#fff' : 'var(--text-muted)',
          border: 'none', borderRadius: '6px', padding: '4px 10px',
          cursor: 'pointer', fontSize: '11px', fontWeight: '600',
          flexShrink: 0, marginLeft: '12px'
        }}>
          {copied === id ? '✓ Copied' : 'Copy'}
        </button>
      </div>
    </div>
  )

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
        id="review-guided"
        title="🤖 AI-Assisted Review (Recommended)"
        description="Review all governance fields with AI concretization. Updates only changed fields — unchanged fields are preserved. All changes logged in governance_history."
        command={`cd ${projectPath} && agentguard review --guided`}
        accent="rgba(59,130,246,0.3)"
      />
      <CommandCard
        id="review"
        title="📋 Interactive Review"
        description="Review governance fields manually. Choose which fields to keep, update, or add rules to. Mark ambiguities as resolved."
        command={`cd ${projectPath} && agentguard review`}
        accent="rgba(16,185,129,0.2)"
      />
      <CommandCard
        id="review-field"
        title="🎯 Review Specific Field"
        description="Update only authorized, prohibited, or requires_confirmation scope. Fastest for targeted changes."
        command={`cd ${projectPath} && agentguard review --field authorized`}
        accent="rgba(99,102,241,0.2)"
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
