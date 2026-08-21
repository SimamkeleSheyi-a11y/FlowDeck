import type { User } from './types'

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://127.0.0.1:8000/api'
let accessToken: string | null = null
let refreshing: Promise<boolean> | null = null

export class ApiError extends Error {
  status: number
  body: unknown
  constructor(status: number, body: unknown) {
    super(errorMessage(body))
    this.status = status
    this.body = body
  }
}

export function errorMessage(body: unknown): string {
  if (!body || typeof body !== 'object') return 'Something went wrong.'
  const record = body as Record<string, unknown>
  if (typeof record.detail === 'string') return record.detail
  for (const value of Object.values(record)) {
    if (typeof value === 'string') return value
    if (Array.isArray(value) && value.length) return String(value[0])
    if (value && typeof value === 'object') {
      const nested = errorMessage(value)
      if (nested !== 'Something went wrong.') return nested
    }
  }
  return 'Something went wrong.'
}

function setAccessToken(token: string | null) { accessToken = token }

async function parseResponse(response: Response) {
  if (response.status === 204) return null
  const text = await response.text()
  if (!text) return null
  try { return JSON.parse(text) } catch { return text }
}

async function refreshSession(): Promise<boolean> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const response = await fetch(`${API_BASE}/auth/refresh/`, { method: 'POST', credentials: 'include' })
        if (!response.ok) { setAccessToken(null); return false }
        const data = await response.json() as { access: string }
        setAccessToken(data.access)
        return true
      } catch { setAccessToken(null); return false }
      finally { refreshing = null }
    })()
  }
  return refreshing
}

interface RequestOptions extends RequestInit { retry?: boolean }
async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { retry = true, headers: suppliedHeaders, ...rest } = options
  const headers = new Headers(suppliedHeaders)
  if (!(rest.body instanceof FormData)) headers.set('Content-Type', 'application/json')
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`)
  const response = await fetch(`${API_BASE}${path}`, { ...rest, headers, credentials: 'include' })
  if (response.status === 401 && retry && await refreshSession()) return request<T>(path, { ...options, retry: false })
  const data = await parseResponse(response)
  if (!response.ok) throw new ApiError(response.status, data)
  return data as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  delete: <T = null>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, body: FormData) => request<T>(path, { method: 'POST', body }),
}

export async function login(email: string, password: string) {
  const response = await fetch(`${API_BASE}/auth/login/`, {
    method: 'POST', credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }),
  })
  const data = await parseResponse(response) as { access?: string; user?: User }
  if (!response.ok || !data.access || !data.user) throw new ApiError(response.status, data)
  setAccessToken(data.access)
  return data.user
}

export async function restoreSession(): Promise<User | null> {
  if (!await refreshSession()) return null
  try { return await api.get<User>('/users/me/') } catch { return null }
}

export async function logout() {
  try { await api.post('/auth/logout/') } finally { setAccessToken(null) }
}
