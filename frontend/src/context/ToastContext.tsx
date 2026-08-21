import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'

type Tone = 'success' | 'error' | 'info'
interface ToastAction { label: string; onClick: () => void | Promise<void> }
interface Toast { id: number; message: string; tone: Tone; action?: ToastAction }
type ShowToast = (message: string, tone?: Tone, action?: ToastAction, duration?: number) => void
const ToastContext = createContext<ShowToast>(() => undefined)
let nextId = 1
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const dismiss = useCallback((id:number) => setToasts(prev=>prev.filter(t=>t.id!==id)), [])
  const show = useCallback<ShowToast>((message, tone = 'info', action, duration = action ? 5000 : 3500) => {
    const id = nextId++
    setToasts((prev) => [...prev, { id, message, tone, action }])
    window.setTimeout(() => dismiss(id), duration)
  }, [dismiss])
  return <ToastContext.Provider value={show}>{children}<div className="toast-stack" aria-live="polite">{toasts.map(t => <div key={t.id} className={`toast ${t.tone}`}><span>{t.message}</span>{t.action&&<button onClick={()=>{void t.action?.onClick();dismiss(t.id)}}>{t.action.label}</button>}</div>)}</div></ToastContext.Provider>
}
export function useToast() { return useContext(ToastContext) }
