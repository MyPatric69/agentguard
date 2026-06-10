import { useState } from 'react'
import GovernanceSummary from './GovernanceSummary.jsx'

function ScoreRing({ checks }) {
  if (!checks) return null
  const total = checks.length
  const ok = checks.filter(c => c.severity === 'ok').length
  const pct = Math.round((ok / total) * 100)
  const r = 56, circ = 2 * Math.PI * r
  const dash = (pct / 100) * circ
  const color = pct === 100 ? 'var(--ok)' :
                pct >= 70 ? 'var(--warning)' : 'var(--critical)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '28px',
                  padding: '24px 28px', background: 'var(--bg-surface)',
                  borderRadius: '12px', marginBottom: '20px',
                  border: '1px solid var(--border)' }}>
      <svg width="140" height="140" style={{ flexShrink: 0 }}>
        <circle cx="70" cy="70" r={r} fill="none"
          stroke="var(--bg-elevated)" strokeWidth="8"/>
        <circle cx="70" cy="70" r={r} fill="none"
          stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 70 70)"
          style={{ transition: 'stroke-dasharray 0.5s ease' }}/>
        <text x="70" y="64" textAnchor="middle"
          fill="var(--text-primary)" fontSize="24" fontWeight="700">
          {pct}%
        </text>
        <text x="70" y="84" textAnchor="middle"
          fill="var(--text-muted)" fontSize="12">
          checks ok
        </text>
      </svg>
      <div>
        <div style={{ fontSize: '22px', fontWeight: '700', color,
                      marginBottom: '4px' }}>
          {pct === 100 ? '✅ All Clear' :
           checks.some(c => c.severity === 'critical') ? '🔴 Blocked' :
           '⚠️ Warnings'}
        </div>
        <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
          {ok} of {total} checks passed
        </div>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)',
                      marginTop: '4px' }}>
          {checks.filter(c => c.severity === 'critical').length > 0 &&
            <span style={{ color: 'var(--critical)' }}>
              {checks.filter(c => c.severity === 'critical').length} critical
            </span>}
          {checks.filter(c => c.severity === 'warning').length > 0 &&
            <span style={{ color: 'var(--warning)', marginLeft: '8px' }}>
              {checks.filter(c => c.severity === 'warning').length} warning
            </span>}
        </div>
      </div>
    </div>
  )
}

export default function CheckPanel({ projectPath, onStatusChange }) {
  const [checks, setChecks] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const runCheck = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(
        `/api/check?path=${encodeURIComponent(projectPath)}`
      )
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setChecks(data)
      if (onStatusChange) {
        const warnings = data.filter(c => c.severity === 'warning').length
        const criticals = data.filter(c => c.severity === 'critical').length
        const overall = criticals > 0 ? 'BLOCKED' : warnings > 0 ? 'WARNINGS' : 'ALL CLEAR'
        const detail = criticals > 0 ? `${criticals} critical` :
                       warnings > 0 ? `${warnings} warning${warnings > 1 ? 's' : ''}` :
                       'all clear'
        onStatusChange(overall, detail)
      }
    } catch(e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const ICON = { ok: '🟢', warning: '🟡', critical: '🔴', info: '🔵' }
  const BG = {
    ok: 'transparent',
    warning: 'rgba(245,158,11,0.05)',
    critical: 'rgba(239,68,68,0.05)',
    info: 'transparent'
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: '700', margin: 0 }}>
            Pre-Flight Check
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)',
                      margin: '4px 0 0' }}>
            Validates governance prerequisites before agent starts
          </p>
        </div>
        <button onClick={runCheck} disabled={loading} style={{
          background: loading ? 'var(--bg-elevated)' : 'var(--accent)',
          color: '#fff', border: 'none', borderRadius: '8px',
          padding: '10px 20px', cursor: loading ? 'default' : 'pointer',
          fontSize: '14px', fontWeight: '600'
        }}>
          {loading ? '⏳ Checking...' : 'Run Check'}
        </button>
      </div>

      {error && (
        <div style={{ background: 'var(--critical-bg)',
                      border: '1px solid var(--critical)',
                      borderRadius: '8px', padding: '12px 16px',
                      color: 'var(--critical)', fontSize: '13px',
                      marginBottom: '16px' }}>
          {error}
        </div>
      )}

      {checks && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: '1fr 220px',
          gap: '16px',
          alignItems: 'start'
        }}>
          {/* Left column — score ring + checks list */}
          <div>
            <ScoreRing checks={checks} />
            <div style={{ background: 'var(--bg-surface)',
                          borderRadius: '12px', border: '1px solid var(--border)',
                          overflow: 'hidden' }}>
              {checks.map((check, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'flex-start', gap: '12px',
                  padding: '12px 16px',
                  borderBottom: i < checks.length - 1
                    ? '1px solid var(--border-subtle)' : 'none',
                  background: BG[check.severity] || 'transparent'
                }}>
                  <span style={{ fontSize: '14px', marginTop: '1px' }}>
                    {ICON[check.severity] || '⚪'}
                  </span>
                  <span style={{
                    fontSize: '13px',
                    color: check.severity === 'critical' ? 'var(--critical)' :
                           check.severity === 'warning' ? 'var(--warning)' :
                           check.severity === 'info' ? 'var(--text-muted)' :
                           'var(--text-primary)'
                  }}>
                    {check.message}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Right column — governance summary */}
          <GovernanceSummary projectPath={projectPath} />
        </div>
      )}

      {!checks && !loading && !error && (
        <div style={{
          background: 'var(--bg-surface)', borderRadius: '12px',
          border: '1px dashed var(--border)', padding: '60px',
          textAlign: 'center', color: 'var(--text-muted)'
        }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>🛡️</div>
          <div style={{ fontSize: '15px', marginBottom: '6px',
                        color: 'var(--text-primary)' }}>
            Ready to check
          </div>
          <div style={{ fontSize: '13px' }}>
            Click "Run Check" to validate governance prerequisites
          </div>
        </div>
      )}
    </div>
  )
}
