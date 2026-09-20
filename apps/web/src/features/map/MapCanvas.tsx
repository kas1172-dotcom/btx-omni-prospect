import { useEffect, useMemo, useRef, useState } from 'react'
import { importLibrary, setOptions } from '@googlemaps/js-api-loader'
import { markersForZoom, type MapMarker } from './mapModel'
import { computeViewport, DEFAULT_US_VIEW, type ViewBounds } from './mapViewport'
import './map.css'

export type MapCameraRequest = { key: string; reset?: boolean; points?: Array<{ latitude: number; longitude: number }>; viewport?: ViewBounds; origin?: { latitude: number; longitude: number }; radiusMiles?: number }
type Props = { markers: MapMarker[]; selectedMarkerId?: string; cameraRequest?: MapCameraRequest; onSelect: (marker: MapMarker) => void; onVisibleMarkers?: (markers: MapMarker[]) => void }
let configuredKey: string | undefined
const markerZIndex = (marker: MapMarker, selected = false) => selected ? 4 : marker.kind === 'cluster' ? 3 : marker.kind === 'customer' || marker.kind === 'prospect' ? 2 : 1
// Account markers may be legacy `account:<accountId>` or facility-scoped
// `account:<accountId>:facility:<facilityId>`; clustering uses the canonical account.
const accountIdFromMarkerId = (id: string) => id.startsWith('account:') ? id.split(':')[1] : undefined

function makeMarkerButton(marker: MapMarker, selected: boolean, onSelect: () => void) {
  const button = document.createElement('button'); button.type = 'button'; button.className = `map-marker-hit${selected ? ' selected' : ''}`; button.setAttribute('aria-label', marker.accessibleLabel); button.setAttribute('aria-pressed', String(selected)); button.title = marker.label
  const glyph = document.createElement('span'); glyph.className = `map-marker map-marker-${marker.kind}`; glyph.setAttribute('aria-hidden', 'true'); glyph.textContent = marker.kind === 'cluster' ? String(marker.memberIds?.length ?? '') : ''; button.append(glyph)
  button.addEventListener('click', event => { event.stopPropagation(); onSelect() }); return button
}
function TestCanvas({ markers, selectedMarkerId, onSelect, onVisibleMarkers }: Props) {
  const markerSignature = markers.filter(marker => marker.kind === 'customer' || marker.kind === 'prospect').map(marker => marker.id).join('|')
  const [focus, setFocus] = useState<{ members?: string[]; signature: string }>({ signature: '' }); const clusterMembers = focus.signature === markerSignature ? focus.members : undefined
  const visible = useMemo(() => { if (!clusterMembers) return markersForZoom(markers, 4); const accountIds = new Set(clusterMembers.map(accountIdFromMarkerId).filter((id): id is string => Boolean(id))); return markers.filter(marker => clusterMembers.includes(marker.id) || marker.kind === 'btx-facility' || (Boolean(marker.accountId) && accountIds.has(marker.accountId!))) }, [clusterMembers, markers])
  useEffect(() => onVisibleMarkers?.(visible), [onVisibleMarkers, visible])
  return <div className="map-test-canvas" role="application" aria-label="Interactive Customer, facility, BTX facility, and intelligence map">{visible.map((marker, index) => <button key={marker.id} type="button" className={`map-marker map-marker-${marker.kind}${marker.id === selectedMarkerId ? ' selected' : ''}`} style={{ left: `${8 + (index % 6) * 9}%`, top: `${12 + Math.floor(index / 6) * 11}%`, minWidth: 44, minHeight: 44, zIndex: markerZIndex(marker, marker.id === selectedMarkerId) }} aria-label={marker.accessibleLabel} aria-pressed={marker.id === selectedMarkerId} onClick={() => marker.kind === 'cluster' ? setFocus({ members: marker.memberIds, signature: markerSignature }) : onSelect(marker)}>{marker.kind === 'cluster' ? marker.memberIds?.length : ''}</button>)}</div>
}

