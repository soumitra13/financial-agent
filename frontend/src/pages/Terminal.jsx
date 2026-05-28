import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { api, pollTask } from '../api/client'

const ACCOUNTS = Array.from({ length: 20 }, (_, i) => `ACC-${String(i + 1).padStart(4, '0')}`)

function TerminalOutput({ lines }) {
  const ref = useRef(null)
  useEffect(() => { ref.current?.scrollTo(0, ref.current.scrollHeight) }, [lines])
  return (
    <div className="terminal" ref={ref} style={{ flexGrow:1 }}>
      {lines.length === 0 && (
        <span className="terminal-line dim">// Awaiting task submission...<span className="terminal-cursor" /></span>
      )}
      {lines.map((l, i) => (
        <div key={i} className={`terminal-line ${l.type || ''}`}>{l.text}</div>
      ))}
      {lines.length > 0 && lines[lines.length - 1].cursor && (
        <span className="terminal-cursor" />
      )}
    </div>
  )
}

function AnomalyGauge({ score, label }) {
  const pct = Math.min(100, Math.max(0, score))
  const color = pct > 70 ? 'var(--red)' : pct > 40 ? 'var(--amber)' : 'var(--green)'
  return (
    <div style={{ padding:'16px 0' }}>
      <div style={{ display:'flex', justifyContent:'space-between', marginBottom:8 }}>
        <span style={{ fontSize:11, fontWeight:700, letterSpacing:'0.12em', textTransform:'uppercase', color:'var(--text-dim)' }}>
          Risk Score
        </span>
        <span style={{ fontSize:20, fontWeight:700, color, fontFamily:"'JetBrains Mono',monospace" }}>
          {pct.toFixed(0)}%
        </span>
      </div>
      <div className="severity-bar" style={{ height:6 }}>
        <div
          className="severity-fill"
          style={{ width:`${pct}%`, background:`linear-gradient(90deg, var(--green), ${color})` }}
        />
      </div>
      {label && (
        <p style={{ fontSize:12, color:'var(--text-dim)', marginTop:8 }}>{label}</p>
      )}
    </div>
  )
}

