import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import ParticleField from '../components/ParticleField'
import { api } from '../api/client'

const FADE = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0 } }
const STAGGER = { show: { transition: { staggerChildren: 0.12 } } }

export default function Home() {
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [health, setHealth] = useState(null)

  useEffect(() => {
    api.getStats().then(setStats).catch(() => {})
    api.health().then(setHealth).catch(() => {})
  }, [])

  const statItems = [
    { label: 'Tasks Processed', value: stats?.total ?? '—', color: 'var(--cyan)' },
    { label: 'Anomalies Flagged', value: stats?.escalations_open ?? '—', color: 'var(--amber)' },
    { label: 'Tasks Today', value: stats?.tasks_today ?? '—', color: 'var(--purple)' },
    { label: 'DB Status', value: health?.database?.status ?? '—', color: health?.database?.status === 'ok' ? 'var(--green)' : 'var(--red)' },
  ]

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--space)',
        overflow: 'hidden',
      }}
    >
      <ParticleField opacity={0.8} />

      {/* Ambient orbs */}
      <div style={{
        position:'absolute', top:'15%', left:'20%',
        width:380, height:380, borderRadius:'50%',
        background:'radial-gradient(circle, rgba(0,212,255,0.06) 0%, transparent 70%)',
        animation:'orb-pulse 6s ease-in-out infinite',
        pointerEvents:'none',
      }} />
      <div style={{
        position:'absolute', bottom:'20%', right:'18%',
        width:300, height:300, borderRadius:'50%',
        background:'radial-gradient(circle, rgba(139,92,246,0.07) 0%, transparent 70%)',
        animation:'orb-pulse 8s ease-in-out infinite reverse',
        pointerEvents:'none',
      }} />

      {/* Grid overlay */}
      <div style={{
        position:'absolute', inset:0,
        backgroundImage:`
          linear-gradient(rgba(0,212,255,0.025) 1px, transparent 1px),
          linear-gradient(90deg, rgba(0,212,255,0.025) 1px, transparent 1px)
        `,
        backgroundSize:'60px 60px',
        pointerEvents:'none',
      }} />

      {/* Content */}
      <motion.div
        variants={STAGGER}
        initial="hidden"
        animate="show"
        style={{
          position:'relative', zIndex:10,
          display:'flex', flexDirection:'column', alignItems:'center',
          textAlign:'center', padding:'0 24px', maxWidth:760,
        }}
      >
        {/* Badge */}
        <motion.div variants={FADE} style={{ marginBottom:24 }}>
          <span style={{
            display:'inline-flex', alignItems:'center', gap:8,
            background:'rgba(0,212,255,0.06)',
            border:'1px solid rgba(0,212,255,0.18)',
            borderRadius:20, padding:'6px 16px',
            fontSize:10, fontWeight:700, letterSpacing:'0.2em',
            textTransform:'uppercase', color:'var(--cyan)',
          }}>
            <span style={{ width:6, height:6, borderRadius:'50%', background:'var(--cyan)', animation:'blink 2s ease-in-out infinite' }} />
            Financial Intelligence System
          </span>
        </motion.div>

        {/* Title */}
        <motion.h1
          variants={FADE}
          className="glow-text"
          style={{
            fontSize:'clamp(38px,6vw,72px)',
            fontWeight:700,
            letterSpacing:'-0.03em',
            lineHeight:1.05,
            marginBottom:20,
            background:'linear-gradient(135deg, #e2e8f0 0%, #00d4ff 50%, #8b5cf6 100%)',
            WebkitBackgroundClip:'text',
            WebkitTextFillColor:'transparent',
          }}
        >
          ANALYZE.<br/>DETECT. PROTECT.
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          variants={FADE}
          style={{
            fontSize:16, color:'var(--text-dim)', lineHeight:1.7,
            maxWidth:500, marginBottom:40,
          }}
        >
          Agentic AI that monitors financial transactions, flags anomalies
          in real time, and escalates critical issues — grounded in your compliance policies.
        </motion.p>

        {/* Stats row */}
        <motion.div
          variants={FADE}
          style={{
            display:'flex', gap:24, marginBottom:44, flexWrap:'wrap', justifyContent:'center',
          }}
        >
          {statItems.map(s => (
            <div key={s.label} style={{ textAlign:'center' }}>
              <div style={{ fontSize:28, fontWeight:700, color:s.color, fontVariantNumeric:'tabular-nums' }}>
                {s.value}
              </div>
              <div style={{ fontSize:10, fontWeight:600, letterSpacing:'0.14em', textTransform:'uppercase', color:'var(--text-muted)', marginTop:2 }}>
                {s.label}
              </div>
            </div>
          ))}
        </motion.div>

        {/* CTA buttons */}
        <motion.div variants={FADE} style={{ display:'flex', gap:12, flexWrap:'wrap', justifyContent:'center' }}>
          <button
            className="btn btn-primary"
            style={{ fontSize:13, padding:'14px 32px', position:'relative', overflow:'hidden' }}
            onClick={() => navigate('/terminal')}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/>
            </svg>
            Open Terminal
          </button>
          <button
            className="btn btn-ghost"
            style={{ fontSize:13, padding:'14px 32px' }}
            onClick={() => navigate('/intelligence')}
          >
            View Intelligence Feed
          </button>
        </motion.div>

        {/* Version tag */}
        <motion.p variants={FADE} style={{ marginTop:40, fontSize:11, color:'var(--text-muted)', fontFamily:"'JetBrains Mono',monospace" }}>
          v0.1.0 · FastAPI · Redis Streams · pgvector · RAG
        </motion.p>
      </motion.div>
    </div>
  )
}
