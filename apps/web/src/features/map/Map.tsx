import { useMemo, useState } from 'react'
import type { BtxMapFacility, MapAccountSegment, MapIntelligence, MapRecord, PublicLocation } from '../../types/api'
import { Empty, Panel, State } from '../../components/UI'
import { MapCanvas } from './MapCanvas'

type SegmentFilter = 'ALL' | MapAccountSegment

const segmentLabel: Record<SegmentFilter, string> = {
  ALL: 'Customers & Prospects',
  CURRENT_CLIENT: 'Customer',
  DORMANT_CUSTOMER: 'Dormant customers',
  PROSPECT: 'Prospects',
  UNKNOWN: 'Unknown / no internal history',
}

const matchesFilters = (record: MapRecord, coverage: 'RICH' | 'ALL', layer: string, segment: SegmentFilter) =>
  (coverage === 'ALL' || record.is_rich_scenario)
  && (layer === 'All' || record.primary_markets.includes(layer))
  && (segment === 'ALL' || record.account_segment === segment)

export function Map({ records, publicLocations, btxFacilities, layers, signals, onAccount, onMapAccountSelect, onMapFacilitySelect }: { records: MapRecord[]; publicLocations: PublicLocation[]; btxFacilities: BtxMapFacility[]; layers: string[]; signals: MapIntelligence[]; onAccount: (id: string) => void; onMapAccountSelect: (id?: string) => void; onMapFacilitySelect: (facilityId?: string, accountId?: string) => void }) {
  const [layer, setLayer] = useState('All')
  const [coverage, setCoverage] = useState<'RICH' | 'ALL'>('RICH')
  const [segment, setSegment] = useState<SegmentFilter>('ALL')
  const [showSignals, setShowSignals] = useState(true)
  const [selected, setSelected] = useState<string>()
  const [controlsOpen, setControlsOpen] = useState(false)

  const visible = useMemo(() => records.filter(record => matchesFilters(record, coverage, layer, segment)), [records, coverage, layer, segment])
  const ids = useMemo(() => new Set(visible.map(record => record.account_id)), [visible])
  const facilities = publicLocations.filter(location => ids.has(location.account_id))
  const intelligence = signals.filter(signal => !signal.account_id || ids.has(signal.account_id))
  const selectedRecord = visible.find(record => record.account_id === selected)

  const applyFilters = (nextCoverage: 'RICH' | 'ALL', nextLayer: string, nextSegment: SegmentFilter, nextShowSignals = showSignals) => {
    if (selected && !records.some(record => record.account_id === selected && matchesFilters(record, nextCoverage, nextLayer, nextSegment))) {
      setSelected(undefined)
      onMapFacilitySelect()
    }
    setCoverage(nextCoverage)
    setLayer(nextLayer)
    setSegment(nextSegment)
    setShowSignals(nextShowSignals)
  }

  const selectAccount = (accountId: string) => {
    setSelected(accountId)
    onMapAccountSelect(accountId)
  }
  const selectFacility = (facilityId: string, accountId?: string) => {
    setSelected(accountId)
    onMapFacilitySelect(facilityId, accountId)
  }
  const clearControls = () => {
    applyFilters('RICH', 'All', 'ALL', true)
  }
  const controlsChanged = layer !== 'All' || coverage !== 'RICH' || segment !== 'ALL' || !showSignals
  const intelligenceMarkers = intelligence.filter(item => item.coordinates).length
  const status = `${coverage === 'RICH' ? 'Curated scenarios' : 'All researched'} · ${layer}${segment === 'ALL' ? '' : ` · ${segmentLabel[segment]}`}`

  return <div className="surface map-workspace">
    <div className="page-title map-title"><span className="eyebrow">National commercial geography</span><h1>Tactical Map</h1><p>Verified public locations, BTX facilities, and geographically supported intelligence. Proximity never changes Customer Attractiveness.</p></div>
    <section className="map-stage" aria-label="Tactical map workspace">
      <MapCanvas records={visible} publicLocations={facilities} btxFacilities={btxFacilities} signals={showSignals ? intelligence : []} selectedAccountId={selected} onAccountSelect={selectAccount} onFacilitySelect={selectFacility} />
      <div className="map-toolbar"><button className="map-layers-trigger" aria-expanded={controlsOpen} aria-controls="map-controls" onClick={() => setControlsOpen(open => !open)}>Map layers</button><span className="map-toolbar-status">{status}</span></div>
      {controlsOpen && <section className="map-controls-panel" id="map-controls" aria-label="Map controls">
        <div className="map-controls-head"><div><span className="eyebrow">Map controls</span><strong>Layers &amp; coverage</strong></div><button onClick={() => setControlsOpen(false)}>Close</button></div>
        <div className="control-group"><span>Coverage</span><div className="chips"><button className={coverage === 'RICH' ? 'selected' : ''} onClick={() => applyFilters('RICH', layer, segment)}>Curated scenarios</button><button className={coverage === 'ALL' ? 'selected' : ''} onClick={() => applyFilters('ALL', layer, segment)}>All researched Customers and Prospects</button></div></div>
        <div className="control-group"><span>Industry</span><div className="chips"><button className={layer === 'All' ? 'selected' : ''} onClick={() => applyFilters(coverage, 'All', segment)}>All</button>{layers.map(value => <button className={layer === value ? 'selected' : ''} key={value} onClick={() => applyFilters(coverage, value, segment)}>{value}</button>)}</div></div>
        <div className="control-group"><span>Customer relationship</span><div className="chips" aria-label="Customer relationship filters">{(Object.keys(segmentLabel) as SegmentFilter[]).map(value => <button className={segment === value ? 'selected' : ''} key={value} onClick={() => applyFilters(coverage, layer, value)}>{segmentLabel[value]}</button>)}</div></div>
        <label className="toggle"><input type="checkbox" checked={showSignals} onChange={event => applyFilters(coverage, layer, segment, event.target.checked)} /> Show geographically linked intelligence</label>
        <div className="map-controls-footer"><small>{visible.length} Customers and Prospects · {facilities.length} researched facilities · {btxFacilities.length} BTX facilities · {intelligenceMarkers} verified intelligence markers</small>{controlsChanged && <button onClick={clearControls}>Clear filters</button>}</div>
      </section>}
      <div className="map-stage-status"><strong>{visible.length} mapped Customers and Prospects</strong><span>{facilities.length} researched facilities · {btxFacilities.length} BTX facilities · {showSignals ? intelligenceMarkers : 0} verified intelligence markers</span></div>
      <div className="map-stage-hint">Click a verified marker to inspect its canonical Customer or facility context.</div>
    </section>
    {visible.length ? <div className="map-layout"><div className="detail-stack">
      <Panel title="Researched facilities"><div className="card-list map-facility-list">{facilities.map(location => <button className="line" key={location.id} onClick={() => selectFacility(location.facility_id, location.account_id)}><span><strong>{location.name}</strong><small>{location.location_type} / {location.city}, {location.region} / {location.truth_state}</small></span><span>Preview</span></button>)}</div></Panel>
      <Panel title="BTX facilities"><div className="card-list map-facility-list">{btxFacilities.map(facility => <button className="line" key={facility.id} onClick={() => selectFacility(facility.facility_id)}><span><strong>{facility.name}</strong><small>{facility.city}, {facility.region}</small></span><span>Preview</span></button>)}</div></Panel>
      {showSignals && <Panel title="Intelligence marker layer">{intelligenceMarkers ? intelligence.filter(item => item.coordinates).map(signal => <p className="map-signal-line" key={signal.id}><State value={signal.evidence_state ?? 'PUBLIC'} /> {signal.title}</p>) : <Empty>No current intelligence event has verified event or canonical-facility coordinates.</Empty>}</Panel>}
    </div><aside className="map-quick-view">{selectedRecord ? <Panel title="Customer quick view"><State value={selectedRecord.relationship} /><h3>{selectedRecord.name}</h3><p>Markets: {selectedRecord.primary_markets.join(', ')}</p><p>Nearest BTX facility: <strong>{selectedRecord.nearest_btx_facility?.name ?? 'Unavailable'}</strong></p><button className="primary" onClick={() => onAccount(selectedRecord.account_id)}>View Customer</button></Panel> : <Panel title="Map preview"><p className="empty">Select a Customer, facility, or intelligence marker.</p></Panel>}</aside></div> : <Empty>No matching mapped records exist for the selected market, coverage, and Customer relationship filters.</Empty>}
  </div>
}
