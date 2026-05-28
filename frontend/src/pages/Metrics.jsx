import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts'
import { api } from '../api/client'

const COLORS = {
  completed: '#10b981',
  pending:   '#f59e0b',
  failed:    '#ef4444',
  critical:  '#ef4444',
  high:      '#f59e0b',
  medium:    '#8b5cf6',
  low:       '#10b981',
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background:'var(--surface-2)', border:'1px solid var(--border-bright)',
      borderRadius:8, padding:'10px 14px', fontSize:12,
    }}>
      {label && <p style={{ color:'var(--text-dim)', marginBottom:4 }}>{label}</p>}
      {payload.map((p,i) => (
        <p key={i} style={{ color:p.color || 'var(--cyan)' }}>
          {p.name}: <strong>{p.value}</strong>
        </p>
      ))}
    </div>
  )
}

function StatCard({ label, value, sub, color = 'var(--cyan)', icon, delay = 0 }) {
  return (
    <motion.div
      className="card"
      initial={{ opacity:0, y:16 }}
      animate={{ opacity:1, y:0 }}
      transition={{ delay }}
      style={{ padding:'22px 24px' }}
    >
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start' }}>
        <div>
          <div className="stat-label">{label}</div>
          <div className="stat-value" style={{ color }}>{value ?? '—'}</div>
          {sub && <div style={{ fontSize:11, color:'var(--text-muted)', marginTop:4 }}>{sub}</div>}
        </div>
        <div style={{
          width:38, height:38, borderRadius:9,
          background:`rgba(${color === 'var(--cyan)' ? '0,212,255' : color === 'var(--green)' ? '16,185,129' : color === 'var(--amber)' ? '245,158,11' : '239,68,68'},0.1)`,
          border:`1px solid rgba(${color === 'var(--cyan)' ? '0,212,255' : color === 'var(--green)' ? '16,185,129' : color === 'var(--amber)' ? '245,158,11' : '239,68,68'},0.2)`,
          display:'flex', alignItems:'center', justifyContent:'center',
          color,
        }}>
          {icon}
        </div>
      </div>
    </motion.div>
  )
}

