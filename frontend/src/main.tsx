import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './context/AuthContext'
import { ToastProvider } from './context/ToastContext'
import './styles.css'

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 15_000, refetchOnWindowFocus: false, retry: 1 } } })
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><BrowserRouter><QueryClientProvider client={queryClient}><ToastProvider><AuthProvider><App/></AuthProvider></ToastProvider></QueryClientProvider></BrowserRouter></React.StrictMode>)
