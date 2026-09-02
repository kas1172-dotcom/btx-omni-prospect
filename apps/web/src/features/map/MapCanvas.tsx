import { useEffect, useMemo, useRef, useState } from 'react'
import { importLibrary, setOptions } from '@googlemaps/js-api-loader'
import { markersForZoom, type MapMarker } from './mapModel'
import './map.css'

type Props = { markers: MapMarker[]; selectedMarkerId?: string; selectionFrame?: MapMarker[]; onSelect: (marker: MapMarker) => void; onVisibleMarkers?: (markers: MapMarker[]) => void }
let configuredKey: string | undefined
const markerZIndex = (marker: MapMarker, selected = false) => selected ? 4 : marker.kind === 'cluster' ? 3 : marker.kind === 'customer' || marker.kind === 'prospect' ? 2 : 1
// Account markers may be legacy `account:<accountId>` or facility-scoped
// `account:<accountId>:facility:<facilityId>`; clustering uses the canonical account.
export const accountIdFromMarkerId = (id: string) => id.startsWith('account:') ? id.split(':')[1] : undefined

function makeMarkerButton(marker: MapMarker, selected: boolean, onSelect: () => void) {
  const button = document.createElement('button'); button.type = 'button'; button.className = `map-marker map-marker-${marker.kind}${selected ? ' selected' : ''}`; button.style.minWidth = '44px'; button.style.minHeight = '44px'; button.setAttribute('aria-label', marker.accessibleLabel); button.setAttribute('aria-pressed', String(selected)); button.title = marker.label; button.addEventListener('click', event => { event.stopPropagation(); onSelect() }); return button
}
function TestCanvas({ markers, selectedMarkerId, onSelect, onVisibleMarkers }: Props) {
  const markerSignature = markers.filter(marker => marker.kind === 'customer' || marker.kind === 'prospect').map(marker => marker.id).join('|')
  const [focus, setFocus] = useState<{ members?: string[]; signature: string }>({ signature: '' }); const clusterMembers = focus.signature === markerSignature ? focus.members : undefined
  const visible = useMemo(() => { if (!clusterMembers) return markersForZoom(markers, 4); const accountIds = new Set(clusterMembers.map(accountIdFromMarkerId).filter((id): id is string => Boolean(id))); return markers.filter(marker => clusterMembers.includes(marker.id) || marker.kind === 'btx-facility' || (Boolean(marker.accountId) && accountIds.has(marker.accountId!))) }, [clusterMembers, markers])
  useEffect(() => onVisibleMarkers?.(visible), [onVisibleMarkers, visible])
  return <div className="map-test-canvas" role="application" aria-label="Interactive Customer, facility, BTX facility, and intelligence map">{visible.map((marker, index) => <button key={marker.id} type="button" className={`map-marker map-marker-${marker.kind}${marker.id === selectedMarkerId ? ' selected' : ''}`} style={{ left: `${8 + (index % 6) * 9}%`, top: `${12 + Math.floor(index / 6) * 11}%`, minWidth: 44, minHeight: 44, zIndex: markerZIndex(marker, marker.id === selectedMarkerId) }} aria-label={marker.accessibleLabel} aria-pressed={marker.id === selectedMarkerId} onClick={() => marker.kind === 'cluster' ? setFocus({ members: marker.memberIds, signature: markerSignature }) : onSelect(marker)}>{marker.kind === 'cluster' ? marker.memberIds?.length : ''}</button>)}</div>
}

