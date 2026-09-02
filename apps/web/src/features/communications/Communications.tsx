import { useCallback, useEffect, useMemo, useState } from "react";
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

type Props = {
  accounts: Account[];
  principal?: Principal;
  items: CommunicationDraft[];
  onItem: (item: CommunicationDraft) => void;
  onAccount: (id: string) => void;
};
const humanize = (value: string) =>
  value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^./, (value) => value.toUpperCase());

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
  const [history, setHistory] = useState<CommunicationHistoryEvent[]>([]);
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
  useEffect(() => {
    if (!selected) return;
    void api
      .communicationHistory(selected.id)
      .then((result) => setHistory(result.events))
      .catch(() => setHistory([]));
  }, [selected]);
  const review = async (decision: "APPROVED" | "REJECTED") => {
    if (!selected) return;
    try {
      onItem(await api.approveCommunication(selected.id, decision));
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
          <div className="communication-list" role="list">
            {visible.length ? (
              visible.map((item) => (
                <button
                  type="button"
                  role="listitem"
                  key={item.id}
                  className={`communication-row ${selected?.id === item.id ? "selected" : ""}`}
                  aria-pressed={selected?.id === item.id}
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
                    <dd>{selected.created_by}</dd>
                  </div>
                </dl>
                <div className="card-actions">
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
                <Disclosure title="Audit history">
                  <ol className="communication-history">
                    {history.map((event) => (
                      <li key={event.id}>
                        <strong>{humanize(event.event)}</strong>
                        <span>
                          {event.actor_id} ·{" "}
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
  const [accountId, setAccountId] = useState(
    draft?.account_id ?? accounts[0]?.id ?? "",
  );
  const [subject, setSubject] = useState(draft?.subject ?? "");
  const [body, setBody] = useState(draft?.body ?? "");
  const [recipients, setRecipients] = useState<string[]>(
    draft?.recipients ?? [],
  );
  const [accountDetail, setAccountDetail] = useState<Account360>();
  const [instruction, setInstruction] = useState(
    "Make this concise and evidence-led.",
  );
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  useEffect(() => {
    if (!accountId) return;
    void api
      .account(accountId)
      .then(setAccountDetail)
      .catch(() => setAccountDetail(undefined));
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
    if (!subject.trim() || !body.trim()) {
      setError("Subject and message are required.");
      return;
    }
    setWorking(true);
    try {
      const result = draft
        ? await api.editCommunication(draft.id, { subject, body, recipients })
        : await api.createCommunication({
            account_id: accountId,
            subject,
            body,
            recipients,
            idempotency_key: `draft-${accountId}-${crypto.randomUUID()}`,
          });
      onSaved(result);
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Draft could not be saved.",
      );
    } finally {
      setWorking(false);
    }
  };
  const assist = async () => {
    setWorking(true);
    try {
      const result = draft
        ? await api.assistCommunication(draft.id, instruction)
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
          disabled={Boolean(draft)}
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
          value={subject}
          onChange={(event) => setSubject(event.target.value)}
        />
        <Textarea
          label="Message"
          rows={8}
          value={body}
          onChange={(event) => setBody(event.target.value)}
        />
        {verifiedRecipients.length ? (
          <SelectInput
            label="Verified professional recipient"
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
            <TextInput
              label="Drafting instruction"
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
          <Button type="submit" variant="primary" loading={working}>
            {draft ? "Save changes" : "Save draft"}
          </Button>
        </footer>
      </form>
    </Drawer>
  );
}
