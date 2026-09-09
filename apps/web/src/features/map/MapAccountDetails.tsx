import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { CanonicalRecord } from "../../components/CanonicalRecord";
import { Button, Empty, EvidenceSource, StatusBadge } from "../../components/UI";
import type { Account360, MapRecord } from "../../types/api";
import { WorkbookFields } from "../accounts/WorkbookFields";
import { FULFILLMENT_LABELS } from "./mapModel";

type Tab = "OVERVIEW" | "COMMERCIAL" | "CONTACTS" | "SOURCES";
const tabs: Array<[Tab, string]> = [["OVERVIEW", "Overview"], ["COMMERCIAL", "Commercial"], ["CONTACTS", "Contacts"], ["SOURCES", "Sources"]];
const money = (minor?: number | null, currency = "USD") => minor == null ? "Unavailable" : new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(minor / 100);

export function MapAccountDetails({ record }: { record: MapRecord }) {
  const [tab, setTab] = useState<Tab>("OVERVIEW");
  const [detail, setDetail] = useState<Account360>();
  const [failure, setFailure] = useState<string>();
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    api.account(record.account_id, controller.signal)
      .then(setDetail)
      .catch((error: unknown) => { if (!controller.signal.aborted) setFailure(error instanceof Error ? error.message : "Site context is unavailable."); });
    return () => controller.abort();
  }, [record.account_id, attempt]);

  const nearest = record.nearest_btx_facility;
  const segmentLabel = { PROSPECT: "Prospect", CURRENT_CLIENT: "Customer", DORMANT_CUSTOMER: "Dormant customer", UNKNOWN: "Other researched" }[record.account_segment];
  return <div className="map-site-detail">
    <div className="map-site-tabs" role="tablist" aria-label="Selected site details">{tabs.map(([value, text]) => <button key={value} role="tab" aria-selected={tab === value} onClick={() => setTab(value)}>{text}</button>)}</div>
    {failure && <div className="map-site-error" role="alert"><span>Canonical site context could not be loaded.</span><Button variant="ghost" onClick={() => { setFailure(undefined); setAttempt((value) => value + 1); }}>Retry</Button></div>}
    {tab === "OVERVIEW" && <section role="tabpanel" aria-label="Overview">
      <WorkbookFields key={record.account_id} accountId={record.account_id} />
      <div className="map-badges"><StatusBadge value={segmentLabel} kind="entity" />{record.btx_top_100 && <StatusBadge value="BTX Top 100 · membership only" />}{record.primary_markets.map((market) => <StatusBadge key={market} value={market} />)}</div>
      <p><strong>Site:</strong> {record.location_name ?? "Canonical facility"}</p>
      <p><strong>Role / location state:</strong> {(record.location_type ?? record.location_truth_state).replaceAll("_", " ")}</p>
      {Boolean(record.naics_assignments?.length) && <p><strong>Account NAICS:</strong> {record.naics_assignments?.map((item) => `${item.code} (${item.taxonomy_version})`).join(" · ")} · POC classification</p>}
      {record.attractiveness_score != null ? <p><strong>Attractiveness:</strong> {record.attractiveness_score} · {record.attractiveness_coverage} coverage</p> : <p>Attractiveness not yet available.</p>}
      {nearest?.distance_miles != null ? <p><strong>Nearest BTX facility:</strong> {nearest.name} · {nearest.distance_miles} miles straight-line</p> : <p>Nearest BTX facility not yet established.</p>}
      {record.governed_next_step && <p><strong>Next:</strong> {record.governed_next_step}</p>}
    </section>}
    {tab === "COMMERCIAL" && <section role="tabpanel" aria-label="Commercial">
      {record.commercial_briefing ? <><h3>{record.commercial_briefing.summary}</h3><p>{record.commercial_briefing.explanation}</p>{record.commercial_briefing.fulfillment && <div className="map-commercial-summary"><span>Ordered <strong>{record.commercial_briefing.fulfillment.ordered_quantity}</strong></span><span>Shipped <strong>{record.commercial_briefing.fulfillment.shipped_quantity}</strong></span><span>Remaining <strong>{record.commercial_briefing.fulfillment.remaining_quantity}</strong></span><span>Shipped value <strong>{money(record.commercial_briefing.fulfillment.shipped_value_minor, record.commercial_briefing.fulfillment.currency)}</strong></span></div>}<p><strong>Next:</strong> {record.commercial_briefing.next_action}</p></> : <Empty>No linked commercial briefing is available.</Empty>}
      {Boolean(record.commercial_business_unit_ids?.length) && <p><strong>Commercial BU context:</strong> {record.commercial_business_unit_ids?.map((id) => id.replaceAll("-", " ")).join(" · ")}. Account scope, not site qualification.</p>}
      {record.fulfillment_attention && <><p><strong>Fulfillment attention:</strong> {record.fulfillment_attention.states.map((state) => FULFILLMENT_LABELS[state] ?? state).join(" · ")} · {record.fulfillment_attention.as_of}</p><p>Account-level obligations do not establish capacity or qualification at this site.</p></>}
    </section>}
    {tab === "CONTACTS" && <section role="tabpanel" aria-label="Contacts">
      {detail ? detail.public_contacts.length ? <div className="map-contact-list">{detail.public_contacts.map((contact) => <EvidenceSource key={`${contact.name ?? contact.role_family}:${contact.title_or_function}`} title={contact.name ?? contact.role_family} source="Public professional research" date={contact.provenance?.last_verified_at} evidenceState={contact.verification_state} url={contact.source_url} detail={`${contact.title_or_function ?? contact.role_family} · contact candidate only; no meeting or introduction is established.`} />)}</div> : <Empty>No verified public contact is available. Review the account's role targets.</Empty> : <p role="status">Loading contact evidence…</p>}
    </section>}
    {tab === "SOURCES" && <section role="tabpanel" aria-label="Sources">
      {detail ? <>{detail.public_facilities.some((facility) => facility.id === record.facility_id) ? <div className="map-contact-list">{detail.public_facilities.filter((facility) => facility.id === record.facility_id).map((facility) => <EvidenceSource key={facility.id} title={facility.name} source={`${facility.city}, ${facility.region}, ${facility.country}`} evidenceState={facility.verification_state} url={facility.source_url} detail={facility.facility_type} />)}</div> : <Empty>No public facility source matches this selected site ID.</Empty>}<details className="map-record-details"><summary>Location and decision lineage</summary><CanonicalRecord value={{ site_id: record.facility_id, location_status: record.location_truth_state, location_provenance: record.location_provenance, commercial_revision: record.commercial_briefing?.revision, attractiveness_status: record.score_status, missing_decision_inputs: record.score_missingness, current_intelligence: record.current_signal_briefs, upcoming_intelligence: record.upcoming_signal_briefs }} /></details></> : <p role="status">Loading source evidence…</p>}
    </section>}
  </div>;
}
