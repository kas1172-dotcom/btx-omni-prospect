import type { BtxMapFacility, Coordinates, MapAccountSegment, MapIntelligence, MapRecord, PublicLocation } from '../../types/api'

export type MapMarkerKind = 'customer' | 'prospect' | 'public-facility' | 'btx-facility' | 'intelligence' | 'upcoming-intelligence' | 'cluster'
export type MapLayer = 'customers' | 'prospects' | 'public-facilities' | 'btx-facilities' | 'intelligence'
export type MapSelection = { markerId: string; kind: MapMarkerKind; accountId?: string; facilityId?: string; eventId?: string }
export type MapMarker = { id: string; kind: MapMarkerKind; label: string; accessibleLabel: string; latitude: number; longitude: number; accountId?: string; facilityId?: string; eventId?: string; memberIds?: string[]; bounds?: { north: number; south: number; east: number; west: number } }
export type MapFilters = { coverage: 'RICH' | 'ALL'; top100: boolean; industries: string[]; relationships: MapAccountSegment[]; layers: MapLayer[]; signalTiming: Array<'CURRENT' | 'UPCOMING'>; radiusMiles?: 30 | 50 | 100 }
export const ALL_MAP_LAYERS: MapLayer[] = ['customers', 'prospects', 'public-facilities', 'btx-facilities', 'intelligence']
export const DEFAULT_MAP_LAYERS: MapLayer[] = ['customers', 'prospects', 'btx-facilities']
export const validCoordinates = (value: Coordinates | null | undefined): value is Coordinates => Boolean(value && Number.isFinite(Number(value.latitude)) && Number.isFinite(Number(value.longitude)) && Math.abs(Number(value.latitude)) <= 90 && Math.abs(Number(value.longitude)) <= 180)
export const relationshipKind = (record: MapRecord): 'customer' | 'prospect' => record.account_segment === 'PROSPECT' ? 'prospect' : 'customer'
export function filterMapRecords(records: MapRecord[], filters: MapFilters) { return records.filter(record => (filters.coverage === 'ALL' || record.is_rich_scenario) && (!filters.top100 || record.btx_top_100) && (!filters.industries.length || filters.industries.some(industry => record.primary_markets.includes(industry))) && (!filters.relationships.length || filters.relationships.includes(record.account_segment))) }
export function buildMapMarkers(records: MapRecord[], publicLocations: PublicLocation[], btxFacilities: BtxMapFacility[], signals: MapIntelligence[], layers: MapLayer[]): MapMarker[] {
  const enabled = new Set(layers); const markers: MapMarker[] = []
  const publicFacilitySeen = new Set<string>()
  const btxFacilitySeen = new Set<string>()
  for (const record of records) { if (!validCoordinates(record.coordinates)) continue; const kind = relationshipKind(record); if (!enabled.has(kind === 'customer' ? 'customers' : 'prospects')) continue; markers.push({ id: record.id, kind, label: record.name, accessibleLabel: `${kind === 'customer' ? 'Customer' : 'Prospect'} marker: ${record.name}`, latitude: Number(record.coordinates.latitude), longitude: Number(record.coordinates.longitude), accountId: record.account_id, facilityId: record.facility_id }) }
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
export function markersForZoom(markers: MapMarker[], zoom: number): MapMarker[] {
  const thresholded = markers.filter(marker => marker.kind === 'customer' || marker.kind === 'prospect' || marker.kind === 'btx-facility' || ((marker.kind === 'intelligence' || marker.kind === 'upcoming-intelligence') && zoom >= 5) || (marker.kind === 'public-facility' && zoom >= 7))
  if (zoom > 5) return thresholded
  const strategic = thresholded.filter(marker => marker.kind === 'customer' || marker.kind === 'prospect')
  const orientation = thresholded.filter(marker => marker.kind === 'btx-facility')
  const cells = new Map<string, MapMarker[]>()
  for (const marker of strategic) { const key = `${Math.floor(marker.latitude / 6)}:${Math.floor(marker.longitude / 8)}`; cells.set(key, [...(cells.get(key) ?? []), marker]) }
  const clustered = [...cells.entries()].map(([key, members]) => {
    if (members.length === 1) return members[0]
    const latitudes = members.map(item => item.latitude); const longitudes = members.map(item => item.longitude)
    return { id: `cluster:${key}:${members.map(item => item.id).sort().join('|')}`, kind: 'cluster' as const, label: `${members.length} Customers and Prospects`, accessibleLabel: `Cluster of ${members.length} Customers and Prospects: ${members.map(item => item.label).join(', ')}`, latitude: latitudes.reduce((sum, value) => sum + value, 0) / members.length, longitude: longitudes.reduce((sum, value) => sum + value, 0) / members.length, memberIds: members.map(item => item.id), bounds: { north: Math.max(...latitudes), south: Math.min(...latitudes), east: Math.max(...longitudes), west: Math.min(...longitudes) } }
  })
  return [...clustered, ...orientation]
}
export const toggleValue = <T extends string>(values: T[], value: T) => values.includes(value) ? values.filter(item => item !== value) : [...values, value]
