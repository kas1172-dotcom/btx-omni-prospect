import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api/client";
import {
  Button,
  Drawer,
  Empty,
  LoadingStatus,
  Panel,
  SearchInput,
  SelectInput,
  StatusBadge,
  StatusMessage,
  Textarea,
  TextInput,
} from "../../components/UI";
import type {
  Account,
  Account360,
  CommunicationDraft,
  CommunicationHistoryEvent,
  Principal,
} from "../../types/api";
import "./communications.css";
import { actorDisplayName, presentationLabel } from "../../components/presentation";

import { canSend, defaultView, deliveryAvailable, inView, queueViews, viewCounts, workflowSteps, type DeliveryState, type QueueView } from "./communicationModel";

type Props = {
  accounts: Account[];
  principal?: Principal;
  items: CommunicationDraft[];
  delivery?: DeliveryState;
  onDelivery: (delivery: DeliveryState) => void;
  accountDetail?: Account360;
  listState: 'loading' | 'loaded' | 'error';
  onRetry: () => void;
  onItem: (item: CommunicationDraft) => void;
  onAccount: (id: string) => void;
};
const humanize = (value: string) => presentationLabel(value, "communication");

export function Communications({
  accounts,
  principal,
  items,
  delivery,
  onDelivery,
  accountDetail,
  listState,
  onRetry,
  onItem,
  onAccount,
}: Props) {
  const [query, setQuery] = useState("");
  const [chosenView, setChosenView] = useState<QueueView>();
  const view = chosenView ?? defaultView(principal);
  const counts = viewCounts(items, principal);
  const createButton = useRef<HTMLButtonElement>(null);
  const [cachedAccount, setCachedAccount] = useState<Account360>();
  const [selectedId, setSelectedId] = useState<string>();
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<CommunicationDraft>();
  const [notice, setNotice] = useState("");
  const [expandedHistoryId, setExpandedHistoryId] = useState<string>();
  const [historyRefresh, setHistoryRefresh] = useState(0);
  const [loadedHistory, setLoadedHistory] = useState<{ id: string; version: number; events: CommunicationHistoryEvent[]; error: boolean }>();
  const accountById = useMemo(
    () => new Map(accounts.map((item) => [item.id, item])),
    [accounts],
  );
  const customer = useCallback(
    (id: string) =>
      accountById.get(id)?.name ??
      accountById.get(id)?.legal_name ??
      "Unknown Customer",
    [accountById],
  );
  const visible = useMemo(
    () =>
      items.filter(
        (item) =>
          `${customer(item.account_id)} ${item.subject} ${item.body}`
            .toLowerCase()
            .includes(query.toLowerCase()) &&
          inView(item, view, principal),
      ),
    [customer, items, query, view, principal],
  );
  const selected = visible.find((item) => item.id === selectedId) ?? visible[0];
  const historyId = selected?.id;
  const historyVersion = selected?.version;
  const currentHistory = loadedHistory?.id === historyId && loadedHistory?.version === historyVersion ? loadedHistory : undefined;
  useEffect(() => {
    if (!historyId || historyVersion === undefined) return;
    const controller = new AbortController();
    void api
      .communicationHistory(historyId, controller.signal)
      .then((result) => { if (!controller.signal.aborted) setLoadedHistory({ id: historyId, version: historyVersion, events: result.events, error: false }); })
      .catch(() => { if (!controller.signal.aborted) setLoadedHistory({ id: historyId, version: historyVersion, events: [], error: true }); });
    return () => controller.abort();
  }, [historyId, historyVersion, historyRefresh]);
  const history = [...(currentHistory?.events ?? [])].sort((a, b) => Date.parse(b.occurred_at) - Date.parse(a.occurred_at) || b.id - a.id);
  const showAllHistory = expandedHistoryId === selected?.id;
  const detailAccount = cachedAccount?.account.id === selected?.account_id ? cachedAccount : accountDetail?.account.id === selected?.account_id ? accountDetail : undefined;
  const startDraft = () => { setEditing(undefined); setEditorOpen(true); };
  const closeEditor = () => {
    setEditorOpen(false);
    // A saved edit can leave the current queue; give focus a stable fallback.
    requestAnimationFrame(() => {
      if (document.activeElement === document.body) createButton.current?.focus();
    });
  };
  const review = async (decision: "APPROVED" | "REJECTED") => {
    if (!selected) return;
    try {
      onItem(await api.approveCommunication(selected.id, decision, selected.version));
      setSelectedId(selected.id);
      setChosenView(decision === "APPROVED" ? "Approved" : "Rejected");
      setNotice(
        `Draft ${decision.toLowerCase()} by human review. No message was sent.`,
      );
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Review failed.");
    }
  };
  const preview = async () => {
    if (!selected) return;
    try {
      const result = await api.previewCommunication(selected.id);
      setNotice(result.message);
      setHistoryRefresh(value => value + 1);
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Preview unavailable.",
      );
    }
  };
  const send = async () => {
    if (!selected || listState !== "loaded" || !canSend(selected, delivery)) return;
    try {
      onItem(
        await api.sendCommunication(
          selected.id,
          `human-confirm-${selected.id}`,
          selected.version,
        ),
      );
      setNotice("Delivery confirmed.");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Delivery blocked.");
    }
  };
  return (
    <div className="surface communications-surface">
      <header className="page-title communications-header">
        <div>
          <span className="eyebrow">Draft and approval workflow</span>
          <h1>Communications</h1>
          <p>
            Trigger → Draft → Human review → Approved send. Gemini can assist
            with words, never authorization or delivery.
          </p>
        </div>
        <Button
          variant="primary"
          size="touch"
          ref={createButton}
          onClick={startDraft}
        >
          Create draft
        </Button>
      </header>
      <div className="communications-views" role="group" aria-label="Communication views">
        {queueViews.map(name => <Button key={name} aria-pressed={view === name} onClick={() => { setChosenView(name); setSelectedId(undefined); }}>
          {name} <span className="communication-count">{listState === 'loaded' ? counts[name] : '—'}</span>
        </Button>)}
      </div>
      <p className="communication-notice" role="status" aria-live="polite">{notice}</p>
      <div className="communications-toolbar">
        <SearchInput aria-label="Search communications" placeholder="Search Customer or draft" value={query} onChange={event => setQuery(event.target.value)} />
        {query && <Button variant="ghost" onClick={() => setQuery("")}>Clear search</Button>}
      </div>
      {listState === 'loading' && <LoadingStatus>Loading communications…</LoadingStatus>}
      {listState === 'error' && <StatusMessage state="error" title="Communications could not be loaded" action={<Button onClick={onRetry}>Retry communications</Button>}>
        {items.length ? 'Previously loaded drafts remain visible. Refresh before sending.' : 'Try again to open your drafts.'}
      </StatusMessage>}
      <div className="communications-workbench">
        <Panel
          title="Customer communications"
          action={
            <span className="panel-kicker">{visible.length} visible</span>
          }
        >
          <div className="communication-list" role="listbox" aria-label="Customer communications">
            {visible.length ? (
              visible.map((item, index) => (
                <button
                  type="button"
                  role="option"
                  key={item.id}
                  className={`communication-row ${selected?.id === item.id ? "selected" : ""}`}
                  aria-selected={selected?.id === item.id}
                  tabIndex={selected?.id === item.id ? 0 : -1}
                  onKeyDown={event => {
                    const next = event.key === 'ArrowDown' ? Math.min(index + 1, visible.length - 1) : event.key === 'ArrowUp' ? Math.max(index - 1, 0) : event.key === 'Home' ? 0 : event.key === 'End' ? visible.length - 1 : undefined;
                    if (next !== undefined) {
                      event.preventDefault();
                      setSelectedId(visible[next].id);
                      event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="option"]')[next]?.focus();
                    } else if (event.key === 'Enter') { event.preventDefault(); setSelectedId(item.id); }
                  }}
                  onClick={() => setSelectedId(item.id)}
                >
                  <span>
                    <strong>{customer(item.account_id)}</strong>
                    <small>{item.subject}</small>
                  </span>
                  <span>
                    <StatusBadge value={item.status} kind="action" />
                    <StatusBadge value={item.approval_status} kind="action" />
                  </span>
                  <small>
                    {item.recipients.length
                      ? `${item.recipients.length} verified recipient(s)`
                      : "Recipient unavailable"}
                  </small>
                </button>
              ))
            ) : (
              listState === 'loaded' ? <StatusMessage title={items.length ? 'No matching drafts' : 'No drafts yet'} action={
                items.length ? <Button onClick={() => { setQuery(""); setChosenView("All"); }}>Show all drafts</Button> : <Button onClick={startDraft}>Create your first draft</Button>
              }>{items.length ? 'Try another view or clear your search.' : 'Create a draft to prepare a Customer communication for review.'}</StatusMessage> : null
            )}
          </div>
        </Panel>
        <aside>
          {selected ? (
            <Panel
              title="Draft detail"
              action={<StatusBadge value={selected.status} kind="action" />}
            >
              <div className="communication-detail">
                <span className="eyebrow">{customer(selected.account_id)}</span>
                <h2>{selected.subject}</h2>
                <ol className="communication-stepper" aria-label="Communication workflow">
                  {workflowSteps(selected, delivery).map(step => <li key={step.label} data-complete={step.complete}>
                    <strong>{step.label}</strong><span>{step.complete ? '✓ ' : ''}{step.detail}</span>
                  </li>)}
                </ol>
                <div className="communication-reading">
                  <p className="communication-body">{selected.body}</p>
                  <DraftContext draft={selected} customer={customer(selected.account_id)} accountDetail={detailAccount} onAccount={() => onAccount(selected.account_id)} />
                </div>
                <dl>
                  <div>
                    <dt>Channel</dt>
                    <dd>{humanize(selected.channel)}</dd>
                  </div>
                  <div>
                    <dt>Recipient</dt>
                    <dd>
                      {selected.recipients.join(", ") ||
                        "Unavailable · no verified professional email"}
                    </dd>
                  </div>
                  <div>
                    <dt>Approval</dt>
                    <dd>{humanize(selected.approval_status)}</dd>
                  </div>
                  <div>
                    <dt>Creator</dt>
                    <dd>{actorDisplayName(selected.created_by, principal)}</dd>
                  </div>
                </dl>
                <div className="card-actions">
                  <Button onClick={async () => {
                    const id = selected.id;
                    try {
                      const result = await api.communications();
                      const saved = result.items.find(item => item.id === id);
                      if (!saved) throw new Error('This communication is no longer available in your permitted work.');
                      onItem(saved);
                      onDelivery(result.delivery);
                      setNotice('Saved communication refreshed. Review its content before taking another action.');
                    } catch (error) { setNotice(error instanceof Error ? error.message : 'Refresh failed.'); }
                  }}>Refresh saved communication</Button>
                  <Button
                    disabled={selected.status === "SENT" || selected.status === "CANCELED"}
                    onClick={() => {
                      setEditing(selected);
                      setEditorOpen(true);
                    }}
                  >
                    Edit draft
                  </Button>
                  <Button variant="ghost" onClick={() => void preview()}>
                    Preview delivery
                  </Button>
                </div>
                {selected.approval_status === "PENDING" && selected.status === "DRAFT" && (
                  <Panel title="Human review" variant="subdued">
                    {principal?.role === "MANAGER" ? (
                      <div className="card-actions">
                        <Button
                          variant="primary"
                          onClick={() => void review("APPROVED")}
                        >
                          Approve
                        </Button>
                        <Button
                          variant="destructive"
                          onClick={() => void review("REJECTED")}
                        >
                          Reject
                        </Button>
                      </div>
                    ) : (
                      <p>
                        Manager review is required. Opening or generating this
                        draft does not approve it.
                      </p>
                    )}
                  </Panel>
                )}
                <footer className="communication-delivery">
                  <p className="muted" id="communication-delivery-note">
                    {delivery?.state === "NOT_CONFIGURED" ? "Delivery is not configured for this environment" : delivery?.label || "Delivery availability is not confirmed"}
                  </p>
                  {selected.status === "READY" && <>
                    {deliveryAvailable(delivery) && <p>Review this draft and confirm before sending.{!selected.recipients.length && ' A verified recipient is required.'}</p>}
                    <Button variant="primary" aria-describedby="communication-delivery-note" disabled={listState !== 'loaded' || !canSend(selected, delivery)} onClick={() => void send()}>Confirm send</Button>
                  </>}
                </footer>
                <section aria-label="Audit history" className="communication-audit">
                  <header><h3>Audit history</h3><Button variant="ghost" onClick={() => { setLoadedHistory(undefined); setHistoryRefresh(value => value + 1); }}>Refresh communication history</Button></header>
                  {!currentHistory && <LoadingStatus>Opening this communication’s history…</LoadingStatus>}
                  {currentHistory?.error && <p role="alert">History could not be loaded. Refresh communication history to try again.</p>}
                  {currentHistory && !currentHistory.error && !history.length && <Empty>No history recorded.</Empty>}
                  <ol className="communication-history">
                    {(showAllHistory ? history : history.slice(0, 5)).map(event => <li key={event.id}>
                      <strong>{humanize(event.event)}</strong>
                      <span title={`Actor ID ${event.actor_id}`}>{actorDisplayName(event.actor_id, principal)} · <time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleString()}</time></span>
                    </li>)}
                  </ol>
                  {history.length > 5 && <Button aria-expanded={showAllHistory} onClick={() => setExpandedHistoryId(showAllHistory ? undefined : selected?.id)}>
                    {showAllHistory ? 'Show latest 5' : `Show all ${history.length} entries`}
                  </Button>}
                </section>
              </div>
            </Panel>
          ) : (
            <Panel title="Draft detail">
              <Empty>Select a draft.</Empty>
            </Panel>
          )}
        </aside>
      </div>
      <CommunicationEditor
        key={`${editorOpen}-${editing?.id ?? "new"}`}
        open={editorOpen}
        draft={editing}
        accounts={accounts}
        onClose={closeEditor}
        onAccountLoaded={setCachedAccount}
        onDelivery={onDelivery}
        onAccount={onAccount}
        onSaved={(draft) => {
          onItem(draft);
          setSelectedId(draft.id);
          if (!inView(draft, view, principal)) setChosenView("All");
          if (!`${customer(draft.account_id)} ${draft.subject} ${draft.body}`.toLowerCase().includes(query.toLowerCase())) setQuery("");
          closeEditor();
          setNotice(
            "Draft saved. It remains unsent and requires human review.",
          );
        }}
      />
    </div>
  );
}

