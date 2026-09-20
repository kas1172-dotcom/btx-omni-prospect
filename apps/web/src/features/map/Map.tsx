import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { BtxMapFacility, MapFilterOptions, MapIntelligence, MapRecord, OmniAssessmentSelection, OmniContext, PublicLocation } from '../../types/api'
import { Button, Drawer, Empty, FilterChip, FilterTrigger, StatusBadge } from '../../components/UI'
import { MapCanvas, type MapCameraRequest } from './MapCanvas'
import { MapAccountDetails } from './MapAccountDetails'
import { SignalBriefCard } from '../../components/SignalBriefCard'
import { DEFAULT_MAP_LAYERS, buildMapMarkers, filterMapRecords, filterMarkersByRadius, haversineMiles, type MapFilters, type MapMarker } from './mapModel'
import type { PendingMapAccount } from '../../types/api'
import type { MapViewSnapshot } from './mapModel'
import { ItineraryPlanner, type ItineraryPlannerHandle } from './ItineraryPlanner'
import { api } from '../../api/client'
import type { AccountPlanning } from '../../types/api'
import { MapFilterPanel } from './MapFilterPanel'
import { layerOptions, relationshipOptions } from './mapPresentation'
import { MapSearch } from './MapSearch'
import { synchronizedMapSites } from './mapListModel'

const layerMarkerKind = { customers: 'customer', prospects: 'prospect', 'public-facilities': 'public-facility', 'btx-facilities': 'btx-facility', intelligence: 'intelligence' }
const defaults: MapFilters = { query: '', coverage: 'ALL', top100: false, industries: [], relationships: [], layers: DEFAULT_MAP_LAYERS, signalTiming: ['CURRENT', 'UPCOMING'], strategicPartnership: 'ALL', shortlistOnly: false }
const markerKindLabel: Record<string, string> = { customer: 'Customer site', prospect: 'Prospect site', 'public-facility': 'Verified public facility', 'btx-facility': 'BTX facility', intelligence: 'Current public intelligence', 'upcoming-intelligence': 'Upcoming public intelligence' }
const filtersActive = (value: MapFilters) => value.top100 || value.industries.length > 0 || value.relationships.length > 0 || (value.strategicPartnership ?? 'ALL') !== 'ALL' || Boolean(value.radiusMiles)

