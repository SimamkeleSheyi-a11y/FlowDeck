import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './components/AppShell'
import { ProtectedRoute } from './components/ProtectedRoute'
import { BoardPage } from './pages/BoardPage'
import { DashboardPage } from './pages/DashboardPage'
import { ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage, VerifyEmailPage } from './pages/AuthPages'
import { SettingsPage } from './pages/SettingsPage'
import { WorkspacePage } from './pages/WorkspacePage'
import { WorkspacesPage } from './pages/WorkspacesPage'

function Private({ children }: { children: ReactNode }) { return <ProtectedRoute><AppShell>{children}</AppShell></ProtectedRoute> }
export default function App(){return <Routes><Route path="/login" element={<LoginPage/>}/><Route path="/register" element={<RegisterPage/>}/><Route path="/verify-email" element={<VerifyEmailPage/>}/><Route path="/forgot-password" element={<ForgotPasswordPage/>}/><Route path="/reset-password" element={<ResetPasswordPage/>}/><Route path="/" element={<Private><DashboardPage/></Private>}/><Route path="/workspaces" element={<Private><WorkspacesPage/></Private>}/><Route path="/workspaces/:id" element={<Private><WorkspacePage/></Private>}/><Route path="/projects/:projectId/board" element={<Private><BoardPage/></Private>}/><Route path="/settings" element={<Private><SettingsPage/></Private>}/><Route path="*" element={<Navigate to="/" replace/>}/></Routes>}