function CommunicationEditor({
  open,
  draft,
  accounts,
  onClose,
  onSaved,
  onAccountLoaded,
  onDelivery,
  onAccount,
}: {
  open: boolean;
  draft?: CommunicationDraft;
  accounts: Account[];
  onClose: () => void;
  onSaved: (draft: CommunicationDraft) => void;
  onAccountLoaded: (detail: Account360) => void;
  onDelivery: (delivery: DeliveryState) => void;
  onAccount: (id: string) => void;
}) {
  const [accountSelection, setAccountId] = useState(draft?.account_id);
  const [baseDraft, setBaseDraft] = useState(draft);
  const [savedComparison, setSavedComparison] = useState<CommunicationDraft>();
  const accountId = accountSelection ?? accounts[0]?.id ?? '';
  const [subject, setSubject] = useState(draft?.subject ?? "");
  const [body, setBody] = useState(draft?.body ?? "");
  const [recipients, setRecipients] = useState<string[]>(
    draft?.recipients ?? [],
  );
  const [loadedAccount, setLoadedAccount] = useState<{ id: string; detail: Account360 }>();
  const accountDetail = loadedAccount?.id === accountId ? loadedAccount.detail : undefined;
  const saveInFlight = useRef(false);
  const createRetry = useRef<{ signature: string; key: string } | undefined>(undefined);
  const [instruction, setInstruction] = useState(
    "Make this concise and evidence-led.",
  );
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  useEffect(() => {
    if (!open || !accountId) return;
    const controller = new AbortController();
    void api
      .account(accountId, controller.signal)
      .then(detail => { if (!controller.signal.aborted) { setLoadedAccount({ id: accountId, detail }); onAccountLoaded(detail); } })
      .catch(() => { if (!controller.signal.aborted) setLoadedAccount(undefined); });
    return () => controller.abort();
  }, [open, accountId, onAccountLoaded]);
  const account = accounts.find((item) => item.id === accountId);
  const customer = account?.name ?? account?.legal_name ?? "Customer";
  const verifiedRecipients = useMemo(
    () =>
      accountDetail?.public_contacts
        .filter((contact) => contact.public_email)
        .map((contact) => ({
          email: contact.public_email as string,
          label: contact.name
            ? `${contact.name} · ${contact.public_email}`
            : (contact.public_email as string),
        })) ?? [],
    [accountDetail],
  );
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    if (saveInFlight.current) return;
    if (!accountId || !accounts.some(item => item.id === accountId)) {
      setError('Choose an available Customer before saving. Your message is retained.');
      return;
    }
    if (!subject.trim() || !body.trim()) {
      setError("Subject and message are required.");
      return;
    }
    const signature = JSON.stringify([accountId, subject, body, recipients]);
    if (createRetry.current?.signature !== signature) createRetry.current = { signature, key: crypto.randomUUID() };
    saveInFlight.current = true;
    setWorking(true);
    try {
      const result = draft
        ? await api.editCommunication(draft.id, { subject, body, recipients, expected_version: baseDraft!.version })
        : await api.createCommunication({
            account_id: accountId,
            subject,
            body,
            recipients,
            idempotency_key: createRetry.current.key,
          });
      onSaved(result);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Draft could not be saved.",
      );
    } finally {
      saveInFlight.current = false;
      setWorking(false);
    }
  };
  const assist = async () => {
    if (saveInFlight.current) return;
    saveInFlight.current = true;
    setWorking(true);
    try {
      const result = draft
        ? await api.assistCommunication(draft.id, instruction, baseDraft!.version)
        : await api.assistNewCommunication({
            account_id: accountId,
            instruction,
            subject,
            body,
          });
      setSubject(result.proposal.subject);
      setBody(result.proposal.body);
      setError(result.message);
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Draft assistance unavailable.",
      );
    } finally {
      saveInFlight.current = false;
      setWorking(false);
    }
  };
  const refreshSaved = async () => {
    if (!draft || saveInFlight.current) return;
    saveInFlight.current = true;
    setWorking(true);
    try {
      const result = await api.communications();
      const saved = result.items.find(item => item.id === draft.id);
      if (!saved) throw new Error('This draft is no longer available in your permitted work. Your local text is retained.');
      setSavedComparison(saved);
      onDelivery(result.delivery);
      setError('Compare the saved version below. Your local text and recipients have not changed.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Saved version could not be refreshed.');
    } finally {
      saveInFlight.current = false;
      setWorking(false);
    }
  };
  const unsaved = subject !== (baseDraft?.subject ?? "") || body !== (baseDraft?.body ?? "") ||
    JSON.stringify(recipients) !== JSON.stringify(baseDraft?.recipients ?? []) ||
    Boolean(accountSelection && accountSelection !== (baseDraft?.account_id ?? accounts[0]?.id));
  return (
    <Drawer
      open={open}
      onClose={onClose}
      titleId="communication-editor-title"
      className="communication-editor"
    >
      <form onSubmit={(event) => void save(event)}>
        <header>
          <div>
            <span className="eyebrow">Human-controlled draft</span>
            <h2 id="communication-editor-title">
              {draft ? "Edit communication" : "Create communication"}
            </h2>
          </div>
          <Button type="button" variant="ghost" onClick={onClose}>
            Close
          </Button>
        </header>
        <p className="communication-save-state" aria-live="polite">{unsaved ? 'Unsaved changes' : draft ? 'Saved draft · no changes' : 'New draft · not saved'}</p>
        <SelectInput
          label="Customer"
          value={accountId}
          disabled={Boolean(draft) || working}
          onChange={(event) => {
            setAccountId(event.target.value);
            setRecipients([]);
          }}
        >
          {accounts.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name ?? item.legal_name}
            </option>
          ))}
        </SelectInput>
        <TextInput
          label="Subject"
          disabled={working}
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
        />
        <Textarea
          label="Message"
          disabled={working}
          rows={8}
          value={body}
          onChange={(event) => setBody(event.target.value)}
        />
        {verifiedRecipients.length ? (
          <SelectInput
            label="Verified professional recipient"
            disabled={working}
            value={recipients[0] ?? ""}
            onChange={(event) =>
              setRecipients(event.target.value ? [event.target.value] : [])
            }
          >
            <option value="">No recipient yet</option>
            {verifiedRecipients.map((recipient) => (
              <option key={recipient.email} value={recipient.email}>
                {recipient.label}
              </option>
            ))}
          </SelectInput>
        ) : (
          <Panel title="Recipient" variant="subdued">
            <p>{`No verified deliverable email is currently available for ${customer}. A Customer-specific draft can still be reviewed.`}</p>
          </Panel>
        )}
        <DraftContext draft={{ trigger: baseDraft?.trigger, evidence_ids: baseDraft?.evidence_ids ?? [], recipients }} customer={customer} accountDetail={accountDetail} onAccount={accountId ? () => { onClose(); onAccount(accountId); } : undefined} />
        <Panel title="Gemini draft assistance" variant="subdued">
            {draft && <>
              <p>Editing saved version {baseDraft?.version}. An edit requires fresh human review.</p>
              <Button type="button" disabled={working} onClick={() => void refreshSaved()}>Refresh saved version for comparison</Button>
              {savedComparison && <section aria-label="Saved communication comparison">
                <p>Saved version {savedComparison.version} · {humanize(savedComparison.approval_status)} · {humanize(savedComparison.status)}</p>
                <h3>{savedComparison.subject}</h3><p style={{ whiteSpace: 'pre-wrap' }}>{savedComparison.body}</p>
                <p>Recipients: {savedComparison.recipients.join(', ') || 'None'}</p>
                <Button type="button" disabled={working} onClick={() => { setBaseDraft(savedComparison); setSavedComparison(undefined); setError('Saved version reviewed. Your local edits remain unchanged; Save is still a separate action.'); }}>Use this reviewed version for my next save</Button>
              </section>}
            </>}
            <TextInput
              label="Drafting instruction"
              disabled={working}
              value={instruction}
              onChange={(event) => setInstruction(event.target.value)}
            />
            <Button
              type="button"
              onClick={() => void assist()}
              disabled={working}
            >
              {draft ? "Propose revision" : "Propose draft"}
            </Button>
            <p className="muted">
              Gemini proposes words only. Review the proposal and save it; it
              cannot select recipients, approve, or send.
            </p>
          </Panel>
        {error && (
          <p role="status" className="notice">
            {error}
          </p>
        )}
        {(baseDraft?.approval_status === "APPROVED" || savedComparison?.approval_status === "APPROVED") && <p className="notice">Saving changes will remove approval and require review again.</p>}
        <footer>
          <Button type="button" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={working} disabled={working || !accountId}>
            {draft ? "Save changes" : "Save draft"}
          </Button>
        </footer>
      </form>
    </Drawer>
  );
}