export default function Terminal() {
  const [accountId, setAccountId] = useState('ACC-0001')
  const [description, setDescription] = useState('')
  const [loading, setLoading] = useState(false)
  const [lines, setLines] = useState([])
  const [result, setResult] = useState(null)

  const addLine = (text, type = '') =>
    setLines(prev => [...prev, { text, type }])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!description.trim() || description.length < 10) return

    setLoading(true)
    setResult(null)
    setLines([])

    addLine(`> Submitting task for ${accountId}...`, 'dim')
    addLine(`> Description: "${description}"`, 'dim')

    try {
      const created = await api.createTask({ account_id: accountId, description })
      addLine(`✓ Task queued: ${created.task_id}`, 'cyan')
      addLine(`> Polling for result...`, 'dim')

      let dots = 0
      const dotTimer = setInterval(() => {
        dots++
        setLines(prev => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last?.type === 'dim' && last.text.startsWith('> Processing')) {
            updated[updated.length - 1] = { text: `> Processing${'.'.repeat(dots % 4)}`, type: 'dim', cursor: true }
          } else {
            updated.push({ text: `> Processing.`, type: 'dim', cursor: true })
          }
          return updated
        })
      }, 600)

      const task = await pollTask(created.task_id, (t) => {
        // live status updates absorbed by dotTimer above
      })

      clearInterval(dotTimer)
      setLines(prev => prev.filter(l => !l.text.startsWith('> Processing')))

      if (task.status === 'completed' && task.result) {
        const r = task.result
        addLine(``, '')
        addLine(`══════════════════════════════════`, 'dim')
        addLine(`  ANALYSIS COMPLETE`, 'cyan')
        addLine(`══════════════════════════════════`, 'dim')
        addLine(``, '')
        if (r.summary)         addLine(`SUMMARY: ${r.summary}`, '')
        if (r.anomaly_detected !== undefined)
          addLine(`ANOMALY: ${r.anomaly_detected ? '⚠ DETECTED' : '✓ CLEAN'}`, r.anomaly_detected ? 'amber' : '')
        if (r.severity)        addLine(`SEVERITY: ${r.severity.toUpperCase()}`, r.severity === 'critical' ? 'red' : r.severity === 'high' ? 'amber' : '')
        if (r.recommendation)  addLine(`ACTION: ${r.recommendation}`, '')
        addLine(``, '')
        addLine(`Steps: ${task.total_steps ?? 'N/A'}  |  Model: ${task.agent_model ?? 'N/A'}`, 'dim')
        setResult(r)
      } else {
        addLine(`✗ Task failed or timed out.`, 'red')
      }
    } catch (err) {
      addLine(`✗ Error: ${err.detail || err.message || 'Unknown error'}`, 'red')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page" style={{ display:'flex', flexDirection:'column', minHeight:'100vh' }}>
      {/* Header */}
      <div className="page-header">
        <div className="label" style={{ marginBottom:10 }}>Analysis Engine</div>
        <h1 className="page-title">Transaction Terminal</h1>
        <p style={{ color:'var(--text-dim)', fontSize:14 }}>
          Submit a transaction for AI-powered compliance analysis and anomaly detection.
        </p>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1.3fr', gap:24, flexGrow:1 }}>
        {/* Left – Input panel */}
        <motion.div
          initial={{ opacity:0, x:-20 }}
          animate={{ opacity:1, x:0 }}
          className="glass-cyan"
          style={{ borderRadius:14, padding:28, display:'flex', flexDirection:'column', gap:20 }}
        >
          <div className="label">Task Configuration</div>

          <form onSubmit={handleSubmit} style={{ display:'flex', flexDirection:'column', gap:18, flexGrow:1 }}>
            {/* Account ID */}
            <div>
              <label style={{ fontSize:12, fontWeight:600, color:'var(--text-dim)', letterSpacing:'0.06em', textTransform:'uppercase', display:'block', marginBottom:7 }}>
                Account ID
              </label>
              <select
                className="input"
                value={accountId}
                onChange={e => setAccountId(e.target.value)}
                style={{ appearance:'none', cursor:'pointer' }}
              >
                {ACCOUNTS.map(a => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>

            {/* Description */}
            <div style={{ flexGrow:1 }}>
              <label style={{ fontSize:12, fontWeight:600, color:'var(--text-dim)', letterSpacing:'0.06em', textTransform:'uppercase', display:'block', marginBottom:7 }}>
                Transaction Description
              </label>
              <textarea
                className="input"
                placeholder="Describe the transaction or query for analysis... (min 10 chars)"
                value={description}
                onChange={e => setDescription(e.target.value)}
                style={{ minHeight:120, resize:'vertical' }}
              />
              <div style={{ fontSize:11, color: description.length < 10 ? 'var(--red)' : 'var(--text-muted)', marginTop:5, textAlign:'right' }}>
                {description.length} chars
              </div>
            </div>

            {/* Example prompts */}
            <div>
              <div style={{ fontSize:11, fontWeight:600, color:'var(--text-muted)', letterSpacing:'0.1em', textTransform:'uppercase', marginBottom:8 }}>
                Quick Prompts
              </div>
              <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
                {[
                  'Check for unusual spending patterns in the last 30 days',
                  'Analyse large international transfers above $10,000',
                  'Review recent cash withdrawals for compliance violations',
                ].map(p => (
                  <button
                    key={p}
                    type="button"
                    className="btn btn-ghost"
                    style={{ textAlign:'left', fontSize:11, padding:'7px 12px', textTransform:'none', letterSpacing:0, justifyContent:'flex-start', fontWeight:400 }}
                    onClick={() => setDescription(p)}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || description.length < 10}
              style={{ fontSize:13, padding:'13px', marginTop:'auto' }}
            >
              {loading ? (
                <>
                  <span style={{ display:'inline-block', width:14, height:14, border:'2px solid rgba(0,212,255,0.3)', borderTopColor:'var(--cyan)', borderRadius:'50%', animation:'spin-slow 0.7s linear infinite' }} />
                  Analyzing...
                </>
              ) : (
                <>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                    <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                  </svg>
                  Run Analysis
                </>
              )}
            </button>
          </form>
        </motion.div>

        {/* Right – Output panel */}
        <motion.div
          initial={{ opacity:0, x:20 }}
          animate={{ opacity:1, x:0 }}
          transition={{ delay:0.1 }}
          style={{ display:'flex', flexDirection:'column', gap:16 }}
        >
          <div
            className="glass-cyan"
            style={{ borderRadius:14, padding:24, display:'flex', flexDirection:'column', gap:12, flexGrow:1 }}
          >
            {/* Terminal title bar */}
            <div style={{ display:'flex', alignItems:'center', gap:8, paddingBottom:12, borderBottom:'1px solid var(--border)' }}>
              <div style={{ display:'flex', gap:6 }}>
                {['var(--red)','var(--amber)','var(--green)'].map((c,i) => (
                  <div key={i} style={{ width:10, height:10, borderRadius:'50%', background:c, opacity:0.7 }} />
                ))}
              </div>
              <span style={{ fontSize:11, fontFamily:"'JetBrains Mono',monospace", color:'var(--text-muted)', marginLeft:8 }}>
                fca-analysis-engine ~ output
              </span>
            </div>

            <TerminalOutput lines={lines} />

            {/* Anomaly gauge shown when result available */}
            <AnimatePresence>
              {result && (
                <motion.div
                  initial={{ opacity:0, y:10 }}
                  animate={{ opacity:1, y:0 }}
                  exit={{ opacity:0 }}
                >
                  <div className="divider" style={{ margin:'8px 0' }} />
                  <AnomalyGauge
                    score={result.risk_score ?? (result.anomaly_detected ? 75 : 15)}
                    label={result.severity ? `Severity: ${result.severity}` : null}
                  />
                  {result.escalated && (
                    <div style={{
                      background:'rgba(239,68,68,0.08)',
                      border:'1px solid rgba(239,68,68,0.22)',
                      borderRadius:8, padding:'10px 14px',
                      fontSize:12, color:'var(--red)', display:'flex', alignItems:'center', gap:8,
                    }}>
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                      Escalated to compliance team
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
