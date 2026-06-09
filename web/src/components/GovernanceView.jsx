import { useState, useEffect } from 'react'

const SECTION_CONFIG = {
  authorized: {
    label: '✅ Authorized',
    color: 'var(--ok)',
    bg: 'rgba(16,185,129,0.05)',
    border: 'rgba(16,185,129,0.2)'
  },
  prohibited: {
    label: '🚫 Prohibited',
    color: 'var(--critical)',
    bg: 'rgba(239,68,68,0.05)',
    border: 'rgba(239,68,68,0.2)'
  },
  requires_confirmation: {
    label: '⚠️ Requires Confirmation',
    color: 'var(--warning)',
    bg: 'rgba(245,158,11,0.05)',
    border: 'rgba(245,158,11,0.2)'
  }
}

function ScopeCard({ sectionKey, items }) {
  const cfg = SECTION_CONFIG[sectionKey]
  if (!items || items.length === 0) return null
  return (
    <div style={{
      background: cfg.bg, border: `1px solid ${cfg.border}`,
      borderRadius: '12px', padding: '16px', marginBottom: '16px'
    }}>
      <div style={{
        fontSize: '13px', fontWeight: '700', color: cfg.color,
        marginBottom: '12px', display: 'flex', alignItems: 'center',
        gap: '8px'
      }}>
        {cfg.label}
        <span style={{
          background: 'var(--bg-elevated)', color: 'var(--text-muted)',
          fontSize: '11px', padding: '1px 8px', borderRadius: '10px',
          fontWeight: '500'
        }}>{items.length}</span>
      </div>
      {items.map((item, i) => (
        <div key={i} style={{
          background: 'var(--bg-surface)', borderRadius: '8px',
          padding: '12px', marginBottom: i < items.length - 1 ? '8px' : 0
        }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
            {item.severity === 'HARD_LIMIT' && (
              <span style={{
                background: 'var(--critical)', color: '#fff',
                fontSize: '9px', padding: '2px 6px', borderRadius: '3px',
                fontWeight: '700', flexShrink: 0, marginTop: '2px'
              }}>HARD LIMIT</span>
            )}
            <div>
              <div style={{
                fontSize: '13px', fontWeight: '500',
                color: 'var(--text-primary)', marginBottom: '4px'
              }}>{item.action}</div>
              {item.reason && (
                <div style={{
                  fontSize: '12px', color: 'var(--text-muted)',
                  lineHeight: '1.5'
                }}>{item.reason}</div>
              )}
              {item.added && (
                <div style={{
                  fontSize: '11px', color: 'var(--bg-elevated)',
                  marginTop: '4px'
                }}>Added {item.added}</div>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default function GovernanceView({ projectPath }) {
  const [gov, setGov] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/governance?path=${encodeURIComponent(projectPath)}`)
      .then(r => r.json())
      .then(data => { setGov(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [projectPath])

  if (loading) return (
    <div style={{ color: 'var(--text-muted)', padding: '60px',
                  textAlign: 'center' }}>Loading governance...</div>
  )

  if (!gov?.exists) return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px dashed var(--border)',
      borderRadius: '12px', padding: '60px', textAlign: 'center'
    }}>
      <div style={{ fontSize: '32px', marginBottom: '12px' }}>📋</div>
      <div style={{ fontSize: '15px', marginBottom: '6px',
                    color: 'var(--text-primary)' }}>
        No governance found
      </div>
      <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
        Run <code>agentguard init --guided</code> to create governance
      </div>
    </div>
  )

  const { governance } = gov
  const scope = governance.scope || {}

  return (
    <div>
      <div style={{ marginBottom: '20px' }}>
        <h1 style={{ fontSize: '20px', fontWeight: '700', margin: '0 0 4px' }}>
          Governance
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
          Defined rules for this agent session
        </p>
      </div>

      <div style={{
        background: 'var(--bg-surface)', borderRadius: '12px',
        border: '1px solid var(--border)', padding: '16px',
        marginBottom: '20px', display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px'
      }}>
        {[
          { label: 'Owner', value: governance.owner },
          { label: 'Escalation', value: governance.escalation?.contact },
          { label: 'Killswitch', value: governance.killswitch }
        ].map(({ label, value }) => (
          <div key={label}>
            <div style={{ fontSize: '10px', fontWeight: '600',
                          color: 'var(--text-muted)', textTransform: 'uppercase',
                          letterSpacing: '0.08em', marginBottom: '4px' }}>
              {label}
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-primary)',
                          fontWeight: '500' }}>
              {value || '—'}
            </div>
          </div>
        ))}
      </div>

      <ScopeCard sectionKey="authorized" items={scope.authorized} />
      <ScopeCard sectionKey="prohibited" items={scope.prohibited} />
      <ScopeCard sectionKey="requires_confirmation" items={scope.requires_confirmation} />
    </div>
  )
}
