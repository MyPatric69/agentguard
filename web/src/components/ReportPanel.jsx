import { useState } from 'react'

export default function ReportPanel({ projectPath }) {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)

  const loadReport = async () => {
    setLoading(true)
    try {
      const res = await fetch(
        `/api/report?path=${encodeURIComponent(projectPath)}`
      )
      setReport(await res.json())
    } finally {
      setLoading(false)
    }
  }

  const StatCard = ({ label, value, color }) => (
    <div style={{
      background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
      borderRadius: '10px',
      padding: '16px 20px',
      flex: 1
    }}>
      <div style={{
        fontSize: '11px', fontWeight: '600',
        color: 'var(--text-muted)',
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        marginBottom: '8px'
      }}>{label}</div>
      <div style={{
        fontSize: '28px', fontWeight: '700',
        color: color || 'var(--text-primary)'
      }}>{value}</div>
    </div>
  )

  const roiRow = (label, value) => (
    <tr key={label}>
      <td style={{
        padding: '6px 12px 6px 0',
        fontSize: '12px', color: 'var(--text-muted)',
        borderBottom: '1px solid var(--border)',
        whiteSpace: 'nowrap'
      }}>{label}</td>
      <td style={{
        padding: '6px 0 6px 12px',
        fontSize: '12px', color: 'var(--text-primary)',
        borderBottom: '1px solid var(--border)',
        fontFamily: 'monospace'
      }}>{value}</td>
    </tr>
  )

  return (
    <div>
      {/* Header */}
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'center', marginBottom: '20px'
      }}>
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: '700', margin: '0 0 4px' }}>
            Session Report
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: 0 }}>
            Post-session governance summary
          </p>
        </div>
        <button onClick={loadReport} disabled={loading} style={{
          background: loading ? 'var(--bg-elevated)' : 'var(--accent)',
          color: '#fff', border: 'none', borderRadius: '8px',
          padding: '10px 20px', cursor: loading ? 'default' : 'pointer',
          fontSize: '14px', fontWeight: '600'
        }}>
          {loading ? '⏳ Loading...' : 'Generate Report'}
        </button>
      </div>

      {!report && !loading && (
        <div style={{
          background: 'var(--bg-surface)', borderRadius: '12px',
          border: '1px dashed var(--border)', padding: '60px',
          textAlign: 'center', color: 'var(--text-muted)'
        }}>
          <div style={{ fontSize: '32px', marginBottom: '12px' }}>📊</div>
          <div style={{ fontSize: '15px', marginBottom: '6px',
                        color: 'var(--text-primary)' }}>
            Ready to generate
          </div>
          <div style={{ fontSize: '13px' }}>
            Run a Claude Code session first, then generate the report
          </div>
        </div>
      )}

      {report && !report.error && (
        <div>
          {/* Meta */}
          <div style={{
            fontSize: '12px', color: 'var(--text-muted)',
            marginBottom: '16px'
          }}>
            Generated: {report.generated}
            {report.duration && ` · Session duration: ${report.duration}`}
            {report.session_id && ` · Session: ${report.session_id.slice(0, 8)}`}
          </div>

          {/* Executive Summary */}
          {report.executive_summary && (() => {
            const exec = report.executive_summary
            const borderColor = exec.productive.startsWith('✅') ? 'var(--ok)'
              : exec.productive.startsWith('❌') ? 'var(--critical)'
              : 'var(--warning)'
            return (
              <div style={{
                background: 'var(--bg-surface)',
                border: `2px solid ${borderColor}`,
                borderRadius: '12px', padding: '20px',
                marginBottom: '20px'
              }}>
                <div style={{
                  fontSize: '13px', fontWeight: '600', marginBottom: '14px',
                  display: 'flex', alignItems: 'center', gap: '8px'
                }}>
                  Executive Summary
                  <span style={{
                    fontSize: '11px', color: 'var(--text-muted)',
                    fontWeight: '400'
                  }}>for non-technical readers</span>
                </div>

                <div style={{
                  fontSize: '24px', fontWeight: '700', marginBottom: '16px',
                  color: borderColor
                }}>
                  {exec.productive}
                </div>

                <div style={{
                  display: 'flex', gap: '32px', flexWrap: 'wrap',
                  fontSize: '12px', marginBottom: '14px'
                }}>
                  <div>
                    <div style={{ color: 'var(--text-muted)', marginBottom: '3px' }}>
                      AI Cost
                    </div>
                    <div style={{ fontFamily: 'monospace', color: 'var(--text-primary)' }}>
                      {exec.cost_label}
                    </div>
                  </div>
                  <div>
                    <div style={{ color: 'var(--text-muted)', marginBottom: '3px' }}>
                      Work Completed
                    </div>
                    <div style={{ color: 'var(--text-primary)' }}>
                      {exec.work_completed}
                    </div>
                  </div>
                  <div>
                    <div style={{ color: 'var(--text-muted)', marginBottom: '3px' }}>
                      Open Items
                    </div>
                    <div style={{ color: 'var(--text-primary)' }}>
                      {exec.open_items}
                    </div>
                  </div>
                </div>

                <div style={{
                  borderTop: '1px solid var(--border)',
                  paddingTop: '10px',
                  fontSize: '11px', color: 'var(--text-muted)'
                }}>
                  Governance: {exec.governance_status}
                </div>
              </div>
            )
          })()}

          {/* ROI Summary */}
          <div style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border)',
            borderRadius: '12px', padding: '16px',
            marginBottom: '20px'
          }}>
            <div style={{
              fontSize: '13px', fontWeight: '600', marginBottom: '12px'
            }}>ROI Summary</div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <tbody>
                {roiRow('Session Duration', report.duration || 'N/A')}
                {roiRow('Session Cost',
                  report.session_cost
                    ? `$${report.session_cost.total_usd?.toFixed(4)} · ${report.session_cost.model}`
                    : 'N/A'
                )}
                {roiRow('Pricing Source',
                  report.session_cost?.pricing_source || 'N/A'
                )}
                {roiRow('Total Tool Calls', report.total)}
                {roiRow('→ Allowed',
                  `${report.allowed} (${report.total > 0 ? Math.round(report.allowed / report.total * 100) : 0}%)`
                )}
                {roiRow('→ Ask (confirmed/unresolved)',
                  `${report.asked ?? 0} (${report.total > 0 ? Math.round((report.asked ?? 0) / report.total * 100) : 0}%)`
                )}
                {roiRow('→ Denied',
                  `${report.denied} (${report.total > 0 ? Math.round(report.denied / report.total * 100) : 0}%)`
                )}
                {roiRow('Unresolved Proposals', report.proposals?.pending ?? 0)}
                {roiRow('PRs Created', report.proposals?.pr_created ?? 0)}
              </tbody>
            </table>
          </div>

          {/* Stat Cards */}
          <div style={{
            display: 'flex', gap: '12px', marginBottom: '20px'
          }}>
            <StatCard label="Total Calls" value={report.total} />
            <StatCard label="Allowed" value={report.allowed}
                      color="var(--ok)" />
            <StatCard label="Ask" value={report.asked ?? 0}
                      color={(report.asked ?? 0) > 0 ? 'var(--warning)' : 'var(--ok)'} />
            <StatCard label="Blocked" value={report.denied}
                      color={report.denied > 0 ? 'var(--critical)' : 'var(--ok)'} />
            <StatCard label="Warnings"
                      value={Object.values(report.watch_counts).reduce((a, b) => a + b, 0)}
                      color="var(--warning)" />
          </div>

          {/* Tool Distribution */}
          {Object.keys(report.tool_counts).length > 0 && (
            <div style={{
              background: 'var(--bg-surface)',
              border: '1px solid var(--border)',
              borderRadius: '12px', padding: '16px',
              marginBottom: '16px'
            }}>
              <div style={{
                fontSize: '13px', fontWeight: '600',
                marginBottom: '12px'
              }}>Tool Distribution</div>
              {Object.entries(report.tool_counts).map(([tool, count]) => {
                const pct = Math.round((count / report.total) * 100)
                return (
                  <div key={tool} style={{
                    display: 'flex', alignItems: 'center',
                    gap: '12px', marginBottom: '8px'
                  }}>
                    <div style={{
                      width: '80px', fontSize: '12px',
                      color: 'var(--accent)', fontFamily: 'monospace'
                    }}>{tool}</div>
                    <div style={{
                      flex: 1, background: 'var(--bg-elevated)',
                      borderRadius: '4px', height: '8px', overflow: 'hidden'
                    }}>
                      <div style={{
                        width: `${pct}%`, height: '100%',
                        background: 'var(--accent)',
                        borderRadius: '4px',
                        transition: 'width 0.5s ease'
                      }}/>
                    </div>
                    <div style={{
                      width: '60px', fontSize: '12px',
                      color: 'var(--text-muted)', textAlign: 'right'
                    }}>{count}x ({pct}%)</div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Blocked Actions */}
          {report.denied_entries.length > 0 && (
            <div style={{
              background: 'rgba(239,68,68,0.05)',
              border: '1px solid rgba(239,68,68,0.2)',
              borderRadius: '12px', padding: '16px',
              marginBottom: '16px'
            }}>
              <div style={{
                fontSize: '13px', fontWeight: '600',
                color: 'var(--critical)', marginBottom: '12px'
              }}>
                Blocked Actions ({report.denied_entries.length})
              </div>
              {report.denied_entries.map((entry, i) => (
                <div key={i} style={{
                  background: 'var(--bg-surface)',
                  borderRadius: '8px', padding: '10px 12px',
                  marginBottom: '8px', fontSize: '12px'
                }}>
                  <div style={{
                    display: 'flex', justifyContent: 'space-between',
                    marginBottom: '4px'
                  }}>
                    <span style={{
                      color: 'var(--accent)', fontFamily: 'monospace'
                    }}>{entry.tool}</span>
                    <span style={{ color: 'var(--text-muted)' }}>
                      {entry.timestamp?.slice(11, 19)}
                    </span>
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    {entry.input_summary}
                  </div>
                  {entry.reason && (
                    <div style={{
                      color: 'var(--critical)', marginTop: '4px',
                      fontSize: '11px'
                    }}>
                      → {entry.reason}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Proposals */}
          {(report.proposals?.total ?? 0) > 0 && (
            <div style={{
              background: 'rgba(245,158,11,0.05)',
              border: '1px solid rgba(245,158,11,0.2)',
              borderRadius: '12px', padding: '16px',
              marginBottom: '16px'
            }}>
              <div style={{
                fontSize: '13px', fontWeight: '600',
                color: 'var(--warning)', marginBottom: '4px'
              }}>
                Proposals ({report.proposals.total})
              </div>
              <div style={{
                fontSize: '11px', color: 'var(--text-muted)',
                marginBottom: '12px'
              }}>
                {report.proposals.pending} pending · {report.proposals.pr_created} PR created
              </div>
              {report.proposals.entries.map((p, i) => (
                <div key={i} style={{
                  background: 'var(--bg-surface)',
                  borderRadius: '8px', padding: '10px 12px',
                  marginBottom: '8px', fontSize: '12px'
                }}>
                  <div style={{
                    display: 'flex', justifyContent: 'space-between',
                    marginBottom: '4px'
                  }}>
                    <span style={{
                      color: 'var(--accent)', fontFamily: 'monospace'
                    }}>{p.tool_name}</span>
                    <span style={{
                      fontSize: '11px', padding: '1px 6px',
                      borderRadius: '4px',
                      background: p.status === 'pending'
                        ? 'rgba(245,158,11,0.15)'
                        : 'rgba(34,197,94,0.15)',
                      color: p.status === 'pending'
                        ? 'var(--warning)'
                        : 'var(--ok)'
                    }}>{p.status}</span>
                  </div>
                  <div style={{
                    fontFamily: 'monospace', fontSize: '11px',
                    color: 'var(--text-muted)', marginBottom: '4px'
                  }}>{p.file_path}</div>
                  <div style={{ color: 'var(--text-secondary)', fontSize: '11px' }}>
                    {p.governance_reason}
                  </div>
                  {p.pr_url && (
                    <div style={{ marginTop: '4px', fontSize: '11px' }}>
                      <a href={p.pr_url} target="_blank" rel="noreferrer"
                         style={{ color: 'var(--accent)' }}>
                        {p.pr_url}
                      </a>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Watch Warnings */}
          {report.watch_events.length > 0 && (
            <div style={{
              background: 'rgba(245,158,11,0.05)',
              border: '1px solid rgba(245,158,11,0.2)',
              borderRadius: '12px', padding: '16px'
            }}>
              <div style={{
                fontSize: '13px', fontWeight: '600',
                color: 'var(--warning)', marginBottom: '12px'
              }}>
                Runtime Warnings ({report.watch_events.length})
              </div>
              {report.watch_events.map((event, i) => (
                <div key={i} style={{
                  background: 'var(--bg-surface)',
                  borderRadius: '8px', padding: '10px 12px',
                  marginBottom: '8px', fontSize: '12px',
                  display: 'flex', gap: '10px'
                }}>
                  <span style={{
                    color: 'var(--warning)', fontWeight: '600',
                    flexShrink: 0
                  }}>{event.event}</span>
                  <span style={{ color: 'var(--text-secondary)' }}>
                    {event.message}
                  </span>
                </div>
              ))}
            </div>
          )}

          {!report.has_data && (
            <div style={{
              textAlign: 'center', color: 'var(--text-muted)',
              padding: '40px', fontSize: '14px'
            }}>
              No session data yet — start a Claude Code session first
            </div>
          )}
        </div>
      )}
    </div>
  )
}
