import { useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import './map.css'
import type { MapRecord, PublicLocation, Signal } from '../../types/api'

type Props = { records: MapRecord[]; publicLocations: PublicLocation[]; signals: Signal[]; onSelect: (accountId: string) => void }

function mapConfiguration() {
  const style = import.meta.env.VITE_MAP_STYLE_URL?.trim()
  const key = import.meta.env.VITE_MAP_API_KEY?.trim()
  if (!style) return { style: null, failure: 'Map configuration is incomplete: VITE_MAP_STYLE_URL is missing from the frontend environment. Add the MapTiler style URL and restart the frontend.' }
  if (!key) return { style: null, failure: 'Map configuration is incomplete: VITE_MAP_API_KEY is missing from the frontend environment. Add the existing domain-restricted browser key and restart the frontend.' }
  try { new URL(style) } catch { return { style: null, failure: 'Map configuration is invalid: VITE_MAP_STYLE_URL is malformed. Use a complete MapTiler style URL, then restart the frontend.' } }
  const separator = style.includes('?') ? '&' : '?'
  return { style: style.includes('key=') ? style : `${style}${separator}key=${encodeURIComponent(key)}`, failure: null }
}

export function MapCanvas({ records, publicLocations, signals, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const [failure, setFailure] = useState<string | null>(null)
  const configuration = mapConfiguration()
  const style = configuration.style
  const setupFailure = configuration.failure
  useEffect(() => {
    if (!style) return
    if (!container.current || mapRef.current) return
    let disposed = false
    try {
      const map = new maplibregl.Map({ container: container.current, style, center: [-98, 38], zoom: 3.2 })
      mapRef.current = map
      map.addControl(new maplibregl.NavigationControl(), 'top-right')
      map.on('error', () => { if (!disposed) setFailure('Map unavailable. The configured MapTiler style or tiles could not load. Confirm the existing browser key permits this local origin, the style URL is valid, and the network can reach MapTiler; do not paste a key into the application.') })
      map.on('load', () => {
        const features = [
          ...records.map(record => ({ type: 'Feature', properties: { accountId: record.account_id, kind: 'sample' }, geometry: { type: 'Point', coordinates: [Number(record.longitude), Number(record.latitude)] } })),
          ...publicLocations.map(location => ({ type: 'Feature', properties: { accountId: location.account_id, kind: 'public' }, geometry: { type: 'Point', coordinates: [Number(location.longitude), Number(location.latitude)] } })),
        ]
        map.addSource('canonical-locations', { type: 'geojson', data: { type: 'FeatureCollection', features } as never, cluster: true, clusterMaxZoom: 10, clusterRadius: 42 })
        map.addLayer({ id: 'location-clusters', type: 'circle', source: 'canonical-locations', filter: ['has', 'point_count'], paint: { 'circle-color': '#2b7db0', 'circle-radius': ['step', ['get', 'point_count'], 16, 20, 21, 80, 28] } })
        map.addLayer({ id: 'location-cluster-count', type: 'symbol', source: 'canonical-locations', filter: ['has', 'point_count'], layout: { 'text-field': '{point_count_abbreviated}', 'text-size': 12 }, paint: { 'text-color': '#ffffff' } })
        map.addLayer({ id: 'canonical-points', type: 'circle', source: 'canonical-locations', filter: ['!', ['has', 'point_count']], paint: { 'circle-color': ['match', ['get', 'kind'], 'public', '#67d6a0', '#79bdf2'], 'circle-radius': 7, 'circle-stroke-width': 2, 'circle-stroke-color': '#0b1523' } })
        map.on('click', 'canonical-points', event => { const id = event.features?.[0]?.properties?.accountId; if (id) onSelect(id) })
        for (const layer of ['location-clusters', 'canonical-points']) map.on('mouseenter', layer, () => { map.getCanvas().style.cursor = 'pointer' })
        for (const layer of ['location-clusters', 'canonical-points']) map.on('mouseleave', layer, () => { map.getCanvas().style.cursor = '' })
      })
    } catch { queueMicrotask(() => setFailure('Map unavailable. Check the MapTiler style URL and browser configuration.')) }
    return () => { disposed = true; mapRef.current?.remove(); mapRef.current = null }
  }, [style, records, publicLocations, signals, onSelect])
  if (setupFailure ?? failure) return <section className="map-unavailable" role="status"><h3>Map unavailable</h3><p>{setupFailure ?? failure}</p><small>Map data, filters, and account selection remain available in the panels below.</small></section>
  return <div ref={container} className="map-canvas" role="application" aria-label="Interactive account and public facility map" />
}
