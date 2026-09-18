import type { MapAccountSegment } from '../../types/api'
import type { MapLayer } from './mapModel'

export const relationshipOptions: Array<[MapAccountSegment, string]> = [
  ['CURRENT_CLIENT', 'Customers'],
  ['DORMANT_CUSTOMER', 'Dormant customers'],
  ['PROSPECT', 'Prospects'],
  ['UNKNOWN', 'Relationship needs review'],
]
export const layerOptions: Array<[MapLayer, string]> = [['customers', 'Customers'], ['prospects', 'Prospects'], ['public-facilities', 'Public facilities'], ['btx-facilities', 'BTX facilities'], ['intelligence', 'Intelligence']]
