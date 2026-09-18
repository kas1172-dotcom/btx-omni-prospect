import { Button } from './UI'
import { clampPage } from './worklistModel'

export function WorklistPagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (page: number) => void }) {
  const current = clampPage(page, total, pageSize)
  const pages = Math.max(1, Math.ceil(total / pageSize))
  if (total <= pageSize) return null
  return <nav className="worklist-pagination" aria-label="Worklist pages"><Button disabled={current === 1} onClick={() => onPage(current - 1)}>Previous</Button><span>Page {current} of {pages}</span><Button disabled={current === pages} onClick={() => onPage(current + 1)}>Next</Button></nav>
}
