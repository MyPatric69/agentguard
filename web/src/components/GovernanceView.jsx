import { useState, useEffect } from 'react'

export default function GovernanceView({ projectPath }) {
  const [gov, setGov] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/governance?path=${encodeURIComponent(projectPath)}`)
      .then(r => r.json())
      .then(setGov)
      .finally(() => setLoading(false))
  }, [projectPath])

  if (loading) return (
    <div style={{ color: '#8b949e', padding: '40px', textAlign: 'center' }}>
      Loading governance...
    </div>
  )

  if (!gov?.exists) return (
    <div style={{
      background: '#161b22', border: '1px solid #21262d',
      borderRadius: '8px', padding: '40px', textAlign: 'center'
    }}>
      <div style={{ color: '#f85149', marginBottom: '12px', fontSize: '16px' }}>
        No governance.yaml found
      </div>
      <div style={{ color: '#8b949e', fontSize: '13px' }}>
        Run: <code>agentguard init --guided</code> to create one
      </div>
    </div>
  )

  const { governance } = gov
  const scope = governance.scope || {}

  const ScopeSection = ({ title, items, color }) => (
    <div style={{ marginBottom: '24px' }}>
      <h3 style={{ fontSize: '14px', color, marginBottom: '12px' }}>{title}</h3>
      {(items || []).map((item, i) => (
        <div key={i} style={{
          background: '#0d1117', border: '1px solid #21262d',
          borderRadius: '6px', padding: '12px', marginBottom: '8px'
        }}>
          <div style={{ fontSize: '13px', fontWeight: '500', marginBottom: '4px' }}>
            {item.severity === 'HARD_LIMIT' && (
              <span style={{
                background: '#da3633', color: '#fff', fontSize: '10px',
                padding: '1px 6px', borderRadius: '3px', marginRight: '8px'
              }}>
                HARD_LIMIT
              </span>
            )}
            {item.action}
          </div>
          {item.reason && (
            <div style={{ fontSize: '12px', color: '#8b949e' }}>
              {item.reason}
            </div>
          )}
          {item.added && (
            <div style={{ fontSize: '11px', color: '#484f58', marginTop: '4px' }}>
              Added: {item.added}
            </div>
          )}
        </div>
      ))}
    </div>
  )

  return (
    <div>
      <div style={{
        background: '#161b22', border: '1px solid #21262d',
        borderRadius: '8px', padding: '16px', marginBottom: '24px',
        display: 'flex', gap: '24px'
      }}>
        <div>
          <div style={{ fontSize: '11px', color: '#8b949e' }}>OWNER</div>
          <div style={{ fontSize: '14px', fontWeight: '600' }}>
            {governance.owner}
          </div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: '#8b949e' }}>ESCALATION</div>
          <div style={{ fontSize: '14px' }}>
            {governance.escalation?.contact}
          </div>
        </div>
        <div>
          <div style={{ fontSize: '11px', color: '#8b949e' }}>KILLSWITCH</div>
          <div style={{ fontSize: '14px' }}>{governance.killswitch}</div>
        </div>
      </div>

      <ScopeSection title="✅ Authorized" items={scope.authorized} color="#3fb950" />
      <ScopeSection title="🚫 Prohibited" items={scope.prohibited} color="#f85149" />
      <ScopeSection title="⚠️ Requires Confirmation" items={scope.requires_confirmation} color="#d29922" />
    </div>
  )
}
