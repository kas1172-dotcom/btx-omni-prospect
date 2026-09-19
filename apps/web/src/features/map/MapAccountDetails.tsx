import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { CanonicalRecord } from "../../components/CanonicalRecord";
import { Button, Empty, EvidenceSource, LoadingStatus, StatusBadge } from "../../components/UI";
import type { Account360, MapRecord } from "../../types/api";
import { WorkbookFields } from "../accounts/WorkbookFields";
import { FULFILLMENT_LABELS } from "./mapModel";
import { SupportingEvidence, WhyThis } from "../../components/SupportingEvidence";
import { RelatedBtxActivity } from "../../components/RelatedBtxActivity";
import { TechnicalDecompositionSection } from "../../components/TechnicalDecompositionSection";
import { ScoreSummary } from "../../components/ScoreSummary";
import { attractivenessSummary, prospectFitSummary } from "../../components/scoreSummaryModel";
import { presentationLabel } from "../../components/presentation";

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
  const segmentLabel = { PROSPECT: "Prospect", CURRENT_CLIENT: "Customer", DORMANT_CUSTOMER: "Dormant customer", UNKNOWN: "Relationship needs review" }[record.account_segment];
  const accountScore = currentDetail?.account_attractiveness;
  const prospectScore = currentDetail?.prospect_fit;
  const score = record.account_segment === "PROSPECT" && prospectScore?.applicable ? prospectFitSummary(prospectScore, record.name) : accountScore ? attractivenessSummary(accountScore, record.name) : undefined;
  const verifiedLocation = [record.city, record.region, record.country].filter(Boolean).join(", ");
  return <div className="map-site-detail">
    <div className="map-site-tabs" role="tablist" aria-label="Selected site details">{tabs.map(([value, text]) => <button key={value} role="tab" aria-selected={tab === value} onClick={() => setTab(value)}>{text}</button>)}</div>
    {currentFailure && <div className="map-site-error" role="alert"><span>Canonical site context could not be loaded.</span><Button variant="ghost" onClick={() => { setFailure(undefined); setAttempt((value) => value + 1); }}>Retry</Button></div>}
    {tab === "OVERVIEW" && <section role="tabpanel" aria-label="Overview">
      <div className="map-badges"><StatusBadge value={segmentLabel} kind="entity" />{record.btx_top_100 && <StatusBadge value="BTX Top 100 · membership only" />}{record.primary_markets.map((market) => <StatusBadge key={market} value={market} />)}</div>
      <p><strong>Organization:</strong> {record.name}</p>
      <p><strong>Facility:</strong> {record.location_name ?? "Canonical facility"}</p>
      <p><strong>Site role:</strong> {presentationLabel(record.location_type ?? "Role unavailable")}</p>
      <p><strong>Verified location:</strong> {verifiedLocation || "Location details unavailable"} · {presentationLabel(record.location_truth_state)}</p>
      <p><strong>Market and industry:</strong> {record.primary_markets.join(" · ") || record.industry || "Unavailable"}</p>
      {Boolean(record.naics_assignments?.length) && <p><strong>Account NAICS:</strong> {record.naics_assignments?.map((item) => `${item.code} (${item.taxonomy_version})`).join(" · ")} · POC classification</p>}
      {record.candidate_capabilities?.length ? <p><strong>Candidate BTX capability fit:</strong> {record.candidate_capabilities.map(item => item.name).join(" · ")}. Derived from account-level business-unit context and requires site qualification.</p> : <p><strong>Candidate BTX capability fit:</strong> No supported account-level capability match is available.</p>}
      {score && <ScoreSummary model={score} />}
      {nearest?.distance_miles != null ? <p><strong>Nearest BTX facility:</strong> {nearest.name} · {nearest.distance_miles} miles straight-line</p> : <p>Nearest BTX facility not yet established.</p>}
      {record.governed_next_step && <p><strong>Next:</strong> {record.governed_next_step}</p>}
      {record.federal_opportunities?.slice(0, 2).map((item) => <article className="map-commercial-summary" key={item.assessment_id}><strong>{item.technical.requirement}</strong><span><b>{item.stage.label}:</b> {item.stage.explanation}</span><span><b>Account connection:</b> {item.account_routes?.[0]?.why}</span><span><b>Next:</b> {item.account_routes?.[0]?.governed_action}</span><small>Account-level federal context; not attributed to this site.</small><SupportingEvidence count={item.supporting_evidence_count} investigationKey={`map-federal:${record.account_id}:${item.assessment_id}:${item.assessment_version}`}><p>{item.durability.explanation}</p><ul>{item.technical.remaining_unknowns.map(gap => <li key={gap}>{gap}</li>)}</ul></SupportingEvidence></article>)}
      {record.current_signal_briefs?.slice(0, 2).map((brief) => <article key={brief.context_id ?? brief.id} className="map-commercial-summary"><strong>{brief.headline}</strong><span><b>What happened:</b> {brief.what_happened}</span><span><b>Why it may matter:</b> {brief.why_it_may_matter} <WhyThis>{brief.action_rationale ?? brief.what_to_watch}</WhyThis></span><span><b>Next:</b> {brief.recommended_action ?? "No seller action is supported yet."}</span>{brief.material_uncertainties?.[0] && <span><b>Material uncertainty:</b> {brief.material_uncertainties[0]}</span>}<small>{brief.geographic_scope === "FACILITY" ? brief.canonical_facility_id === record.facility_id ? "Verified site scope" : "Other verified facility context; not attributed to this site" : "Account-wide context; not attributed to this site"}</small><SupportingEvidence count={new Set([...brief.evidence_ids, ...(brief.references ?? []).map(item => item.evidence_id), ...(brief.evidence_package?.commercial_records ?? []).map(item => item.record_id)]).size} investigationKey={`map:${record.facility_id}:${brief.assessment_id ?? brief.id}:${brief.assessment_version ?? 0}`}><section><h4>Program and component evidence</h4><TechnicalDecompositionSection technical={brief.technical_opportunity} /></section><section><h4>Related BTX records</h4><RelatedBtxActivity accountId={record.account_id} records={brief.evidence_package?.commercial_records ?? []} /></section><section><h4>Sources</h4>{brief.references?.map(source => <EvidenceSource key={source.evidence_id} title={source.title} source="Public source" date={source.publication_date ?? undefined} evidenceState="Source reviewed" url={source.url} />)}</section></SupportingEvidence></article>)}
      <SupportingEvidence count={1} investigationKey={`map-workbook:${record.account_id}:${record.facility_id}`}><WorkbookFields key={record.account_id} accountId={record.account_id} /></SupportingEvidence>
    </section>}
    {tab === "COMMERCIAL" && <section role="tabpanel" aria-label="Commercial">
      {record.commercial_briefing ? <><h3>{record.commercial_briefing.summary}</h3><p>{record.commercial_briefing.explanation}</p>{record.commercial_briefing.fulfillment && <div className="map-commercial-summary"><span>Ordered <strong>{record.commercial_briefing.fulfillment.ordered_quantity}</strong></span><span>Shipped <strong>{record.commercial_briefing.fulfillment.shipped_quantity}</strong></span><span>Remaining <strong>{record.commercial_briefing.fulfillment.remaining_quantity}</strong></span><span>Shipped value <strong>{money(record.commercial_briefing.fulfillment.shipped_value_minor, record.commercial_briefing.fulfillment.currency)}</strong></span></div>}<p><strong>Next:</strong> {record.commercial_briefing.next_action}</p></> : <Empty>No linked commercial briefing is available.</Empty>}
      {Boolean(record.commercial_business_unit_ids?.length) && <p><strong>Commercial BU context:</strong> {record.commercial_business_unit_ids?.map((id) => id.replaceAll("-", " ")).join(" · ")}. Account scope, not site qualification.</p>}
      {record.fulfillment_attention && <><p><strong>Fulfillment attention:</strong> {record.fulfillment_attention.states.map((state) => FULFILLMENT_LABELS[state] ?? state).join(" · ")} · {record.fulfillment_attention.as_of}</p><p>Account-level obligations do not establish capacity or qualification at this site.</p></>}
    </section>}
    {tab === "CONTACTS" && <section role="tabpanel" aria-label="Contacts">
      {currentDetail ? currentDetail.public_contacts.length ? <div className="map-contact-list">{currentDetail.public_contacts.map((contact) => <EvidenceSource key={`${contact.name ?? contact.role_family}:${contact.title_or_function}`} title={contact.name ?? contact.role_family} source="Public professional research" date={contact.provenance?.last_verified_at} evidenceState={contact.verification_state} url={contact.source_url} detail={`${contact.title_or_function ?? contact.role_family} · contact candidate only; no meeting or introduction is established.`} />)}</div> : <Empty>No verified public contact is available. Review the account's role targets.</Empty> : <LoadingStatus>Opening contact evidence…</LoadingStatus>}
    </section>}
    {tab === "SOURCES" && <section role="tabpanel" aria-label="Sources">
      {currentDetail ? <>{currentDetail.public_facilities.some((facility) => facility.id === record.facility_id) ? <div className="map-contact-list">{currentDetail.public_facilities.filter((facility) => facility.id === record.facility_id).map((facility) => <EvidenceSource key={facility.id} title={facility.name} source={`${facility.city}, ${facility.region}, ${facility.country}`} evidenceState={facility.verification_state} url={facility.source_url} detail={facility.facility_type} />)}</div> : <Empty>No public facility source matches this selected site ID.</Empty>}<details className="map-record-details"><summary>Location and decision evidence</summary><CanonicalRecord value={{ site: record.location_name ?? record.facility_id, facility_reference: record.facility_id, location_status: record.location_truth_state, commercial_revision: record.commercial_briefing?.revision, score_status: record.score_status, missing_score_inputs: currentDetail.account_attractiveness.missingness, current_intelligence: record.current_signal_briefs, upcoming_intelligence: record.upcoming_signal_briefs }} /></details></> : <LoadingStatus>Opening location and source evidence…</LoadingStatus>}
    </section>}
  </div>;
}
