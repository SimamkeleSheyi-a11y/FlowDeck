import { LayoutDashboard, KanbanSquare, Users } from 'lucide-react'
import { Link } from 'react-router-dom'

export function WorkspaceTabs({ workspaceId, boardHref, active }: { workspaceId: string; boardHref?: string | null; active: 'dashboard' | 'board' | 'members' }) {
  return <nav className="workspace-tabs" aria-label="Workspace navigation">
    <Link className={active === 'dashboard' ? 'active' : ''} to={`/workspaces/${workspaceId}`}><LayoutDashboard size={16}/> Dashboard</Link>
    {boardHref ? <Link className={active === 'board' ? 'active' : ''} to={boardHref}><KanbanSquare size={16}/> Board</Link> : <span className="disabled"><KanbanSquare size={16}/> Board</span>}
    <Link className={active === 'members' ? 'active' : ''} to={`/workspaces/${workspaceId}?tab=members`}><Users size={16}/> Members</Link>
  </nav>
}
