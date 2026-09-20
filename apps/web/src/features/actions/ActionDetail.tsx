import { useEffect, useRef, useState, type ReactNode } from 'react'
import { api } from '../../api/client'
import { Button, Disclosure, Panel, SelectInput, TextInput, Textarea } from '../../components/UI'
import { HighCardinalitySelector, type GovernedChoice } from '../../components/HighCardinalitySelector'
import type { Account, Action, ActionHistoryEvent, ActionSubtask, ActionStatus, Principal, Signal } from '../../types/api'
import { actionSource, closed } from './actionModel'

type Edit = Parameters<typeof api.editAction>[1]
type Mutate = (operation: (current: Action) => Promise<Action>, optimistic?: Partial<Action>) => Promise<void>
const message = (error: unknown) => error instanceof Error ? error.message : 'Save failed. Your draft is retained.'

export function InlineField({ label, value, onSave, refresh, type = 'text', children, choices, disabled }: {
  label: string; value: string; onSave: (value: string) => Promise<void>; refresh: () => Promise<void>; type?: string; children?: ReactNode
  choices?: GovernedChoice[]; disabled?: boolean
}) {
  const [draft, setDraft] = useState(value)
  const [state, setState] = useState('')
  const dirty = useRef(false)
  const saving = useRef(false)
  const latestDraft = useRef(value)
  useEffect(() => { if (!dirty.current) setDraft(value) }, [value])
  const save = async (next: string) => {
    if (saving.current || (!dirty.current && next === value)) return
    saving.current = true; setState('Saving…')
    let succeeded = false
    try { await onSave(next); succeeded = true; dirty.current = latestDraft.current !== next; setState(dirty.current ? 'Unsaved' : 'Saved') }
    catch (error) { setState(`${message(error)} Your typed value is retained. Review the latest revision before retrying.`) }
    finally { saving.current = false; if (succeeded && dirty.current) void save(latestDraft.current) }
  }
  const change = (next: string) => { dirty.current = true; latestDraft.current = next; setDraft(next); setState('Unsaved') }
  return <div className="inline-field">
    {choices ? <HighCardinalitySelector label={label} value={draft} choices={choices} disabled={disabled} allChoice={{ label: 'No customer', description: 'Personal task without an organization' }} onChange={next => { change(next); void save(next) }} /> : children ? <SelectInput label={label} aria-label={label} value={draft} onChange={event => { change(event.target.value); void save(event.target.value) }}>{children}</SelectInput>
      : type === 'textarea' ? <Textarea label={label} aria-label={label} value={draft} onChange={event => change(event.target.value)} onBlur={() => void save(draft)} />
        : <TextInput label={label} aria-label={label} type={type} value={draft} onChange={event => change(event.target.value)} onBlur={() => void save(draft)} />}
    <small role="status">{state}</small>
    {state.includes('retained') && <Button onClick={() => void refresh().then(() => save(draft)).catch(error => setState(message(error)))}>Reload revision and retry {label}</Button>}
  </div>
}

function SubtasksSection({ action, mutate, refresh }: { action: Action; mutate: Mutate; refresh: () => Promise<void> }) {
  const [title, setTitle] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const receipts = useRef(new Map<string, string>())
  const [pending, setPending] = useState(0)
  const children = action.subtasks.filter(child => !child.removed)
  const change = async (id: string | undefined, changes: Partial<ActionSubtask>) => {
    const signature = JSON.stringify([id, changes])
    const key = receipts.current.get(signature) ?? crypto.randomUUID()
    receipts.current.set(signature, key)
    setPending(value => value + 1)
    try {
      await mutate(current => api.subtask(current.id, id, { ...changes, expected_version: current.version, idempotency_key: key }), id ? { subtasks: action.subtasks.map(child => child.id === id ? { ...child, ...changes } : child) } : undefined)
      receipts.current.delete(signature); setError('')
    } catch (caught) { setError(message(caught)); throw caught }
    finally { setPending(value => value - 1) }
  }
  return <section aria-label="Subtasks"><h3>Subtasks · {children.filter(child => child.done).length}/{children.length}</h3>
    {!closed(action) && <form onSubmit={event => { event.preventDefault(); if (!title.trim() || busy) return; setBusy(true); void change(undefined, { title: title.trim() }).then(() => setTitle('')).catch(() => undefined).finally(() => setBusy(false)) }}><TextInput label="New subtask" value={title} onChange={event => setTitle(event.target.value)} /><Button type="submit" disabled={busy || !title.trim()}>Add subtask</Button></form>}
    {error && <p role="alert">{error}</p>}
    <ul className="subtask-list">{action.subtasks.map(child => <li key={child.id}>{child.removed
      ? <div>Removed: {child.title} <Button disabled={closed(action) || pending > 0} onClick={() => void change(child.id, { removed: false }).catch(() => undefined)}>Restore subtask</Button></div>
      : <><label><input type="checkbox" checked={child.done} disabled={closed(action) || pending > 0} onChange={event => void change(child.id, { done: event.target.checked }).catch(() => undefined)} />Done: {child.title}</label>
        <InlineField label="Subtask title" value={child.title} refresh={refresh} onSave={value => change(child.id, { title: value })} />
        <InlineField label="Subtask due date" type="date" value={child.due_date ?? ''} refresh={refresh} onSave={value => change(child.id, { due_date: value || null })} />
        <InlineField label="Subtask owner" value={child.owner_id ?? ''} refresh={refresh} onSave={value => change(child.id, { owner_id: value || null })} />
        <Button disabled={closed(action) || pending > 0} onClick={() => void change(child.id, { removed: true }).catch(() => undefined)}>Remove subtask</Button></>}</li>)}</ul>
  </section>
}