export function MapCanvas(props: Props) {
  const { markers, selectedMarkerId, selectionFrame, onSelect, onVisibleMarkers } = props
  const testMode = import.meta.env.VITE_MAP_TEST_MODE === 'true'; const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY; const mapId = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID || 'DEMO_MAP_ID'
  const testUnconfigured = testMode && new URLSearchParams(window.location.search).has('map-test-unconfigured')
  const container = useRef<HTMLDivElement>(null); const mapRef = useRef<google.maps.Map | undefined>(undefined); const markerRefs = useRef<google.maps.marker.AdvancedMarkerElement[]>([]); const propsRef = useRef(props); const lastFramed = useRef<string | undefined>(undefined); const [zoom, setZoom] = useState(4); const [failure, setFailure] = useState<string | null>(null)
  const visible = useMemo(() => markersForZoom(markers, zoom), [markers, zoom])
  useEffect(() => { propsRef.current = props }, [props])
  useEffect(() => onVisibleMarkers?.(visible), [onVisibleMarkers, visible])
  useEffect(() => {
    if (testMode || !apiKey || !container.current) return
    let cancelled = false; let zoomListener: google.maps.MapsEventListener | undefined
    const load = async () => { try {
      if (!configuredKey) { setOptions({ key: apiKey, v: 'weekly' }); configuredKey = apiKey }
      if (configuredKey !== apiKey) throw new Error('Conflicting Google Maps configuration')
      const { Map } = await importLibrary('maps')
      if (cancelled || !container.current) return
      const map = new Map(container.current, { center: { lat: 38, lng: -98 }, zoom: 4, minZoom: 3, mapId, mapTypeControl: false, streetViewControl: false, fullscreenControl: false }); mapRef.current = map
      zoomListener = map.addListener('zoom_changed', () => setZoom(map.getZoom() ?? 4))
    } catch { if (!cancelled) setFailure('The Google Maps renderer could not load. Verify the browser key, API restrictions, billing, and quota configuration.') } }
    void load(); const observer = new ResizeObserver(() => { if (mapRef.current) google.maps.event.trigger(mapRef.current, 'resize') }); observer.observe(container.current)
    return () => { cancelled = true; zoomListener?.remove(); observer.disconnect(); markerRefs.current.forEach(marker => { marker.map = null }); markerRefs.current = []; mapRef.current = undefined }
  }, [apiKey, mapId, testMode])
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    Promise.resolve(importLibrary('marker')).then(({ AdvancedMarkerElement }) => { markerRefs.current.forEach(marker => { marker.map = null }); markerRefs.current = visible.map(marker => { const selected = marker.id === selectedMarkerId; const choose = () => { if (marker.kind === 'cluster' && marker.bounds) { map.fitBounds(marker.bounds, 80); if ((map.getZoom() ?? 0) < 6) map.setZoom(6) } else onSelect(marker) }; const advanced = new AdvancedMarkerElement({ map, position: { lat: marker.latitude, lng: marker.longitude }, title: marker.accessibleLabel, gmpClickable: true, zIndex: markerZIndex(marker, selected) }); advanced.append(makeMarkerButton(marker, selected, choose)); return advanced }) }).catch(() => setFailure('The Google Maps marker layer could not load.'))
  }, [visible, selectedMarkerId, onSelect])
  useEffect(() => {
    const map = mapRef.current
    if (!map || !selectedMarkerId || lastFramed.current === selectedMarkerId) return
    const selected = markers.find(marker => marker.id === selectedMarkerId)
    if (!selected) return
    lastFramed.current = selectedMarkerId
    const frame = selectionFrame?.length ? selectionFrame : [selected]
    if (frame.length > 1) { const bounds = new google.maps.LatLngBounds(); frame.forEach(marker => bounds.extend({ lat: marker.latitude, lng: marker.longitude })); map.fitBounds(bounds, { top: 70, left: 70, right: 360, bottom: 90 }) }
    else { map.panTo({ lat: selected.latitude, lng: selected.longitude }); if ((map.getZoom() ?? 4) < 8) map.setZoom(8) }
  }, [markers, selectedMarkerId, selectionFrame])
  if (testUnconfigured) return <section className="map-unavailable" role="status"><h3>Map not configured</h3><p>Google Maps browser configuration is required to display verified geography.</p></section>
  if (testMode) return <TestCanvas {...props} />
  if (!apiKey) return <section className="map-unavailable" role="status"><h3>Map not configured</h3><p>Google Maps browser configuration is required to display verified geography.</p></section>
  if (failure) return <section className="map-unavailable" role="status"><h3>Map unavailable</h3><p>{failure}</p></section>
  return <div ref={container} className="map-canvas" role="application" aria-label="Interactive Google Customer, facility, BTX facility, and intelligence map" />
}
