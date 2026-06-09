import { useState, useEffect } from 'react'
import CheckPanel from './components/CheckPanel.jsx'
import GovernanceView from './components/GovernanceView.jsx'

function VerifyPanel({ projectPath }) {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const runVerify = async () => {
    setLoading(true)
    try {
      const res = await fetch(`/api/verify?path=${encodeURIComponent(projectPath)}`)
      setResult(await res.json())
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center',
                    justifyContent: 'space-between', marginBottom: '20px' }}>
        <h2 style={{ margin: 0, fontSize: '16px' }}>Pin Verification</h2>
        <button onClick={runVerify} disabled={loading} style={{
          background: '#1f6feb', color: '#fff', border: 'none',
          borderRadius: '6px', padding: '8px 16px', cursor: 'pointer',
          fontSize: '13px', fontWeight: '600'
        }}>
          {loading ? 'Verifying...' : 'Run Verify'}
        </button>
      </div>
      {result && (
        <div style={{
          background: '#161b22', border: '1px solid #21262d',
          borderRadius: '8px', padding: '20px'
        }}>
          <div style={{
            marginBottom: '12px', fontWeight: '700', fontSize: '14px',
            color: result.success ? '#3fb950' : '#f85149'
          }}>
            {result.success ? '✅ All pins verified' : '⚠️ Pin issues detected'}
          </div>
          {result.output && (
            <pre style={{
              fontSize: '12px', color: '#8b949e', whiteSpace: 'pre-wrap',
              fontFamily: 'monospace', lineHeight: '1.5'
            }}>
              {result.output}
            </pre>
          )}
        </div>
      )}
      {!result && !loading && (
        <div style={{
          background: '#161b22', border: '1px solid #21262d',
          borderRadius: '8px', padding: '40px', textAlign: 'center',
          color: '#8b949e', fontSize: '14px'
        }}>
          Click "Run Verify" to check concretization pin integrity
        </div>
      )}
    </div>
  )
}

export default function App() {
  const [activeTab, setActiveTab] = useState('check')
  const [projectPath, setProjectPath] = useState('.')

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0d1117',
      color: '#e6edf3',
      fontFamily: 'system-ui, sans-serif'
    }}>
      <header style={{
        borderBottom: '1px solid #21262d',
        padding: '16px 24px',
        display: 'flex',
        alignItems: 'center',
        gap: '16px'
      }}>
        <div style={{ fontSize: '20px', fontWeight: '700', color: '#58a6ff' }}>
          🛡️ AgentGuard
        </div>
        <div style={{ fontSize: '12px', color: '#8b949e' }}>v0.6.0</div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
          {['check', 'governance', 'verify'].map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)} style={{
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              background: activeTab === tab ? '#1f6feb' : '#21262d',
              color: activeTab === tab ? '#fff' : '#8b949e',
              fontSize: '13px',
              fontWeight: activeTab === tab ? '600' : '400'
            }}>
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>
      </header>

      <div style={{
        padding: '12px 24px',
        background: '#161b22',
        borderBottom: '1px solid #21262d',
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
      }}>
        <span style={{ fontSize: '13px', color: '#8b949e' }}>Project:</span>
        <input
          value={projectPath}
          onChange={e => setProjectPath(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && setProjectPath(e.target.value)}
          placeholder="Enter project path..."
          style={{
            background: '#0d1117',
            border: '1px solid #30363d',
            borderRadius: '6px',
            padding: '6px 12px',
            color: '#e6edf3',
            fontSize: '13px',
            width: '400px'
          }}
        />
        <span style={{ fontSize: '12px', color: '#484f58' }}>
          Multiple projects: run agentguard web --port 8768 in second terminal
        </span>
      </div>

      <main style={{ padding: '24px' }}>
        {activeTab === 'check' && <CheckPanel projectPath={projectPath} />}
        {activeTab === 'governance' && <GovernanceView projectPath={projectPath} />}
        {activeTab === 'verify' && <VerifyPanel projectPath={projectPath} />}
      </main>
    </div>
  )
}
