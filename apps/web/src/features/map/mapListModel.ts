import type { MapMarker } from './mapModel'

export const synchronizedMapSites = (markers: MapMarker[]) => markers.some(marker => marker.kind === 'cluster') ? markers.filter(marker => marker.kind !== 'cluster') : markers
export const synchronizedSiteCount = (markers: MapMarker[]) => synchronizedMapSites(markers).length
