import { useEffect, useId, useState, type ReactNode } from 'react'
import { Drawer } from './UI'

function useNarrowEvidenceLayout() {
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 760px)').matches)
  useEffect(() => {
    const query = window.matchMedia('(max-width: 760px)')
    const update = () => setNarrow(query.matches)
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])
  return narrow
}

export function SupportingEvidence({ count, investigationKey, children }: { count: number; investigationKey: string; children: ReactNode }) {
  const [state, setState] = useState<{ key: string; open: boolean }>({ key: investigationKey, open: false })
  const open = state.key === investigationKey && state.open
  const narrow = useNarrowEvidenceLayout()
  const titleId = useId()
  const toggle = () => setState({ key: investigationKey, open: !open })
  const label = `${open ? 'Hide' : 'View'} supporting evidence (${count})`
  return <div className="supporting-evidence">
    <button type="button" className="supporting-evidence-trigger" aria-expanded={open} onClick={toggle}>{label}<span aria-hidden="true">{open ? '⌃' : '⌄'}</span></button>
    {narrow ? <Drawer open={open} onClose={() => setState({ key: investigationKey, open: false })} titleId={titleId} className="supporting-evidence-drawer"><header><h2 id={titleId}>Supporting evidence</h2><button type="button" onClick={() => setState({ key: investigationKey, open: false })} aria-label="Close supporting evidence">×</button></header><div className="supporting-evidence-body">{children}</div></Drawer> : open ? <div className="supporting-evidence-body">{children}</div> : null}
  </div>
}

export function WhyThis({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false)
  return <span className="why-this"><button type="button" aria-expanded={open} onClick={() => setOpen(value => !value)}>Why this?</button>{open && <span className="why-this-detail">{children}</span>}</span>
}
