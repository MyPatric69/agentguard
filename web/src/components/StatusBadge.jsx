export default function StatusBadge({ result }) {
  const config = {
    'ALL CLEAR': { bg: '#1a4731', color: '#3fb950', text: '✅ ALL CLEAR' },
    'WARNINGS': { bg: '#2d2a1e', color: '#d29922', text: '⚠️ WARNINGS' },
    'BLOCKED': { bg: '#3d1a1a', color: '#f85149', text: '🔴 BLOCKED' },
  }
  const match = Object.entries(config).find(([k]) => result?.includes(k))
  const c = match ? match[1] : { bg: '#161b22', color: '#8b949e', text: result }

  return (
    <span style={{
      background: c.bg, color: c.color, padding: '6px 14px',
      borderRadius: '6px', fontSize: '14px', fontWeight: '700'
    }}>
      {c.text}
    </span>
  )
}
