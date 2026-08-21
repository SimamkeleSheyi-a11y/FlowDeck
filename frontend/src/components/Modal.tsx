import { X } from 'lucide-react'
import { useEffect, type ReactNode } from 'react'
export function Modal({ title, children, onClose, wide = false }: { title: string; children: ReactNode; onClose: () => void; wide?: boolean }) {
  useEffect(() => { const key=(event:KeyboardEvent)=>{ if(event.key==='Escape') onClose() }; window.addEventListener('keydown',key); return()=>window.removeEventListener('keydown',key) }, [onClose])
  return <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
    <section className={`modal ${wide ? 'modal-wide' : ''}`} role="dialog" aria-modal="true">
      <header><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Close"><X size={18}/></button></header>
      {children}
    </section>
  </div>
}