export function Map({ records, pendingAccounts = [], initialSnapshot, initialAccountId, initialFacilityId, onSnapshot, publicLocations, btxFacilities, layers, filterOptions, signals, onAccount, onRelationships, onMapAccountSelect, onMapFacilitySelect, onMapEventSelect, onOmniContext }: { records: MapRecord[]; pendingAccounts?: PendingMapAccount[]; initialSnapshot?: MapViewSnapshot; initialAccountId?: string; initialFacilityId?: string; onSnapshot?: (snapshot: MapViewSnapshot, mode?: 'push' | 'replace') => void; publicLocations: PublicLocation[]; btxFacilities: BtxMapFacility[]; layers: string[]; filterOptions: MapFilterOptions; signals: MapIntelligence[]; onAccount: (id: string, assessment?: OmniAssessmentSelection) => void; onRelationships: (id: string) => void; onMapAccountSelect: (id?: string) => void; onMapFacilitySelect: (facilityId?: string, accountId?: string) => void; onMapEventSelect?: (id?: string) => void; onOmniContext?: (context: Pick<OmniContext, 'active_filters' | 'visible_record_ids' | 'selected_event_id' | 'selected_assessment'>) => void }) {
  const initialFilters = initialSnapshot?.filters ?? defaults
  const [filters, setFilters] = useState<MapFilters>(() => initialFilters); const [draftFilters, setDraftFilters] = useState<MapFilters>(() => initialFilters); const [selectedSnapshot, setSelected] = useState<MapMarker | undefined>(() => initialSnapshot?.selected); const [controlsOpen, setControlsOpen] = useState(false); const [renderedMarkers, setRenderedMarkers] = useState<MapMarker[]>([])
  const snapshotMode = useRef<'push' | 'replace'>('replace')
  const [planning, setPlanning] = useState<AccountPlanning>()
  const [planningError, setPlanningError] = useState(false)
  const [planningMessage, setPlanningMessage] = useState('')
  const [selectionFrame, setSelectionFrame] = useState<MapCameraRequest>()
  const itinerary = useRef<ItineraryPlannerHandle>(null)
  const rowRefs = useRef(new globalThis.Map<string, HTMLTableRowElement>())
  useEffect(() => {
    const restore = (event: Event) => {
      const snapshot = (event as CustomEvent<MapViewSnapshot | undefined>).detail
      if (!snapshot) return
      setFilters(snapshot.filters)
      setDraftFilters(snapshot.filters)
      setSelected(snapshot.selected)
    }
    window.addEventListener('btx:map-restore', restore)
    return () => window.removeEventListener('btx:map-restore', restore)
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    void api.accountPlanning(controller.signal).then(value => { if (!controller.signal.aborted) { setPlanning(value); setPlanningError(false) } }).catch(() => { if (!controller.signal.aborted) setPlanningError(true) })
    return () => controller.abort()
  }, [])
  const partnershipIds = useMemo(() => new Set(planning?.strategic_partnerships.map(item => item.account_id) ?? []), [planning])
  const shortlistIds = useMemo(() => new Set(planning?.shortlist.map(item => item.account_id) ?? []), [planning])
  const planningFilter = useCallback(<T extends { account_id: string },>(items: T[]) => items.filter(item =>
    ((filters.strategicPartnership ?? 'ALL') === 'ALL' || ((filters.strategicPartnership === 'ONLY') === partnershipIds.has(item.account_id)))
    && (!filters.shortlistOnly || shortlistIds.has(item.account_id))), [filters.shortlistOnly, filters.strategicPartnership, partnershipIds, shortlistIds])
  const visible = useMemo(() => planningFilter(filterMapRecords(records, filters)), [records, filters, planningFilter]); const ids = useMemo(() => new Set(visible.map(record => record.account_id)), [visible])
  const naicsOptions = useMemo(() => [...new Set([...records, ...pendingAccounts].flatMap(record => record.naics_assignments?.map(item => item.code) ?? []))].sort(), [records, pendingAccounts])
  const fulfillmentOptions = useMemo(() => [...new Set([...records, ...pendingAccounts].flatMap(record => record.fulfillment_attention?.states ?? []))].sort(), [records, pendingAccounts])
  const pending = useMemo(() => planningFilter(filterMapRecords(pendingAccounts, filters)).filter(account => filters.layers.includes(account.account_segment === 'PROSPECT' ? 'prospects' : 'customers')), [pendingAccounts, filters, planningFilter])
  const facilities = useMemo(() => publicLocations.filter(location => ids.has(location.account_id)), [publicLocations, ids]); const intelligence = useMemo(() => signals.filter(signal => (!signal.account_id || ids.has(signal.account_id)) && filters.signalTiming.includes(signal.marker_mode === 'UPCOMING' ? 'UPCOMING' : 'CURRENT')), [filters.signalTiming, signals, ids])
  const allMarkers = useMemo(() => buildMapMarkers(visible, facilities, btxFacilities, intelligence, filters.layers), [visible, facilities, btxFacilities, intelligence, filters.layers])
  const restoredSelection = !selectedSnapshot && (initialAccountId || initialFacilityId) ? allMarkers.find(marker => (initialFacilityId && marker.facilityId === initialFacilityId) || (initialAccountId && marker.accountId === initialAccountId)) : undefined
  const selected = allMarkers.find(marker => marker.id === (selectedSnapshot ?? restoredSelection)?.id)
  useEffect(() => { onSnapshot?.({ filters, selected }, snapshotMode.current); snapshotMode.current = 'replace' }, [filters, selected, onSnapshot])
  useEffect(() => { onMapEventSelect?.(selected?.eventId); onMapFacilitySelect(selected?.facilityId, selected?.accountId) }, [selected, onMapEventSelect, onMapFacilitySelect])
  const focal = selected && selected.kind !== 'cluster' ? selected : undefined
  const markers = useMemo(() => filterMarkersByRadius(allMarkers, focal, filters.radiusMiles), [allMarkers, focal, filters.radiusMiles])
  const sitesInView = useMemo(() => synchronizedMapSites(markers), [markers])
  const selectedRecord = selected ? records.find(record => record.id === selected.id) ?? (selected.accountId ? records.find(record => record.account_id === selected.accountId && record.facility_id === selected.facilityId) : undefined) : undefined
  const selectedFacility = selected?.facilityId ? [...publicLocations, ...btxFacilities].find(facility => facility.facility_id === selected.facilityId) : undefined
  const selectedSignal = selected?.eventId ? signals.find(signal => signal.event_id === selected.eventId) : undefined
  const accountName = useCallback((id: string) => records.find(record => record.account_id === id)?.name ?? 'Open Customer', [records])
  const selectMarker = useCallback((marker: MapMarker) => { setSelected(marker); setSelectionFrame({ key: `selection:${marker.id}:${Date.now()}`, points: [marker] }); onMapEventSelect?.(marker.eventId); if (marker.facilityId) onMapFacilitySelect(marker.facilityId, marker.accountId); else if (marker.accountId) onMapAccountSelect(marker.accountId) }, [onMapAccountSelect, onMapEventSelect, onMapFacilitySelect])
  useEffect(() => { if (selected?.id) rowRefs.current.get(selected.id)?.scrollIntoView({ block: 'nearest' }) }, [selected?.id])
  const clearSelection = () => { setSelected(undefined); onMapEventSelect?.(); onMapFacilitySelect() }
  const updateFilters = (next: MapFilters, mode: 'push' | 'replace' = 'push') => {
    snapshotMode.current = mode
    setFilters(next)
    if (next.radiusMiles !== filters.radiusMiles && focal && next.radiusMiles) setSelectionFrame({ key: `radius:${focal.id}:${next.radiusMiles}:${Date.now()}`, origin: focal, radiusMiles: next.radiusMiles })
    if (!selectedSnapshot) return
    const record = selectedSnapshot.accountId ? records.find(item => item.id === selectedSnapshot.id || (item.account_id === selectedSnapshot.accountId && item.facility_id === selectedSnapshot.facilityId)) : undefined
    const planningAllows = !selectedSnapshot.accountId || (((next.strategicPartnership ?? 'ALL') === 'ALL' || ((next.strategicPartnership === 'ONLY') === partnershipIds.has(selectedSnapshot.accountId))) && (!next.shortlistOnly || shortlistIds.has(selectedSnapshot.accountId)))
    const recordAllows = !record || filterMapRecords([record], next).length > 0
    const layerAllows = selectedSnapshot.kind === 'btx-facility' ? next.layers.includes('btx-facilities') : selectedSnapshot.kind === 'public-facility' ? next.layers.includes('public-facilities') : selectedSnapshot.kind.includes('intelligence') ? next.layers.includes('intelligence') : next.layers.includes(selectedSnapshot.kind === 'prospect' ? 'prospects' : 'customers')
    if (!planningAllows || !recordAllows || !layerAllows) { setSelected(undefined); onMapEventSelect?.(); onMapFacilitySelect() }
  }
  const clearFilters = () => updateFilters(defaults); const changed = filtersActive(filters); const draftChanged = filtersActive(draftFilters)
  const title = selectedRecord?.name ?? selectedFacility?.name ?? selectedSignal?.title ?? selected?.label
  useEffect(() => { onOmniContext?.({ active_filters: { search: filters.query, coverage: filters.coverage, layers: filters.layers.join(','), markets: filters.industries.join(','), signal_timing: filters.signalTiming.join(','), strategic_partnership: filters.strategicPartnership ?? 'ALL', saved_shortlist: filters.shortlistOnly ? 'true' : '', radius_miles: filters.radiusMiles?.toString() ?? '', naics_codes: filters.naicsCodes?.join(',') ?? '', commercial_business_unit_ids: filters.businessUnitIds?.join(',') ?? '', capability_ids: filters.capabilityIds?.join(',') ?? '', fulfillment_states: filters.fulfillmentStates?.join(',') ?? '' }, visible_record_ids: renderedMarkers.filter(marker => marker.kind !== 'cluster').slice(0, 50).map(marker => marker.eventId ?? marker.accountId ?? marker.facilityId ?? marker.id), selected_event_id: selected?.eventId, selected_assessment: selectedSignal?.assessment_id && selectedSignal.assessment_version && selectedSignal.account_id ? { assessment_id: selectedSignal.assessment_id, assessment_version: selectedSignal.assessment_version, event_id: selectedSignal.event_id, account_id: selectedSignal.account_id } : undefined }) }, [filters, onOmniContext, renderedMarkers, selected?.eventId, selectedSignal])
  const selectedShortlist = selected?.accountId ? planning?.shortlist_records.find(item => item.account_id === selected.accountId) : undefined
  const setShortlist = async () => {
    if (!selected?.accountId) return
    setPlanningMessage('Saving shortlist…')
    try {
      const item = await api.saveShortlist({ account_id: selected.accountId, kind: 'RESEARCH', objective: 'Review this map-selected organization and its verified site context.', target_date: null, active: !selectedShortlist?.active, expected_version: selectedShortlist?.version ?? null, idempotency_key: crypto.randomUUID() })
      setPlanning(current => current ? { ...current, shortlist_records: [...current.shortlist_records.filter(value => value.account_id !== item.account_id), item], shortlist: item.active === false ? current.shortlist.filter(value => value.account_id !== item.account_id) : [...current.shortlist.filter(value => value.account_id !== item.account_id), item] } : current)
      setPlanningMessage(item.active === false ? 'Removed from your shortlist.' : 'Added to your shortlist.')
    } catch { setPlanningMessage('Shortlist could not be updated. Retry without leaving this site.') }
  }
  return <div className="surface map-workspace">
    <div className="page-title map-title"><span className="eyebrow">National commercial geography</span><h1>Tactical Map</h1><p>Explore organizations, facilities and public-intelligence geography. Nearby locations do not establish manufacturing fit or make an opportunity more attractive.</p></div>
    <MapSearch markers={allMarkers} onSelect={selectMarker} />
    <div className="map-compose">
    <section className="map-stage" aria-label="Tactical Map V2 workspace">
      <MapCanvas markers={markers} selectedMarkerId={selected?.id} cameraRequest={selectionFrame} onSelect={selectMarker} onVisibleMarkers={setRenderedMarkers} />
      <div className="map-toolbar"><FilterTrigger active={changed} aria-expanded={controlsOpen} onClick={() => { setDraftFilters(filters); setControlsOpen(true) }}>Filters</FilterTrigger><Button variant="ghost" onClick={() => setSelectionFrame({ key: `reset:${Date.now()}`, reset: true })}>Reset view</Button><Button onClick={() => itinerary.current?.open()}>Itinerary</Button><span>{sitesInView.length} sites in view</span></div>
      <div className="map-active-filters" aria-label="Active map filters">{filters.top100 && <FilterChip selected onClear={() => updateFilters({ ...filters, top100: false })}>BTX Top 100 · SAMPLE</FilterChip>}{filters.strategicPartnership === 'ONLY' && <FilterChip selected onClear={() => updateFilters({ ...filters, strategicPartnership: 'ALL' })}>Only partnerships</FilterChip>}{filters.strategicPartnership === 'EXCLUDE' && <FilterChip selected onClear={() => updateFilters({ ...filters, strategicPartnership: 'ALL' })}>Exclude partnerships</FilterChip>}{filters.radiusMiles && <FilterChip selected aria-label={`Remove ${filters.radiusMiles}-mile straight-line radius filter`} onClear={() => updateFilters({ ...filters, radiusMiles: undefined })}>{filters.radiusMiles}-mile straight-line radius</FilterChip>}{filters.industries.map(value => <FilterChip key={value} selected onClear={() => updateFilters({ ...filters, industries: filters.industries.filter(item => item !== value) })}>{value}</FilterChip>)}{filters.relationships.map(value => <FilterChip key={value} selected onClear={() => updateFilters({ ...filters, relationships: filters.relationships.filter(item => item !== value) })}>{relationshipOptions.find(([id]) => id === value)?.[1] ?? 'Customer status'}</FilterChip>)}</div>
      {!markers.length && <div className="map-no-results"><Empty>No verified markers match the selected filters.</Empty><Button onClick={clearFilters}>Clear filters</Button></div>}
      <div className="map-legend" aria-label="Map legend">{layerOptions.filter(([id]) => filters.layers.includes(id)).map(([id, label]) => <span key={id}><i className={`map-legend-marker map-marker-${layerMarkerKind[id]}`} />{label}</span>)}</div>
      {selected && <aside className="map-selection" aria-label="Selected map location"><div className="map-selection-content"><button className="map-selection-close" aria-label="Close selected map location" onClick={clearSelection}>×</button><span className="eyebrow">{markerKindLabel[selected.kind] ?? 'Selected map location'}</span><h2>{title}</h2>{selectedSignal ? <><StatusBadge value={selectedSignal.marker_mode === 'UPCOMING' ? 'Upcoming source-supported event' : 'Current collected intelligence'} kind="evidence" /><SignalBriefCard brief={selectedSignal} accountName={accountName} onAccount={onAccount} onUseInOmni={() => onMapEventSelect?.(selectedSignal.event_id)} selected /></> : <>{selectedRecord && <MapAccountDetails key={selectedRecord.id} record={selectedRecord} />}{selectedFacility && !selectedRecord && <><p>{'city' in selectedFacility ? `${selectedFacility.city}, ${selectedFacility.region}` : 'Verified facility location'}</p><p>{'location_type' in selectedFacility ? selectedFacility.location_type : 'BTX facility'} · location verified</p>{'source_url' in selectedFacility && selectedFacility.source_url && <a href={selectedFacility.source_url} target="_blank" rel="noreferrer">Inspect location source →</a>}</>}{planningMessage && <p role="status">{planningMessage}</p>}{selected?.accountId && <div className="map-selection-actions">{selected.facilityId && <Button variant="primary" size="touch" onClick={() => itinerary.current?.add(selected)}>Add to itinerary</Button>}<Button size="touch" onClick={() => void setShortlist()}>{selectedShortlist?.active ? 'Remove from shortlist' : 'Add to shortlist'}</Button><Button size="touch" onClick={() => onAccount(selected.accountId!)}>Open Organization 360</Button><Button size="touch" onClick={() => onRelationships(selected.accountId!)}>Explore relationships</Button><Button size="touch" onClick={() => window.dispatchEvent(new Event('btx:open-omni'))}>Ask Omni</Button></div>}</>}</div></aside>}
    </section>
    </div>
    <section className="map-site-table" aria-label="Map site table"><header><div><h2>Sites in view</h2><p aria-live="polite"><strong>{sitesInView.length}</strong> sites in view · <strong>{pending.length}</strong> location pending.</p></div></header><div className="map-site-table-scroll"><table><thead><tr><th>Name</th><th>Type</th><th>Market</th><th>Status</th>{focal && <th>Distance from origin</th>}<th><span className="sr-only">Itinerary</span></th></tr></thead><tbody>{sitesInView.map(marker => { const record = marker.accountId ? records.find(item => item.account_id === marker.accountId && (!marker.facilityId || item.facility_id === marker.facilityId)) : undefined; return <tr key={marker.id} ref={node => { if (node) rowRefs.current.set(marker.id, node); else rowRefs.current.delete(marker.id) }} className={selected?.id === marker.id ? 'selected' : undefined}><td><button type="button" aria-pressed={selected?.id === marker.id} onClick={() => selectMarker(marker)}><strong>{marker.label}</strong></button></td><td>{markerKindLabel[marker.kind] ?? 'Mapped site'}</td><td>{record?.primary_markets.join(' · ') || 'Not applicable'}</td><td>{record ? relationshipOptions.find(([id]) => id === record.account_segment)?.[1] ?? 'Needs review' : marker.kind === 'btx-facility' ? 'BTX site' : 'Verified'}</td>{focal && <td>{Math.round(haversineMiles(focal, marker))} mi straight-line</td>}<td>{marker.accountId && marker.facilityId ? <Button size="touch" variant="ghost" onClick={() => itinerary.current?.add(marker)}>Add to itinerary</Button> : <span>—</span>}</td></tr> })}</tbody></table></div>{pending.length > 0 && <details><summary>Location pending ({pending.length})</summary><p>These matching organizations remain available without fabricated coordinates.</p><ul>{pending.map(account => <li key={account.id}><button type="button" onClick={() => onAccount(account.account_id)}>{account.name} · {account.primary_markets.join(' · ')}</button></li>)}</ul></details>}</section>
    <Drawer open={controlsOpen} onClose={() => setControlsOpen(false)} titleId="map-filter-title" className="map-filter-sheet"><header><div><span className="eyebrow">Map controls</span><h2 id="map-filter-title">Filters</h2></div><Button variant="ghost" onClick={() => setControlsOpen(false)}>Close</Button></header>
      <MapFilterPanel filters={draftFilters} onChange={setDraftFilters} onReset={() => setDraftFilters(defaults)} onClose={() => { updateFilters(draftFilters, 'push'); setControlsOpen(false) }} changed={draftChanged} markets={layers} naics={naicsOptions} filterOptions={filterOptions} fulfillment={fulfillmentOptions} planning={planning} planningError={planningError} focal={focal} />
    </Drawer>
    <ItineraryPlanner ref={itinerary} />
  </div>
}
