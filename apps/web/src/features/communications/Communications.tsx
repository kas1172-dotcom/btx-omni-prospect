import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api/client";
import {
  Button,
  Disclosure,
  Drawer,
  Empty,
  FilterChip,
  Panel,
  SearchInput,
  SelectInput,
  StatusBadge,
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

type Props = {
  accounts: Account[];
  principal?: Principal;
  items: CommunicationDraft[];
  onItem: (item: CommunicationDraft) => void;
  onAccount: (id: string) => void;
};
const humanize = (value: string) => presentationLabel(value, "communication");

export function Communications({
  accounts,
  principal,
  items,
  onItem,
  onAccount,
}: Props) {
  const [query, setQuery] = useState("");
  const [state, setState] = useState("ALL");
  const [selectedId, setSelectedId] = useState<string>();
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<CommunicationDraft>();
  const [notice, setNotice] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
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
          (state === "ALL" ||
            item.status === state ||
            item.approval_status === state),
      ),
    [customer, items, query, state],
  );
  const selected = items.find((item) => item.id === selectedId) ?? visible[0];
  const historyId = selected?.id;
  const historyVersion = selected?.version;
  const currentHistory = loadedHistory?.id === historyId && loadedHistory?.version === historyVersion ? loadedHistory : undefined;
  useEffect(() => {
    if (!historyOpen || !historyId || historyVersion === undefined) return;
    const controller = new AbortController();
    void api
      .communicationHistory(historyId, controller.signal)
      .then((result) => { if (!controller.signal.aborted) setLoadedHistory({ id: historyId, version: historyVersion, events: result.events, error: false }); })
      .catch(() => { if (!controller.signal.aborted) setLoadedHistory({ id: historyId, version: historyVersion, events: [], error: true }); });
    return () => controller.abort();
  }, [historyOpen, historyId, historyVersion, historyRefresh]);
  const review = async (decision: "APPROVED" | "REJECTED") => {
    if (!selected) return;
    try {
      onItem(await api.approveCommunication(selected.id, decision, selected.version));
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
    if (!selected) return;
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
          <span className="eyebrow">Governed outreach</span>
          <h1>Communications</h1>
          <p>
            Trigger → Draft → Human review → Approved send. Gemini can assist
            with words, never authorization or delivery.
          </p>
        </div>
        <Button
          variant="primary"
          size="touch"
          onClick={() => {
            setEditing(undefined);
            setEditorOpen(true);
          }}
        >
          Create draft
        </Button>
      </header>
      <div className="communications-summary">
        <Panel variant="subdued">
          <span className="eyebrow">Drafts</span>
          <strong>
            {items.filter((item) => item.status === "DRAFT").length}
          </strong>
        </Panel>
        <Panel variant="subdued">
          <span className="eyebrow">Awaiting review</span>
          <strong>
            {items.filter((item) => item.approval_status === "PENDING").length}
          </strong>
        </Panel>
        <Panel variant="subdued">
          <span className="eyebrow">Ready</span>
          <strong>
            {items.filter((item) => item.status === "READY").length}
          </strong>
        </Panel>
        <Panel variant="subdued">
          <span className="eyebrow">Delivery</span>
          <StatusBadge value="NOT_CONFIGURED" kind="integration" />
        </Panel>
      </div>
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      <div className="communications-toolbar">
        <SearchInput
          aria-label="Search communications"
          placeholder="Search Customer or draft"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <SelectInput
          aria-label="Filter communications"
          value={state}
          onChange={(event) => setState(event.target.value)}
        >
          <option value="ALL">All states</option>
          <option value="DRAFT">Draft</option>
          <option value="PENDING">Awaiting review</option>
          <option value="READY">Ready</option>
          <option value="SENT">Sent</option>
        </SelectInput>
        {(query || state !== "ALL") && (
          <FilterChip
            selected
            onClear={() => {
              setQuery("");
              setState("ALL");
            }}
          >
            Clear filters
          </FilterChip>
        )}
      </div>
      <div className="communications-workbench">
        <Panel
          title="Customer communications"
          action={
            <span className="panel-kicker">{visible.length} visible</span>
          }
        >
          <div className="communication-list" role="listbox" aria-label="Customer communications">
            {visible.length ? (
              visible.map((item) => (
                <button
                  type="button"
                  role="option"
                  key={item.id}
                  className={`communication-row ${selected?.id === item.id ? "selected" : ""}`}
                  aria-selected={selected?.id === item.id}
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
              <Empty>No communication drafts match these filters.</Empty>
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
                <p className="communication-body">{selected.body}</p>
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
                      setNotice('Saved communication refreshed. Review its content before taking another action.');
                    } catch (error) { setNotice(error instanceof Error ? error.message : 'Refresh failed.'); }
                  }}>Refresh saved communication</Button>
                  <Button
                    onClick={() => {
                      setEditing(selected);
                      setEditorOpen(true);
                    }}
                  >
                    Edit draft
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => onAccount(selected.account_id)}
                  >
                    View Customer
                  </Button>
                  <Button variant="ghost" onClick={() => void preview()}>
                    Preview delivery
                  </Button>
                </div>
                {selected.approval_status === "PENDING" && (
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
                {selected.status === "READY" && (
                  <Panel title="Delivery confirmation" variant="subdued">
                    <p>
                      Delivery remains unavailable until an approved provider is
                      configured. Human confirmation is still required.
                    </p>
                    <Button
                      variant="primary"
                      disabled={!selected.recipients.length}
                      onClick={() => void send()}
                    >
                      Confirm send
                    </Button>
                  </Panel>
                )}
                <Disclosure title="Audit history" open={historyOpen} onOpenChange={setHistoryOpen}>
                  {!currentHistory && <p role="status">Loading this communication’s history…</p>}
                  {currentHistory?.error && <p role="alert">History could not be loaded. No other communication’s history is shown.</p>}
                  <Button onClick={() => setHistoryRefresh(value => value + 1)}>Refresh communication history</Button>
                  <ol className="communication-history">
                    {(currentHistory?.events ?? []).map((event) => (
                      <li key={event.id}>
                        <strong>{humanize(event.event)}</strong>
                        <span>
                          Actor ID {event.actor_id} ·{" "}
                          {new Date(event.occurred_at).toLocaleString()}
                        </span>
                      </li>
                    ))}
                  </ol>
                </Disclosure>
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
        onClose={() => setEditorOpen(false)}
        onSaved={(draft) => {
          onItem(draft);
          setSelectedId(draft.id);
          setEditorOpen(false);
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
}: {
  open: boolean;
  draft?: CommunicationDraft;
  accounts: Account[];
  onClose: () => void;
  onSaved: (draft: CommunicationDraft) => void;
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
    if (!accountId) return;
    const controller = new AbortController();
    void api
      .account(accountId, controller.signal)
      .then(detail => { if (!controller.signal.aborted) setLoadedAccount({ id: accountId, detail }); })
      .catch(() => { if (!controller.signal.aborted) setLoadedAccount(undefined); });
    return () => controller.abort();
  }, [accountId]);
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
      setError('Compare the saved version below. Your local text and recipients have not changed.');
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Saved version could not be refreshed.');
    } finally {
      saveInFlight.current = false;
      setWorking(false);
    }
  };
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
