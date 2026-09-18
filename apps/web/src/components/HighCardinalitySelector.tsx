import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { presentationLabel } from './presentation'
import './high-cardinality-selector.css'

export interface GovernedChoice {
  id: string
  label: string
  description?: string
  group?: string
  searchText?: string
}

const MAX_RESULTS = 12

export function HighCardinalitySelector({ label, choices, value, onChange, allChoice, disabled = false, recentIds = [], placeholder = 'Search organizations' }: {
  label: string
  choices: GovernedChoice[]
  value?: string
  onChange: (id: string) => void
  allChoice?: { label: string; description: string }
  disabled?: boolean
  recentIds?: string[]
  placeholder?: string
}) {
  const generatedId = useId()
  const inputId = `${generatedId}-input`
  const listId = `${generatedId}-list`
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const root = useRef<HTMLDivElement>(null)
  const selected = choices.find(choice => choice.id === value)
  const ordered = useMemo(() => {
    const recent = new Map(recentIds.map((id, index) => [id, index]))
    return [...choices].sort((left, right) => {
      const leftRecent = recent.get(left.id); const rightRecent = recent.get(right.id)
      if (leftRecent !== undefined || rightRecent !== undefined) return (leftRecent ?? Number.MAX_SAFE_INTEGER) - (rightRecent ?? Number.MAX_SAFE_INTEGER)
      return left.label.localeCompare(right.label) || left.id.localeCompare(right.id)
    })
  }, [choices, recentIds])
  const matches = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase()
    return ordered.filter(choice => !needle || `${choice.label} ${choice.description ?? ''} ${choice.searchText ?? ''}`.toLocaleLowerCase().includes(needle)).slice(0, MAX_RESULTS)
  }, [ordered, query])
  const options = allChoice ? [{ id: '', label: allChoice.label, description: allChoice.description, group: 'Scope' }, ...matches] : matches
  useEffect(() => {
    if (!open) return
    const close = (event: PointerEvent) => { if (!root.current?.contains(event.target as Node)) setOpen(false) }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [open])
  const choose = (id: string) => { onChange(id); setOpen(false); setQuery('') }
  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown') { event.preventDefault(); setOpen(true); setActive(index => Math.min(index + 1, Math.max(0, options.length - 1))) }
    else if (event.key === 'ArrowUp') { event.preventDefault(); setOpen(true); setActive(index => Math.max(0, index - 1)) }
    else if (event.key === 'Enter' && open && options[active]) { event.preventDefault(); choose(options[active].id) }
    else if (event.key === 'Escape') { event.preventDefault(); setOpen(false); setQuery('') }
  }
  const selectionLabel = value ? selected?.label ?? 'Selected organization unavailable' : allChoice?.label ?? 'Choose an organization'
  return <div className="governed-selector" ref={root}>
    <label htmlFor={inputId}>{label}</label>
    <div className="governed-selector-control">
      <input id={inputId} role="combobox" type="search" autoComplete="off" disabled={disabled} value={open ? query : selectionLabel} placeholder={placeholder} aria-expanded={open} aria-controls={listId} aria-autocomplete="list" aria-activedescendant={open && options[active] ? `${generatedId}-${active}` : undefined} onFocus={event => { setOpen(true); setQuery(''); setActive(0); event.currentTarget.select() }} onChange={event => { setOpen(true); setQuery(event.target.value); setActive(0) }} onKeyDown={onKeyDown} />
      <button type="button" disabled={disabled} aria-label={`Open ${label}`} aria-expanded={open} onClick={() => { setOpen(current => !current); setActive(0) }}>⌄</button>
    </div>
    <span className="governed-selector-announcement" role="status" aria-live="polite">{open ? `${matches.length}${ordered.length > matches.length ? ' shown' : ''} matching choices` : `${selectionLabel} selected`}</span>
    {open && <div id={listId} role="listbox" aria-label={`${label} choices`} className="governed-selector-list">
      {options.map((choice, index) => <button id={`${generatedId}-${index}`} key={choice.id || '__all__'} type="button" role="option" aria-selected={(value ?? '') === choice.id} className={active === index ? 'active' : ''} onPointerMove={() => setActive(index)} onClick={() => choose(choice.id)}>
        <span><strong>{choice.label}</strong>{choice.description && <small>{choice.description}</small>}</span>
        {choice.group && <small>{presentationLabel(choice.group)}</small>}
      </button>)}
      {!matches.length && <p role="status">No choices match this filter. Clear or change the search to inspect the governed account list.</p>}
      {matches.length > 0 && ordered.length > matches.length && <p className="governed-selector-more">Showing the first {MAX_RESULTS} matches. Keep typing to narrow the full set of {ordered.length} choices.</p>}
    </div>}
  </div>
}