function DraftContext({ draft, customer, accountDetail, onAccount }: {
  draft: Pick<CommunicationDraft, 'trigger' | 'evidence_ids' | 'recipients'>;
  customer: string;
  accountDetail?: Account360;
  onAccount?: () => void;
}) {
  return <section className="communication-context" aria-label="Why this draft exists">
    <h3>Why this draft exists</h3>
    <dl>
      <div><dt>Trigger</dt><dd>{draft.trigger || "No trigger recorded"}</dd></div>
      <div><dt>Evidence</dt><dd>{draft.evidence_ids.length ? <ul>{draft.evidence_ids.map(id => {
        const label = accountDetail?.intelligence.find(signal => signal.id === id)?.title;
        return <li key={id}>{label || id}{label && <small>{id}</small>}</li>;
      })}</ul> : "No evidence linked"}</dd></div>
      <div><dt>Customer</dt><dd>{customer}</dd></div>
      <div><dt>Recipient</dt><dd>{draft.recipients.length ? draft.recipients.map(email => {
        const contact = accountDetail?.public_contacts.find(item => item.public_email?.toLowerCase() === email.toLowerCase());
        return <p key={email}>{email}<small>{contact ? 'Public contact' : 'Public contact · source details unavailable'}
          {contact?.provenance?.last_verified_at && <> · Last verified {new Date(contact.provenance.last_verified_at).toLocaleDateString()}</>}
        </small></p>;
      }) : "Recipient unavailable"}</dd></div>
    </dl>
    {onAccount && <Button type="button" variant="ghost" onClick={onAccount}>View Customer</Button>}
  </section>;
}
