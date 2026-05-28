import { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '../api/client'

function fmtDate(iso) {
  if (!iso) return 'Never'
  return new Date(iso).toLocaleString('en-US', { month:'short', day:'numeric', year:'numeric', hour:'2-digit', minute:'2-digit' })
}

function CreateKeyModal({ onClose, onCreated }) {
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(false)
  const [newKey, setNewKey] = useState(null)
  const [copied, setCopied] = useState(false)

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setLoading(true)
    try {
      const result = await api.createKey(name.trim())
      setNewKey(result)
      onCreated()
    } catch (err) {
      alert(err.detail || 'Failed to create key')
    } finally {
      setLoading(false)
    }
  }

  const copyKey = () => {
    navigator.clipboard.writeText(newKey.key)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="modal-overlay">
      <motion.div
        className="modal"
        initial={{ scale:0.95, opacity:0 }}
        animate={{ scale:1, opacity:1 }}
      >
        {!newKey ? (
          <>
            <div className="label" style={{ marginBottom:10 }}>Key Management</div>
            <h3 style={{ fontSize:20, fontWeight:700, marginBottom:6 }}>Generate New Key</h3>
            <p style={{ fontSize:13, color:'var(--text-dim)', marginBottom:24, lineHeight:1.6 }}>
              Give your key a memorable label (e.g. "prod-server", "dev-laptop").
            </p>
            <form onSubmit={handleCreate}>
              <input
                className="input"
                placeholder="Key name..."
                value={name}
                onChange={e => setName(e.target.value)}
                autoFocus
                style={{ marginBottom:16 }}
              />
              <div style={{ display:'flex', gap:10 }}>
                <button type="button" className="btn btn-ghost" style={{ flex:1, fontSize:12 }} onClick={onClose}>
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={loading || !name.trim()}
                  style={{ flex:2, fontSize:12 }}
                >
                  {loading ? 'Generating...' : 'Generate Key'}
                </button>
              </div>
            </form>
          </>
        ) : (
          <>
            <div style={{ textAlign:'center', marginBottom:20 }}>
              <div style={{
                width:48, height:48, borderRadius:12, margin:'0 auto 16px',
                background:'var(--green-dim)', border:'1px solid rgba(16,185,129,0.3)',
                display:'flex', alignItems:'center', justifyContent:'center',
              }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="2">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
              </div>
              <h3 style={{ fontSize:18, fontWeight:700, marginBottom:6 }}>Key Generated</h3>
              <p style={{ fontSize:13, color:'var(--red)', fontWeight:600 }}>
                ⚠ Copy this key now — it will not be shown again.
              </p>
            </div>

            <div style={{
              background:'rgba(0,0,0,0.4)',
              border:'1px solid rgba(0,212,255,0.15)',
              borderRadius:8, padding:'12px 16px',
              marginBottom:16, wordBreak:'break-all',
              fontFamily:"'JetBrains Mono',monospace",
              fontSize:12, color:'var(--cyan)', lineHeight:1.6,
            }}>
              {newKey.key}
            </div>

            <div style={{ display:'flex', gap:10 }}>
              <button
                className="btn btn-primary"
                style={{ flex:2, fontSize:12 }}
                onClick={copyKey}
              >
                {copied ? '✓ Copied!' : 'Copy Key'}
              </button>
              <button className="btn btn-ghost" style={{ flex:1, fontSize:12 }} onClick={onClose}>
                Done
              </button>
            </div>
          </>
        )}
      </motion.div>
    </div>
  )
}

export default function Vault() {
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [revoking, setRevoking] = useState(null)

  const loadKeys = () => {
    api.listKeys().then(data => { setKeys(data); setLoading(false) }).catch(() => setLoading(false))
  }

  useEffect(() => { loadKeys() }, [])

  const handleRevoke = async (id) => {
    if (!confirm('Revoke this key? This cannot be undone.')) return
    setRevoking(id)
    try {
      await api.revokeKey(id)
      loadKeys()
    } catch (err) {
      alert(err.detail || 'Failed to revoke key')
    } finally {
      setRevoking(null)
    }
  }

  const activeKeys = keys.filter(k => k.is_active)
  const revokedKeys = keys.filter(k => !k.is_active)

  return (
    <div className="page">
      <div className="page-header">
        <div className="label" style={{ marginBottom:10 }}>Authentication</div>
        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-end', flexWrap:'wrap', gap:12 }}>
          <div>
            <h1 className="page-title">API Key Vault</h1>
            <p style={{ color:'var(--text-dim)', fontSize:14 }}>
              Manage API keys for system access. Keys are stored as SHA-256 hashes.
            </p>
          </div>
          <button className="btn btn-primary" style={{ fontSize:12 }} onClick={() => setShowCreate(true)}>
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            Generate Key
          </button>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display:'flex', gap:16, marginBottom:32, flexWrap:'wrap' }}>
        {[
          { label:'Active Keys', value:activeKeys.length, color:'var(--green)' },
          { label:'Revoked Keys', value:revokedKeys.length, color:'var(--text-muted)' },
          { label:'Total Keys', value:keys.length, color:'var(--cyan)' },
        ].map(s => (
          <div key={s.label} className="card" style={{ padding:'16px 24px', display:'flex', alignItems:'center', gap:16 }}>
            <span style={{ fontSize:28, fontWeight:700, color:s.color }}>{s.value}</span>
            <span style={{ fontSize:11, fontWeight:600, letterSpacing:'0.1em', textTransform:'uppercase', color:'var(--text-dim)' }}>{s.label}</span>
          </div>
        ))}
      </div>

      {/* Active keys */}
      <div style={{ marginBottom:32 }}>
        <div className="label" style={{ marginBottom:16 }}>Active Keys</div>
        {loading ? (
          <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
            {[1,2].map(i => <div key={i} className="skeleton" style={{ height:72 }} />)}
          </div>
        ) : activeKeys.length === 0 ? (
          <div className="card" style={{ padding:24, textAlign:'center', color:'var(--text-muted)', fontSize:13 }}>
            No active keys. Generate one to get started.
          </div>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
            <AnimatePresence>
              {activeKeys.map(k => (
                <motion.div
                  key={k.id}
                  layout
                  initial={{ opacity:0, y:8 }}
                  animate={{ opacity:1, y:0 }}
                  exit={{ opacity:0, height:0 }}
                  className="glass-cyan"
                  style={{ borderRadius:12, padding:'18px 22px', display:'flex', alignItems:'center', gap:16, flexWrap:'wrap' }}
                >
                  {/* Key icon */}
                  <div style={{ width:38, height:38, borderRadius:9, background:'rgba(16,185,129,0.1)', border:'1px solid rgba(16,185,129,0.22)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="var(--green)" strokeWidth="1.8">
                      <circle cx="8" cy="15" r="4"/><path d="m21 2-9.6 9.6M15 3l3 3"/>
                    </svg>
                  </div>

                  <div style={{ flexGrow:1 }}>
                    <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:4 }}>
                      <span style={{ fontWeight:600, fontSize:14 }}>{k.name}</span>
                      <span className="badge badge-active">Active</span>
                    </div>
                    <div style={{ display:'flex', gap:16, flexWrap:'wrap' }}>
                      <span className="mono" style={{ fontSize:11, color:'var(--text-muted)' }}>
                        ID: {k.id.slice(0,12)}...
                      </span>
                      <span style={{ fontSize:11, color:'var(--text-muted)' }}>
                        Created: {fmtDate(k.created_at)}
                      </span>
                      {k.last_used_at && (
                        <span style={{ fontSize:11, color:'var(--text-muted)' }}>
                          Last used: {fmtDate(k.last_used_at)}
                        </span>
                      )}
                    </div>
                  </div>

                  <button
                    className="btn btn-danger"
                    disabled={revoking === k.id}
                    onClick={() => handleRevoke(k.id)}
                  >
                    {revoking === k.id ? 'Revoking...' : 'Revoke'}
                  </button>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>

      {/* Revoked keys */}
      {revokedKeys.length > 0 && (
        <div>
          <div className="label" style={{ marginBottom:16, color:'var(--text-muted)' }}>Revoked Keys</div>
          <div style={{ display:'flex', flexDirection:'column', gap:8, opacity:0.5 }}>
            {revokedKeys.map(k => (
              <div key={k.id} className="card" style={{ padding:'14px 22px', display:'flex', alignItems:'center', gap:12 }}>
                <span style={{ fontWeight:500, fontSize:13 }}>{k.name}</span>
                <span className="badge badge-revoked">Revoked</span>
                <span className="mono" style={{ fontSize:11, color:'var(--text-muted)', marginLeft:'auto' }}>
                  {k.id.slice(0,12)}...
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <AnimatePresence>
        {showCreate && (
          <CreateKeyModal
            onClose={() => setShowCreate(false)}
            onCreated={loadKeys}
          />
        )}
      </AnimatePresence>
    </div>
  )
}
