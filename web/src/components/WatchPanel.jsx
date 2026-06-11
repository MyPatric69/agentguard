import { useState, useEffect, useRef } from 'react'

export default function WatchPanel({ projectPath }) {
  const [entries, setEntries] = useState([])
  const [status, setStatus] = useState('connecting')
  const [stats, setStats] = useState({ allowed: 0, denied: 0, total: 0 })
  const wsRef = useRef(null)
  const bottomRef = useRef(null)

  useEffect(() => {
    const ws = new WebSocket(
      `ws://localhost:8767/ws/watch?path=${encodeURIComponent(projectPath)}`
    )
    wsRef.current = ws

    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data)
      if (msg.type === 'status') {
        setStatus(msg.exists ? 'watching' : 'waiting')
      } else if (msg.type === 'waiting') {
        setStatus('waiting')
      } else if (msg.type === 'entry') {
        const entry = msg.data
        setEntries(prev => [...prev.slice(-100), entry])
        setStats(prev => ({
          total: prev.total + 1,
          allowed: prev.allowed + (entry.decision === 'allow' ? 1 : 0),
          denied: prev.denied + (entry.decision === 'deny' ? 1 : 0),
        }))
      }
    }

    ws.onclose = () => setStatus('disconnected')
    ws.onerror = () => setStatus('error')

    return () => ws.close()
  }, [projectPath])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [entries])

  const DECISION_COLOR = {
    allow: 'var(--ok)',
    deny: 'var(--critical)',
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', marginBottom: '16px', flexShrink: 0
      }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: '700', margin: '0 0 4px' }}>
            Live Watch
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
            Real-time tool call monitoring
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <span style={{ fontSize: '12px', color: 'var(--ok)' }}>
            ✓ {stats.allowed} allowed
          </span>
          <span style={{ fontSize: '12px', color: 'var(--critical)' }}>
            ✗ {stats.denied} blocked
          </span>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            fontSize: '12px',
            color: status === 'watching' ? 'var(--ok)' :
                   status === 'waiting' ? 'var(--warning)' :
                   'var(--critical)'
          }}>
            <span style={{
              width: '8px', height: '8px', borderRadius: '50%',
              background: 'currentColor',
              animation: status === 'watching' ? 'pulse 2s infinite' : 'none'
            }}/>
            {status === 'watching' ? 'Live' :
             status === 'waiting' ? 'Waiting for session...' :
             status}
          </div>
        </div>
      </div>

      <div style={{
        flex: 1, background: 'var(--bg-surface)',
        borderRadius: '12px', border: '1px solid var(--border)',
        overflow: 'auto', padding: '12px'
      }}>
        {entries.length === 0 ? (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: '100%', color: 'var(--text-muted)', fontSize: '14px',
            flexDirection: 'column', gap: '8px'
          }}>
            <div style={{ fontSize: '32px' }}>👁️</div>
            <div>Start a Claude Code session to see live activity</div>
            <code style={{ fontSize: '12px' }}>claude</code>
          </div>
        ) : (
          entries.map((entry, i) => (
            <div key={i} style={{
              display: 'flex', gap: '10px', alignItems: 'flex-start',
              padding: '6px 0',
              borderBottom: '1px solid var(--border-subtle)',
              fontSize: '12px'
            }}>
              <span style={{
                color: DECISION_COLOR[entry.decision] || 'var(--text-muted)',
                flexShrink: 0, fontWeight: '700', width: '14px'
              }}>
                {entry.decision === 'allow' ? '✓' : '✗'}
              </span>
              <span style={{ color: 'var(--accent)', flexShrink: 0, width: '80px' }}>
                {entry.tool}
              </span>
              <span style={{
                color: 'var(--text-secondary)', flex: 1,
                overflow: 'hidden', textOverflow: 'ellipsis',
                whiteSpace: 'nowrap'
              }}>
                {entry.input_summary}
              </span>
              {entry.reason && (
                <span style={{
                  color: 'var(--critical)', fontSize: '11px',
                  flexShrink: 0, maxWidth: '200px',
                  overflow: 'hidden', textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap'
                }}>
                  {entry.reason}
                </span>
              )}
              <span style={{
                color: 'var(--text-muted)', flexShrink: 0, fontSize: '10px'
              }}>
                {new Date(entry.timestamp).toLocaleTimeString()}
              </span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  )
}
