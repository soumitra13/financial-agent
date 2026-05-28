import { useState } from 'react'
import { setApiKey } from '../api/client'

export default function ApiKeyModal({ onClose }) {
  const [key, setKey] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    const trimmed = key.trim()
    if (!trimmed.startsWith('fca_')) {
      setError('Key must start with fca_')
      return
    }
    setApiKey(trimmed)
    onClose()
  }

  return (
    <div className="modal-overlay">
      <div className="modal" style={{ animation: 'fade-up 0.3s ease' }}>
        {/* Icon */}
        <div style={{ display:'flex', justifyContent:'center', marginBottom:24 }}>
          <div style={{
            width:56, height:56, borderRadius:14,
            background:'linear-gradient(135deg,rgba(0,212,255,0.12),rgba(139,92,246,0.12))',
            border:'1px solid rgba(0,212,255,0.22)',
            display:'flex', alignItems:'center', justifyContent:'center',
            boxShadow:'0 0 30px rgba(0,212,255,0.12)',
          }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--cyan)" strokeWidth="1.8">
              <circle cx="8" cy="15" r="4"/>
              <path d="m21 2-9.6 9.6M15 3l3 3"/>
            </svg>
          </div>
        </div>

        <div className="label" style={{ justifyContent:'center', marginBottom:8 }}>Authentication Required</div>
        <h2 style={{ fontSize:20, fontWeight:700, textAlign:'center', marginBottom:8 }}>Enter API Key</h2>
        <p style={{ fontSize:13, color:'var(--text-dim)', textAlign:'center', marginBottom:24, lineHeight:1.6 }}>
          Find your key in the API container logs on startup, or run{' '}
          <code style={{ fontFamily:"'JetBrains Mono',monospace", color:'var(--cyan)', fontSize:12 }}>
            docker compose logs api
          </code>
        </p>

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom:16 }}>
            <input
              type="text"
              className="input mono"
              placeholder="fca_xxxxxxxx..."
              value={key}
              onChange={e => { setKey(e.target.value); setError('') }}
              autoFocus
              style={{ fontSize:13 }}
            />
            {error && (
              <p style={{ color:'var(--red)', fontSize:12, marginTop:6 }}>{error}</p>
            )}
          </div>
          <button type="submit" className="btn btn-primary" style={{ width:'100%', fontSize:13, padding:'13px' }}>
            Connect to System
          </button>
        </form>

        <p style={{ fontSize:11, color:'var(--text-muted)', textAlign:'center', marginTop:16 }}>
          Key is stored locally in your browser.
        </p>
      </div>
    </div>
  )
}
