import { useState } from 'react'

export default function VerifyPanel({ projectPath }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const runVerify = async () => {
    setLoading(true)
    try {
      const res = await fetch(
        `/api/verify?path=${encodeURIComponent(projectPath)}`
      )
      setResult(await res.json())
    } finally { setLoading(false) }
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between',
                    alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: '700', margin: 0 }}>
            Verify Pins
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)',
                      margin: '4px 0 0' }}>
            Confirms governance was generated consistently
          </p>
        </div>
        <button onClick={runVerify} disabled={loading} style={{
          background: loading ? 'var(--bg-elevated)' : 'var(--accent)',
          color: '#fff', border: 'none', borderRadius: '8px',
          padding: '10px 20px', cursor: loading ? 'default' : 'pointer',
          fontSize: '14px', fontWeight: '600'
        }}>
          {loading ? '⏳ Verifying...' : 'Run Verify'}
        </button>
      </div>

      {result && (
        <div>
          <div style={{
            background: result.success ? 'rgba(16,185,129,0.1)' :
                        'rgba(239,68,68,0.1)',
            border: `1px solid ${result.success ?
              'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)'}`,
            borderRadius: '12px', padding: '16px 20px',
            marginBottom: '16px', display: 'flex',
            alignItems: 'center', gap: '12px'
          }}>
            <span style={{ fontSize: '24px' }}>
              {result.success ? '✅' : '⚠️'}
            </span>
            <div>
              <div style={{
                fontSize: '15px', fontWeight: '600',
                color: result.success ? 'var(--ok)' : 'var(--warning)'
              }}>
                {result.success
                  ? 'All pins verified — governance is reproducible'
                  : 'Pin issues detected'}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)',
                            marginTop: '2px' }}>
                {result.success
                  ? 'Concretization outputs match stored hashes'
                  : 'Re-run agentguard init --guided to regenerate pins'}
              </div>
            </div>
          </div>

          <div style={{
            background: 'var(--bg-surface)', borderRadius: '12px',
            border: '1px solid var(--border)', padding: '16px'
          }}>
            <pre style={{
              margin: 0, fontSize: '12px', color: 'var(--text-muted)',
              fontFamily: 'monospace', whiteSpace: 'pre-wrap'
            }}>{result.output}</pre>
          </div>
        </div>
      )}

      {!result && !loading && (
        <div style={{
          background: 'var(--bg-surface)', borderRadius: '12px',
          border: '1px dashed var(--border)', padding: '60px',
          textAlign: 'center', color: 'var(--text-muted)'
        }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>🔐</div>
          <div style={{ fontSize: '15px', marginBottom: '6px',
                        color: 'var(--text-primary)' }}>
            Ready to verify
          </div>
          <div style={{ fontSize: '13px' }}>
            Checks that governance pins match their stored hashes
          </div>
        </div>
      )}
    </div>
  )
}