export default function Metrics() {
  const [stats, setStats]   = useState(null)
  const [tasks, setTasks]   = useState([])
  const [health, setHealth] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.getStats(),
      api.listTasks(100),
      api.health(),
    ]).then(([s, t, h]) => {
      setStats(s)
      setTasks(t)
      setHealth(h)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  // Build bar chart data — tasks per hour (last 12 hours)
  const hourlyData = (() => {
    const now = Date.now()
    const buckets = Array.from({ length: 12 }, (_, i) => {
      const h = new Date(now - (11 - i) * 3600_000)
      return {
        hour: h.getHours().toString().padStart(2,'0') + ':00',
        count: 0,
        flagged: 0,
      }
    })
    tasks.forEach(t => {
      const age = now - new Date(t.created_at).getTime()
      if (age < 12 * 3600_000) {
        const idx = 11 - Math.floor(age / 3600_000)
        if (idx >= 0 && idx < 12) {
          buckets[idx].count++
          if (t.result?.anomaly_detected) buckets[idx].flagged++
        }
      }
    })
    return buckets
  })()

  // Pie data — status distribution
  const pieData = stats ? [
    { name: 'Completed', value: stats.completed, color: COLORS.completed },
    { name: 'Pending',   value: stats.pending,   color: COLORS.pending },
    { name: 'Failed',    value: stats.failed,    color: COLORS.failed },
  ].filter(d => d.value > 0) : []

  if (loading) {
    return (
      <div className="page">
        <div className="page-header">
          <div className="label" style={{ marginBottom:10 }}>System</div>
          <h1 className="page-title">Metrics</h1>
        </div>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:16 }}>
          {[1,2,3,4].map(i => <div key={i} className="skeleton" style={{ height:100 }} />)}
        </div>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="label" style={{ marginBottom:10 }}>System Intelligence</div>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-end', flexWrap:'wrap', gap:12 }}>
          <div>
            <h1 className="page-title">Metrics</h1>
            <p style={{ color:'var(--text-dim)', fontSize:14 }}>
              Real-time system performance and anomaly intelligence.
            </p>
          </div>
          {/* Health indicator */}
          <div style={{ display:'flex', alignItems:'center', gap:8 }}>
            <div style={{
              width:8, height:8, borderRadius:'50%',
              background: health?.database?.status === 'ok' ? 'var(--green)' : 'var(--red)',
              animation: health?.database?.status === 'ok' ? 'blink 2s ease-in-out infinite' : 'none',
            }} />
            <span style={{ fontSize:12, color:'var(--text-dim)' }}>
              {health?.database?.status === 'ok' ? 'All systems operational' : 'Database issue'}
            </span>
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))', gap:16, marginBottom:32 }}>
        <StatCard
          label="Total Tasks"
          value={stats?.total}
          color="var(--cyan)"
          delay={0}
          icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>}
        />
        <StatCard
          label="Completed"
          value={stats?.completed}
          color="var(--green)"
          delay={0.06}
          icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>}
        />
        <StatCard
          label="Open Escalations"
          value={stats?.escalations_open}
          sub={stats?.escalations_critical ? `${stats.escalations_critical} critical` : null}
          color={stats?.escalations_open > 0 ? 'var(--amber)' : 'var(--green)'}
          delay={0.12}
          icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/></svg>}
        />
        <StatCard
          label="Anomaly Rate"
          value={`${stats?.anomaly_rate ?? 0}%`}
          sub="of total tasks"
          color={stats?.anomaly_rate > 10 ? 'var(--red)' : 'var(--green)'}
          delay={0.18}
          icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>}
        />
        <StatCard
          label="Tasks Today"
          value={stats?.tasks_today}
          color="var(--purple)"
          delay={0.24}
          icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>}
        />
        <StatCard
          label="Pending"
          value={stats?.pending}
          color="var(--amber)"
          delay={0.3}
          icon={<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>}
        />
      </div>

      {/* Charts row */}
      <div style={{ display:'grid', gridTemplateColumns:'2fr 1fr', gap:24, marginBottom:24 }}>
        {/* Hourly tasks bar chart */}
        <motion.div
          className="glass-cyan"
          initial={{ opacity:0, y:20 }}
          animate={{ opacity:1, y:0 }}
          transition={{ delay:0.3 }}
          style={{ borderRadius:14, padding:24 }}
        >
          <div className="label" style={{ marginBottom:16 }}>Task Volume — Last 12 Hours</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={hourlyData} barGap={4}>
              <CartesianGrid strokeDasharray="2 4" stroke="rgba(255,255,255,0.04)" vertical={false} />
              <XAxis dataKey="hour" tick={{ fill:'var(--text-muted)', fontSize:10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill:'var(--text-muted)', fontSize:10 }} axisLine={false} tickLine={false} width={28} />
              <Tooltip content={<CustomTooltip />} cursor={{ fill:'rgba(0,212,255,0.04)' }} />
              <Bar dataKey="count" name="Total" fill="rgba(0,212,255,0.55)" radius={[3,3,0,0]} />
              <Bar dataKey="flagged" name="Flagged" fill="rgba(245,158,11,0.7)" radius={[3,3,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Status pie */}
        <motion.div
          className="glass-cyan"
          initial={{ opacity:0, y:20 }}
          animate={{ opacity:1, y:0 }}
          transition={{ delay:0.36 }}
          style={{ borderRadius:14, padding:24 }}
        >
          <div className="label" style={{ marginBottom:16 }}>Status Distribution</div>
          {pieData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie data={pieData} cx="50%" cy="50%" innerRadius={45} outerRadius={70} paddingAngle={3} dataKey="value">
                    {pieData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} opacity={0.85} />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div style={{ display:'flex', flexDirection:'column', gap:8, marginTop:8 }}>
                {pieData.map((d,i) => (
                  <div key={i} style={{ display:'flex', justifyContent:'space-between', alignItems:'center', fontSize:12 }}>
                    <div style={{ display:'flex', alignItems:'center', gap:6 }}>
                      <div style={{ width:8, height:8, borderRadius:2, background:d.color }} />
                      <span style={{ color:'var(--text-dim)' }}>{d.name}</span>
                    </div>
                    <span style={{ fontWeight:600, color:'var(--text)' }}>{d.value}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div style={{ height:160, display:'flex', alignItems:'center', justifyContent:'center', color:'var(--text-muted)', fontSize:13 }}>
              No data yet
            </div>
          )}
        </motion.div>
      </div>

      {/* System info */}
      {health && (
        <motion.div
          className="glass-cyan"
          initial={{ opacity:0, y:20 }}
          animate={{ opacity:1, y:0 }}
          transition={{ delay:0.42 }}
          style={{ borderRadius:14, padding:24 }}
        >
          <div className="label" style={{ marginBottom:16 }}>System Health</div>
          <div style={{ display:'flex', gap:24, flexWrap:'wrap' }}>
            {[
              { k:'Database', v:health.database?.status },
              { k:'Active Tasks', v:health.database?.active_tasks },
              { k:'Environment', v:health.environment },
            ].map(item => (
              <div key={item.k}>
                <div style={{ fontSize:10, fontWeight:700, letterSpacing:'0.14em', textTransform:'uppercase', color:'var(--text-muted)', marginBottom:4 }}>{item.k}</div>
                <div style={{
                  fontSize:14, fontWeight:600,
                  color: item.v === 'ok' ? 'var(--green)' : item.v === 'degraded' ? 'var(--amber)' : 'var(--text)',
                }}>
                  {String(item.v ?? '—')}
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      )}
    </div>
  )
}
