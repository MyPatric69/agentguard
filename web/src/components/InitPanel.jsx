import { useEffect, useState } from 'react'

function GovernanceStatusBanner({ projectPath }) {
  const [status, setStatus] = useState(null)

  useEffect(() => {
    fetch(`/api/governance?path=${encodeURIComponent(projectPath)}`)
      .then(r => r.json())
      .then(data => setStatus(data.exists))
      .catch(() => setStatus(false))
  }, [projectPath])

  if (status === null) return null
  return (
    <div style={{
      padding: '12px 16px', borderRadius: '8px',
      background: status ? 'rgba(16,185,129,0.1)' : 'rgba(239,68,68,0.1)',
      border: `1px solid ${status ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
      fontSize: '13px',
      color: status ? 'var(--ok)' : 'var(--critical)'
    }}>
      {status
        ? '✅ governance.yaml found — use Review & Update to modify'
        : '❌ No governance.yaml — run setup to create one'}
    </div>
  )
}

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

export default function InitPanel({ projectPath, runInTerminal }) {
  return (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '20px', fontWeight: '700', margin: '0 0 4px' }}>
          Setup Governance
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
          Define enforceable governance rules for this project
        </p>
      </div>

      <GovernanceStatusBanner projectPath={projectPath} />

      <div style={{ marginTop: '20px' }}>
        <CommandCard
          title="⚡ Guided Setup (Recommended)"
          description="AI-powered 5-step dialog. Translates your intent into concrete, enforceable rules. Uses claude-sonnet for reliable schema generation."
          cmd={`cd ${projectPath} && agentguard init --guided\r`}
          accent="rgba(59,130,246,0.3)"
          onRun={() => runInTerminal(`cd ${projectPath} && agentguard init --guided\r`)}
        />
        <CommandCard
          title="📝 Interactive Setup"
          description="Manual setup without AI. Fill in governance fields directly. Good for teams with existing governance policies."
          cmd={`cd ${projectPath} && agentguard init --interactive\r`}
          accent="rgba(16,185,129,0.2)"
          onRun={() => runInTerminal(`cd ${projectPath} && agentguard init --interactive\r`)}
        />
        <CommandCard
          title="📄 Template Only"
          description="Generate a governance.yaml template to fill in manually. Best for scripted or CI/CD environments."
          cmd={`cd ${projectPath} && agentguard init --template-only\r`}
          accent="rgba(99,102,241,0.2)"
          onRun={() => runInTerminal(`cd ${projectPath} && agentguard init --template-only\r`)}
        />
      </div>

      <div style={{
        marginTop: '20px', padding: '14px 16px',
        background: 'rgba(245,158,11,0.08)',
        border: '1px solid rgba(245,158,11,0.2)',
        borderRadius: '10px', fontSize: '12px',
        color: 'var(--text-muted)', lineHeight: '1.6'
      }}>
        💡 <strong style={{ color: 'var(--warning)' }}>Before running guided setup:</strong>{' '}
        know which files/paths the agent may touch, what success looks like,
        and who is accountable. AgentGuard cannot fill knowledge gaps — it exposes them.
      </div>
    </div>
  )
}
