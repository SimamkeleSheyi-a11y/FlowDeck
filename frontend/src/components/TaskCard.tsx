import { useSortable } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { CalendarDays, CheckSquare2, GripVertical } from 'lucide-react'
import type { KeyboardEvent } from 'react'
import type { Task } from '../api/types'
export function TaskCard({ task, onOpen }: { task: Task; onOpen: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: task.id, data: { type: 'task', task } })
  const style = { transform: CSS.Transform.toString(transform), transition }
  const key=(event:KeyboardEvent<HTMLElement>)=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();onOpen()}}
  return <article ref={setNodeRef} style={style} className={`task-card ${isDragging?'dragging':''}`} onClick={onOpen} onKeyDown={key} tabIndex={0} role="button" aria-label={`Open task ${task.title}`}>
    <div className="task-card-top"><span className={`priority-stripe ${task.priority.toLowerCase()}`} title={`${task.priority} priority`}/><button className="drag-handle" {...attributes} {...listeners} onClick={e=>e.stopPropagation()} aria-label="Drag task"><GripVertical size={15}/></button></div>
    <h3>{task.title}</h3>
    <div className="task-card-footer"><div className="task-card-meta">{task.due_date&&<span className={new Date(task.due_date+'T23:59:59').getTime()<Date.now()?'overdue':''}><CalendarDays size={14}/>{new Date(task.due_date+'T00:00:00').toLocaleDateString(undefined,{month:'short',day:'numeric'})}</span>}{task.checklist_total>0&&<span><CheckSquare2 size={14}/>{task.checklist_done}/{task.checklist_total}</span>}</div>{task.assignees.length>0&&<div className="task-avatars" aria-label={`${task.assignees.length} assignees`}>{task.assignees.slice(0,3).map(a=><span key={a.id} title={a.user.display_name}>{a.user.display_name.slice(0,1).toUpperCase()}</span>)}{task.assignees.length>3&&<span>+{task.assignees.length-3}</span>}</div>}</div>
  </article>
}
