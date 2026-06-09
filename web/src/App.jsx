import { useState, useEffect } from 'react'
import CheckPanel from './components/CheckPanel.jsx'
import GovernanceView from './components/GovernanceView.jsx'
import VerifyPanel from './components/VerifyPanel.jsx'
import InitPanel from './components/InitPanel.jsx'
import ReviewPanel from './components/ReviewPanel.jsx'
import TerminalPanel from './components/TerminalPanel.jsx'
import './index.css'

const NAV_ITEMS = [
  { id: 'check', label: 'Pre-Flight Check', icon: '🛡️', group: 'monitor' },
  { id: 'governance', label: 'Governance', icon: '📋', group: 'monitor' },
  { id: 'verify', label: 'Verify Pins', icon: '🔐', group: 'monitor' },
  { id: 'terminal', label: 'Terminal', icon: '💻', group: 'monitor' },
  { id: 'init', label: 'Setup Governance', icon: '⚙️', group: 'setup' },
  { id: 'review', label: 'Review & Update', icon: '✏️', group: 'setup' },
]

function NavGroup({ label, items, activeTab, setActiveTab }) {
  return (
    <div style={{ padding: '0 12px', marginBottom: '16px' }}>
      <div style={{
        fontSize: '10px', fontWeight: '600', color: 'var(--text-muted)',
        letterSpacing: '0.08em', textTransform: 'uppercase',
        padding: '0 8px', marginBottom: '6px'
      }}>{label}</div>
      {items.map(item => (
        <button key={item.id} onClick={() => setActiveTab(item.id)}
          style={{
            width: '100%', display: 'flex', alignItems: 'center',
            gap: '10px', padding: '8px 10px', borderRadius: '6px',
            border: 'none', cursor: 'pointer', marginBottom: '2px',
            background: activeTab === item.id ? 'var(--accent)' : 'transparent',
            color: activeTab === item.id ? '#fff' : 'var(--text-secondary)',
            fontSize: '13px', fontWeight: activeTab === item.id ? '600' : '400',
            textAlign: 'left', transition: 'background 0.15s'
          }}>
          <span>{item.icon}</span>
          <span>{item.label}</span>
        </button>
      ))}
    </div>
  )
}

export default function App() {
  const [activeTab, setActiveTab] = useState('check')
  const [projectPath, setProjectPath] = useState('.')
  const [checkStatus, setCheckStatus] = useState(null)
  const [checkStatusDetail, setCheckStatusDetail] = useState(null)
  const [projectName, setProjectName] = useState('')
  const [pendingCommand, setPendingCommand] = useState(null)
  const [projects, setProjects] = useState([])

  const runInTerminal = (cmd) => {
    setPendingCommand(cmd)
    setActiveTab('terminal')
  }

  useEffect(() => {
    fetch('/api/projects')
      .then(r => r.json())
      .then(data => {
        setProjects(data.projects || [])
        if (data.projects?.length > 0 && projectPath === '.') {
          setProjectPath(data.projects[0].path)
        }
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetch(`/api/project-info?path=${encodeURIComponent(projectPath)}`)
      .then(r => r.json())
      .then(d => setProjectName(d.name))
      .catch(() => setProjectName(''))
  }, [projectPath])

  const handleStatusChange = (status, detail) => {
    setCheckStatus(status)
    setCheckStatusDetail(detail)
  }

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
        }}>v0.7.0</span>
        {checkStatus && (
          <div style={{
            marginLeft: 'auto',
            display: 'flex', alignItems: 'center', gap: '8px',
            fontSize: '12px',
            color: checkStatus === 'ALL CLEAR' ? 'var(--ok)' :
                   checkStatus === 'WARNINGS' ? 'var(--warning)' :
                   'var(--critical)',
            cursor: 'default'
          }}>
            <span style={{
              width: '8px', height: '8px', borderRadius: '50%',
              background: 'currentColor', display: 'inline-block'
            }}/>
            {projectName || projectPath} — {checkStatusDetail}
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
          <NavGroup
            label="Monitor"
            items={NAV_ITEMS.filter(n => n.group === 'monitor')}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
          />
          <NavGroup
            label="Setup"
            items={NAV_ITEMS.filter(n => n.group === 'setup')}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
          />

          {/* Project */}
          <div style={{
            marginTop: 'auto', padding: '12px',
            borderTop: '1px solid var(--border)'
          }}>
            <div style={{
              fontSize: '10px', fontWeight: '600', color: 'var(--text-muted)',
              letterSpacing: '0.08em', textTransform: 'uppercase',
              marginBottom: '8px'
            }}>Project</div>

            {projects.length > 1 ? (
              <select
                value={projectPath}
                onChange={e => setProjectPath(e.target.value)}
                style={{
                  width: '100%', background: 'var(--bg-base)',
                  border: '1px solid var(--border)', borderRadius: '6px',
                  padding: '6px 10px', color: 'var(--text-primary)',
                  fontSize: '12px', cursor: 'pointer',
                  appearance: 'none', boxSizing: 'border-box'
                }}>
                {projects.map(p => (
                  <option key={p.path} value={p.path}>
                    {p.name} {p.has_governance ? '✓' : '⚠'}
                  </option>
                ))}
              </select>
            ) : (
              <div>
                <div style={{
                  fontSize: '13px', fontWeight: '600',
                  color: 'var(--text-primary)', marginBottom: '4px'
                }}>
                  {projects[0]?.name || projectPath}
                </div>
                <input
                  value={projectPath}
                  onChange={e => setProjectPath(e.target.value)}
                  placeholder="Project path..."
                  style={{
                    width: '100%', background: 'var(--bg-base)',
                    border: '1px solid var(--border)', borderRadius: '6px',
                    padding: '5px 8px', color: 'var(--text-muted)',
                    fontSize: '11px', boxSizing: 'border-box'
                  }}
                />
              </div>
            )}

            {projects.length > 1 && (
              <div style={{
                fontSize: '10px', color: 'var(--text-muted)',
                marginTop: '6px'
              }}>
                {projects.length} projects · ✓ has governance
              </div>
            )}
          </div>
        </aside>

        {/* Main Content */}
        <main style={{
          flex: 1, overflow: 'auto', padding: '24px',
          background: 'var(--bg-base)'
        }}>
          {activeTab === 'check' && (
            <CheckPanel projectPath={projectPath} onStatusChange={handleStatusChange} />
          )}
          {activeTab === 'governance' && <GovernanceView projectPath={projectPath} />}
          {activeTab === 'verify' && <VerifyPanel projectPath={projectPath} />}
          {activeTab === 'init' && <InitPanel projectPath={projectPath} runInTerminal={runInTerminal} />}
          {activeTab === 'review' && <ReviewPanel projectPath={projectPath} runInTerminal={runInTerminal} />}
          {activeTab === 'terminal' && (
            <TerminalPanel
              projectPath={projectPath}
              pendingCommand={pendingCommand}
              onCommandConsumed={() => setPendingCommand(null)}
            />
          )}
        </main>
      </div>
    </div>
  )
}
