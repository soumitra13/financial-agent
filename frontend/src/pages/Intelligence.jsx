import { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '../api/client'

const FILTERS = ['All', 'Pending', 'Completed', 'Failed']

function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString('en-US', { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' })
}

function statusClass(s) {
  if (s === 'completed') return 'completed'
  if (s === 'failed')    return 'failed'
  return 'pending'
}

function TaskCard({ task, onViewAudit }) {
  const r = task.result || {}
  const anomaly = r.anomaly_detected
  const severity = r.severity || 'low'

  return (
    <motion.div
      layout
      initial={{ opacity:0, y:12 }}
      animate={{ opacity:1, y:0 }}
      exit={{ opacity:0, scale:0.97 }}
      className="card"
      style={{ padding:20 }}
    >
      {/* Top row */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:12 }}>
        <div>
          <span className="mono" style={{ fontSize:11, color:'var(--text-muted)' }}>
            {String(task.id).slice(0,8)}...
          </span>
          <div style={{ fontSize:13, fontWeight:500, color:'var(--text)', marginTop:4, lineHeight:1.4, maxWidth:320 }}>
            {task.description.length > 72 ? task.description.slice(0,72) + '…' : task.description}
          </div>
        </div>
        <span className={`badge badge-${statusClass(task.status)}`} style={{ flexShrink:0, marginLeft:12 }}>
          {task.status}
        </span>
      </div>

      {/* Meta row */}
      <div style={{ display:'flex', gap:16, flexWrap:'wrap', marginBottom:12 }}>
        {r.anomaly_detected !== undefined && (
          <span className={`badge badge-${anomaly ? severity : 'completed'}`}>
            {anomaly ? `⚠ Anomaly · ${severity}` : '✓ Clean'}
          </span>
        )}
        <span style={{ fontSize:11, color:'var(--text-muted)', display:'flex', alignItems:'center', gap:4 }}>
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
          </svg>
          {fmtTime(task.created_at)}
        </span>
        {task.total_steps && (
          <span style={{ fontSize:11, color:'var(--text-muted)' }}>
            {task.total_steps} steps
          </span>
        )}
      </div>

      {/* Risk bar if completed */}
      {task.status === 'completed' && (
        <div className="severity-bar">
          <div
            className="severity-fill"
            style={{
              width: anomaly ? (severity === 'critical' ? '95%' : severity === 'high' ? '75%' : severity === 'medium' ? '50%' : '20%') : '8%',
              background: anomaly
                ? (severity === 'critical' ? 'var(--red)' : severity === 'high' ? 'var(--amber)' : 'var(--purple)')
                : 'var(--green)',
            }}
          />
        </div>
      )}

      {/* Footer */}
      {task.status === 'completed' && (
        <div style={{ marginTop:12, display:'flex', justifyContent:'flex-end' }}>
          <button
            className="btn btn-ghost"
            style={{ fontSize:10, padding:'5px 10px' }}
            onClick={() => onViewAudit(task.id)}
          >
            View Audit Trail →
          </button>
        </div>
      )}
    </motion.div>
  )
}

function AuditDrawer({ taskId, onClose }) {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getAudit(taskId).then(data => { setEntries(data); setLoading(false) }).catch(() => setLoading(false))
  }, [taskId])

  return (
    <motion.div
      initial={{ x:'100%' }}
      animate={{ x:0 }}
      exit={{ x:'100%' }}
      transition={{ type:'spring', damping:28, stiffness:300 }}
      style={{
        position:'fixed', top:0, right:0, bottom:0, width:460,
        background:'var(--surface-2)',
        borderLeft:'1px solid rgba(0,212,255,0.12)',
        zIndex:200, overflowY:'auto', padding:28,
        boxShadow:'-20px 0 60px rgba(0,0,0,0.5)',
      }}
    >
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:24 }}>
        <div>
          <div className="label" style={{ marginBottom:6 }}>Decision Chain</div>
          <h3 style={{ fontSize:18, fontWeight:700 }}>Audit Trail</h3>
          <p className="mono" style={{ fontSize:11, color:'var(--text-muted)', marginTop:2 }}>{String(taskId).slice(0,16)}...</p>
        </div>
        <button className="btn btn-ghost" style={{ padding:'7px 12px', fontSize:12 }} onClick={onClose}>✕ Close</button>
      </div>

      {loading ? (
        <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
          {[1,2,3].map(i => <div key={i} className="skeleton" style={{ height:70 }} />)}
        </div>
      ) : entries.length === 0 ? (
        <p style={{ color:'var(--text-muted)', fontSize:13 }}>No audit entries found.</p>
      ) : (
        <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
          {entries.map((e, i) => (
            <div key={e.id} className="card" style={{ padding:16, borderLeft:`3px solid ${e.status === 'success' ? 'var(--green)' : 'var(--red)'}` }}>
              <div style={{ display:'flex', justifyContent:'space-between', marginBottom:6 }}>
                <span style={{ fontSize:11, fontWeight:700, color:'var(--cyan)', letterSpacing:'0.06em', textTransform:'uppercase' }}>
                  Step {e.step_number} · {e.action_name || e.action_type}
                </span>
                <span style={{ fontSize:10, color:'var(--text-muted)' }}>{e.duration_ms}ms</span>
              </div>
              {e.reasoning && (
                <p style={{ fontSize:12, color:'var(--text-dim)', lineHeight:1.5 }}>{e.reasoning}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </motion.div>
  )
}

export default function Intelligence() {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('All')
  const [auditTaskId, setAuditTaskId] = useState(null)

  const load = useCallback(() => {
    api.listTasks(60).then(data => { setTasks(data); setLoading(false) }).catch(() => setLoading(false))
  }, [])

  useEffect(() => { load() }, [load])

  // Auto-refresh every 8 seconds
  useEffect(() => {
    const t = setInterval(load, 8000)
    return () => clearInterval(t)
  }, [load])

  const filtered = tasks.filter(t => {
    if (filter === 'All')       return true
    if (filter === 'Pending')   return t.status === 'pending'
    if (filter === 'Completed') return t.status === 'completed'
    if (filter === 'Failed')    return t.status === 'failed'
    return true
  })

  const counts = {
    All: tasks.length,
    Pending: tasks.filter(t => t.status === 'pending').length,
    Completed: tasks.filter(t => t.status === 'completed').length,
    Failed: tasks.filter(t => t.status === 'failed').length,
  }

  return (
    <div className="page">
      {/* Header */}
      <div className="page-header">
        <div className="label" style={{ marginBottom:10 }}>Live Feed</div>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-end', flexWrap:'wrap', gap:12 }}>
          <div>
            <h1 className="page-title">Intelligence Feed</h1>
            <p style={{ color:'var(--text-dim)', fontSize:14 }}>
              All analysis tasks · auto-refreshes every 8s
            </p>
          </div>
          <button className="btn btn-ghost" style={{ fontSize:11 }} onClick={load}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display:'flex', gap:8, marginBottom:28, alignItems:'center' }}>
        <div className="tabs">
          {FILTERS.map(f => (
            <button key={f} className={`tab ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)}>
              {f} <span style={{ marginLeft:4, opacity:0.6 }}>({counts[f]})</span>
            </button>
          ))}
        </div>
      </div>

      {/* Grid */}
      {loading ? (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(340px,1fr))', gap:16 }}>
          {[1,2,3,4,5,6].map(i => <div key={i} className="skeleton" style={{ height:130 }} />)}
        </div>
      ) : filtered.length === 0 ? (
        <motion.div
          initial={{ opacity:0 }}
          animate={{ opacity:1 }}
          style={{ textAlign:'center', padding:'80px 0', color:'var(--text-muted)' }}
        >
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ marginBottom:16, opacity:0.3 }}>
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <p>No tasks found for this filter.</p>
        </motion.div>
      ) : (
        <motion.div
          layout
          style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(340px,1fr))', gap:16 }}
        >
          <AnimatePresence>
            {filtered.map(task => (
              <TaskCard key={task.id} task={task} onViewAudit={setAuditTaskId} />
            ))}
          </AnimatePresence>
        </motion.div>
      )}

      {/* Audit drawer */}
      <AnimatePresence>
        {auditTaskId && (
          <>
            <motion.div
              initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}
              style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.5)', zIndex:199 }}
              onClick={() => setAuditTaskId(null)}
            />
            <AuditDrawer taskId={auditTaskId} onClose={() => setAuditTaskId(null)} />
          </>
        )}
      </AnimatePresence>
    </div>
  )
}