export function MapCanvas(props: Props) {
  const { markers, selectedMarkerId, onSelect, onVisibleMarkers } = props
  const testMode = import.meta.env.VITE_MAP_TEST_MODE === 'true'; const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY; const mapId = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID || 'DEMO_MAP_ID'
  const testUnconfigured = testMode && new URLSearchParams(window.location.search).has('map-test-unconfigured')
  const container = useRef<HTMLDivElement>(null); const mapRef = useRef<google.maps.Map | undefined>(undefined); const markerRefs = useRef(new Map<string, { advanced: google.maps.marker.AdvancedMarkerElement; signature: string }>()); const propsRef = useRef(props); const lastCameraKey = useRef<string | undefined>(undefined); const [zoom, setZoom] = useState(DEFAULT_US_VIEW.zoom); const [mapReady, setMapReady] = useState(0); const [failure, setFailure] = useState<string | null>(null); const [clusterMembers, setClusterMembers] = useState<string[]>([])
  const visible = useMemo(() => markersForZoom(markers, zoom, selectedMarkerId), [markers, zoom, selectedMarkerId])
  useEffect(() => { propsRef.current = props }, [props])
  useEffect(() => onVisibleMarkers?.(visible), [onVisibleMarkers, visible])
  useEffect(() => {
    if (testMode || !apiKey || !container.current) return
    const registry = markerRefs.current
    let cancelled = false; let zoomListener: google.maps.MapsEventListener | undefined
    const load = async () => { try {
      if (!configuredKey) { setOptions({ key: apiKey, v: 'weekly' }); configuredKey = apiKey }
      if (configuredKey !== apiKey) throw new Error('Conflicting Google Maps configuration')
      const { Map } = await importLibrary('maps')
      if (cancelled || !container.current) return
      const map = new Map(container.current, { center: { lat: DEFAULT_US_VIEW.center.latitude, lng: DEFAULT_US_VIEW.center.longitude }, zoom: DEFAULT_US_VIEW.zoom, minZoom: 3, mapId,
        mapTypeControl: false, streetViewControl: false, fullscreenControl: false,
        // Weekly Maps now defaults to a camera menu. Keep direct keyboard/touch
        // zoom controls independent of that provider default and our detail panel.
        cameraControl: false, zoomControl: true,
        zoomControlOptions: { position: google.maps.ControlPosition.LEFT_BOTTOM },
        scaleControl: true, keyboardShortcuts: true,
      }); mapRef.current = map
      zoomListener = map.addListener('zoom_changed', () => setZoom(map.getZoom() ?? 4))
      setMapReady(version => version + 1)
    } catch { if (!cancelled) setFailure('The Google Maps renderer could not load. Verify the browser key, API restrictions, billing, and quota configuration.') } }
    void load(); const observer = new ResizeObserver(() => { if (mapRef.current) google.maps.event.trigger(mapRef.current, 'resize') }); observer.observe(container.current)
    return () => { cancelled = true; zoomListener?.remove(); observer.disconnect(); registry.forEach(({ advanced }) => { advanced.map = null }); registry.clear(); mapRef.current = undefined; lastCameraKey.current = undefined }
  }, [apiKey, mapId, testMode])
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    let cancelled = false
    Promise.resolve(importLibrary('marker')).then(({ AdvancedMarkerElement }) => {
      if (cancelled || mapRef.current !== map) return
      const wanted = new Set(visible.map(marker => marker.id))
      for (const [id, entry] of markerRefs.current) if (!wanted.has(id)) { entry.advanced.map = null; markerRefs.current.delete(id) }
      for (const marker of visible) {
        const selected = marker.id === selectedMarkerId
        const signature = JSON.stringify([marker, selected])
        const previous = markerRefs.current.get(marker.id)
        if (previous?.signature === signature) continue
        const choose = () => {
          if (marker.kind === 'cluster' && marker.bounds) {
            // An explicit member list also works for coincident sites, where zoom
            // alone cannot separate markers. No artificial location offsets.
            setClusterMembers(marker.memberIds ?? [])
            const plan = computeViewport({ points: (marker.memberIds ?? []).flatMap(id => { const member = propsRef.current.markers.find(item => item.id === id); return member ? [member] : [] }), padding: { right: 80, left: 80, top: 80, bottom: 80 } })
            if (plan.kind === 'center') { map.setCenter({ lat: plan.center.latitude, lng: plan.center.longitude }); map.setZoom(plan.zoom) }
            else if (plan.kind === 'bounds') { map.fitBounds(plan.bounds, plan.padding); google.maps.event.addListenerOnce(map, 'idle', () => { if ((map.getZoom() ?? plan.maxZoom) > plan.maxZoom) map.setZoom(plan.maxZoom) }) }
          } else { setClusterMembers([]); propsRef.current.onSelect(marker) }
        }
        const advanced = previous?.advanced ?? new AdvancedMarkerElement({ map, gmpClickable: true })
        advanced.position = { lat: marker.latitude, lng: marker.longitude }; advanced.title = marker.accessibleLabel; advanced.zIndex = markerZIndex(marker, selected)
        advanced.replaceChildren(makeMarkerButton(marker, selected, choose))
        markerRefs.current.set(marker.id, { advanced, signature })
      }
    }).catch(() => { if (!cancelled) setFailure('The Google Maps marker layer could not load.') })
    return () => { cancelled = true }
  }, [visible, selectedMarkerId, mapReady])
  useEffect(() => {
    const map = mapRef.current; const element = container.current; const request = props.cameraRequest
    if (!map || !element || !request || lastCameraKey.current === request.key || element.clientWidth <= 0 || element.clientHeight <= 0) return
    const compact = element.clientWidth < 760
    const plan = computeViewport({ ...request, current: { center: { latitude: map.getCenter()?.lat() ?? DEFAULT_US_VIEW.center.latitude, longitude: map.getCenter()?.lng() ?? DEFAULT_US_VIEW.center.longitude }, zoom: map.getZoom() ?? DEFAULT_US_VIEW.zoom }, padding: compact ? { top: 90, left: 40, right: 40, bottom: Math.round(element.clientHeight * 0.45) } : { top: 70, left: 70, right: 380, bottom: 90 } })
    lastCameraKey.current = request.key
    if (plan.kind === 'center') { map.setCenter({ lat: plan.center.latitude, lng: plan.center.longitude }); map.setZoom(plan.zoom) }
    else if (plan.kind === 'bounds') { map.fitBounds(plan.bounds, plan.padding); google.maps.event.addListenerOnce(map, 'idle', () => { if ((map.getZoom() ?? plan.maxZoom) > plan.maxZoom) map.setZoom(plan.maxZoom) }) }
  }, [props.cameraRequest, mapReady])
  if (testUnconfigured) return <section className="map-unavailable" role="status"><h3>Interactive map unavailable in this build</h3><p>A permitted Google Maps browser configuration was not included when this frontend was built. The synchronized site list and verified details remain available.</p></section>
  if (testMode) return <TestCanvas {...props} />
  if (!apiKey) return <section className="map-unavailable" role="status"><h3>Interactive map unavailable in this build</h3><p>A permitted Google Maps browser configuration was not included when this frontend was built. The synchronized site list and verified details remain available.</p></section>
  if (failure) return <section className="map-unavailable" role="status"><h3>Map unavailable</h3><p>{failure}</p></section>
  const members = markers.filter(marker => clusterMembers.includes(marker.id))
  return <><div ref={container} className="map-canvas" role="application" aria-label="Interactive Google Customer, facility, BTX facility, and intelligence map" />{members.length > 0 && <section className="map-cluster-members" aria-label="Sites in selected cluster"><header><strong>{members.length} sites</strong><button type="button" onClick={() => setClusterMembers([])} aria-label="Close cluster sites">Close</button></header><p>Choose a site, including sites sharing the same coordinates.</p><ul>{members.map(marker => <li key={marker.id}><button type="button" aria-pressed={marker.id === selectedMarkerId} onClick={() => { setClusterMembers([]); onSelect(marker) }}>{marker.label}<small>{marker.kind === 'customer' ? 'Customer' : 'Prospect'}</small></button></li>)}</ul></section>}</>
}
