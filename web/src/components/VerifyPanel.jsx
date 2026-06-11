import { useState } from 'react'

export default function VerifyPanel({ projectPath }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [repairResult, setRepairResult] = useState(null)
  const [repairing, setRepairing] = useState(false)

  const runVerify = async () => {
    setLoading(true)
    try {
      const res = await fetch(
        `/api/verify-json?path=${encodeURIComponent(projectPath)}`
      )
      setResult(await res.json())
    } finally { setLoading(false) }
  }

  const runRepair = async () => {
    setRepairing(true)
    try {
      const res = await fetch(
        `/api/verify-repair?path=${encodeURIComponent(projectPath)}`
      )
      setRepairResult(await res.json())
      await runVerify()
    } finally { setRepairing(false) }
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
        <div style={{ display: 'flex', gap: '8px' }}>
          <button onClick={runRepair} disabled={repairing || loading} style={{
            background: 'var(--bg-elevated)',
            color: 'var(--text-secondary)',
            border: '1px solid var(--border)',
            borderRadius: '8px',
            padding: '10px 16px',
            cursor: repairing ? 'default' : 'pointer',
            fontSize: '14px', fontWeight: '600'
          }}>
            {repairing ? '⏳ Repairing...' : '🔧 Repair Pins'}
          </button>
          <button onClick={runVerify} disabled={loading} style={{
            background: loading ? 'var(--bg-elevated)' : 'var(--accent)',
            color: '#fff', border: 'none', borderRadius: '8px',
            padding: '10px 20px', cursor: loading ? 'default' : 'pointer',
            fontSize: '14px', fontWeight: '600'
          }}>
            {loading ? '⏳ Verifying...' : 'Run Verify'}
          </button>
        </div>
      </div>

      {repairResult && (
        <div style={{
          background: repairResult.repaired > 0
            ? 'rgba(16,185,129,0.1)' : 'rgba(99,102,241,0.1)',
          border: `1px solid ${repairResult.repaired > 0
            ? 'rgba(16,185,129,0.3)' : 'rgba(99,102,241,0.3)'}`,
          borderRadius: '8px', padding: '10px 14px',
          marginBottom: '12px', fontSize: '13px',
          color: repairResult.repaired > 0 ? 'var(--ok)' : 'var(--info)'
        }}>
          🔧 {repairResult.message}
        </div>
      )}

      {result && (
        <div>
          {/* Status banner */}
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
                {result.message}
              </div>
              {result.success && (
                <div style={{ fontSize: '12px', color: 'var(--text-muted)',
                              marginTop: '2px' }}>
                  Concretization outputs match stored hashes
                </div>
              )}
            </div>
          </div>

          {/* Pin cards */}
          {result.success && result.pins.map((pin, i) => (
            <div key={i} style={{
              background: 'var(--bg-surface)',
              border: '1px solid rgba(16,185,129,0.2)',
              borderRadius: '10px', padding: '14px 16px',
              marginBottom: '8px',
              display: 'flex', alignItems: 'center', gap: '12px'
            }}>
              <span style={{
                background: 'rgba(16,185,129,0.15)',
                color: 'var(--ok)', fontSize: '13px',
                padding: '4px 10px', borderRadius: '6px', fontWeight: '600',
                flexShrink: 0
              }}>✓ verified</span>
              <div>
                <div style={{ fontSize: '13px', fontWeight: '600',
                              color: 'var(--text-primary)' }}>
                  {pin.field}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)',
                              marginTop: '2px' }}>
                  {pin.model}{pin.model && pin.date ? ' · ' : ''}{pin.date}
                </div>
              </div>
            </div>
          ))}
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
