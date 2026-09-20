import { useId, useState, type ReactNode } from 'react'
import { Button, FilterChip } from './UI'
import './filter-bar.css'

export interface AppliedFilter { key: string; label: string; remove: () => void }
export function AppliedFilterChips({ filters, onClear, count }: { filters: AppliedFilter[]; onClear: () => void; count: number }) {
  return <div className="applied-filter-chips" aria-label="Applied filters">
    {filters.map(filter => <FilterChip key={filter.key} selected onClear={filter.remove}>{filter.label}</FilterChip>)}
    <Button variant="ghost" onClick={onClear} disabled={!filters.length}>Clear all</Button>
    <span role="status">{count} results</span>
  </div>
}

export function FilterBar({ search, children, sort, filters, onClear, count, label = 'Filter controls' }: {
  search: ReactNode; children: ReactNode; sort?: ReactNode; filters: AppliedFilter[]; onClear: () => void; count: number; label?: string
}) {
  const [expanded, setExpanded] = useState(false)
  const id = useId()
  return <section className="shared-filters" aria-label={label}>
    <div className="shared-filter-bar">
      <div className="filter-search">{search}</div>
      <Button className="filter-mobile-trigger" aria-controls={id} aria-expanded={expanded} onClick={() => setExpanded(value => !value)}>Filters <span aria-label={`${filters.length} active filters`}>{filters.length}</span></Button>
      <div id={id} className={`filter-facets ${expanded ? 'expanded' : ''}`}>{children}{sort && <div className="filter-sort">{sort}</div>}</div>
    </div>
    <AppliedFilterChips filters={filters} onClear={onClear} count={count} />
  </section>
}
