import { DndContext, PointerSensor, closestCorners, useDroppable, useSensor, useSensors, type DragEndEvent } from '@dnd-kit/core'
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Columns3, Plus, Users } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ApiError, api } from '../api/client'
import type { Board, BoardColumn, Priority, Project, ProjectMember, Task, Workspace, WorkspaceMember } from '../api/types'
import { Modal } from '../components/Modal'
import { TaskCard } from '../components/TaskCard'
import { TaskDrawer } from '../components/TaskDrawer'
import { WorkspaceTabs } from '../components/WorkspaceTabs'
import { useToast } from '../context/ToastContext'

function DroppableColumn({ column, onCreate, onOpen }: { column: BoardColumn; onCreate: () => void; onOpen: (id: string) => void }) {
  const { setNodeRef, isOver } = useDroppable({ id: column.id, data: { type: 'column', columnId: column.id } })
  return <section ref={setNodeRef} className={`kanban-column ${isOver ? 'column-over' : ''}`}>
    <header><div><span className="column-dot"/><strong>{column.name}</strong><small>{column.tasks.length}</small></div><button className="icon-button" onClick={onCreate} aria-label={`Add task to ${column.name}`}><Plus size={17}/></button></header>
    <SortableContext items={column.tasks.map(t => t.id)} strategy={verticalListSortingStrategy}><div className={`column-tasks ${column.tasks.length===0?'empty-column':''}`}>{column.tasks.map(task => <TaskCard key={task.id} task={task} onOpen={() => onOpen(task.id)}/>) }{column.tasks.length===0&&<div className="column-empty-copy"><span>No tasks yet</span><small>Move work here or create a new task.</small></div>}</div></SortableContext>
    <button className="add-task-button" onClick={onCreate}><Plus size={15}/> Add Task</button>
  </section>
}

