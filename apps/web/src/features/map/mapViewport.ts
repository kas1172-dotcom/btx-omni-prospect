export type ViewPoint = { latitude: number; longitude: number }
export type ViewBounds = { north: number; south: number; east: number; west: number }
export type ViewPadding = { top: number; right: number; bottom: number; left: number }
export type CurrentView = { center: ViewPoint; zoom: number }
export type ViewportRequest = {
  reset?: boolean
  points?: ViewPoint[]
  viewport?: ViewBounds
  origin?: ViewPoint
  radiusMiles?: number
  current?: CurrentView
  padding?: Partial<ViewPadding>
}
export type ViewportPlan =
  | { kind: 'keep'; center: ViewPoint; zoom: number }
  | { kind: 'center'; center: ViewPoint; zoom: number }
  | { kind: 'bounds'; bounds: ViewBounds; padding: ViewPadding; maxZoom: number }

export const DEFAULT_US_VIEW: CurrentView = { center: { latitude: 38, longitude: -98 }, zoom: 4 }
const DEFAULT_PADDING: ViewPadding = { top: 72, right: 72, bottom: 88, left: 72 }
const SITE_ZOOM = 12
const MAX_BOUNDS_ZOOM = 13
const EARTH_RADIUS_MILES = 3958.7613

export const validViewPoint = (point: ViewPoint | null | undefined): point is ViewPoint => Boolean(point
  && Number.isFinite(point.latitude)
  && Number.isFinite(point.longitude)
  && Math.abs(point.latitude) <= 90
  && Math.abs(point.longitude) <= 180)

const radians = (degrees: number) => degrees * Math.PI / 180
const milesBetween = (a: ViewPoint, b: ViewPoint) => {
  const deltaLat = radians(b.latitude - a.latitude)
  const deltaLon = radians(b.longitude - a.longitude)
  const latA = radians(a.latitude)
  const latB = radians(b.latitude)
  const value = Math.sin(deltaLat / 2) ** 2 + Math.cos(latA) * Math.cos(latB) * Math.sin(deltaLon / 2) ** 2
  return EARTH_RADIUS_MILES * 2 * Math.asin(Math.sqrt(value))
}
const normalizedPadding = (padding: Partial<ViewPadding> | undefined): ViewPadding => ({ ...DEFAULT_PADDING, ...padding })
const validBounds = (bounds: ViewBounds | undefined): bounds is ViewBounds => Boolean(bounds
  && [bounds.north, bounds.south, bounds.east, bounds.west].every(Number.isFinite)
  && bounds.north >= bounds.south
  && Math.abs(bounds.north) <= 90
  && Math.abs(bounds.south) <= 90
  && Math.abs(bounds.east) <= 180
  && Math.abs(bounds.west) <= 180)
const boundsForPoints = (points: ViewPoint[]): ViewBounds => ({
  north: Math.max(...points.map(point => point.latitude)),
  south: Math.min(...points.map(point => point.latitude)),
  east: Math.max(...points.map(point => point.longitude)),
  west: Math.min(...points.map(point => point.longitude)),
})
const radiusBounds = (origin: ViewPoint, radiusMiles: number): ViewBounds => {
  const latitudeDelta = radiusMiles / 69
  const longitudeDelta = radiusMiles / Math.max(1, 69 * Math.cos(radians(origin.latitude)))
  return {
    north: Math.min(90, origin.latitude + latitudeDelta),
    south: Math.max(-90, origin.latitude - latitudeDelta),
    east: Math.min(180, origin.longitude + longitudeDelta),
    west: Math.max(-180, origin.longitude - longitudeDelta),
  }
}

export function computeViewport(request: ViewportRequest): ViewportPlan {
  const padding = normalizedPadding(request.padding)
  if (request.reset) return { kind: 'center', center: DEFAULT_US_VIEW.center, zoom: DEFAULT_US_VIEW.zoom }
  if (validBounds(request.viewport)) return { kind: 'bounds', bounds: request.viewport, padding, maxZoom: MAX_BOUNDS_ZOOM }
  if (validViewPoint(request.origin) && Number.isFinite(request.radiusMiles) && Number(request.radiusMiles) > 0) {
    return { kind: 'bounds', bounds: radiusBounds(request.origin, Number(request.radiusMiles)), padding, maxZoom: MAX_BOUNDS_ZOOM }
  }
  const points = (request.points ?? []).filter(validViewPoint)
  if (!points.length) {
    const current = request.current && validViewPoint(request.current.center) && Number.isFinite(request.current.zoom) ? request.current : DEFAULT_US_VIEW
    return { kind: 'keep', center: current.center, zoom: current.zoom }
  }
  const bounds = boundsForPoints(points)
  const spread = milesBetween({ latitude: bounds.north, longitude: bounds.west }, { latitude: bounds.south, longitude: bounds.east })
  if (points.length === 1 || spread < 1.25) {
    const center = { latitude: (bounds.north + bounds.south) / 2, longitude: (bounds.east + bounds.west) / 2 }
    return { kind: 'center', center, zoom: SITE_ZOOM }
  }
  return { kind: 'bounds', bounds, padding, maxZoom: MAX_BOUNDS_ZOOM }
}
