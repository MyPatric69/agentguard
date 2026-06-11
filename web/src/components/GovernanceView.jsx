import { useState, useEffect } from 'react'

const SECTION_CONFIG = {
  authorized: {
    label: '✅ Authorized',
    color: 'var(--ok)',
    bg: 'rgba(16,185,129,0.05)',
    border: 'rgba(16,185,129,0.2)'
  },
  prohibited: {
    label: '🚫 Prohibited',
    color: 'var(--critical)',
    bg: 'rgba(239,68,68,0.05)',
    border: 'rgba(239,68,68,0.2)'
  },
  requires_confirmation: {
    label: '⚠️ Requires Confirmation',
    color: 'var(--warning)',
    bg: 'rgba(245,158,11,0.05)',
    border: 'rgba(245,158,11,0.2)'
  }
}

function ScopeCard({ sectionKey, items, editMode, onEdit, onDelete, onAdd }) {
  const cfg = SECTION_CONFIG[sectionKey]
  if (!editMode && (!items || items.length === 0)) return null
  return (
    <div style={{
      background: cfg.bg, border: `1px solid ${cfg.border}`,
      borderRadius: '12px', padding: '16px', marginBottom: '20px'
    }}>
      <div style={{
        fontSize: '13px', fontWeight: '700', color: cfg.color,
        marginBottom: '12px', display: 'flex', alignItems: 'center',
        gap: '8px'
      }}>
        {cfg.label}
        <span style={{
          background: 'var(--bg-elevated)', color: 'var(--text-muted)',
          fontSize: '11px', padding: '1px 8px', borderRadius: '10px',
          fontWeight: '500'
        }}>{(items || []).length}</span>
      </div>
      {(items || []).map((item, i) => (
        <div key={i} style={{
          background: 'var(--bg-surface)', borderRadius: '8px',
          padding: editMode ? '12px' : '14px 16px', marginBottom: '8px',
          borderLeft: `3px solid ${cfg.color}`
        }}>
          {editMode ? (
            <div>
              <input
                value={item.action || ''}
                onChange={e => onEdit(sectionKey, i, 'action', e.target.value)}
                placeholder="Action..."
                style={{
                  width: '100%', background: 'var(--bg-base)',
                  border: '1px solid var(--border)', borderRadius: '6px',
                  padding: '6px 10px', color: 'var(--text-primary)',
                  fontSize: '13px', marginBottom: '6px',
                  boxSizing: 'border-box'
                }}
              />
              <input
                value={item.reason || ''}
                onChange={e => onEdit(sectionKey, i, 'reason', e.target.value)}
                placeholder="Reason..."
                style={{
                  width: '100%', background: 'var(--bg-base)',
                  border: '1px solid var(--border)', borderRadius: '6px',
                  padding: '6px 10px', color: 'var(--text-muted)',
                  fontSize: '12px', boxSizing: 'border-box'
                }}
              />
              <button onClick={() => onDelete(sectionKey, i)} style={{
                background: 'rgba(239,68,68,0.1)',
                color: 'var(--critical)', border: 'none',
                borderRadius: '4px', padding: '4px 10px',
                cursor: 'pointer', fontSize: '11px', marginTop: '6px'
              }}>🗑️ Delete</button>
            </div>
          ) : (
            <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
              {item.severity === 'HARD_LIMIT' && (
                <span style={{
                  background: 'var(--critical)', color: '#fff',
                  fontSize: '9px', padding: '2px 6px', borderRadius: '3px',
                  fontWeight: '700', flexShrink: 0, marginTop: '2px'
                }}>HARD LIMIT</span>
              )}
              <div>
                <div style={{
                  fontSize: '13px', fontWeight: '500',
                  color: 'var(--text-primary)', marginBottom: '4px'
                }}>{item.action}</div>
                {item.reason && (
                  <div style={{
                    fontSize: '12px', color: 'var(--text-muted)',
                    lineHeight: '1.5'
                  }}>{item.reason}</div>
                )}
                {item.added && (
                  <div style={{
                    fontSize: '11px', color: 'var(--bg-elevated)',
                    marginTop: '4px'
                  }}>Added {item.added}</div>
                )}
              </div>
            </div>
          )}
        </div>
      ))}
      {editMode && (
        <button onClick={() => onAdd(sectionKey)} style={{
          width: '100%', background: 'transparent',
          border: `1px dashed ${cfg.color}`,
          borderRadius: '8px', padding: '8px',
          color: cfg.color, cursor: 'pointer',
          fontSize: '12px', marginTop: '4px'
        }}>
          + Add Rule
        </button>
      )}
    </div>
  )
}

