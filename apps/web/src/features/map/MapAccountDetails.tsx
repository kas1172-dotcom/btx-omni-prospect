import { CanonicalRecord } from '../../components/CanonicalRecord'
import { WorkbookFields } from '../accounts/WorkbookFields'
import { StatusBadge } from '../../components/UI'
import type { MapRecord } from '../../types/api'
import { FULFILLMENT_LABELS } from './mapModel'

export function MapAccountDetails({ record }: { record: MapRecord }) {
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [fulfillmentOpen, setFulfillmentOpen] = useState(false)
  const nearest = record.nearest_btx_facility
  const segmentLabel = { PROSPECT: 'Prospect', CURRENT_CLIENT: 'Customer', DORMANT_CUSTOMER: 'Dormant customer', UNKNOWN: 'Other researched' }[record.account_segment]
  return <>
    <WorkbookFields key={record.account_id} accountId={record.account_id} />
    <div className="map-badges"><StatusBadge value={segmentLabel} kind="entity" />{record.btx_top_100 && <StatusBadge value="BTX Top 100 · membership only" />}{record.primary_markets.map(market => <StatusBadge key={market} value={market} />)}</div>
    <p>{record.location_name ?? 'Canonical facility'} · {(record.location_type ?? record.location_truth_state).replaceAll('_', ' ')}</p>
    {Boolean(record.naics_assignments?.length) && <p>Account NAICS: {record.naics_assignments?.map(item => `${item.code} (${item.taxonomy_version})`).join(' · ')} · POC classification</p>}
    {Boolean(record.commercial_business_unit_ids?.length) && <p>Commercial BU context: {record.commercial_business_unit_ids?.map(id => id.replaceAll('-', ' ')).join(' · ')}. Account scope, not site qualification.</p>}
    {record.attractiveness_score != null ? <p>Attractiveness: <strong>{record.attractiveness_score}</strong> · {record.attractiveness_coverage} coverage</p> : <p>Attractiveness not yet available.</p>}
    {nearest?.distance_miles != null ? <p>Nearest BTX facility: <strong>{nearest.name}</strong> · {nearest.distance_miles} miles straight-line</p> : <p>Nearest BTX facility not yet established.</p>}
    {record.commercial_briefing?.summary && <p>{record.commercial_briefing.summary}</p>}
    {record.governed_next_step && <p><strong>Next:</strong> {record.governed_next_step}</p>}
    {record.fulfillment_attention && <details onToggle={event => setFulfillmentOpen(event.currentTarget.open)}><summary>Fulfillment attention · {record.fulfillment_attention.as_of}</summary>{fulfillmentOpen && <><p>{record.fulfillment_attention.states.map(state => FULFILLMENT_LABELS[state] ?? state).join(' · ')}</p><p>Account-level obligations; these do not establish capacity or qualification at this customer site.</p><CanonicalRecord value={record.fulfillment_attention} /></>}</details>}
    <details className="map-record-details" onToggle={event => setDetailsOpen(event.currentTarget.open)}><summary>Site evidence and decision details</summary>{detailsOpen && <CanonicalRecord value={{ site_id: record.facility_id, location_status: record.location_truth_state, location_provenance: record.location_provenance, attractiveness_status: record.score_status, missing_decision_inputs: record.score_missingness, commercial_context: record.commercial_briefing, current_intelligence: record.current_signal_briefs, upcoming_intelligence: record.upcoming_signal_briefs }} />}</details>
  </>
}
import { useState } from 'react'
