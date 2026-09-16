import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { CanonicalRecord } from "../../components/CanonicalRecord";
import { Button, Empty, EvidenceSource, StatusBadge } from "../../components/UI";
import type { Account360, MapRecord } from "../../types/api";
import { WorkbookFields } from "../accounts/WorkbookFields";
import { FULFILLMENT_LABELS } from "./mapModel";
import { SupportingEvidence, WhyThis } from "../../components/SupportingEvidence";
import { RelatedBtxActivity } from "../../components/RelatedBtxActivity";
import { TechnicalDecompositionSection } from "../../components/TechnicalDecompositionSection";

type Tab = "OVERVIEW" | "COMMERCIAL" | "CONTACTS" | "SOURCES";
const tabs: Array<[Tab, string]> = [["OVERVIEW", "Overview"], ["COMMERCIAL", "Commercial"], ["CONTACTS", "Contacts"], ["SOURCES", "Sources"]];
const money = (minor?: number | null, currency = "USD") => minor == null ? "Unavailable" : new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(minor / 100);

export function MapAccountDetails({ record }: { record: MapRecord }) {
  const [tab, setTab] = useState<Tab>("OVERVIEW");
  const [detail, setDetail] = useState<Account360>();
  const [failure, setFailure] = useState<{ accountId: string; message: string }>();
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    api.account(record.account_id, controller.signal)
      .then((value) => { if (!controller.signal.aborted) { setDetail(value); setFailure(undefined); } })
      .catch((error: unknown) => { if (!controller.signal.aborted) setFailure({ accountId: record.account_id, message: error instanceof Error ? error.message : "Site context is unavailable." }); });
    return () => controller.abort();
  }, [record.account_id, attempt]);
  const currentDetail = detail?.account.id === record.account_id ? detail : undefined;
  const currentFailure = failure?.accountId === record.account_id ? failure : undefined;

  const nearest = record.nearest_btx_facility;
  const prospectRange = record.prospect_fit?.applicable && record.prospect_fit.score_low != null && record.prospect_fit.score_high != null
    ? (record.prospect_fit.score != null ? record.prospect_fit.score : `${record.prospect_fit.score_low}–${record.prospect_fit.score_high}`)
    : undefined;
  const segmentLabel = { PROSPECT: "Prospect", CURRENT_CLIENT: "Customer", DORMANT_CUSTOMER: "Dormant customer", UNKNOWN: "Other researched" }[record.account_segment];
  return <div className="map-site-detail">
    <div className="map-site-tabs" role="tablist" aria-label="Selected site details">{tabs.map(([value, text]) => <button key={value} role="tab" aria-selected={tab === value} onClick={() => setTab(value)}>{text}</button>)}</div>
    {currentFailure && <div className="map-site-error" role="alert"><span>Canonical site context could not be loaded.</span><Button variant="ghost" onClick={() => { setFailure(undefined); setAttempt((value) => value + 1); }}>Retry</Button></div>}
    {tab === "OVERVIEW" && <section role="tabpanel" aria-label="Overview">
      <WorkbookFields key={record.account_id} accountId={record.account_id} />
      <div className="map-badges"><StatusBadge value={segmentLabel} kind="entity" />{record.btx_top_100 && <StatusBadge value="BTX Top 100 · membership only" />}{record.primary_markets.map((market) => <StatusBadge key={market} value={market} />)}</div>
      <p><strong>Site:</strong> {record.location_name ?? "Canonical facility"}</p>
      <p><strong>Role / location state:</strong> {(record.location_type ?? record.location_truth_state).replaceAll("_", " ")}</p>
      {Boolean(record.naics_assignments?.length) && <p><strong>Account NAICS:</strong> {record.naics_assignments?.map((item) => `${item.code} (${item.taxonomy_version})`).join(" · ")} · POC classification</p>}
      {record.account_segment === "PROSPECT" ? (prospectRange ? <p><strong>Prospect Fit:</strong> {prospectRange} · {Number(record.prospect_fit!.coverage) * 100}% input coverage{record.prospect_fit!.score == null ? " · bounded range" : ""}</p> : <p>Prospect Fit requires scoped research.</p>) : (record.attractiveness_score != null ? <p><strong>Opportunity Priority:</strong> {record.attractiveness_score} · {Number(record.attractiveness_coverage) * 100}% input coverage</p> : <p>Opportunity Priority is unavailable until a specific pursuit has sufficient inputs.</p>)}
      {nearest?.distance_miles != null ? <p><strong>Nearest BTX facility:</strong> {nearest.name} · {nearest.distance_miles} miles straight-line</p> : <p>Nearest BTX facility not yet established.</p>}
      {record.governed_next_step && <p><strong>Next:</strong> {record.governed_next_step}</p>}
      {record.current_signal_briefs?.slice(0, 2).map((brief) => <article key={brief.context_id ?? brief.id} className="map-commercial-summary"><strong>{brief.headline}</strong><span><b>What happened:</b> {brief.what_happened}</span><span><b>Why it may matter:</b> {brief.why_it_may_matter} <WhyThis>{brief.action_rationale ?? brief.what_to_watch}</WhyThis></span><span><b>Next:</b> {brief.recommended_action ?? "No seller action is supported yet."}</span>{brief.material_uncertainties?.[0] && <span><b>Material uncertainty:</b> {brief.material_uncertainties[0]}</span>}<small>{brief.geographic_scope === "FACILITY" ? brief.canonical_facility_id === record.facility_id ? "Verified site scope" : "Other verified facility context; not attributed to this site" : "Account-wide context; not attributed to this site"}</small><SupportingEvidence count={new Set([...brief.evidence_ids, ...(brief.references ?? []).map(item => item.evidence_id), ...(brief.evidence_package?.commercial_records ?? []).map(item => item.record_id)]).size} investigationKey={`map:${record.facility_id}:${brief.assessment_id ?? brief.id}:${brief.assessment_version ?? 0}`}><section><h4>Program and component evidence</h4><TechnicalDecompositionSection technical={brief.technical_opportunity} /></section><section><h4>Related BTX records</h4><RelatedBtxActivity accountId={record.account_id} records={brief.evidence_package?.commercial_records ?? []} /></section><section><h4>Sources</h4>{brief.references?.map(source => <EvidenceSource key={source.evidence_id} title={source.title} source="Public source" date={source.publication_date ?? undefined} evidenceState="Source reviewed" url={source.url} />)}</section></SupportingEvidence></article>)}
    </section>}
    {tab === "COMMERCIAL" && <section role="tabpanel" aria-label="Commercial">
      {record.commercial_briefing ? <><h3>{record.commercial_briefing.summary}</h3><p>{record.commercial_briefing.explanation}</p>{record.commercial_briefing.fulfillment && <div className="map-commercial-summary"><span>Ordered <strong>{record.commercial_briefing.fulfillment.ordered_quantity}</strong></span><span>Shipped <strong>{record.commercial_briefing.fulfillment.shipped_quantity}</strong></span><span>Remaining <strong>{record.commercial_briefing.fulfillment.remaining_quantity}</strong></span><span>Shipped value <strong>{money(record.commercial_briefing.fulfillment.shipped_value_minor, record.commercial_briefing.fulfillment.currency)}</strong></span></div>}<p><strong>Next:</strong> {record.commercial_briefing.next_action}</p></> : <Empty>No linked commercial briefing is available.</Empty>}
      {Boolean(record.commercial_business_unit_ids?.length) && <p><strong>Commercial BU context:</strong> {record.commercial_business_unit_ids?.map((id) => id.replaceAll("-", " ")).join(" · ")}. Account scope, not site qualification.</p>}
      {record.fulfillment_attention && <><p><strong>Fulfillment attention:</strong> {record.fulfillment_attention.states.map((state) => FULFILLMENT_LABELS[state] ?? state).join(" · ")} · {record.fulfillment_attention.as_of}</p><p>Account-level obligations do not establish capacity or qualification at this site.</p></>}
    </section>}
    {tab === "CONTACTS" && <section role="tabpanel" aria-label="Contacts">
      {currentDetail ? currentDetail.public_contacts.length ? <div className="map-contact-list">{currentDetail.public_contacts.map((contact) => <EvidenceSource key={`${contact.name ?? contact.role_family}:${contact.title_or_function}`} title={contact.name ?? contact.role_family} source="Public professional research" date={contact.provenance?.last_verified_at} evidenceState={contact.verification_state} url={contact.source_url} detail={`${contact.title_or_function ?? contact.role_family} · contact candidate only; no meeting or introduction is established.`} />)}</div> : <Empty>No verified public contact is available. Review the account's role targets.</Empty> : <p role="status">Loading contact evidence…</p>}
    </section>}
    {tab === "SOURCES" && <section role="tabpanel" aria-label="Sources">
      {currentDetail ? <>{currentDetail.public_facilities.some((facility) => facility.id === record.facility_id) ? <div className="map-contact-list">{currentDetail.public_facilities.filter((facility) => facility.id === record.facility_id).map((facility) => <EvidenceSource key={facility.id} title={facility.name} source={`${facility.city}, ${facility.region}, ${facility.country}`} evidenceState={facility.verification_state} url={facility.source_url} detail={facility.facility_type} />)}</div> : <Empty>No public facility source matches this selected site ID.</Empty>}<details className="map-record-details"><summary>Location and decision evidence</summary><CanonicalRecord value={{ site: record.location_name ?? record.facility_id, facility_reference: record.facility_id, location_status: record.location_truth_state, location_provenance: record.location_provenance, commercial_revision: record.commercial_briefing?.revision, score_status: record.score_status, missing_score_inputs: record.score_missingness, current_intelligence: record.current_signal_briefs, upcoming_intelligence: record.upcoming_signal_briefs }} /></details></> : <p role="status">Loading source evidence…</p>}
    </section>}
  </div>;
}
