import { useState } from 'react'
import StatusBadge from './StatusBadge.jsx'

export default function CheckPanel({ projectPath }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const runCheck = async () => {
    setLoading(true)
    try {
      const res = await fetch(`/api/check?path=${encodeURIComponent(projectPath)}`)
      setResult(await res.json())
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center',
                    justifyContent: 'space-between', marginBottom: '20px' }}>
        <h2 style={{ margin: 0, fontSize: '16px' }}>Pre-Flight Check</h2>
        <button onClick={runCheck} disabled={loading} style={{
          background: '#1f6feb', color: '#fff', border: 'none',
          borderRadius: '6px', padding: '8px 16px', cursor: 'pointer',
          fontSize: '13px', fontWeight: '600'
        }}>
          {loading ? 'Checking...' : 'Run Check'}
        </button>
      </div>

      {result && (
        <div style={{
          background: '#161b22', border: '1px solid #21262d',
          borderRadius: '8px', padding: '20px'
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
                {check.level === 'ok' ? '🟢' :
                 check.level === 'warning' ? '🟡' :
                 check.level === 'critical' ? '🔴' : '🔵'}
              </span>
              <div>
                <div style={{ fontSize: '13px', fontWeight: '500' }}>
                  {check.status}
                </div>
                <div style={{ fontSize: '12px', color: '#8b949e' }}>
                  {check.message}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {!result && !loading && (
        <div style={{
          background: '#161b22', border: '1px solid #21262d',
          borderRadius: '8px', padding: '40px', textAlign: 'center',
          color: '#8b949e', fontSize: '14px'
        }}>
          Click "Run Check" to validate governance prerequisites
        </div>
      )}
    </div>
  )
}