export default function GovernanceView({ projectPath }) {
  const [gov, setGov] = useState(null)
  const [loading, setLoading] = useState(true)
  const [editMode, setEditMode] = useState(false)
  const [localItems, setLocalItems] = useState({})
  const [pending, setPending] = useState([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setLoading(true)
    fetch(`/api/governance?path=${encodeURIComponent(projectPath)}`)
      .then(r => r.json())
      .then(data => { setGov(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [projectPath])

  useEffect(() => {
    if (editMode && gov?.governance?.scope) {
      setLocalItems({
        authorized: [...(gov.governance.scope.authorized || [])],
        prohibited: [...(gov.governance.scope.prohibited || [])],
        requires_confirmation: [
          ...(gov.governance.scope.requires_confirmation || [])
        ]
      })
    }
  }, [editMode])

  const handleEdit = (section, index, field, value) => {
    setLocalItems(prev => {
      const updated = [...prev[section]]
      updated[index] = { ...updated[index], [field]: value }
      return { ...prev, [section]: updated }
    })
    setPending(prev => {
      const existing = prev.findIndex(
        p => p.section === section && p.action === 'update' && p.index === index
      )
      const change = { section, action: 'update', index, item: { [field]: value } }
      if (existing >= 0) {
        const updated = [...prev]
        updated[existing] = {
          ...updated[existing],
          item: { ...updated[existing].item, [field]: value }
        }
        return updated
      }
      return [...prev, change]
    })
  }

  const handleDelete = (section, index) => {
    setLocalItems(prev => {
      const updated = [...prev[section]]
      updated.splice(index, 1)
      return { ...prev, [section]: updated }
    })
    setPending(prev => [...prev, { section, action: 'delete', index }])
  }

  const handleAdd = (section) => {
    const newItem = {
      action: '',
      reason: '',
      added: new Date().toISOString().slice(0, 10)
    }
    setLocalItems(prev => ({
      ...prev,
      [section]: [...prev[section], newItem]
    }))
    setPending(prev => [...prev, { section, action: 'add', item: newItem }])
  }

  const saveChanges = async () => {
    setSaving(true)
    try {
      for (const change of pending) {
        await fetch('/api/governance/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: projectPath, ...change })
        })
      }
      setPending([])
      setEditMode(false)
      const res = await fetch(
        `/api/governance?path=${encodeURIComponent(projectPath)}`
      )
      setGov(await res.json())
    } finally {
      setSaving(false)
    }
  }

  if (loading) return (
    <div style={{ color: 'var(--text-muted)', padding: '60px',
                  textAlign: 'center' }}>Loading governance...</div>
  )

  if (!gov?.exists) return (
    <div style={{
      background: 'var(--bg-surface)', border: '1px dashed var(--border)',
      borderRadius: '12px', padding: '60px', textAlign: 'center'
    }}>
      <div style={{ fontSize: '32px', marginBottom: '12px' }}>📋</div>
      <div style={{ fontSize: '15px', marginBottom: '6px',
                    color: 'var(--text-primary)' }}>
        No governance found
      </div>
      <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
        Run <code>agentguard init --guided</code> to create governance
      </div>
    </div>
  )

  const { governance } = gov
  const scope = governance.scope || {}
  const displayItems = editMode ? localItems : {
    authorized: scope.authorized || [],
    prohibited: scope.prohibited || [],
    requires_confirmation: scope.requires_confirmation || []
  }

  return (
    <div>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', marginBottom: '20px'
      }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: '700', margin: '0 0 4px' }}>
            Governance
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
            Defined rules for this agent session
          </p>
        </div>
        <button
          onClick={() => { setEditMode(!editMode); setPending([]) }}
          style={{
            background: editMode ? 'var(--bg-elevated)' : 'var(--accent)',
            color: editMode ? 'var(--text-muted)' : '#fff',
            border: '1px solid var(--border)',
            borderRadius: '8px', padding: '8px 16px',
            cursor: 'pointer', fontSize: '13px', fontWeight: '600'
          }}>
          {editMode ? '✕ Cancel' : '✏️ Edit'}
        </button>
      </div>

      {editMode && pending.length > 0 && (
        <div style={{
          background: 'rgba(59,130,246,0.1)',
          border: '1px solid rgba(59,130,246,0.3)',
          borderRadius: '8px', padding: '12px 16px',
          marginBottom: '16px',
          display: 'flex', justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span style={{ fontSize: '13px', color: 'var(--accent)' }}>
            ✏️ {pending.length} change{pending.length > 1 ? 's' : ''} pending
          </span>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button onClick={() => setPending([])} style={{
              background: 'transparent', color: 'var(--text-muted)',
              border: '1px solid var(--border)', borderRadius: '6px',
              padding: '6px 14px', cursor: 'pointer', fontSize: '13px'
            }}>Discard</button>
            <button onClick={saveChanges} disabled={saving} style={{
              background: 'var(--accent)', color: '#fff',
              border: 'none', borderRadius: '6px',
              padding: '6px 14px', cursor: saving ? 'default' : 'pointer',
              fontSize: '13px', fontWeight: '600'
            }}>
              {saving ? '⏳ Saving...' : 'Save All'}
            </button>
          </div>
        </div>
      )}

      <div style={{
        background: 'var(--bg-surface)', borderRadius: '12px',
        border: '1px solid var(--border)', padding: '16px',
        marginBottom: '20px', display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px'
      }}>
        {[
          { label: 'Owner', value: governance.owner },
          { label: 'Escalation', value: governance.escalation?.contact },
          { label: 'Killswitch', value: governance.killswitch }
        ].map(({ label, value }) => (
          <div key={label}>
            <div style={{ fontSize: '10px', fontWeight: '600',
                          color: 'var(--text-muted)', textTransform: 'uppercase',
                          letterSpacing: '0.08em', marginBottom: '4px' }}>
              {label}
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-primary)',
                          fontWeight: '500' }}>
              {value || '—'}
            </div>
          </div>
        ))}
      </div>

      <ScopeCard
        sectionKey="authorized"
        items={displayItems.authorized}
        editMode={editMode}
        onEdit={handleEdit}
        onDelete={handleDelete}
        onAdd={handleAdd}
      />
      <ScopeCard
        sectionKey="prohibited"
        items={displayItems.prohibited}
        editMode={editMode}
        onEdit={handleEdit}
        onDelete={handleDelete}
        onAdd={handleAdd}
      />
      <ScopeCard
        sectionKey="requires_confirmation"
        items={displayItems.requires_confirmation}
        editMode={editMode}
        onEdit={handleEdit}
        onDelete={handleDelete}
        onAdd={handleAdd}
      />
    </div>
  )
}
