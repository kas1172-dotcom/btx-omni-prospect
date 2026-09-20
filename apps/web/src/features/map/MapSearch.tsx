import { useId, useMemo, useState, type KeyboardEvent } from 'react'
import { SearchInput } from '../../components/UI'
import type { MapMarker } from './mapModel'

const markerType = (marker: MapMarker) => marker.kind === 'btx-facility' ? 'BTX site' : marker.kind === 'public-facility' ? 'Public site' : marker.kind.includes('intelligence') ? 'Intelligence' : marker.kind === 'prospect' ? 'Prospect site' : 'Customer site'

export function MapSearch({ markers, onSelect }: { markers: MapMarker[]; onSelect: (marker: MapMarker) => void }) {
  const listId = useId()
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const normalized = query.trim().toLocaleLowerCase()
  const results = useMemo(() => normalized ? markers
    .filter(marker => `${marker.organizationName ?? ''} ${marker.siteName ?? ''} ${marker.label} ${marker.address ?? ''}`.toLocaleLowerCase().includes(normalized))
    .sort((a, b) => Number(b.kind === 'btx-facility') - Number(a.kind === 'btx-facility') || a.label.localeCompare(b.label))
    .slice(0, 12) : [], [markers, normalized])
  const choose = (marker: MapMarker) => { onSelect(marker); setQuery(marker.label); setActive(0) }
  const keyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'ArrowDown' && results.length) { event.preventDefault(); setActive(value => (value + 1) % results.length) }
    else if (event.key === 'ArrowUp' && results.length) { event.preventDefault(); setActive(value => (value - 1 + results.length) % results.length) }
    else if (event.key === 'Enter' && results[active]) { event.preventDefault(); choose(results[active]) }
    else if (event.key === 'Escape') { event.preventDefault(); setQuery(''); setActive(0) }
  }
  return <div className="map-search">
    <SearchInput label="Search the tactical map" value={query} onChange={event => { setQuery(event.target.value); setActive(0) }} onKeyDown={keyDown} placeholder="BTX site, organization, city or region" role="combobox" aria-expanded={Boolean(normalized)} aria-controls={listId} aria-activedescendant={results[active] ? `${listId}-${active}` : undefined} autoComplete="off" />
    {normalized && <div className="map-search-results" id={listId} role="listbox" aria-label="Map search results">
      {results.map((marker, index) => <button id={`${listId}-${index}`} key={marker.id} type="button" role="option" aria-selected={index === active} onMouseEnter={() => setActive(index)} onClick={() => choose(marker)}><strong>{marker.label}</strong><span>{markerType(marker)}{marker.address ? ` · ${marker.address}` : ''}</span></button>)}
      {!results.length && <p role="status">No BTX site, organization, city or region matches this search.</p>}
    </div>}
  </div>
}
