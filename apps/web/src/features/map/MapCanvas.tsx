import { useEffect, useRef } from 'react'
import * as maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import './map.css'
import type { MapRecord, PublicLocation, Signal } from '../../types/api'

type Props = { records: MapRecord[]; publicLocations: PublicLocation[]; signals: Signal[]; onSelect: (accountId: string) => void }

const mapStyle = import.meta.env.VITE_MAP_STYLE_URL ?? 'https://demotiles.maplibre.org/style.json'

export function MapCanvas({ records, publicLocations, signals, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  useEffect(() => {
    if (!container.current || mapRef.current) return
    const map = new maplibregl.Map({ container: container.current, style: mapStyle, center: [-98, 38], zoom: 3.2 })
    map.addControl(new maplibregl.NavigationControl(), 'top-right')
    map.on('load', () => {
      const features = [
        ...records.map(record => ({ type: 'Feature', properties: { accountId: record.account_id, label: record.industry, kind: 'sample', truth: record.location_truth_state }, geometry: { type: 'Point', coordinates: [Number(record.longitude), Number(record.latitude)] } })),
        ...publicLocations.map(location => ({ type: 'Feature', properties: { accountId: location.account_id, label: location.location_name, kind: 'public', truth: location.truth_state }, geometry: { type: 'Point', coordinates: [Number(location.longitude), Number(location.latitude)] } })),
        ...signals.filter(signal => signal.account_id).map(signal => ({ type: 'Feature', properties: { accountId: signal.account_id, label: signal.title, kind: 'signal', truth: signal.data_mode === 'CONNECTED' ? 'LIVE_PUBLIC' : 'SAMPLE' }, geometry: null })),
      ].filter(feature => feature.geometry)
      map.addSource('canonical-locations', { type: 'geojson', data: { type: 'FeatureCollection', features } as never, cluster: true, clusterMaxZoom: 10, clusterRadius: 42 })
      map.addLayer({ id: 'location-clusters', type: 'circle', source: 'canonical-locations', filter: ['has', 'point_count'], paint: { 'circle-color': '#2b7db0', 'circle-radius': ['step', ['get', 'point_count'], 16, 20, 21, 80, 28] } })
      map.addLayer({ id: 'location-cluster-count', type: 'symbol', source: 'canonical-locations', filter: ['has', 'point_count'], layout: { 'text-field': '{point_count_abbreviated}', 'text-size': 12 }, paint: { 'text-color': '#ffffff' } })
      map.addLayer({ id: 'canonical-points', type: 'circle', source: 'canonical-locations', filter: ['!', ['has', 'point_count']], paint: { 'circle-color': ['match', ['get', 'kind'], 'public', '#67d6a0', 'signal', '#f3c969', '#79bdf2'], 'circle-radius': 7, 'circle-stroke-width': 2, 'circle-stroke-color': '#0b1523' } })
      map.on('click', 'location-clusters', event => { const feature = map.queryRenderedFeatures(event.point, { layers: ['location-clusters'] })[0]; const clusterId = feature?.properties?.cluster_id; const source = map.getSource('canonical-locations') as maplibregl.GeoJSONSource; if (clusterId !== undefined && feature?.geometry.type === 'Point') source.getClusterExpansionZoom(clusterId).then((zoom: number) => map.easeTo({ center: feature.geometry.coordinates as [number, number], zoom })) })
      map.on('click', 'canonical-points', event => { const feature = event.features?.[0]; if (feature?.properties?.accountId) onSelect(feature.properties.accountId) })
      for (const layer of ['location-clusters', 'canonical-points']) map.on('mouseenter', layer, () => { map.getCanvas().style.cursor = 'pointer' })
      for (const layer of ['location-clusters', 'canonical-points']) map.on('mouseleave', layer, () => { map.getCanvas().style.cursor = '' })
    })
    mapRef.current = map
    return () => { map.remove(); mapRef.current = null }
  }, [records, publicLocations, signals, onSelect])
  return <div ref={container} className="map-canvas" role="application" aria-label="Interactive account, public facility, and intelligence map" />
}
