export interface Paginated<T> { count: number; next: string | null; previous: string | null; results: T[] }

export interface User {
  id: string
  email: string
  display_name: string
  bio: string
  avatar: string | null
  is_email_verified: boolean
  created_at: string
}

export interface Workspace {
  id: string
  name: string
  slug: string
  description: string
  created_at: string
  updated_at: string
  archived_at: string | null
  my_role: 'OWNER' | 'ADMIN' | 'MEMBER' | null
}

export interface WorkspaceMember { id: string; user: User; role: 'OWNER' | 'ADMIN' | 'MEMBER'; joined_at: string }
export interface WorkspaceInvitation { id: string; email: string; invited_by: User; intended_role: 'ADMIN' | 'MEMBER'; status: string; expires_at: string; created_at: string; responded_at: string | null }

export interface Project {
  id: string
  workspace_id: string
  workspace_name: string
  board_id: string | null
  name: string
  description: string
  created_at: string
  updated_at: string
  archived_at: string | null
  am_i_a_project_member: boolean
}
export interface ProjectMember { id: string; user: User; joined_at: string }

export type Priority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT'
export interface Label { id: string; name: string; color: string; created_at: string }
export interface Assignee { id: string; user: User; assigned_at: string }
export interface Task {
  id: string
  column_id: string
  project_id: string
  title: string
  description: string
  priority: Priority
  position: number
  start_date: string | null
  due_date: string | null
  is_completed: boolean
  version: number
  assignees: Assignee[]
  labels: Label[]
  checklist_total: number
  checklist_done: number
  created_by: User
  created_at: string
  updated_at: string
}
export interface BoardColumn { id: string; name: string; position: number; created_at: string; tasks: Task[] }
export interface Board { id: string; project_id: string; columns: BoardColumn[]; created_at: string }
export interface ChecklistItem { id: string; text: string; is_done: boolean; position: number; created_at: string }
export interface Checklist { id: string; items: ChecklistItem[]; created_at: string }
export interface Comment { id: string; task_id: string; author: User; body: string; created_at: string; updated_at: string; edited_at: string | null }
export interface ActivityEvent { id: string; actor: User | null; event_type: string; target_type: string; target_id: string | null; metadata: Record<string, unknown>; created_at: string }
