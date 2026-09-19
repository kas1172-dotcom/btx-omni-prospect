import { useEffect, useState } from "react";
import { api } from "../../api/client";
import type { Account360, Alert, CommandPriorityItem } from "../../types/api";
import { Button, Disclosure, Empty, LoadingStatus, Notice, State } from "../../components/UI";

const money = (value?: number | null, currency = "USD") =>
  value == null
    ? "Unavailable"
    : new Intl.NumberFormat("en-US", {
        style: "currency",
        currency,
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      }).format(value / 100);

const date = (value?: string | null) =>
  value
    ? new Date(value).toLocaleDateString("en-US", { timeZone: "UTC" })
    : "Unassigned";

const label = (value?: string | null) =>
  value
    ? value.replaceAll("_", " ").toLowerCase().replace(/^./, (character) => character.toUpperCase())
    : "Unavailable";

export function CommercialRecoveryBriefing({
  item,
  alert,
  onBack,
  onAccount,
  onAction,
}: {
  item: CommandPriorityItem;
  alert?: Alert;
  onBack: () => void;
  onAccount: (id: string) => void;
  onAction: (alert: Alert) => void;
}) {
  const accountId = item.account_id;
  const [load, setLoad] = useState<{ detail?: Account360; failure?: string; loading: boolean }>({ loading: true });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!accountId) return;
    const controller = new AbortController();
    api.account(accountId, controller.signal)
      .then((detail) => setLoad({ detail, loading: false }))
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setLoad({ failure: error instanceof Error ? error.message : "Commercial context is unavailable.", loading: false });
      });
    return () => controller.abort();
  }, [accountId, attempt]);

  if (load.loading) return <div className="recovery-briefing"><Button variant="ghost" onClick={onBack}>← Back to Today</Button><LoadingStatus>Reconciling the commercial records behind this recovery decision…</LoadingStatus></div>;
  if (load.failure) return <div className="recovery-briefing"><Button variant="ghost" onClick={onBack}>← Back to Today</Button><Notice title="Recovery briefing unavailable" tone="warning"><p>{load.failure}</p><Button variant="secondary" onClick={() => { setLoad({ loading: true }); setAttempt((value) => value + 1); }}>Retry</Button></Notice></div>;

  const detail = load.detail;
  const brief = detail?.commercial_briefing;
  const fulfillment = brief?.fulfillment;
  return (
    <div className="recovery-briefing">
      <div className="recovery-toolbar">
        <Button variant="ghost" onClick={onBack}>← Back to Today</Button>
        <div><State value={item.severity ?? "REVIEW"} /><State value={label(brief?.work_status)} /></div>
      </div>
      <header className="recovery-hero">
        <span className="eyebrow">Internal risk / recovery briefing</span>
        <p>{detail?.account.name ?? detail?.account.legal_name ?? "Customer unavailable"}</p>
        <h1>{brief?.summary ?? item.reason}</h1>
        <p>{brief?.explanation ?? item.reason}</p>
      </header>

      {brief ? <>
        <section className="recovery-metrics" aria-label="Reconciled fulfillment">
          <article><span>Ordered quantity</span><strong>{fulfillment?.ordered_quantity ?? "Unavailable"}</strong><small>{fulfillment?.order_line_id ?? "Order line unavailable"}</small></article>
          <article><span>Shipped quantity</span><strong>{fulfillment?.shipped_quantity ?? "Unavailable"}</strong><small>Shipped {date(fulfillment?.latest_shipped_date)}</small></article>
          <article className="recovery-attention"><span>Remaining quantity</span><strong>{fulfillment?.remaining_quantity ?? "Unavailable"}</strong><small>{label(fulfillment?.state)}</small></article>
          <article><span>Shipped value</span><strong>{money(fulfillment?.shipped_value_minor, fulfillment?.currency)}</strong><small>Order-line value {money(fulfillment?.order_value_minor, fulfillment?.currency)}</small></article>
        </section>

        <div className="recovery-layout">
          <main>
            <section>
              <span className="eyebrow">What happened</span>
              <h2>{brief.summary}</h2>
              <p>{brief.explanation ?? "Review the linked commercial evidence."}</p>
            </section>
            <section>
              <span className="eyebrow">Why it matters</span>
              <h2>Commitment and customer recovery</h2>
              <p>{fulfillment ? `${fulfillment.remaining_quantity} of ${fulfillment.ordered_quantity} units remain against the selected order line. The shipped value is ${money(fulfillment.shipped_value_minor, fulfillment.currency)}; this does not represent the remaining value.` : "Fulfillment quantities are unavailable, so commitment should wait for record reconciliation."}</p>
            </section>
            <section className="recovery-next">
              <span className="eyebrow">Recovery action</span>
              <h2>What should happen next?</h2>
              <p>{brief.next_action}</p>
              <div className="recovery-owner"><span><small>Owner</small><strong>{brief.assigned_owner_id ?? `Unassigned · role ${brief.owner_role_id ?? "unavailable"}`}</strong></span><span><small>Due</small><strong>{date(brief.due_date)}</strong></span></div>
              <Notice tone="warning" title="Proposal not completed">This recovery step is pending. Creating a proposal does not send a message, update HubSpot, or prove buyer acceptance.</Notice>
            </section>
          </main>
          <aside aria-label="Recovery actions and evidence">
            <section>
              <span className="eyebrow">Work state</span>
              <h2>{label(brief.work_status)}</h2>
              <p>{brief.prerequisites?.join(" ") ?? "Assign an owner and verify scope before execution."}</p>
            </section>
            <section className="recovery-actions">
              <span className="eyebrow">Next action</span>
              {alert ? <Button variant="primary" onClick={() => onAction(alert)}>Create action proposal</Button> : <p>No canonical action suggestion is available for this record.</p>}
              {accountId && <Button variant="secondary" onClick={() => onAccount(accountId)}>Open customer record</Button>}
            </section>
            <Disclosure title={`Underlying commercial records · ${brief.evidence_ids.length}`}>
              {brief.evidence_ids.length ? <ul className="recovery-evidence-list">{brief.evidence_ids.map((id) => <li key={id}>{id}</li>)}</ul> : <Empty>No linked record identifiers are available.</Empty>}
            </Disclosure>
          </aside>
        </div>
      </> : <Empty>No canonical commercial briefing is available for this customer.</Empty>}
    </div>
  );
}
