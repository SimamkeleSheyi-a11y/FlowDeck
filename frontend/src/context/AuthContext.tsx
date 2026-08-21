import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { login as apiLogin, logout as apiLogout, restoreSession } from '../api/client'
import type { User } from '../api/types'

interface AuthValue {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  setUser: (user: User | null) => void
  refreshUser: () => Promise<void>
}
const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => { restoreSession().then(setUser).finally(() => setLoading(false)) }, [])
  const value = useMemo<AuthValue>(() => ({
    user, loading, setUser,
    login: async (email, password) => setUser(await apiLogin(email, password)),
    logout: async () => { await apiLogout(); setUser(null) },
    refreshUser: async () => { setUser(await restoreSession()) },
  }), [user, loading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error('useAuth must be inside AuthProvider'); return value }
