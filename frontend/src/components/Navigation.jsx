import { NavLink } from 'react-router-dom'

const NAV_ITEMS = [
  {
    to: '/',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <circle cx="12" cy="12" r="3"/>
        <path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
      </svg>
    ),
    label: 'Command',
  },
  {
    to: '/terminal',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <polyline points="4 17 10 11 4 5"/>
        <line x1="12" y1="19" x2="20" y2="19"/>
      </svg>
    ),
    label: 'Terminal',
  },
  {
    to: '/intelligence',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <path d="M2 20h20M4 20V10l8-6 8 6v10"/>
        <rect x="9" y="14" width="6" height="6"/>
      </svg>
    ),
    label: 'Intelligence',
  },
  {
    to: '/metrics',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <line x1="18" y1="20" x2="18" y2="10"/>
        <line x1="12" y1="20" x2="12" y2="4"/>
        <line x1="6"  y1="20" x2="6"  y2="14"/>
      </svg>
    ),
    label: 'Metrics',
  },
  {
    to: '/vault',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
        <rect x="3" y="11" width="18" height="11" rx="2"/>
        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        <circle cx="12" cy="16" r="1" fill="currentColor"/>
      </svg>
    ),
    label: 'Vault',
  },
]

export default function Navigation() {
  return (
    <nav
      style={{
        position: 'fixed',
        left: 0,
        top: 0,
        bottom: 0,
        width: 'var(--nav-width)',
        background: 'rgba(7,12,24,0.92)',
        backdropFilter: 'blur(20px)',
        borderRight: '1px solid rgba(0,212,255,0.08)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        paddingTop: '20px',
        paddingBottom: '20px',
        gap: '4px',
        zIndex: 100,
      }}
    >
      {/* Logo mark */}
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: '10px',
          background: 'linear-gradient(135deg,rgba(0,212,255,0.18),rgba(139,92,246,0.18))',
          border: '1px solid rgba(0,212,255,0.25)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          marginBottom: '24px',
          boxShadow: '0 0 18px rgba(0,212,255,0.15)',
          flexShrink: 0,
        }}
      >
        <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:12, fontWeight:700, color:'var(--cyan)', letterSpacing:'-0.04em' }}>FCA</span>
      </div>

      {NAV_ITEMS.map(item => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.to === '/'}
          data-tooltip={item.label}
          style={({ isActive }) => ({
            width: 44,
            height: 44,
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            textDecoration: 'none',
            color: isActive ? 'var(--cyan)' : 'var(--text-muted)',
            background: isActive ? 'rgba(0,212,255,0.09)' : 'transparent',
            border: isActive ? '1px solid rgba(0,212,255,0.2)' : '1px solid transparent',
            boxShadow: isActive ? '0 0 16px rgba(0,212,255,0.12)' : 'none',
            transition: 'all 0.2s ease',
          })}
        >
          {item.icon}
        </NavLink>
      ))}
    </nav>
  )
}
