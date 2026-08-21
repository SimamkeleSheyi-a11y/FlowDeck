import { useQuery } from '@tanstack/react-query'
import { ArrowRight, CheckCircle2, Clock3, Folder, FolderKanban, Plus, Sparkles } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Paginated, Project, Task, Workspace } from '../api/types'
import { useAuth } from '../context/AuthContext'

function dueLabel(date: string | null) { if(!date) return 'No due date'; const days=Math.ceil((new Date(date+'T23:59:59').getTime()-Date.now())/86400000); if(days<0)return `${Math.abs(days)}d overdue`; if(days===0)return 'Due today'; return `Due in ${days}d` }
function relativeUpdated(value:string){const ms=Date.now()-new Date(value).getTime();const days=Math.max(0,Math.floor(ms/86400000));if(days===0)return 'Updated today';if(days===1)return 'Updated yesterday';if(days<30)return `Updated ${days} days ago`;return `Updated ${new Date(value).toLocaleDateString(undefined,{month:'short',day:'numeric'})}`}
export function DashboardPage(){
  const{user}=useAuth();
  const enabled=!!user?.is_email_verified
  const workspaces=useQuery({queryKey:['workspaces'],queryFn:()=>api.get<Paginated<Workspace>>('/workspaces/?limit=100'),enabled})
  const projects=useQuery({queryKey:['projects'],queryFn:()=>api.get<Paginated<Project>>('/projects/?limit=100'),enabled})
  const mine=useQuery({queryKey:['tasks','mine'],queryFn:()=>api.get<Paginated<Task>>('/tasks/?assignee=me&is_completed=false&limit=100'),enabled})
  const tasks=mine.data?.results??[]
  const overdue=tasks.filter(t=>t.due_date&&new Date(t.due_date+'T23:59:59').getTime()<Date.now())
  const loading=workspaces.isLoading||projects.isLoading||mine.isLoading
  return <div className="page">
    <div className="page-heading dashboard-heading"><div><span className="eyebrow">Home</span><h1>Good to see you, {user?.display_name?.split(' ')[0]}.</h1><p>Your teams, projects and next actions at a glance.</p></div><Link to="/workspaces" className="primary-button"><Plus size={17}/> New workspace</Link></div>
    {loading ? <div className="skeleton-grid">{[1,2,3,4].map(i=><div key={i} className="skeleton-card"/>)}</div> : <div className="stat-grid">
      <div className="stat-card"><FolderKanban/><div><strong>{projects.data?.count??0}</strong><span>Active projects</span></div></div>
      <div className="stat-card"><Clock3/><div><strong>{tasks.length}</strong><span>Tasks assigned to me</span>{tasks.length===0&&<small>Clear deck — enjoy it.</small>}</div></div>
      <div className="stat-card danger"><Sparkles/><div><strong>{overdue.length}</strong><span>Overdue tasks</span></div></div>
      <div className="stat-card"><CheckCircle2/><div><strong>{workspaces.data?.count??0}</strong><span>Workspaces</span></div></div>
    </div>}
    <div className="dashboard-grid">
      <section className="panel"><div className="panel-head"><div><span className="eyebrow">Recent Workspaces</span><h2>Pick up where you left off</h2></div><Link to="/workspaces">View all workspaces →</Link></div>{(workspaces.data?.results??[]).length?<div className="recent-workspace-list">{(workspaces.data?.results??[]).slice(0,6).map(w=><Link key={w.id} to={`/workspaces/${w.id}`}><span className="recent-folder"><Folder size={18}/></span><span><strong>{w.name}</strong><small>{w.my_role ?? 'Member'} · {relativeUpdated(w.updated_at)}</small></span><ArrowRight size={16}/></Link>)}</div>:<div className="empty-state compact"><Folder size={28}/><strong>No workspaces yet</strong><span>Create one to organise your first project.</span></div>}</section>
      <section className="panel"><div className="panel-head"><div><span className="eyebrow">Projects</span><h2>Recent project boards</h2></div><Link to="/workspaces">View all projects →</Link></div>{(projects.data?.results??[]).length?<div className="project-mini-list">{(projects.data?.results??[]).slice(0,6).map(p=><Link key={p.id} to={p.board_id?`/projects/${p.id}/board`:`/workspaces/${p.workspace_id}`}><div className="project-symbol">{p.name.slice(0,2).toUpperCase()}</div><div><strong>{p.name}</strong><span>{p.workspace_name}</span></div><ArrowRight size={16}/></Link>)}</div>:<div className="empty-state compact"><FolderKanban size={28}/><strong>No projects yet</strong><span>Create a workspace, then start your first project.</span></div>}</section>
    </div>
    <section className="panel assigned-panel"><div className="panel-head"><div><span className="eyebrow">My Work</span><h2>Tasks assigned to me</h2></div></div>{tasks.length?<div className="task-list">{tasks.slice(0,8).map(t=><Link className="task-row" key={t.id} to={`/projects/${t.project_id}/board?task=${t.id}`}><span className={`priority-dot ${t.priority.toLowerCase()}`}/><div><strong>{t.title}</strong><span>{dueLabel(t.due_date)}</span></div><ArrowRight size={16}/></Link>)}</div>:<div className="empty-inline"><CheckCircle2 size={20}/><span>No assigned tasks right now. Your deck is clear.</span></div>}</section>
  </div>
}