function ApprovalSection({ action, principal, mutate, history }: { action: Action; principal?: Principal; mutate: Mutate; history: ActionHistoryEvent[] }) {
  const [comment, setComment] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const run = (operation: (current: Action) => Promise<Action>) => { setBusy(true); void mutate(operation).then(() => { setError(''); setComment('') }).catch(caught => setError(message(caught))).finally(() => setBusy(false)) }
  const pending = ['PENDING', 'REQUESTED'].includes(action.approval_status)
  const canDecide = pending && principal?.role === 'MANAGER' && (action.approval_requested_by ?? action.created_by) !== principal.user_id
  return <section aria-label="Approval"><h3>Approval</h3><p className="approval-badge">{action.approval_status.replaceAll('_', ' ')}</p>
    {action.approval_comment && <blockquote>{action.approval_comment}</blockquote>}
    {principal?.user_id === action.owner_id && !closed(action) && action.approval_status !== 'REQUESTED' && <Button disabled={busy} onClick={() => run(current => api.requestApproval(current.id, current.version))}>Request approval</Button>}
    {pending && <p>Awaiting a manager decision. Approval does not complete this task.</p>}
    {canDecide && <><Textarea label="Manager comment" value={comment} onChange={event => setComment(event.target.value)} /><div className="card-actions">
      <Button disabled={busy} onClick={() => run(current => api.approve(current.id, 'APPROVED', current.version, comment))}>Approve</Button>
      <Button disabled={busy || !comment.trim()} onClick={() => run(current => api.approve(current.id, 'CHANGES_REQUESTED', current.version, comment))}>Request changes</Button>
      <Button disabled={busy || !comment.trim()} onClick={() => run(current => api.approve(current.id, 'REJECTED', current.version, comment))}>Reject</Button></div><small>A comment is required for request changes and reject.</small></>}
    {error && <p role="alert">{error}</p>}
    <ol aria-label="Approval history">{history.filter(event => event.event.startsWith('APPROVAL_')).map(event => <li key={event.id}>{String(event.metadata.after)} · {event.actor_id} · {new Date(event.occurred_at).toLocaleString()} {String(event.metadata.comment ?? '')}</li>)}</ol>
  </section>
}

