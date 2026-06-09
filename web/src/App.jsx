import { useState } from 'react'
import CheckPanel from './components/CheckPanel.jsx'
import GovernanceView from './components/GovernanceView.jsx'
import VerifyPanel from './components/VerifyPanel.jsx'
import './index.css'

const NAV_ITEMS = [
  { id: 'check', label: 'Pre-Flight Check', icon: '🛡️', group: 'monitor' },
  { id: 'governance', label: 'Governance', icon: '📋', group: 'monitor' },
  { id: 'verify', label: 'Verify Pins', icon: '🔐', group: 'monitor' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('check')
  const [projectPath, setProjectPath] = useState('.')
  const [checkStatus, setCheckStatus] = useState(null)

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      background: 'var(--bg-base)',
      color: 'var(--text-primary)',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    }}>
      {/* Top Header */}
      <header style={{
        height: '52px',
        background: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 20px',
        gap: '12px',
        flexShrink: 0
      }}>
        <span style={{ fontSize: '18px' }}>🛡️</span>
        <span style={{
          fontSize: '16px', fontWeight: '700', color: 'var(--accent)'
        }}>AgentGuard</span>
        <span style={{
          fontSize: '11px', color: 'var(--text-muted)',
          background: 'var(--bg-elevated)', padding: '2px 8px',
          borderRadius: '10px'
        }}>v0.6.0</span>
        {checkStatus && (
          <div style={{
            marginLeft: 'auto',
            display: 'flex', alignItems: 'center', gap: '8px',
            fontSize: '12px',
            color: checkStatus === 'ALL CLEAR' ? 'var(--ok)' :
                   checkStatus === 'WARNINGS' ? 'var(--warning)' :
                   'var(--critical)'
          }}>
            <span style={{
              width: '8px', height: '8px', borderRadius: '50%',
              background: 'currentColor', display: 'inline-block'
            }}/>
            {projectPath} — {checkStatus}
          </div>
        )}
      </header>

      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        {/* Sidebar */}
        <aside style={{
          width: '220px',
          background: 'var(--bg-surface)',
          borderRight: '1px solid var(--border)',
          display: 'flex',
          flexDirection: 'column',
          padding: '16px 0',
          flexShrink: 0
        }}>
          {/* Navigation */}
          <div style={{ padding: '0 12px', marginBottom: '8px' }}>
            <div style={{
              fontSize: '10px', fontWeight: '600', color: 'var(--text-muted)',
              letterSpacing: '0.08em', textTransform: 'uppercase',
              padding: '0 8px', marginBottom: '6px'
            }}>Monitor</div>
            {NAV_ITEMS.map(item => (
              <button key={item.id} onClick={() => setActiveTab(item.id)}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center',
                  gap: '10px', padding: '8px 10px', borderRadius: '6px',
                  border: 'none', cursor: 'pointer', marginBottom: '2px',
                  background: activeTab === item.id
                    ? 'var(--accent)' : 'transparent',
                  color: activeTab === item.id
                    ? '#fff' : 'var(--text-secondary)',
                  fontSize: '13px', fontWeight: activeTab === item.id ? '600' : '400',
                  textAlign: 'left', transition: 'background 0.15s'
                }}>
                <span>{item.icon}</span>
                <span>{item.label}</span>
              </button>
            ))}
          </div>

          {/* Project Path */}
          <div style={{
            marginTop: 'auto', padding: '12px',
            borderTop: '1px solid var(--border)'
          }}>
            <div style={{
              fontSize: '10px', fontWeight: '600', color: 'var(--text-muted)',
              letterSpacing: '0.08em', textTransform: 'uppercase',
              marginBottom: '8px'
            }}>Project</div>
            <input
              value={projectPath}
              onChange={e => setProjectPath(e.target.value)}
              placeholder="Project path..."
              style={{
                width: '100%', background: 'var(--bg-base)',
                border: '1px solid var(--border)', borderRadius: '6px',
                padding: '6px 10px', color: 'var(--text-primary)',
                fontSize: '12px', boxSizing: 'border-box'
              }}
            />
            <div style={{
              fontSize: '10px', color: 'var(--text-muted)', marginTop: '6px',
              lineHeight: '1.4'
            }}>
              Multiple projects: use<br/>
              <code style={{ color: 'var(--accent)' }}>--port 8768</code>
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <main style={{
          flex: 1, overflow: 'auto', padding: '24px',
          background: 'var(--bg-base)'
        }}>
          {activeTab === 'check' && <CheckPanel projectPath={projectPath} onStatusChange={setCheckStatus} />}
          {activeTab === 'governance' && <GovernanceView projectPath={projectPath} />}
          {activeTab === 'verify' && <VerifyPanel projectPath={projectPath} />}
        </main>
      </div>
    </div>
  )
}
