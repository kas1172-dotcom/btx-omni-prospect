import type { AccountPlanning, MapFilterOptions } from '../../types/api'
import { Button, FilterChip, LoadingStatus } from '../../components/UI'
import { toggleValue, type MapFilters, type MapMarker } from './mapModel'
import { relationshipOptions } from './mapPresentation'

export function MapFilterPanel({ filters, onChange, onReset, onClose, changed, markets, naics, filterOptions, fulfillment, planning, planningError, focal }: {
  filters: MapFilters
  onChange: (next: MapFilters) => void
  onReset: () => void
  onClose: () => void
  changed: boolean
  markets: string[]
  naics: string[]
  filterOptions: MapFilterOptions
  fulfillment: string[]
  planning?: AccountPlanning
  planningError: boolean
  focal?: MapMarker
}) {
  void naics; void filterOptions; void fulfillment
  return <>
    <fieldset><legend>Market</legend>{markets.map(value => <FilterChip key={value} selected={filters.industries.includes(value)} onClick={() => onChange({ ...filters, industries: toggleValue(filters.industries, value) })}>{value}</FilterChip>)}</fieldset>
    <fieldset><legend>Customer status</legend>{relationshipOptions.map(([value, label]) => <FilterChip key={value} selected={filters.relationships.includes(value)} onClick={() => onChange({ ...filters, relationships: toggleValue(filters.relationships, value) })}>{label}</FilterChip>)}</fieldset>
    <fieldset><legend>Top 100 membership</legend><FilterChip selected={filters.top100} onClick={() => onChange({ ...filters, top100: !filters.top100 })}>BTX Top 100 · SAMPLE membership</FilterChip></fieldset>
    <fieldset><legend>Strategic partnership</legend>{planningError && <p role="alert">Saved planning is temporarily unavailable. Existing results remain visible.</p>}{!planning && !planningError && <LoadingStatus>Opening saved planning filters…</LoadingStatus>}<FilterChip disabled={!planning} selected={(filters.strategicPartnership ?? 'ALL') === 'EXCLUDE'} onClick={() => onChange({ ...filters, strategicPartnership: filters.strategicPartnership === 'EXCLUDE' ? 'ALL' : 'EXCLUDE' })}>Exclude partnerships</FilterChip><FilterChip disabled={!planning} selected={filters.strategicPartnership === 'ONLY'} onClick={() => onChange({ ...filters, strategicPartnership: filters.strategicPartnership === 'ONLY' ? 'ALL' : 'ONLY' })}>Only partnerships</FilterChip></fieldset>
    {focal && <fieldset><legend>Straight-line proximity radius</legend><p>This is map radius only, not driving distance or score input.</p>{([30, 50, 100] as const).map(value => <FilterChip key={value} selected={filters.radiusMiles === value} onClick={() => onChange({ ...filters, radiusMiles: filters.radiusMiles === value ? undefined : value })}>{value} miles</FilterChip>)}</fieldset>}
    <div className="map-filter-actions"><Button onClick={onReset} disabled={!changed}>Reset filters</Button><Button variant="primary" onClick={onClose}>Apply to map</Button></div>
    <p className="map-filter-boundary">Filters change the visible planning set only. They do not alter deterministic scores, account classification, facility evidence or commercial ownership.</p>
  </>
}
