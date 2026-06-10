import { useState, useEffect } from 'react'

export default function GovernanceSummary({ projectPath }) {
  const [gov, setGov] = useState(null)

  useEffect(() => {
    fetch(`/api/governance?path=${encodeURIComponent(projectPath)}`)
      .then(r => r.json())
      .then(setGov)
      .catch(() => {})
  }, [projectPath])

  if (!gov?.exists) return null

  const scope = gov.governance?.scope || {}
  const authorized = scope.authorized || []
  const prohibited = scope.prohibited || []
  const confirmation = scope.requires_confirmation || []
  const hardLimits = prohibited.filter(
    p => p.severity === 'HARD_LIMIT'
  )

  const Section = ({ label, items, color, border }) => (
    <div style={{
      background: 'var(--bg-base)',
      border: `1px solid ${border}`,
      borderRadius: '8px',
      padding: '10px 12px',
      marginBottom: '8px'
    }}>
      <div style={{
        fontSize: '11px', fontWeight: '700',
        color, marginBottom: '8px',
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <span>{label}</span>
        <span style={{
          background: 'var(--bg-elevated)',
          color: 'var(--text-muted)',
          fontSize: '10px', padding: '1px 7px',
          borderRadius: '10px', fontWeight: '500'
        }}>{items.length}</span>
      </div>
      {items.slice(0, 2).map((item, i) => (
        <div key={i} style={{
          fontSize: '11px',
          color: 'var(--text-secondary)',
          padding: '4px 0',
          borderTop: i > 0 ? '1px solid var(--border-subtle)' : 'none',
          lineHeight: '1.4'
        }}>
          {item.severity === 'HARD_LIMIT' && (
            <span style={{
              background: 'var(--critical)',
              color: '#fff', fontSize: '9px',
              padding: '1px 4px', borderRadius: '3px',
              fontWeight: '700', marginRight: '5px'
            }}>HL</span>
          )}
          {item.action?.length > 45
            ? item.action.slice(0, 45) + '…'
            : item.action}
        </div>
      ))}
      {items.length > 2 && (
        <div style={{
          fontSize: '10px', color: 'var(--text-muted)',
          marginTop: '6px'
        }}>
          +{items.length - 2} more
        </div>
      )}
    </div>
  )

  return (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: '12px',
      padding: '14px',
      height: 'fit-content'
    }}>
      <div style={{
        fontSize: '12px', fontWeight: '600',
        color: 'var(--text-muted)',
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        marginBottom: '12px'
      }}>
        Governance
      </div>

      {/* Owner strip */}
      <div style={{
        fontSize: '11px', color: 'var(--text-muted)',
        marginBottom: '12px', display: 'flex',
        justifyContent: 'space-between'
      }}>
        <span>{gov.governance?.owner}</span>
        {hardLimits.length > 0 && (
          <span style={{ color: 'var(--critical)', fontWeight: '600' }}>
            {hardLimits.length} hard limits
          </span>
        )}
      </div>

      <Section
        label="✅ Authorized"
        items={authorized}
        color="var(--ok)"
        border="rgba(16,185,129,0.2)"
      />
      <Section
        label="🚫 Prohibited"
        items={prohibited}
        color="var(--critical)"
        border="rgba(239,68,68,0.2)"
      />
      <Section
        label="⚠️ Confirms"
        items={confirmation}
        color="var(--warning)"
        border="rgba(245,158,11,0.2)"
      />
    </div>
  )
}