export function ActionDetail({ action, accounts, principal, signals, onItem, onAccount, onClose, onTransition }: {
  action: Action; accounts: Account[]; principal?: Principal; signals: Signal[]; onItem: (action: Action) => void;
  onAccount: (id: string) => void; onClose: () => void; onTransition: (action: Action, status: ActionStatus, all?: boolean) => Promise<void>
}) {
  const current = useRef(action)
  const queue = useRef(Promise.resolve())
  const pane = useRef<HTMLElement>(null)
  const [history, setHistory] = useState<ActionHistoryEvent[]>([])
  const [historyError, setHistoryError] = useState('')
  const [historyLoading, setHistoryLoading] = useState(true)
  const [historyRetry, setHistoryRetry] = useState(0)
  const [error, setError] = useState('')
  const [completeNotice, setCompleteNotice] = useState(false)
  useEffect(() => { current.current = action }, [action])
  useEffect(() => { pane.current?.focus() }, [])
  useEffect(() => {
    let active = true
    void api.history(action.id).then(result => { if (active) { setHistory(result.events); setHistoryError('') } }).catch(() => { if (active) setHistoryError('Action history could not be loaded. No empty history has been assumed.') }).finally(() => { if (active) setHistoryLoading(false) })
    return () => { active = false }
  }, [action.id, action.version, historyRetry])
  const refresh = async () => { const latest = await api.action(action.id); current.current = latest; onItem(latest) }
  const mutate: Mutate = (operation, optimistic) => {
    const pending = queue.current.catch(() => undefined).then(async () => {
      const previous = current.current
      if (optimistic) onItem({ ...previous, ...optimistic })
      try { const saved = await operation(previous); current.current = saved; onItem(saved) }
      catch (caught) { current.current = previous; onItem(previous); throw caught }
    })
    queue.current = pending; return pending
  }
  const edit = (changes: Edit) => mutate(item => api.editAction(item.id, { ...changes, expected_version: item.version }), changes)
  const transition = (status: ActionStatus, all = false) => {
    if (status === 'COMPLETED' && !all && action.subtasks.some(child => !child.done && !child.removed)) { setCompleteNotice(true); return }
    void queue.current.catch(() => undefined).then(() => onTransition(current.current, status, all)).then(() => { setError(''); setCompleteNotice(false) }).catch(caught => setError(message(caught)))
  }
  const source = actionSource(action)
  const sections = [
    { id: 'fields', content: <section aria-label="Task fields"><InlineField label="Title" value={action.title} onSave={value => edit({ title: value })} refresh={refresh} /><InlineField label="Description" type="textarea" value={action.description ?? ''} onSave={value => edit({ description: value || null })} refresh={refresh} />
      <SelectInput label="Status" aria-label="Status" value={action.status} onChange={event => transition(event.target.value as ActionStatus)}><option value={action.status}>{action.status}</option>{action.allowed_transitions.map(status => <option key={status}>{status}</option>)}</SelectInput>
      {closed(action) ? <Button disabled={!action.allowed_transitions.length} onClick={() => transition(action.allowed_transitions[0])}>Reopen</Button> : <div className="card-actions">{action.allowed_transitions.includes('COMPLETED') && <Button onClick={() => transition('COMPLETED')}>Complete</Button>}{action.allowed_transitions.includes('CANCELED') && <Button onClick={() => transition('CANCELED')}>Cancel task</Button>}</div>}
      {completeNotice && <div role="status">This task has open subtasks. <Button onClick={() => transition('COMPLETED', true)}>Complete all and finish</Button></div>}
      {closed(action) && !action.allowed_transitions.length && <p role="alert">The previous work state was not recorded. Reopening requires reviewed recovery; no prior state has been guessed.</p>}
      <InlineField label="Priority" value={action.priority} onSave={value => edit({ priority: value as Action['priority'] })} refresh={refresh}><option>HIGH</option><option>MEDIUM</option><option>LOW</option></InlineField>
      <InlineField label="Due date" type="date" value={action.due_date ?? ''} onSave={value => edit({ due_date: value || null })} refresh={refresh} />
      {principal?.role === 'MANAGER' ? <InlineField label="Owner" value={action.owner_id ?? ''} onSave={value => edit({ owner_id: value || null })} refresh={refresh} /> : <p>Owner: {action.owner_id ?? 'Unassigned'}</p>}
      <InlineField label="Customer" value={action.account_id ?? ''} onSave={value => edit({ account_id: value || null })} refresh={refresh} disabled={Boolean(action.evidence_ids.length || action.source_suggestion_id || action.context_referents.some(([kind]) => !kind.startsWith('source_')))} choices={accounts.map(account => ({ id: account.id, label: account.name ?? account.legal_name ?? account.id }))} />
      {action.account_id && <Button onClick={() => onAccount(action.account_id!)}>View Customer</Button>}
      {source ? <p>Created from <a href={source.href}>{source.label}</a></p> : <p>Creation source was not recorded.</p>}
      {error && <p role="alert">{error}</p>}</section> },
    { id: 'subtasks', content: <SubtasksSection action={action} mutate={mutate} refresh={refresh} /> },
    { id: 'approval', content: <ApprovalSection action={action} principal={principal} mutate={mutate} history={history} /> },
    { id: 'evidence', content: <Disclosure title="Evidence and history"><p>Evidence IDs: {action.evidence_ids.length ? action.evidence_ids.join(', ') : 'None recorded'}</p>{signals.filter(signal => action.evidence_ids.includes(signal.id) || signal.evidence_ids.some(id => action.evidence_ids.includes(id))).map(signal => <p key={signal.id}><a href={signal.source_url} target="_blank" rel="noreferrer">{signal.title}</a> · {signal.evidence_state}</p>)}
      {historyLoading && <p role="status">Loading history…</p>}{historyError ? <div role="alert">{historyError}<Button onClick={() => setHistoryRetry(value => value + 1)}>Retry history</Button></div> : <ol className="action-history" aria-label="Action history">{history.map(event => <li key={event.id}><strong>{event.event.replaceAll('_', ' ')}</strong><span>{event.actor_id} · {new Date(event.occurred_at).toLocaleString()}<br />{JSON.stringify(event.metadata)}</span></li>)}</ol>}</Disclosure> },
  ]
  return <aside ref={pane} tabIndex={-1} className="action-detail" aria-label="Action detail" onKeyDown={event => { if (event.key === 'Escape' && window.matchMedia('(max-width: 760px)').matches) onClose() }}><Panel title="Action detail" action={<Button onClick={onClose}>Close detail</Button>}><ol className="action-sections">{sections.map(section => <li key={section.id}>{section.content}</li>)}</ol></Panel></aside>
}
