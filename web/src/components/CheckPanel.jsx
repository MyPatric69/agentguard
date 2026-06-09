import { useState } from 'react'
import StatusBadge from './StatusBadge.jsx'

export default function CheckPanel({ projectPath }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const runCheck = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/check?path=${encodeURIComponent(projectPath)}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const checks = await res.json()
      const hasCritical = checks.some(c => c.severity === 'critical')
      const hasWarning = checks.some(c => c.severity === 'warning')
      const overall = hasCritical ? 'BLOCKED' : hasWarning ? 'WARNINGS' : 'ALL CLEAR'
      setResult({ checks, result: overall })
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center',
                    justifyContent: 'space-between', marginBottom: '8px' }}>
        <h2 style={{ margin: 0, fontSize: '16px' }}>Pre-Flight Check</h2>
        <button onClick={runCheck} disabled={loading} style={{
          background: '#1f6feb', color: '#fff', border: 'none',
          borderRadius: '6px', padding: '8px 16px', cursor: 'pointer',
          fontSize: '13px', fontWeight: '600'
        }}>
          {loading ? 'Checking...' : 'Run Check'}
        </button>
      </div>

      {error && (
        <div style={{ color: '#f85149', fontSize: '13px', marginTop: '8px', marginBottom: '12px' }}>
          Error: {error}
        </div>
      )}

      {result && (
        <div style={{
          background: '#161b22', border: '1px solid #21262d',
          borderRadius: '8px', padding: '20px', marginTop: '12px'
        }}>
          <div style={{ marginBottom: '16px' }}>
            <StatusBadge result={result.result} />
          </div>
          {result.checks && result.checks.map((check, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'flex-start', gap: '12px',
              padding: '8px 0', borderBottom: '1px solid #21262d'
            }}>
              <span style={{ fontSize: '16px', flexShrink: 0 }}>
                {check.severity === 'ok' ? '🟢' :
                 check.severity === 'warning' ? '🟡' :
                 check.severity === 'critical' ? '🔴' : '🔵'}
              </span>
              <div style={{ fontSize: '13px', color: '#e6edf3' }}>
                {check.message}
              </div>
            </div>
          ))}
        </div>
      )}

      {!result && !loading && !error && (
        <div style={{
          background: '#161b22', border: '1px solid #21262d',
          borderRadius: '8px', padding: '40px', textAlign: 'center',
          color: '#8b949e', fontSize: '14px', marginTop: '12px'
        }}>
          Click "Run Check" to validate governance prerequisites
        </div>
      )}
    </div>
  )
}
