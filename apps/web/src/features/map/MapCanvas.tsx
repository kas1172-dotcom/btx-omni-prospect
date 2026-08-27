import { useEffect, useRef, useState } from 'react'
import { importLibrary, setOptions } from '@googlemaps/js-api-loader'
import type { MapMarker } from './mapModel'
import './map.css'

type Props = { markers: MapMarker[]; selectedMarkerId?: string; onSelect: (marker: MapMarker) => void }
let configuredKey: string | undefined

function makeMarkerButton(marker: MapMarker, selected: boolean, onSelect: () => void) {
  const button = document.createElement('button'); button.type = 'button'; button.className = `map-marker map-marker-${marker.kind}${selected ? ' selected' : ''}`; button.style.minWidth = '44px'; button.style.minHeight = '44px'; button.setAttribute('aria-label', marker.accessibleLabel); button.setAttribute('aria-pressed', String(selected)); button.title = marker.label; button.addEventListener('click', event => { event.stopPropagation(); onSelect() }); return button
}
function TestCanvas({ markers, selectedMarkerId, onSelect }: Props) { return <div className="map-test-canvas" role="application" aria-label="Interactive Customer, facility, BTX facility, and intelligence map">{markers.map((marker, index) => <button key={marker.id} type="button" className={`map-marker map-marker-${marker.kind}${marker.id === selectedMarkerId ? ' selected' : ''}`} style={{ left: `${10 + (index * 17) % 78}%`, top: `${18 + (index * 23) % 62}%`, minWidth: 44, minHeight: 44 }} aria-label={marker.accessibleLabel} aria-pressed={marker.id === selectedMarkerId} onClick={() => onSelect(marker)} />)}</div> }

export function MapCanvas(props: Props) {
  const { markers, selectedMarkerId, onSelect } = props
  const testMode = import.meta.env.VITE_MAP_TEST_MODE === 'true'; const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY; const mapId = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID || 'DEMO_MAP_ID'
  const testUnconfigured = testMode && new URLSearchParams(window.location.search).has('map-test-unconfigured')
  const container = useRef<HTMLDivElement>(null); const mapRef = useRef<google.maps.Map | undefined>(undefined); const markerRefs = useRef<google.maps.marker.AdvancedMarkerElement[]>([]); const propsRef = useRef(props); const [failure, setFailure] = useState<string | null>(null)
  useEffect(() => { propsRef.current = { markers, selectedMarkerId, onSelect } }, [markers, selectedMarkerId, onSelect])
  useEffect(() => {
    if (testMode || !apiKey || !container.current) return
    let cancelled = false
    const load = async () => { try {
      if (!configuredKey) { setOptions({ key: apiKey, v: 'weekly' }); configuredKey = apiKey }
      if (configuredKey !== apiKey) throw new Error('Conflicting Google Maps configuration')
      const [{ Map }, { AdvancedMarkerElement }] = await Promise.all([importLibrary('maps'), importLibrary('marker')])
      if (cancelled || !container.current) return
      const map = new Map(container.current, { center: { lat: 38, lng: -98 }, zoom: 4, mapId, mapTypeControl: false, streetViewControl: false, fullscreenControl: false }); mapRef.current = map
      markerRefs.current = propsRef.current.markers.map(marker => { const advanced = new AdvancedMarkerElement({ map, position: { lat: marker.latitude, lng: marker.longitude }, title: marker.accessibleLabel, gmpClickable: true }); advanced.append(makeMarkerButton(marker, marker.id === propsRef.current.selectedMarkerId, () => propsRef.current.onSelect(marker))); return advanced })
    } catch { if (!cancelled) setFailure('The Google Maps renderer could not load. Verify the browser key, API restrictions, billing, and quota configuration.') } }
    void load(); const observer = new ResizeObserver(() => { if (mapRef.current) google.maps.event.trigger(mapRef.current, 'resize') }); observer.observe(container.current)
    return () => { cancelled = true; observer.disconnect(); markerRefs.current.forEach(marker => { marker.map = null }); markerRefs.current = []; mapRef.current = undefined }
  }, [apiKey, mapId, testMode])
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    Promise.resolve(importLibrary('marker')).then(({ AdvancedMarkerElement }) => { markerRefs.current.forEach(marker => { marker.map = null }); markerRefs.current = markers.map(marker => { const advanced = new AdvancedMarkerElement({ map, position: { lat: marker.latitude, lng: marker.longitude }, title: marker.accessibleLabel, gmpClickable: true }); advanced.append(makeMarkerButton(marker, marker.id === selectedMarkerId, () => onSelect(marker))); return advanced }) }).catch(() => setFailure('The Google Maps marker layer could not load.'))
  }, [markers, selectedMarkerId, onSelect])
  if (testUnconfigured) return <section className="map-unavailable" role="status"><h3>Map not configured</h3><p>Google Maps browser configuration is required to display verified geography.</p></section>
  if (testMode) return <TestCanvas {...props} />
  if (!apiKey) return <section className="map-unavailable" role="status"><h3>Map not configured</h3><p>Google Maps browser configuration is required to display verified geography.</p></section>
  if (failure) return <section className="map-unavailable" role="status"><h3>Map unavailable</h3><p>{failure}</p></section>
  return <div ref={container} className="map-canvas" role="application" aria-label="Interactive Google Customer, facility, BTX facility, and intelligence map" />
}
