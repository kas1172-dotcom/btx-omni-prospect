import type { ReactNode } from 'react'

export function Panel({ title, children, action }: { title?: string; children: ReactNode; action?: ReactNode }) {
  return <section className="panel">{title && <header className="panel-head"><h2>{title}</h2>{action}</header>}{children}</section>
}
export function State({ value }: { value: string }) { return <span className={`state state-${value.toLowerCase()}`}>{value.replaceAll('_', ' ')}</span> }
export function Empty({ children }: { children: ReactNode }) { return <p className="empty">{children}</p> }
