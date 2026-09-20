import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { Drawer } from '../../components/UI'
import chevron from './assets/chevron.svg'

export function OpportunityMenu({ label, value, children }: { label: string; value?: string; children: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [mobile, setMobile] = useState(() => window.matchMedia('(max-width: 700px)').matches)
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const id = useId()
  useEffect(() => {
    const query = window.matchMedia('(max-width: 700px)')
    const change = () => setMobile(query.matches)
    query.addEventListener('change', change)
    return () => query.removeEventListener('change', change)
  }, [])
  useEffect(() => {
    if (!open || mobile) return
    root.current?.querySelector<HTMLElement>('.opp-popover button, .opp-popover input')?.focus()
    const outside = (e: PointerEvent) => { if (!root.current?.contains(e.target as Node)) setOpen(false) }
    const escape = (e: KeyboardEvent) => { if (e.key === 'Escape') { setOpen(false); trigger.current?.focus() } }
    document.addEventListener('pointerdown', outside); document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', escape) }
  }, [open, mobile])
  const content = <><h3 id={id}>{label}</h3>{children}</>
  return <div className="opp-menu" ref={root}><button ref={trigger} className="opp-menu-trigger" aria-expanded={open} aria-controls={`${id}-content`} onClick={() => setOpen(!open)}>{label}{value && <strong>{value}</strong>}<img src={chevron} alt="" /></button>{open && (mobile ? <Drawer open titleId={id} onClose={() => setOpen(false)} className="opp-menu-sheet"><div className="opp-sheet-handle" /><div id={`${id}-content`} className="opp-menu-content">{content}<button className="opp-primary" onClick={() => setOpen(false)}>Done</button></div></Drawer> : <div id={`${id}-content`} className="opp-popover opp-menu-content" onBlur={e => { if (!root.current?.contains(e.relatedTarget)) setOpen(false) }}>{content}</div>)}</div>
}
export function MenuChoice({ selected, children, onClick }: { selected: boolean; children: ReactNode; onClick: () => void }) {
  return <button className={`opp-menu-choice ${selected ? 'selected' : ''}`} aria-pressed={selected} onClick={onClick}><span aria-hidden="true">{selected ? '●' : '○'}</span>{children}</button>
}