export function BoardPage() {
  const { projectId } = useParams();const [params, setParams] = useSearchParams();const qc = useQueryClient();const toast = useToast();
  const [createTaskColumn, setCreateTaskColumn] = useState<string | null>(null);const [columnOpen,setColumnOpen]=useState(false);const[columnName,setColumnName]=useState('');const [teamOpen, setTeamOpen] = useState(false);const [title, setTitle] = useState('');const [description, setDescription] = useState('');const [priority, setPriority] = useState<Priority>('MEDIUM');const [due, setDue] = useState('')
  const project = useQuery({ queryKey: ['project', projectId], queryFn: () => api.get<Project>(`/projects/${projectId}/`), enabled: !!projectId })
  const workspace=useQuery({queryKey:['workspace',project.data?.workspace_id],queryFn:()=>api.get<Workspace>(`/workspaces/${project.data?.workspace_id}/`),enabled:!!project.data?.workspace_id})
  const boardId = project.data?.board_id
  const board = useQuery({ queryKey: ['board', projectId], queryFn: () => api.get<Board>(`/boards/${boardId}/full/`), enabled: !!boardId })
  const projectMembers = useQuery({ queryKey: ['project-members', projectId], queryFn: () => api.get<ProjectMember[]>(`/projects/${projectId}/members/`), enabled: !!projectId && teamOpen })
  const workspaceMembers = useQuery({ queryKey: ['workspace-members', project.data?.workspace_id], queryFn: () => api.get<WorkspaceMember[]>(`/workspaces/${project.data?.workspace_id}/members/`), enabled: !!project.data?.workspace_id && teamOpen })
  const canManage=workspace.data?.my_role==='OWNER'||workspace.data?.my_role==='ADMIN'
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 6 } }))
  const tasksById = useMemo(() => new Map((board.data?.columns ?? []).flatMap(c => c.tasks.map(t => [t.id, t] as const))), [board.data])
  const create = useMutation({ mutationFn: () => api.post<Task>('/tasks/', { column_id: createTaskColumn, title, description, priority, due_date: due || null }), onSuccess: () => { void qc.invalidateQueries({ queryKey: ['board', projectId] });setCreateTaskColumn(null); setTitle(''); setDescription(''); setPriority('MEDIUM'); setDue('');toast('Task created.', 'success') }, onError: e => toast(e.message, 'error') })
  const createColumn=useMutation({mutationFn:()=>api.post<BoardColumn>(`/boards/${boardId}/columns/`,{name:columnName}),onSuccess:()=>{void qc.invalidateQueries({queryKey:['board',projectId]});setColumnOpen(false);setColumnName('');toast('Column added.','success')},onError:e=>toast(e.message,'error')})
  function openTask(id: string) { setParams({ task: id }) } function closeTask() { setParams({}) }

  async function onDragEnd(event: DragEndEvent) {
    const activeId = String(event.active.id);const overId = event.over ? String(event.over.id) : null;if (!overId || activeId === overId) return
    const task = tasksById.get(activeId);if (!task || !board.data) return
    const sourceColumn=board.data.columns.find(c=>c.id===task.column_id);const sourceTasks=sourceColumn?.tasks.filter(t=>t.id!==task.id)??[];const originalIndex=sourceColumn?.tasks.findIndex(t=>t.id===task.id)??0;const previousAfterTaskId=originalIndex>0?sourceColumn!.tasks[originalIndex-1].id:null
    let targetColumn = board.data.columns.find(c => c.id === overId);const overTask = tasksById.get(overId);if (!targetColumn && overTask) targetColumn = board.data.columns.find(c => c.id === overTask.column_id);if (!targetColumn) return
    const targetTasks = targetColumn.tasks.filter(t => t.id !== task.id);let afterTaskId: string | null = null
    if (overTask) { const idx = targetTasks.findIndex(t => t.id === overTask.id);afterTaskId = idx > 0 ? targetTasks[idx - 1].id : null } else if (targetTasks.length) afterTaskId = targetTasks[targetTasks.length - 1].id
    try {
      const moved=await api.post<Task & {conflict?:boolean}>(`/tasks/${task.id}/move/`, { column_id: targetColumn.id, after_task_id: afterTaskId, version: task.version, strict: true })
      await qc.invalidateQueries({ queryKey: ['board', projectId] })
      const destinationName=targetColumn.name
      if(sourceColumn && sourceColumn.id!==targetColumn.id || previousAfterTaskId!==afterTaskId){
        toast(`Task moved to ${destinationName}.`,'success',{label:'Undo',onClick:async()=>{try{await api.post(`/tasks/${task.id}/move/`,{column_id:sourceColumn?.id??task.column_id,after_task_id:previousAfterTaskId,version:moved.version,strict:true});await qc.invalidateQueries({queryKey:['board',projectId]});toast('Move undone.','info')}catch(err){toast(err instanceof Error?err.message:'Could not undo the move.','error')}}},5000)
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) toast('This board changed elsewhere. We refreshed the latest version — try your move again.', 'info')
      else toast(e instanceof Error ? e.message : 'Could not move task.', 'error')
      await qc.invalidateQueries({ queryKey: ['board', projectId] })
    }
  }
  async function addProjectMember(userId: string) { try { await api.post(`/projects/${projectId}/members/`, { user_id: userId });await qc.invalidateQueries({ queryKey: ['project-members', projectId] });toast('Member added to project.', 'success') } catch (e) { toast(e instanceof Error ? e.message : 'Could not add member.', 'error') } }
  async function removeProjectMember(userId: string) { try { await api.delete(`/projects/${projectId}/members/${userId}/`);await qc.invalidateQueries({ queryKey: ['project-members', projectId] });toast('Member removed from project.', 'success') } catch (e) { toast(e instanceof Error ? e.message : 'Could not remove member.', 'error') } }
  const projectMemberIds = new Set((projectMembers.data ?? []).map(m => m.user.id))
  return <div className="page board-page">
    <div className="board-heading"><div><Link className="back-link" to={project.data ? `/workspaces/${project.data.workspace_id}` : '/workspaces'}><ArrowLeft size={15}/> All Workspaces</Link><span className="eyebrow">Kanban Board</span><h1>{project.data?.name ?? 'Board'}</h1><p>{project.data?.description || 'Drag tasks between columns to track progress.'}</p></div><div className="heading-actions"><button className="secondary-button" onClick={() => setTeamOpen(true)}><Users size={16}/> Project team</button>{canManage&&<button className="secondary-button" onClick={()=>setColumnOpen(true)}><Columns3 size={16}/> Add column</button>}</div></div>
    {project.data?.workspace_id&&<WorkspaceTabs workspaceId={project.data.workspace_id} boardHref={`/projects/${projectId}/board`} active="board"/>}
    {board.isLoading ? <div className="board-skeleton">{[1,2,3].map(i=><div key={i}><span/><span/><span/></div>)}</div> : !board.data?.columns.length ? <div className="empty-board"><div className="empty-board-icon"><Columns3 size={32}/></div><h2>Your board is ready.</h2><p>Create your first column to start organising work.</p>{canManage?<button className="primary-button large-action" onClick={()=>setColumnOpen(true)}><Plus size={18}/> Add First Column</button>:<span>An owner or admin can add the first column.</span>}</div> : <DndContext sensors={sensors} collisionDetection={closestCorners} onDragEnd={e => void onDragEnd(e)}><div className="kanban-board">{board.data.columns.map(column => <DroppableColumn key={column.id} column={column} onCreate={() => setCreateTaskColumn(column.id)} onOpen={openTask}/>)}</div></DndContext>}
    {createTaskColumn && <Modal title="Create task" onClose={() => setCreateTaskColumn(null)}><form className="stack-form" onSubmit={(e: FormEvent) => { e.preventDefault(); create.mutate() }}><label>Title<input autoFocus required value={title} onChange={e => setTitle(e.target.value)}/></label><label>Description<textarea rows={4} value={description} onChange={e => setDescription(e.target.value)}/></label><div className="form-row"><label>Priority<select value={priority} onChange={e => setPriority(e.target.value as Priority)}>{['LOW','MEDIUM','HIGH','URGENT'].map(p => <option key={p}>{p}</option>)}</select></label><label>Due date<input type="date" value={due} onChange={e => setDue(e.target.value)}/></label></div><div className="form-actions"><button type="button" className="secondary-button" onClick={() => setCreateTaskColumn(null)}>Cancel</button><button className="primary-button" disabled={create.isPending}>{create.isPending ? 'Creating…' : 'Create task'}</button></div></form></Modal>}
    {columnOpen&&<Modal title={board.data?.columns.length?'Add column':'Add your first column'} onClose={()=>setColumnOpen(false)}><form className="stack-form" onSubmit={(e:FormEvent)=>{e.preventDefault();createColumn.mutate()}}><label>Column name<input autoFocus required value={columnName} onChange={e=>setColumnName(e.target.value)} placeholder="e.g. Review"/></label><p className="modal-copy">Columns represent stages in your workflow. You can add tasks as soon as the column is created.</p><div className="form-actions"><button type="button" className="secondary-button" onClick={()=>setColumnOpen(false)}>Cancel</button><button className="primary-button" disabled={createColumn.isPending}>{createColumn.isPending?'Adding…':'Add column'}</button></div></form></Modal>}
    {teamOpen && <Modal title="Project team" onClose={() => setTeamOpen(false)}><div className="team-manager"><span className="eyebrow">On this project</span>{(projectMembers.data ?? []).length ? (projectMembers.data ?? []).map(member => <div className="team-manager-row" key={member.id}><div className="avatar small">{member.user.display_name.slice(0,1).toUpperCase()}</div><div><strong>{member.user.display_name}</strong><span>{member.user.email}</span></div><button className="ghost-danger" onClick={() => void removeProjectMember(member.user.id)}>Remove</button></div>) : <p className="muted-copy">No explicit project members yet. Workspace owners/admins can still manage the board.</p>}<div className="divider"/><span className="eyebrow">Available workspace members</span>{(workspaceMembers.data ?? []).filter(member => !projectMemberIds.has(member.user.id)).map(member => <div className="team-manager-row" key={member.id}><div className="avatar small">{member.user.display_name.slice(0,1).toUpperCase()}</div><div><strong>{member.user.display_name}</strong><span>{member.role}</span></div><button className="secondary-button mini" onClick={() => void addProjectMember(member.user.id)}>Add</button></div>)}</div></Modal>}
    {params.get('task') && projectId && <TaskDrawer taskId={params.get('task')!} projectId={projectId} onClose={closeTask}/>} 
  </div>
}
