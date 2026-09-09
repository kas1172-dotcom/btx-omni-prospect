import { useEffect, useMemo, useState } from "react";
import { api } from "../../api/client";
import type { Account360, MonitorSignalBrief } from "../../types/api";
import {
  Button,
  Disclosure,
  Empty,
  EvidenceSource,
  Notice,
  State,
} from "../../components/UI";
import { EvidencePassages } from "../../components/EvidencePassages";

const date = (value?: string) =>
  value
    ? new Date(value).toLocaleDateString("en-US", { timeZone: "UTC" })
    : "Unavailable";

const label = (value: string) =>
  value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (character) => character.toUpperCase());

const money = (value?: number | null, currency = "USD") =>
  value == null
    ? "Unavailable"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency,
        maximumFractionDigits: 0,
      }).format(value / 100);

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
  onAccount: (id: string) => void;
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
  const commercial = detail?.customer_360.commercial.records ?? [];
  const contact = detail?.public_contacts[0];
  const facility = detail?.public_facilities[0];
  const confidence = brief.signal_confidence;

  if (accountId && (load.accountId !== accountId || load.loading)) return <BriefingLoading onBack={onBack} />;

  return (
    <div className="intelligence-briefing">
      <div className="intelligence-briefing-toolbar">
        <Button variant="ghost" onClick={onBack}>← Back to Intelligence</Button>
        <div>
          <State value={label(brief.data_mode)} />
          <State value={label(brief.freshness)} />
        </div>
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
            <p>{brief.why_it_may_matter}</p>
            {brief.seller_summary !== brief.why_it_may_matter && <p>{brief.seller_summary}</p>}
          </section>

          <section>
            <div className="section-heading">
              <div>
                <span className="eyebrow">Canonical customer context</span>
                <h2>{isProspect ? "Component research" : "Components and BTX business units"}</h2>
              </div>
            </div>
            <p className="intelligence-context-qualification">These records provide account context only. They do not establish that this public event applies to a BTX-supplied component, program, or site.</p>
            {components.length ? (
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

          {!isProspect && (
            <section>
              <span className="eyebrow">Existing commercial context</span>
              <h2>BTX account context</h2>
              {commercial.length ? (
                <div className="intelligence-commercial-grid">
                  {commercial.map((record) => (
                    <article key={record.business_unit ?? record.id}>
                      <strong>{record.business_unit ?? "Business unit unavailable"}</strong>
                      <span>TTM revenue {money(record.ttm_revenue_minor, record.currency)}</span>
                      <span>TTM bookings {money(record.ttm_bookings_minor, record.currency)}</span>
                    </article>
                  ))}
                </div>
              ) : <Empty>No linked commercial records are available.</Empty>}
            </section>
          )}

          <section className="intelligence-next-conversation">
            <span className="eyebrow">Next conversation</span>
            <h2>What should the seller do next?</h2>
            <p>{brief.recommended_action ?? brief.what_to_watch}</p>
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
            {account && <Button variant="secondary" onClick={() => onAccount(account.id)}>Open full profile</Button>}
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
            {brief.recommended_action && accountId && <Button variant="secondary" onClick={() => onCreateAction(brief)}>Create action proposal</Button>}
            <p>{accountId ? "The subject already exists in Customers & Prospects; no duplicate account will be created." : "Account creation is unavailable until canonical identity resolution succeeds."}</p>
          </section>
        </aside>
      </div>

      <Disclosure title="Evidence and operational details">
        <div className="intelligence-evidence">
          <p><b>Watch next:</b> {brief.what_to_watch}</p>
          <p><b>Collected:</b> {date(brief.collection_timestamp)} · <b>Resolution:</b> {label(brief.resolution_state)} · <b>Publication:</b> {label(brief.seller_promotion_state)}</p>
          <EvidenceSource title={brief.headline} source={brief.source_system} date={brief.publication_timestamp} evidenceState={brief.resolution_state} validationState={brief.seller_promotion_state} url={brief.source_url} detail={`Evidence IDs: ${brief.evidence_ids.length ? brief.evidence_ids.join(", ") : "Unavailable"}`} />
          {brief.data_mode === "LIVE_PUBLIC" && <EvidencePassages eventId={brief.id} />}
        </div>
      </Disclosure>
    </div>
  );
}
