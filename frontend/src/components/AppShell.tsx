import { Boxes, Home, Keyboard, LogOut, Menu, Settings, X } from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { Modal } from './Modal'
import { SearchPalette } from './SearchPalette'

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const [shortcuts, setShortcuts] = useState(false)
  const links = [
    { to: '/', label: 'Home', icon: Home },
    { to: '/workspaces', label: 'Workspaces', icon: Boxes },
    { to: '/settings', label: 'Account Settings', icon: Settings },
  ]
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key === '/') { event.preventDefault(); setShortcuts(true) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  const initial = user?.display_name?.trim().slice(0,1).toUpperCase() || user?.email?.slice(0,1).toUpperCase() || '?'
  return <div className="app-shell">
    <aside className={`sidebar ${open ? 'open' : ''}`}>
      <div className="brand"><span className="brand-mark">F</span><div className="brand-copy"><span>FlowDeck</span><small>Make work flow.</small></div><button className="sidebar-close" onClick={() => setOpen(false)}><X size={18}/></button></div>
      <nav>{links.map(({to,label,icon:Icon}) => <NavLink key={to} to={to} end={to === '/'} onClick={() => setOpen(false)}><Icon size={18}/><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-foot">
        <button className="shortcut-link" onClick={()=>setShortcuts(true)}><Keyboard size={17}/> Keyboard shortcuts <kbd>Ctrl /</kbd></button>
        <div className="sidebar-profile" title={`${user?.display_name ?? ''}\n${user?.email ?? ''}`}><div className="avatar">{initial}</div><div><strong>{user?.display_name || 'FlowDeck user'}</strong><span>{user?.is_email_verified ? 'Verified account' : 'Email not verified'}</span></div></div>
        <button className="nav-logout" onClick={() => void logout()}><LogOut size={17}/> Log out</button>
      </div>
    </aside>
    <div className="main-column">
      <header className="mobile-topbar"><button className="icon-button" onClick={() => setOpen(true)}><Menu size={20}/></button><div className="brand"><span className="brand-mark">F</span><span>FlowDeck</span></div><SearchPalette/></header>
      <header className="desktop-topbar"><SearchPalette/></header>
      {!user?.is_email_verified && <div className="verification-banner">Verify your email before creating workspaces, projects or tasks. Check the backend console in local development for the verification link.</div>}
      <main className="main-content">{children}</main>
    </div>
    {shortcuts && <Modal title="Keyboard shortcuts" onClose={()=>setShortcuts(false)}><div className="shortcut-list"><div><kbd>Ctrl / Cmd + K</kbd><span>Open global search</span></div><div><kbd>Ctrl / Cmd + /</kbd><span>Show keyboard shortcuts</span></div><div><kbd>Enter / Space</kbd><span>Open a focused task card</span></div><div><kbd>Esc</kbd><span>Close dialogs, drawers and search</span></div><div><kbd>Enter</kbd><span>Submit the focused form</span></div></div></Modal>}
  </div>
}
