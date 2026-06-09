import { useEffect, useRef, useState } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'

export default function TerminalPanel({ projectPath }) {
  const termRef = useRef(null)
  const termInstance = useRef(null)
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
    termInstance.current = term

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
      term.write('\r\n\x1b[32m AgentGuard Terminal\x1b[0m')
      term.write(`\r\n\x1b[90m Project: ${projectPath}\x1b[0m\r\n\r\n`)
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

  const quickCommands = [
    { label: 'check', cmd: 'agentguard check\r' },
    { label: 'check --ai-review', cmd: 'agentguard check --ai-review\r' },
    { label: 'init --guided', cmd: 'agentguard init --guided\r' },
    { label: 'review --guided', cmd: 'agentguard review --guided\r' },
    { label: 'verify', cmd: 'agentguard verify\r' },
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

      <div style={{
        display: 'flex', gap: '8px', marginBottom: '12px',
        flexWrap: 'wrap', flexShrink: 0
      }}>
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

      <div style={{
        flex: 1, background: '#0d1117', borderRadius: '10px',
        border: '1px solid var(--border)', padding: '12px',
        overflow: 'hidden', minHeight: '400px'
      }}>
        <div ref={termRef} style={{ height: '100%', width: '100%' }} />
      </div>
    </div>
  )
}
