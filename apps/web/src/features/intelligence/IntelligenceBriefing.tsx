import { useEffect, useMemo, useState } from "react";
import { api } from "../../api/client";
import type { Account360, MonitorSignalBrief, OmniAssessmentSelection } from "../../types/api";
import { Button, Empty, EvidenceSource, Notice, State } from "../../components/UI";
import { EvidencePassages } from "../../components/EvidencePassages";
import { TechnicalDecompositionSection } from "../../components/TechnicalDecompositionSection";
import { SupportingEvidence, WhyThis } from "../../components/SupportingEvidence";
import { RelatedBtxActivity } from "../../components/RelatedBtxActivity";

const date = (value?: string) =>
  value
    ? new Date(value).toLocaleDateString("en-US", { timeZone: "UTC" })
    : "Unavailable";

const label = (value: string) =>
  value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (character) => character.toUpperCase());

function BriefingLoading({ onBack }: { onBack: () => void }) {
  return (
    <div className="intelligence-briefing">
      <Button variant="ghost" onClick={onBack}>← Back to Intelligence</Button>
      <div className="intelligence-briefing-loading" role="status" aria-live="polite">
        <span className="ui-skeleton" />
        <span className="ui-skeleton" />
        <span className="ui-skeleton" />
        <span>Loading canonical customer context…</span>
      </div>
    </div>
  );
}

