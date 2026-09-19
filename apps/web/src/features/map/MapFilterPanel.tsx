import type { AccountPlanning, MapFilterOptions } from '../../types/api'
import { HighCardinalitySelector, type GovernedChoice } from '../../components/HighCardinalitySelector'
import { Button, FilterChip, LoadingStatus, SearchInput } from '../../components/UI'
import { FULFILLMENT_LABELS, toggleValue, type MapFilters, type MapMarker } from './mapModel'
import { layerOptions, relationshipOptions } from './mapPresentation'

const selectedChoices = (ids: string[] | undefined, choices: GovernedChoice[]) => (ids ?? []).map(id => choices.find(choice => choice.id === id) ?? { id, label: 'Selected saved value' })

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
  const naicsChoices = naics.map(code => ({ id: code, label: `NAICS ${code}`, description: 'Account classification', searchText: code }))
  const businessUnitChoices = filterOptions.business_units.map(unit => ({ id: unit.id, label: unit.name, description: 'BTX business unit', searchText: unit.id }))
  const capabilityChoices = filterOptions.capabilities.map(([id, name]) => ({ id, label: name, description: 'Candidate BTX capability', searchText: id }))
  const add = (key: 'naicsCodes' | 'businessUnitIds' | 'capabilityIds', value: string) => value && onChange({ ...filters, [key]: toggleValue(filters[key] ?? [], value) })
  return <>
    <fieldset><legend>Search</legend><SearchInput label="Search organizations and sites" value={filters.query} onChange={event => onChange({ ...filters, query: event.target.value })} placeholder="Organization, site, city or market" /></fieldset>
    <fieldset><legend>Customer, Prospect or review state</legend>{relationshipOptions.map(([value, label]) => <FilterChip key={value} selected={filters.relationships.includes(value)} onClick={() => onChange({ ...filters, relationships: toggleValue(filters.relationships, value) })}>{label}</FilterChip>)}</fieldset>
    <fieldset><legend>Industry and market</legend>{markets.map(value => <FilterChip key={value} selected={filters.industries.includes(value)} onClick={() => onChange({ ...filters, industries: toggleValue(filters.industries, value) })}>{value}</FilterChip>)}</fieldset>
    <fieldset><legend>NAICS</legend><p>Account classification only; not a verified site registration.</p><HighCardinalitySelector label="Add NAICS classification" choices={naicsChoices.filter(choice => !filters.naicsCodes?.includes(choice.id))} onChange={value => add('naicsCodes', value)} placeholder="Search NAICS codes" />{selectedChoices(filters.naicsCodes, naicsChoices).map(choice => <FilterChip key={choice.id} selected onClear={() => onChange({ ...filters, naicsCodes: filters.naicsCodes?.filter(id => id !== choice.id) })}>{choice.label}</FilterChip>)}</fieldset>
    <fieldset><legend>BTX business unit</legend><p>Account-level commercial context; not site qualification or available capacity.</p><HighCardinalitySelector label="Add business unit" choices={businessUnitChoices.filter(choice => !filters.businessUnitIds?.includes(choice.id))} onChange={value => add('businessUnitIds', value)} placeholder="Search business units" />{selectedChoices(filters.businessUnitIds, businessUnitChoices).map(choice => <FilterChip key={choice.id} selected onClear={() => onChange({ ...filters, businessUnitIds: filters.businessUnitIds?.filter(id => id !== choice.id) })}>{choice.label}</FilterChip>)}</fieldset>
    <fieldset><legend>Capability</legend><p>Candidate BTX alignment from account-level context; not facility qualification.</p><HighCardinalitySelector label="Add capability" choices={capabilityChoices.filter(choice => !filters.capabilityIds?.includes(choice.id))} onChange={value => add('capabilityIds', value)} placeholder="Search BTX capabilities" />{selectedChoices(filters.capabilityIds, capabilityChoices).map(choice => <FilterChip key={choice.id} selected onClear={() => onChange({ ...filters, capabilityIds: filters.capabilityIds?.filter(id => id !== choice.id) })}>{choice.label}</FilterChip>)}</fieldset>
    <fieldset><legend>Decision or fulfillment state</legend><p>Recorded account-level obligations, not site capacity.</p>{fulfillment.map(value => <FilterChip key={value} selected={Boolean(filters.fulfillmentStates?.includes(value))} onClick={() => onChange({ ...filters, fulfillmentStates: toggleValue(filters.fulfillmentStates ?? [], value) })}>{FULFILLMENT_LABELS[value] ?? 'Recorded fulfillment state'}</FilterChip>)}</fieldset>
    <fieldset><legend>Intelligence timing</legend><FilterChip selected={filters.signalTiming.includes('CURRENT')} onClick={() => onChange({ ...filters, signalTiming: toggleValue(filters.signalTiming, 'CURRENT') })}>Current intelligence</FilterChip><FilterChip selected={filters.signalTiming.includes('UPCOMING')} onClick={() => onChange({ ...filters, signalTiming: toggleValue(filters.signalTiming, 'UPCOMING') })}>Upcoming intelligence</FilterChip></fieldset>
    <fieldset><legend>Strategic Partnership and shortlist</legend>{planningError && <p role="alert">Saved planning is temporarily unavailable. Existing results remain visible.</p>}{!planning && !planningError && <LoadingStatus>Opening saved planning filters…</LoadingStatus>}<FilterChip disabled={!planning} selected={(filters.strategicPartnership ?? 'ALL') === 'EXCLUDE'} onClick={() => onChange({ ...filters, strategicPartnership: filters.strategicPartnership === 'EXCLUDE' ? 'ALL' : 'EXCLUDE' })}>Exclude partnerships</FilterChip><FilterChip disabled={!planning} selected={filters.strategicPartnership === 'ONLY'} onClick={() => onChange({ ...filters, strategicPartnership: filters.strategicPartnership === 'ONLY' ? 'ALL' : 'ONLY' })}>Only partnerships</FilterChip><FilterChip disabled={!planning} selected={Boolean(filters.shortlistOnly)} onClick={() => onChange({ ...filters, shortlistOnly: !filters.shortlistOnly })}>My shortlist</FilterChip></fieldset>
    {focal && <fieldset><legend>Straight-line proximity radius</legend><p>This is map radius only, not driving distance or score input.</p>{([30, 50, 100] as const).map(value => <FilterChip key={value} selected={filters.radiusMiles === value} onClick={() => onChange({ ...filters, radiusMiles: filters.radiusMiles === value ? undefined : value })}>{value} miles</FilterChip>)}</fieldset>}
    <fieldset><legend>Visible map layers</legend>{layerOptions.map(([value, label]) => <FilterChip key={value} selected={filters.layers.includes(value)} onClick={() => onChange({ ...filters, layers: toggleValue(filters.layers, value) })}>{label}</FilterChip>)}</fieldset>
    <div className="map-filter-actions"><Button onClick={onReset} disabled={!changed}>Reset filters</Button><Button variant="primary" onClick={onClose}>Apply to map</Button></div>
    <p className="map-filter-boundary">Filters change the visible planning set only. They do not alter deterministic scores, account classification, facility evidence or commercial ownership.</p>
  </>
}
