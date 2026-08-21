import { useQuery } from '@tanstack/react-query'
import { Boxes, FolderKanban, Search, SquareCheckBig, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import type { Paginated, Project, Task, Workspace } from '../api/types'
import { useAuth } from '../context/AuthContext'

export function SearchPalette() {
  const { user } = useAuth()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const enabled = !!user?.is_email_verified
  const workspaces = useQuery({ queryKey: ['search','workspaces'], queryFn: () => api.get<Paginated<Workspace>>('/workspaces/?limit=100'), enabled: open && enabled, staleTime: 30_000 })
  const projects = useQuery({ queryKey: ['search','projects'], queryFn: () => api.get<Paginated<Project>>('/projects/?limit=100'), enabled: open && enabled, staleTime: 30_000 })
  const tasks = useQuery({ queryKey: ['search','tasks'], queryFn: () => api.get<Paginated<Task>>('/tasks/?limit=100'), enabled: open && enabled, staleTime: 15_000 })

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); setOpen(v => !v) }
      if (event.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  useEffect(() => { if (open) window.setTimeout(() => inputRef.current?.focus(), 0); else setQuery('') }, [open])

  const projectMap = useMemo(() => new Map((projects.data?.results ?? []).map(p => [p.id, p])), [projects.data])
  const normalized = query.trim().toLowerCase()
  const results = useMemo(() => {
    if (!normalized) return []
    const ws = (workspaces.data?.results ?? []).filter(w => `${w.name} ${w.description}`.toLowerCase().includes(normalized)).slice(0,4).map(w => ({ id:`w-${w.id}`, kind:'Workspace', title:w.name, sub:w.description || `${w.my_role ?? 'Member'} workspace`, href:`/workspaces/${w.id}`, Icon:Boxes }))
    const ps = (projects.data?.results ?? []).filter(p => `${p.name} ${p.description} ${p.workspace_name}`.toLowerCase().includes(normalized)).slice(0,5).map(p => ({ id:`p-${p.id}`, kind:'Project', title:p.name, sub:p.workspace_name, href:p.board_id ? `/projects/${p.id}/board` : `/workspaces/${p.workspace_id}`, Icon:FolderKanban }))
    const ts = (tasks.data?.results ?? []).filter(t => `${t.title} ${t.description} ${t.priority} ${t.labels.map(l=>l.name).join(' ')} ${t.assignees.map(a=>a.user.display_name).join(' ')}`.toLowerCase().includes(normalized)).slice(0,7).map(t => ({ id:`t-${t.id}`, kind:'Task', title:t.title, sub:projectMap.get(t.project_id)?.name ?? t.priority, href:`/projects/${t.project_id}/board?task=${t.id}`, Icon:SquareCheckBig }))
    return [...ws, ...ps, ...ts]
  }, [normalized, workspaces.data, projects.data, tasks.data, projectMap])

  return <>
    <button className="search-trigger" onClick={() => setOpen(true)}><Search size={16}/><span>Search FlowDeck</span><kbd>Ctrl K</kbd></button>
    {open && <div className="search-backdrop" onMouseDown={e => { if (e.currentTarget === e.target) setOpen(false) }}>
      <section className="search-palette" role="dialog" aria-modal="true" aria-label="Search FlowDeck">
        <div className="search-input-wrap"><Search size={18}/><input ref={inputRef} value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search workspaces, projects and tasks…"/><button className="icon-button" onClick={()=>setOpen(false)} aria-label="Close search"><X size={17}/></button></div>
        {!enabled ? <div className="search-empty">Verify your email to search your workspace data.</div> : !normalized ? <div className="search-empty"><strong>Find anything quickly.</strong><span>Try a workspace, project, task title, label, assignee or priority.</span></div> : (workspaces.isLoading || projects.isLoading || tasks.isLoading) ? <div className="search-empty"><span className="spinner"/> Searching…</div> : results.length ? <div className="search-results">{results.map(({id,kind,title,sub,href,Icon}) => <Link key={id} to={href} onClick={()=>setOpen(false)}><span className="search-result-icon"><Icon size={17}/></span><span><small>{kind}</small><strong>{title}</strong><em>{sub}</em></span></Link>)}</div> : <div className="search-empty">No matches for “{query}”.</div>}
      </section>
    </div>}
  </>
}