export function IntelligenceBriefing({
  brief,
  onBack,
  onAccount,
  onCreateAction,
  onUseInOmni,
}: {
  brief: MonitorSignalBrief;
  onBack: () => void;
  onAccount: (id: string, assessment?: OmniAssessmentSelection) => void;
  onCreateAction: (brief: MonitorSignalBrief) => void;
  onUseInOmni: (brief: MonitorSignalBrief) => void;
}) {
  const accountId = brief.canonical_account_ids[0];
  const [load, setLoad] = useState<{ accountId?: string; detail?: Account360; failure?: string; loading: boolean }>(() => ({ accountId, loading: Boolean(accountId) }));
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!accountId) return;
    const controller = new AbortController();
    api.account(accountId, controller.signal)
      .then((detail) => setLoad({ accountId, detail, loading: false }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setLoad({ accountId, failure: error instanceof Error ? error.message : "Customer context is unavailable.", loading: false });
        }
      });
    return () => controller.abort();
  }, [accountId, attempt]);

  const detail = load.accountId === accountId ? load.detail : undefined;
  const failure = load.accountId === accountId ? load.failure : undefined;

  const account = detail?.account;
  const isProspect = account
    ? ["PROSPECT", "TARGET", "PUBLIC_MARKET"].includes(account.relationship)
    : false;
  const businessUnits = useMemo(
    () => new Map((detail?.customer_360.business_units ?? []).map((unit) => [unit.id, unit.name ?? unit.id])),
    [detail],
  );
  const components = detail?.customer_360.components ?? [];
  const contact = detail?.public_contacts[0];
  const facility = detail?.public_facilities[0];
  const confidence = brief.signal_confidence;
  const eventRecords = brief.evidence_package?.commercial_records ?? [];
  const eventFits = brief.evidence_package?.capability_fit ?? [];

  if (accountId && (load.accountId !== accountId || load.loading)) return <BriefingLoading onBack={onBack} />;

  return (
    <div className="intelligence-briefing">
      <div className="intelligence-briefing-toolbar">
        <Button variant="ghost" onClick={onBack}>← Back to Intelligence</Button>
        <span className="muted">Public intelligence assessment</span>
      </div>
      {failure && (
        <Notice title="Customer context could not be loaded" tone="warning">
          <p>{failure}</p>
          <Button variant="secondary" onClick={() => {
            setLoad({ accountId, loading: true });
            setAttempt((value) => value + 1);
          }}>Retry</Button>
        </Notice>
      )}
      <header className="intelligence-briefing-hero">
        <span className="eyebrow">{isProspect ? "New prospect briefing" : "Customer intelligence briefing"}</span>
        <p className="intelligence-briefing-account">{account?.name ?? account?.legal_name ?? "Unresolved public subject"}</p>
        <h1>{brief.headline}</h1>
        <p className="intelligence-briefing-lede">{brief.what_happened}</p>
        <div className="intelligence-briefing-source-line">
          <span>{brief.source_system}</span>
          <span>Published {date(brief.publication_timestamp)}</span>
          {brief.relevant_event_timestamp && <span>Event {date(brief.relevant_event_timestamp)}</span>}
          {brief.source_url && <a href={brief.source_url} target="_blank" rel="noreferrer">Read source ↗</a>}
        </div>
      </header>

      <div className="intelligence-briefing-layout">
        <main className="intelligence-briefing-main">
          <section>
            <span className="eyebrow">Why this matters</span>
            <h2>Commercial relevance</h2>
            <p>{brief.why_it_may_matter} <WhyThis>{brief.action_rationale ?? brief.what_to_watch}</WhyThis></p>
            {!!brief.material_uncertainties?.length && <p><strong>Material uncertainty:</strong> {brief.material_uncertainties[0]}</p>}
          </section>
          <SupportingEvidence count={new Set([...brief.evidence_ids, ...(brief.references ?? []).map(item => item.evidence_id), ...eventRecords.map(item => item.record_id)]).size} investigationKey={`intelligence:${brief.assessment_id ?? brief.id}:${brief.assessment_version ?? 0}`}>
          <section>
            <div className="section-heading">
              <div>
                <span className="eyebrow">Canonical customer context</span>
                <h2>{isProspect ? "Component research" : "Components and BTX business units"}</h2>
              </div>
            </div>
            <p className="intelligence-context-qualification">{brief.evidence_package?.commercial_record_scope === "EXACT_PROGRAM" ? "These records share the resolved program scope; technical qualification remains a separate decision." : "Account context records do not establish that this public event applies to a BTX-supplied component, program, or site."}</p>
            {brief.technical_opportunity?.components?.length ? (
              <TechnicalDecompositionSection technical={brief.technical_opportunity} />
            ) : eventFits.length ? (
              <div className="intelligence-component-table" role="table" aria-label="Event-specific capability fit">
                <div role="row" className="intelligence-component-head"><span role="columnheader">Public candidate</span><span role="columnheader">Controlled component</span><span role="columnheader">BTX business unit</span><span role="columnheader">State</span></div>
                {eventFits.map((fit, index) => <div role="row" key={`${fit.candidate}:${index}`}><strong role="cell">{fit.candidate ?? "Candidate unavailable"}</strong><span role="cell">{fit.component ?? "Not established"}</span><span role="cell">{fit.business_unit ?? "Review required"}</span><State value={label(fit.status ?? "UNAVAILABLE")} /></div>)}
              </div>
            ) : components.length ? (
              <div className="intelligence-component-table" role="table" aria-label="Components and applicable business units">
                <div role="row" className="intelligence-component-head">
                  <span role="columnheader">Component</span>
                  <span role="columnheader">Program</span>
                  <span role="columnheader">BTX business unit</span>
                  <span role="columnheader">Evidence</span>
                </div>
                {components.slice(0, 8).map((component) => (
                  <div role="row" key={component.id}>
                    <strong role="cell">{component.name ?? component.id}</strong>
                    <span role="cell">{component.program_id ?? "Not linked"}</span>
                    <span role="cell">{component.business_unit_ids?.map((id) => businessUnits.get(id) ?? id).join(", ") || "Review required"}</span>
                    <State value={label(component.evidence_state ?? "UNAVAILABLE")} />
                  </div>
                ))}
              </div>
            ) : (
              <Empty>No canonical component association is available for this public signal. Research remains the next step.</Empty>
            )}
          </section>

          <section>
              <span className="eyebrow">Existing commercial context</span>
              <h2>Related BTX activity to review</h2>
              {accountId && !isProspect ? <RelatedBtxActivity accountId={accountId} records={eventRecords} /> : <Empty>{isProspect ? "No confirmed BTX commercial history is available for this Prospect." : "No linked commercial records are available."}</Empty>}
          </section>
          <section className="intelligence-evidence"><h2>Sources</h2><EvidenceSource title={brief.headline} source={brief.source_system} date={brief.publication_timestamp} evidenceState="Source reviewed" url={brief.source_url} detail="Primary public source for this assessment" />{brief.data_mode === "LIVE_PUBLIC" && <EvidencePassages eventId={brief.id} />}</section>
          </SupportingEvidence>

          <section className="intelligence-next-conversation">
            <span className="eyebrow">Next conversation</span>
            <h2>What should the seller do next?</h2>
            <p>{brief.recommended_action ?? brief.what_to_watch}</p>
            {brief.action_rationale && <p>{brief.action_rationale}</p>}
            {!isProspect && (
              <div>
                <strong>Confirm applicability before acting</strong>
                <ul>
                  <li>Which customer site, program, or component does this notice actually affect?</li>
                  <li>What source-backed evidence connects the public event to the current BTX scope?</li>
                  <li>Does the current deterministic delivery, qualification, or risk decision constrain the action?</li>
                </ul>
              </div>
            )}
          </section>
        </main>

        <aside className="intelligence-briefing-sidebar" aria-label="Briefing decisions and actions">
          <section>
            <span className="eyebrow">Why it matters</span>
            <p>{brief.why_it_may_matter}</p>
          </section>
          <section>
            <span className="eyebrow">Customer / prospect</span>
            <h2>{account?.name ?? account?.legal_name ?? "Canonical identity pending"}</h2>
            <p>{account ? label(account.relationship) : "This public subject is not linked to a canonical account."}</p>
            {facility && <p>{facility.name} · {facility.city}, {facility.region}</p>}
            {account && <Button variant="secondary" onClick={() => onAccount(account.id, brief.assessment_id && brief.assessment_version ? { assessment_id: brief.assessment_id, assessment_version: brief.assessment_version, event_id: brief.id, account_id: account.id } : undefined)}>Open full profile</Button>}
          </section>
          <section>
            <span className="eyebrow">Relevant contact evidence</span>
            {contact ? (
              <EvidenceSource
                title={contact.name ?? contact.role_family}
                source="Public professional research"
                date={contact.provenance?.last_verified_at}
                evidenceState={contact.verification_state}
                url={contact.source_url}
                detail={`${contact.title_or_function ?? contact.role_family} · role candidate only; no introduction is established.`}
              />
            ) : <p>No verified contact is available. Role target: {account?.contact_role_families?.[0] ?? "procurement or engineering"}.</p>}
          </section>
          <section>
            <span className="eyebrow">Applicable decision</span>
            <h2>Signal confidence</h2>
            <strong className="intelligence-score">{confidence?.score == null ? "More evidence needed" : `${confidence.score}/100`}</strong>
            <p>{confidence ? `${confidence.data_coverage.present} of ${confidence.data_coverage.applicable} applicable inputs supported.` : "No deterministic signal-confidence decision is available."}</p>
          </section>
          <section className="intelligence-briefing-actions">
            <span className="eyebrow">Pursuit actions</span>
            <Button variant="primary" onClick={() => onUseInOmni(brief)}>Ask Omni about this signal</Button>
            {brief.recommended_action && accountId && brief.assessment_id && <Button variant="secondary" onClick={() => onCreateAction(brief)}>Create action proposal</Button>}
            {brief.recommended_action && accountId && !brief.assessment_id && <p>The assessment is awaiting durable publication before an action proposal can be created.</p>}
            <p>{accountId ? "The subject already exists in Customers & Prospects; no duplicate account will be created." : "Account creation is unavailable until canonical identity resolution succeeds."}</p>
          </section>
        </aside>
      </div>

    </div>
  );
}
