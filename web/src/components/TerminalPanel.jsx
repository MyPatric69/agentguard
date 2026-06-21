import { useEffect, useRef, useState } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'

const LEVELS = ['warn', 'alert', 'critical']
const getLevel = (i) => LEVELS[Math.min(i, LEVELS.length - 1)]

function CostAwarenessEditor({ projectPath }) {
  const [data, setData] = useState(undefined)  // undefined = loading, null = absent
  const [editMode, setEditMode] = useState(false)
  const [editVals, setEditVals] = useState([''])
  const [repeatLast, setRepeatLast] = useState(true)
  const [repeatInterval, setRepeatInterval] = useState('2.00')
  const [saveError, setSaveError] = useState('')
  const [saving, setSaving] = useState(false)

  const load = () => {
    fetch(`/api/cost-awareness?path=${encodeURIComponent(projectPath)}`)
      .then(r => r.json())
      .then(d => setData(d.cost_awareness ?? null))
      .catch(() => setData(null))
  }

  useEffect(() => { setData(undefined); load() }, [projectPath])

  if (data === undefined) return null

  const enterEdit = () => {
    if (data?.thresholds?.length) {
      setEditVals(data.thresholds.map(t => String(t.at_usd)))
      setRepeatLast(data.repeat_last_threshold !== false)
      setRepeatInterval(String(data.repeat_interval_usd ?? 2.0))
    } else {
      setEditVals([''])
      setRepeatLast(true)
      setRepeatInterval('2.00')
    }
    setSaveError('')
    setEditMode(true)
  }

  const validate = () => {
    if (editVals.length === 0) return 'Add at least one threshold'
    const nums = editVals.map(v => parseFloat(v))
    if (nums.some(n => isNaN(n) || n <= 0)) return 'All values must be positive numbers'
    for (let i = 1; i < nums.length; i++) {
      if (nums[i] <= nums[i - 1]) return 'Values must be strictly ascending'
    }
    const ri = parseFloat(repeatInterval)
    if (isNaN(ri) || ri <= 0) return 'Repeat interval must be a positive number'
    return null
  }

  const handleSave = async () => {
    const err = validate()
    if (err) { setSaveError(err); return }
    setSaving(true)
    setSaveError('')
    const newData = {
      thresholds: editVals.map((v, i) => ({ at_usd: parseFloat(v), level: getLevel(i) })),
      repeat_last_threshold: repeatLast,
      repeat_interval_usd: parseFloat(repeatInterval),
    }
    try {
      const resp = await fetch('/api/governance/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: projectPath, cost_awareness: newData }),
      })
      const result = await resp.json()
      if (result.success) {
        setData(newData)
        setEditMode(false)
      } else {
        setSaveError(result.message || 'Save failed')
      }
    } catch {
      setSaveError('Network error — check server connection')
    } finally {
      setSaving(false)
    }
  }

  const cardStyle = {
    background: 'var(--bg-surface)', borderRadius: '8px',
    border: '1px solid var(--border)', padding: '12px 16px',
    marginBottom: '12px', flexShrink: 0,
  }
  const inputStyle = {
    background: 'var(--bg-base)', border: '1px solid var(--border)',
    borderRadius: '4px', padding: '4px 8px',
    color: 'var(--text-primary)', fontSize: '12px',
  }

  return (
    <div style={cardStyle}>
      <div style={{
        display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', marginBottom: editMode ? '12px' : 0
      }}>
        <span style={{
          fontSize: '11px', fontWeight: '600', color: 'var(--text-muted)',
          textTransform: 'uppercase', letterSpacing: '0.06em'
        }}>
          💰 Cost Awareness Thresholds
        </span>
        {!editMode && (
          <button onClick={enterEdit} style={{
            background: 'none', border: '1px solid var(--border)',
            borderRadius: '5px', padding: '3px 10px',
            color: 'var(--accent)', fontSize: '11px', cursor: 'pointer'
          }}>✏️ Edit</button>
        )}
      </div>

      {!editMode && (
        <div style={{ marginTop: data ? '10px' : 0 }}>
          {!data ? (
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Not configured</span>
          ) : (
            <>
              {(data.thresholds || []).map((t, i) => (
                <div key={i} style={{
                  fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '2px'
                }}>
                  <span style={{ color: 'var(--accent)', fontFamily: 'monospace' }}>
                    ${t.at_usd.toFixed(2)}
                  </span>
                  <span style={{ color: 'var(--text-muted)', margin: '0 6px' }}>→</span>
                  <span style={{
                    color: t.level === 'critical' ? 'var(--critical)' : 'var(--warning)',
                    fontSize: '11px'
                  }}>{t.level}</span>
                </div>
              ))}
              {data.repeat_last_threshold && (
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                  repeats every ${data.repeat_interval_usd ?? 2} above last threshold
                </div>
              )}
            </>
          )}
        </div>
      )}

      {editMode && (
        <div>
          {editVals.map((v, i) => (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px'
            }}>
              <span style={{
                fontSize: '11px', color: 'var(--text-muted)', width: '52px', flexShrink: 0
              }}>{getLevel(i)}</span>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>$</span>
              <input
                type="number" min="0.01" step="0.01" value={v}
                onChange={e => setEditVals(vals => vals.map((x, j) => j === i ? e.target.value : x))}
                style={{ ...inputStyle, width: '80px' }}
              />
              {editVals.length > 1 && (
                <button
                  onClick={() => setEditVals(vals => vals.filter((_, j) => j !== i))}
                  style={{
                    background: 'none', border: 'none',
                    color: 'var(--text-muted)', cursor: 'pointer', fontSize: '16px', padding: '0 2px'
                  }}>×</button>
              )}
            </div>
          ))}

          {editVals.length < 4 && (
            <button
              onClick={() => setEditVals(v => [...v, ''])}
              style={{
                background: 'none', border: '1px dashed var(--border)',
                borderRadius: '4px', padding: '3px 10px',
                color: 'var(--text-muted)', fontSize: '11px',
                cursor: 'pointer', marginBottom: '10px'
              }}>+ Add threshold</button>
          )}

          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            marginBottom: '6px', marginTop: '4px'
          }}>
            <label style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              fontSize: '11px', color: 'var(--text-muted)', cursor: 'pointer'
            }}>
              <input
                type="checkbox" checked={repeatLast}
                onChange={e => setRepeatLast(e.target.checked)}
              />
              Repeat above last threshold every $
            </label>
            <input
              type="number" min="0.01" step="0.01" value={repeatInterval}
              onChange={e => setRepeatInterval(e.target.value)}
              disabled={!repeatLast}
              style={{ ...inputStyle, width: '60px', opacity: repeatLast ? 1 : 0.4 }}
            />
          </div>

          {saveError && (
            <div style={{ fontSize: '11px', color: 'var(--critical)', marginBottom: '6px' }}>
              ⚠ {saveError}
            </div>
          )}

          <div style={{ fontSize: '10px', color: 'var(--warning)', marginBottom: '8px' }}>
            ⚠ Saving will require AgentGuard confirmation
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={handleSave} disabled={saving}
              style={{
                background: 'var(--accent)', border: 'none', borderRadius: '5px',
                padding: '5px 14px', color: '#fff', fontSize: '12px',
                cursor: saving ? 'default' : 'pointer', opacity: saving ? 0.7 : 1
              }}>
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              onClick={() => { setEditMode(false); setSaveError('') }}
              disabled={saving}
              style={{
                background: 'var(--bg-base)', border: '1px solid var(--border)',
                borderRadius: '5px', padding: '5px 14px',
                color: 'var(--text-secondary)', fontSize: '12px', cursor: 'pointer'
              }}>Cancel</button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function TerminalPanel({ projectPath, pendingCommand, onCommandConsumed }) {
  const termRef = useRef(null)
  const wsRef = useRef(null)
  const fitAddon = useRef(null)
  const [connected, setConnected] = useState(false)
  const [projectName, setProjectName] = useState('')

  useEffect(() => {
    fetch(`/api/project-info?path=${encodeURIComponent(projectPath)}`)
      .then(r => r.json())
      .then(d => setProjectName(d.name))
      .catch(() => {})
  }, [projectPath])

  useEffect(() => {
    if (!termRef.current) return

    const term = new Terminal({
      theme: {
        background: '#0d1117',
        foreground: '#e6edf3',
        cursor: '#58a6ff',
        selectionBackground: '#264f78',
        black: '#0d1117',
        brightBlack: '#6e7681',
        red: '#ff7b72',
        brightRed: '#ffa198',
        green: '#3fb950',
        brightGreen: '#56d364',
        yellow: '#d29922',
        brightYellow: '#e3b341',
        blue: '#58a6ff',
        brightBlue: '#79c0ff',
        magenta: '#bc8cff',
        brightMagenta: '#d2a8ff',
        cyan: '#39c5cf',
        brightCyan: '#56d4dd',
        white: '#b1bac4',
        brightWhite: '#f0f6fc',
      },
      fontFamily: '"SF Mono", "Fira Code", "Cascadia Code", monospace',
      fontSize: 13,
      lineHeight: 1.4,
      cursorBlink: true,
      scrollback: 1000,
    })

    const fit = new FitAddon()
    const links = new WebLinksAddon()
    term.loadAddon(fit)
    term.loadAddon(links)
    term.open(termRef.current)
    fit.fit()

    fitAddon.current = fit

    const wsUrl = `ws://localhost:8767/ws/terminal?path=${encodeURIComponent(projectPath)}`
    const ws = new WebSocket(wsUrl)
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    const sendResize = (cols, rows) => {
      if (ws.readyState === WebSocket.OPEN) {
        const buf = new Uint8Array(5)
        buf[0] = 0x01
        new DataView(buf.buffer).setUint16(1, cols)
        new DataView(buf.buffer).setUint16(3, rows)
        ws.send(buf)
      }
    }

    ws.onopen = () => {
      setConnected(true)
      sendResize(term.cols, term.rows)
    }

    ws.onmessage = (e) => {
      const data = new Uint8Array(e.data)
      term.write(data)
    }

    ws.onclose = () => {
      setConnected(false)
      term.write('\r\n\x1b[90m[Connection closed]\x1b[0m\r\n')
    }

    ws.onerror = () => {
      term.write('\r\n\x1b[31m[Connection error]\x1b[0m\r\n')
    }

    term.onData(data => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(new TextEncoder().encode(data))
      }
    })

    const resizeObs = new ResizeObserver(() => {
      fit.fit()
      sendResize(term.cols, term.rows)
    })
    resizeObs.observe(termRef.current)

    return () => {
      resizeObs.disconnect()
      ws.close()
      term.dispose()
    }
  }, [projectPath])

  useEffect(() => {
    if (pendingCommand && connected && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(new TextEncoder().encode(pendingCommand))
      onCommandConsumed?.()
    }
  }, [pendingCommand, connected])

  const quickCommands = [
    { label: '🛡️ check', cmd: 'agentguard check\r', group: 'monitor' },
    { label: '🔍 check --ai-review', cmd: 'agentguard check --ai-review\r', group: 'monitor' },
    { label: '🔐 verify', cmd: 'agentguard verify\r', group: 'monitor' },
    { label: '⚡ init --guided', cmd: 'agentguard init --guided\r', group: 'setup' },
    { label: '✏️ review --guided', cmd: 'agentguard review --guided\r', group: 'setup' },
    { label: '📋 review', cmd: 'agentguard review\r', group: 'setup' },
  ]

  const sendCmd = (cmd) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(new TextEncoder().encode(cmd))
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        marginBottom: '16px', flexShrink: 0
      }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: '700', margin: '0 0 4px' }}>
            Terminal
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
            Run agentguard commands interactively
          </p>
        </div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: '8px',
          fontSize: '12px'
        }}>
          <span style={{
            width: '8px', height: '8px', borderRadius: '50%',
            background: connected ? 'var(--ok)' : 'var(--critical)',
            display: 'inline-block'
          }}/>
          <span style={{ color: 'var(--text-muted)' }}>
            {connected ? `Connected · ${projectName || projectPath}` : 'Disconnected'}
          </span>
        </div>
      </div>

      <div style={{ marginBottom: '12px', flexShrink: 0 }}>
        <div style={{
          fontSize: '11px', color: 'var(--text-muted)',
          marginBottom: '6px', fontWeight: '600',
          textTransform: 'uppercase', letterSpacing: '0.06em'
        }}>
          Quick Commands
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {quickCommands.map(({ label, cmd }) => (
            <button key={label} onClick={() => sendCmd(cmd)}
              disabled={!connected}
              style={{
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                borderRadius: '6px', padding: '5px 12px',
                color: connected ? 'var(--accent)' : 'var(--text-muted)',
                fontSize: '12px', fontFamily: 'monospace',
                cursor: connected ? 'pointer' : 'default'
              }}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <CostAwarenessEditor projectPath={projectPath} />

      <div style={{
        flex: 1, background: '#0d1117', borderRadius: '10px',
        border: '1px solid var(--border)', padding: '12px',
        overflow: 'hidden', minHeight: '300px'
      }}>
        <div ref={termRef} style={{ height: '100%', width: '100%' }} />
      </div>
    </div>
  )
}
