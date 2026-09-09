import type { BtxMapFacility, Coordinates, MapAccountSegment, MapIntelligence, MapRecord, PublicLocation } from '../../types/api'

export type MapMarkerKind = 'customer' | 'prospect' | 'public-facility' | 'btx-facility' | 'intelligence' | 'upcoming-intelligence' | 'cluster'
export type MapLayer = 'customers' | 'prospects' | 'public-facilities' | 'btx-facilities' | 'intelligence'
export type MapSelection = { markerId: string; kind: MapMarkerKind; accountId?: string; facilityId?: string; eventId?: string }
export type MapMarker = { id: string; kind: MapMarkerKind; label: string; accessibleLabel: string; latitude: number; longitude: number; accountId?: string; facilityId?: string; eventId?: string; memberIds?: string[]; bounds?: { north: number; south: number; east: number; west: number } }
export type MapFilters = { coverage: 'RICH' | 'ALL'; top100: boolean; industries: string[]; relationships: MapAccountSegment[]; layers: MapLayer[]; signalTiming: Array<'CURRENT' | 'UPCOMING'>; strategicPartnership?: 'ALL' | 'EXCLUDE' | 'ONLY'; shortlistOnly?: boolean; radiusMiles?: 30 | 50 | 100; naicsCodes?: string[]; businessUnitIds?: string[]; fulfillmentStates?: string[] }
export const FULFILLMENT_LABELS: Record<string, string> = { MISSED_COMMITMENT: 'Missed delivery commitment', ACCEPTANCE_PENDING: 'Acceptance pending', OPEN_SHIPMENT: 'Open shipment balance', NO_OPEN_FULFILLMENT_EXCEPTION: 'No open fulfillment exception' }
export type MapViewSnapshot = { filters: MapFilters; selected?: MapMarker }
export const ALL_MAP_LAYERS: MapLayer[] = ['customers', 'prospects', 'public-facilities', 'btx-facilities', 'intelligence']
export const DEFAULT_MAP_LAYERS: MapLayer[] = ['customers', 'prospects', 'btx-facilities']
// The API deliberately serializes Decimal coordinates as strings. Accept that
// contract, but never coerce null/blank/booleans into a fabricated zero location.
const numericCoordinate = (value: unknown): boolean => (typeof value === 'number' || (typeof value === 'string' && /^-?\d+(?:\.\d+)?$/.test(value))) && Number.isFinite(Number(value))
export const validCoordinates = (value: Coordinates | null | undefined): value is Coordinates => Boolean(value && numericCoordinate(value.latitude) && numericCoordinate(value.longitude) && Math.abs(Number(value.latitude)) <= 90 && Math.abs(Number(value.longitude)) <= 180)
export const relationshipKind = (record: MapRecord): 'customer' | 'prospect' => record.account_segment === 'PROSPECT' ? 'prospect' : 'customer'
export function filterMapRecords<T extends Pick<MapRecord, 'is_rich_scenario' | 'btx_top_100' | 'primary_markets' | 'account_segment' | 'naics_assignments' | 'commercial_business_unit_ids' | 'fulfillment_attention'>>(records: T[], filters: MapFilters): T[] {
  return records.filter(record => (filters.coverage === 'ALL' || record.is_rich_scenario)
    && (!filters.top100 || record.btx_top_100)
    && (!filters.industries.length || filters.industries.some(industry => record.primary_markets.includes(industry)))
    && (!filters.relationships.length || filters.relationships.includes(record.account_segment))
    && (!filters.naicsCodes?.length || record.naics_assignments?.some(item => filters.naicsCodes?.includes(item.code)))
    && (!filters.businessUnitIds?.length || record.commercial_business_unit_ids?.some(id => filters.businessUnitIds?.includes(id)))
    && (!filters.fulfillmentStates?.length || record.fulfillment_attention?.states.some(state => filters.fulfillmentStates?.includes(state))))
}
export function buildMapMarkers(records: MapRecord[], publicLocations: PublicLocation[], btxFacilities: BtxMapFacility[], signals: MapIntelligence[], layers: MapLayer[]): MapMarker[] {
  const enabled = new Set(layers); const markers: MapMarker[] = []
  const publicFacilitySeen = new Set<string>()
  const btxFacilitySeen = new Set<string>()
  for (const record of records) { if (!validCoordinates(record.coordinates)) continue; const kind = relationshipKind(record); if (!enabled.has(kind === 'customer' ? 'customers' : 'prospects')) continue; const label = record.location_name && record.location_name !== record.name ? `${record.name} · ${record.location_name}` : record.name; markers.push({ id: record.id, kind, label, accessibleLabel: `${kind === 'customer' ? 'Customer' : 'Prospect'} marker: ${label}`, latitude: Number(record.coordinates.latitude), longitude: Number(record.coordinates.longitude), accountId: record.account_id, facilityId: record.facility_id }) }
  if (enabled.has('public-facilities')) for (const facility of publicLocations) {
    if (!validCoordinates(facility.coordinates)) continue
    if (publicFacilitySeen.has(facility.facility_id)) continue
    publicFacilitySeen.add(facility.facility_id)
    markers.push({ id: `facility:${facility.facility_id}`, kind: 'public-facility', label: facility.name, accessibleLabel: `Public facility marker: ${facility.name}`, latitude: Number(facility.coordinates.latitude), longitude: Number(facility.coordinates.longitude), accountId: facility.account_id, facilityId: facility.facility_id })
  }
  if (enabled.has('btx-facilities')) for (const facility of btxFacilities) {
    if (!validCoordinates(facility.coordinates)) continue
    if (btxFacilitySeen.has(facility.facility_id)) continue
    btxFacilitySeen.add(facility.facility_id)
    markers.push({ id: `btx:${facility.facility_id}`, kind: 'btx-facility', label: facility.name, accessibleLabel: `BTX facility marker: ${facility.name}`, latitude: Number(facility.coordinates.latitude), longitude: Number(facility.coordinates.longitude), facilityId: facility.facility_id })
  }
  if (enabled.has('intelligence')) for (const signal of signals) if (validCoordinates(signal.coordinates)) { const upcoming = signal.marker_mode === 'UPCOMING'; markers.push({ id: `intelligence:${signal.event_id}`, kind: upcoming ? 'upcoming-intelligence' : 'intelligence', label: signal.headline, accessibleLabel: `${upcoming ? 'Upcoming governed event' : 'Current collected intelligence'} marker: ${signal.headline}`, latitude: Number(signal.coordinates.latitude), longitude: Number(signal.coordinates.longitude), accountId: signal.account_id, facilityId: signal.facility_id, eventId: signal.event_id }) }
  return markers
}
export function haversineMiles(a: Pick<MapMarker, 'latitude' | 'longitude'>, b: Pick<MapMarker, 'latitude' | 'longitude'>) {
  const radians = (degrees: number) => degrees * Math.PI / 180
  const deltaLat = radians(b.latitude - a.latitude); const deltaLon = radians(b.longitude - a.longitude)
  const latA = radians(a.latitude); const latB = radians(b.latitude)
  const value = Math.sin(deltaLat / 2) ** 2 + Math.cos(latA) * Math.cos(latB) * Math.sin(deltaLon / 2) ** 2
  return 3958.7613 * 2 * Math.asin(Math.sqrt(value))
}
export const filterMarkersByRadius = (markers: MapMarker[], focal: MapMarker | undefined, radiusMiles?: 30 | 50 | 100) => !focal || !radiusMiles ? markers : markers.filter(marker => marker.id === focal.id || haversineMiles(focal, marker) <= radiusMiles)
export function markersForZoom(markers: MapMarker[], zoom: number, selectedMarkerId?: string): MapMarker[] {
  const thresholded = markers.filter(marker => marker.kind === 'customer' || marker.kind === 'prospect' || marker.kind === 'btx-facility' || ((marker.kind === 'intelligence' || marker.kind === 'upcoming-intelligence') && zoom >= 5) || (marker.kind === 'public-facility' && zoom >= 7))
  // Screen-space radius at the current zoom, independent of map panning. Stable
  // canonical order keeps cluster membership reproducible after a data refresh.
  // Selected context stays individually reachable, including at shared coordinates.
  const strategic = thresholded.filter(marker => (marker.kind === 'customer' || marker.kind === 'prospect') && marker.id !== selectedMarkerId).sort((a, b) => a.id.localeCompare(b.id))
  const orientation = thresholded.filter(marker => marker.id === selectedMarkerId || (marker.kind !== 'customer' && marker.kind !== 'prospect'))
  const world = 256 * 2 ** Math.max(0, Math.min(22, Number.isFinite(zoom) ? zoom : 4))
  const radius = 48
  const groups: Array<{ x: number; y: number; members: MapMarker[] }> = []
  const cells = new Map<string, number[]>()
  const cellCount = Math.ceil(world / radius)
  const cellKey = (x: number, y: number) => `${(x + cellCount) % cellCount}:${y}`
  for (const marker of strategic) {
    const sine = Math.sin(Math.max(-85.051129, Math.min(85.051129, marker.latitude)) * Math.PI / 180)
    const x = (marker.longitude + 180) / 360 * world
    const y = (0.5 - Math.log((1 + sine) / (1 - sine)) / (4 * Math.PI)) * world
    const cellX = Math.floor(x / radius); const cellY = Math.floor(y / radius)
    const candidates = new Set<number>()
    for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (const index of cells.get(cellKey(cellX + dx, cellY + dy)) ?? []) candidates.add(index)
    const match = [...candidates].sort((a, b) => a - b).find(index => {
      const group = groups[index]; const deltaX = Math.abs(x - group.x)
      return Math.hypot(Math.min(deltaX, world - deltaX), y - group.y) <= radius
    })
    if (match !== undefined) groups[match].members.push(marker)
    else { const index = groups.length; groups.push({ x, y, members: [marker] }); const key = cellKey(cellX, cellY); cells.set(key, [...(cells.get(key) ?? []), index]) }
  }
  const clustered = groups.map(({ members }) => {
    if (members.length === 1) return members[0]
    const latitudes = members.map(item => item.latitude); const longitudes = members.map(item => item.longitude)
    // Unwrap around the first member so date-line clusters do not appear at 0°.
    const anchor = longitudes[0]; const unwrapped = longitudes.map(value => anchor + ((value - anchor + 540) % 360 - 180))
    const wrap = (value: number) => ((value + 540) % 360) - 180
    return { id: `cluster:${members.map(item => item.id).join('|')}`, kind: 'cluster' as const, label: `${members.length} Customers and Prospects`, accessibleLabel: `Cluster of ${members.length} Customers and Prospects: ${members.map(item => item.label).join(', ')}`, latitude: latitudes.reduce((sum, value) => sum + value, 0) / members.length, longitude: wrap(unwrapped.reduce((sum, value) => sum + value, 0) / members.length), memberIds: members.map(item => item.id), bounds: { north: Math.max(...latitudes), south: Math.min(...latitudes), east: wrap(Math.max(...unwrapped)), west: wrap(Math.min(...unwrapped)) } }
  })
  return [...clustered, ...orientation]
}
export const toggleValue = <T extends string>(values: T[], value: T) => values.includes(value) ? values.filter(item => item !== value) : [...values, value]
