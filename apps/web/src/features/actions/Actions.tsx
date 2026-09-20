import { useEffect, useMemo, useRef, useState } from 'react'
import { api, resolveFederalAssessment } from '../../api/client'
import { Button, Empty, Panel, SearchInput, SelectInput, StatTile, StatusBadge, TextInput } from '../../components/UI'
import { FilterBar, type AppliedFilter } from '../../components/FilterBar'
import type { Account, Action, ActionStatus, FederalAssessment, OmniContext, Principal, Signal, Suggestion } from '../../types/api'
import { workspaceHash, type WorkspaceLocation } from '../../app/navigation'
import { WorklistPagination } from '../../components/WorklistPagination'
import { clampPage, pageSlice } from '../../components/worklistModel'
import { SuggestionList } from './SuggestionList'
import { CrmProposalPanel } from './CrmProposalPanel'
import { ActionDetail } from './ActionDetail'
import { actionSource, closed, compareDue, overdue, relativeDue } from './actionModel'
import './actions.css'

type Props = {
  sourceAlertId?: string; onClearSource: () => void; initialActionId?: string
  items: Action[]; suggestions: Suggestion[]; principal?: Principal; accounts: Account[]; signals: Signal[]; warning: string
  onItem: (item: Action) => void; onSuggestions: (items: Suggestion[]) => void; onAccount: (id: string) => void
  onActionSelect: (id?: string) => void; onOmniContext: (context: Pick<OmniContext, 'active_filters' | 'visible_record_ids' | 'selected_federal_opportunity'>) => void
  location: WorkspaceLocation; onLocationChange: (next: WorkspaceLocation, mode?: 'push' | 'replace') => void
}
const PAGE_SIZE = 12
const priorityOrder = { HIGH: 0, MEDIUM: 1, LOW: 2 }

export function Actions({ items, suggestions, principal, accounts, signals, warning, onItem, onSuggestions, onAccount, onActionSelect, onOmniContext, sourceAlertId, onClearSource, location, onLocationChange }: Props) {
  const tab = location.subview === 'suggestions' || sourceAlertId ? 'suggestions' : location.subview === 'completed' ? 'completed' : 'actions'
  const query = String(location.filters?.query ?? '')
  const status = String(location.filters?.status ?? 'ALL')
  const priority = String(location.filters?.priority ?? 'ALL')
  const sort = location.sort ?? 'DUE'
  const suggestionView = String(location.filters?.suggestion_view ?? 'ACTIVE')
  const selectedId = location.actionId
  const [title, setTitle] = useState('')
  const [notice, setNotice] = useState('')
  const [creating, setCreating] = useState(false)
  const [undo, setUndo] = useState<Action>()
  const [federalAssessment, setFederalAssessment] = useState<FederalAssessment>()
  const createReceipt = useRef<{ title: string; key: string } | undefined>(undefined)
  const rows = useRef(new Map<string, HTMLButtonElement>())
  const revealed = useRef<string | undefined>(undefined)
  const quickAdd = useRef<HTMLFormElement>(null)
  const customerName = (id: string | null) => id ? accounts.find(account => account.id === id)?.name ?? accounts.find(account => account.id === id)?.legal_name ?? id : 'No customer'
  const changeFilters = (patch: Record<string, string | undefined>) => {
    const filters: Record<string, string | string[] | undefined> = { ...location.filters, page: undefined, ...patch }
    onLocationChange({ ...location, filters: Object.fromEntries(Object.entries(filters).filter((entry): entry is [string, string | string[]] => entry[1] !== undefined)) }, 'replace')
  }
  const setTab = (subview: string) => { onClearSource(); onLocationChange({ ...location, subview, filters: { ...location.filters, status: 'ALL', page: '1' } }) }
  const select = (item: Action) => { onLocationChange({ ...location, actionId: item.id }, 'replace') }
  const clear = () => onLocationChange({ ...location, filters: {}, sort: 'DUE' }, 'replace')
  const applied: AppliedFilter[] = [
    ...(query ? [{ key: 'query', label: `Search: ${query}`, remove: () => changeFilters({ query: undefined }) }] : []),
    ...(status !== 'ALL' ? [{ key: 'status', label: `Status: ${status}`, remove: () => changeFilters({ status: undefined }) }] : []),
    ...(priority !== 'ALL' ? [{ key: 'priority', label: `Priority: ${priority}`, remove: () => changeFilters({ priority: undefined }) }] : []),
  ]
  const visible = useMemo(() => items.filter(item => (tab === 'completed' ? closed(item) : !closed(item))
    && (status === 'ALL' || status === 'ACTIVE' && !closed(item) || item.status === status)
    && (priority === 'ALL' || item.priority === priority)
    && `${item.title} ${item.description ?? ''} ${item.owner_id ?? ''} ${accounts.find(account => account.id === item.account_id)?.name ?? ''}`.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => (sort === 'PRIORITY' ? priorityOrder[a.priority] - priorityOrder[b.priority] : sort === 'UPDATED' ? b.updated_at.localeCompare(a.updated_at) : compareDue(a, b)) || a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id)), [items, tab, status, priority, query, sort, accounts])
  const page = clampPage(Number(location.filters?.page ?? 1), visible.length, PAGE_SIZE)
  const displayed = pageSlice(visible, page, PAGE_SIZE)
  const selected = items.find(item => item.id === selectedId)
  const scopedSuggestions = useMemo(() => sourceAlertId ? suggestions.filter(item => item.source_alert_id === sourceAlertId) : suggestions, [sourceAlertId, suggestions])
  useEffect(() => {
    if (!selectedId) { revealed.current = undefined; return }
    if (!selected || revealed.current === selectedId) return
    revealed.current = selectedId
    const index = visible.findIndex(item => item.id === selectedId)
    const selectedPage = Math.floor(index / PAGE_SIZE) + 1
    if (index >= 0 && page !== selectedPage && !location.filters?.page) onLocationChange({ ...location, filters: { ...location.filters, page: String(selectedPage) } }, 'replace')
  }, [selectedId, selected, visible, page, location, onLocationChange])
  useEffect(() => {
    if (sourceAlertId && location.subview !== 'suggestions') onLocationChange({ ...location, subview: 'suggestions' }, 'replace')
  }, [sourceAlertId, location, onLocationChange])
  useEffect(() => { onActionSelect(selected?.id) }, [selected?.id, onActionSelect])
  useEffect(() => {
    onOmniContext({ active_filters: { query, action_status: status, priority }, visible_record_ids: (tab === 'suggestions' ? scopedSuggestions : visible).map(item => item.id).slice(0, 50), selected_federal_opportunity: location.federal && selected ? { opportunity_id: location.federal.opportunityId, assessment_id: location.federal.assessmentId, assessment_version: location.federal.assessmentVersion, route_type: location.federal.routeType, account_id: location.federal.accountId, partnership_id: location.federal.partnershipId } : undefined })
  }, [query, status, priority, visible, onOmniContext, location.federal, selected, tab, scopedSuggestions])
  useEffect(() => () => { onActionSelect(undefined); onOmniContext({}) }, [onActionSelect, onOmniContext])
  useEffect(() => {
    if (!undo) return
    const timeout = window.setTimeout(() => setUndo(undefined), 8000)
    return () => window.clearTimeout(timeout)
  }, [undo])
  useEffect(() => {
    const federal = location.federal
    if (!selected || !federal || !selected.context_referents.some(([kind, value]) => kind === 'federal_assessment' && value === federal.assessmentId)) return
    const controller = new AbortController()
    void resolveFederalAssessment({ opportunity_id: federal.opportunityId, assessment_id: federal.assessmentId, assessment_version: federal.assessmentVersion, route_type: federal.routeType, account_id: federal.accountId, partnership_id: federal.partnershipId }, controller.signal).then(setFederalAssessment).catch(() => undefined)
    return () => controller.abort()
  }, [location.federal, selected])
  const transition = async (item: Action, next: ActionStatus, all = false) => {
    const updated = await api.transition(item.id, next, item.version, all)
    onItem(updated)
    if (closed(updated)) setUndo(updated)
    setNotice(`Task ${next.toLowerCase().replaceAll('_', ' ')}.`)
  }
  const convert = async (suggestion: Suggestion) => {
    try { const created = await api.convertSuggestion(suggestion.id, suggestion.revision); onItem(created); onSuggestions(suggestions.map(item => item.id === suggestion.id ? { ...item, converted_action_id: created.id } : item)); onClearSource(); onLocationChange({ ...location, subview: 'actions', actionId: created.id, filters: {} }); setNotice('Suggestion converted to one durable Action. No external operation was executed.') }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Suggestion conversion failed.') }
  }
  const create = async () => {
    if (!title.trim() || creating) return
    const trimmed = title.trim()
    if (createReceipt.current?.title !== trimmed) createReceipt.current = { title: trimmed, key: crypto.randomUUID() }
    setCreating(true)
    try { const created = await api.createAction({ title: trimmed, priority: 'MEDIUM', idempotency_key: createReceipt.current.key, context_referents: [['source_screen', 'Actions'], ['source_route', workspaceHash({ surface: 'actions' })]] }); onItem(created); setTitle(''); createReceipt.current = undefined; onLocationChange({ ...location, subview: 'actions', actionId: created.id, filters: {} }) }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Task creation failed; your title and retry key are retained.') }
    finally { setCreating(false) }
  }
  const closeDetail = () => { const previous = selectedId; onLocationChange({ ...location, actionId: undefined }, 'replace'); window.requestAnimationFrame(() => { const row = previous ? rows.current.get(previous) : undefined; if (row?.isConnected) row.focus(); else quickAdd.current?.querySelector('input')?.focus() }) }
  return <div className={`surface actions-surface ${selected && tab !== 'suggestions' ? 'detail-open' : ''}`}>
    <header className="page-title actions-header"><div><span className="eyebrow">Personal workspace</span><h1>Actions</h1><p>Your tasks, subtasks, approvals and evidence.</p></div></header>
    <p className="truth-note">{principal?.display_name} · {warning}</p>{notice && <p role="status">{notice}</p>}
    {undo && <div className="action-undo" role="status">Task {undo.status.toLowerCase()}. <Button onClick={() => { const target = undo; void api.action(target.id).then(latest => { if (latest.version !== target.version || latest.status !== target.status || !latest.allowed_transitions.length) throw new Error('Task changed since it was closed. Review it before reopening.'); return api.transition(latest.id, latest.allowed_transitions[0], latest.version) }).then(updated => { onItem(updated); setUndo(undefined); setNotice('Task reopened.') }).catch(error => setNotice(error.message)) }}>Undo</Button></div>}
    <nav className="actions-tabs" aria-label="Action views">{[['actions', 'My Actions'], ['suggestions', `Suggested (${suggestions.filter(item => !item.dismissed && !item.converted_action_id).length})`], ['completed', 'Closed']].map(([value, text]) => <button key={value} aria-current={tab === value ? 'page' : undefined} className={tab === value ? 'active' : ''} onClick={() => setTab(value)}>{text}</button>)}</nav>
    <div className="actions-summary-grid" aria-label="Actions summary"><StatTile label="Open" value={items.filter(item => item.status === 'OPEN').length} /><StatTile label="In progress" value={items.filter(item => item.status === 'IN_PROGRESS').length} /><StatTile label="Overdue" value={items.filter(item => overdue(item)).length} />{principal?.role === 'MANAGER' && <StatTile label="Pending approval" value={items.filter(item => !closed(item) && ['PENDING', 'REQUESTED'].includes(item.approval_status) && (item.approval_requested_by ?? item.created_by) !== principal.user_id).length} />}</div>
    {tab === 'suggestions' ? <>{sourceAlertId && <section className="notice" aria-label="Selected Today priority"><p>Showing the recommendation linked to your Today priority.</p><Button onClick={onClearSource}>Show all suggestions</Button>{scopedSuggestions.filter(item => item.converted_action_id).map(item => <Button key={item.id} onClick={() => { onClearSource(); onLocationChange({ ...location, subview: 'actions', actionId: item.converted_action_id }) }}>Open existing action</Button>)}</section>}<SuggestionList onClear={clear} suggestions={scopedSuggestions} name={customerName} onConvert={convert} onFeedback={(id, patch) => onSuggestions(suggestions.map(item => item.id === id ? { ...item, ...patch } : item))} onRefreshed={onSuggestions} query={query} onQuery={value => changeFilters({ query: value })} priority={priority} onPriority={value => changeFilters({ priority: value })} sort={['PRIORITY', 'RECENT', 'CUSTOMER'].includes(sort) ? sort : 'PRIORITY'} onSort={value => onLocationChange({ ...location, sort: value }, 'replace')} view={suggestionView} onView={value => changeFilters({ suggestion_view: value })} page={Number(location.filters?.page ?? 1)} onPage={value => changeFilters({ page: String(value) })} selectedId={location.recordId} onSelected={recordId => onLocationChange({ ...location, recordId }, 'replace')} /></> : <>
      <FilterBar label="Actions filters" search={<SearchInput aria-label="Search actions" placeholder="Search tasks" value={query} onChange={event => changeFilters({ query: event.target.value })} />} sort={<SelectInput aria-label="Sort actions" value={sort} onChange={event => onLocationChange({ ...location, sort: event.target.value }, 'replace')}><option value="DUE">Due date</option><option value="PRIORITY">Priority</option><option value="UPDATED">Recently updated</option></SelectInput>} filters={applied} onClear={clear} count={visible.length}><SelectInput aria-label="Filter by status" value={status} onChange={event => changeFilters({ status: event.target.value })}><option value="ALL">All statuses</option>{(tab === 'completed' ? ['COMPLETED', 'CANCELED'] : ['OPEN', 'IN_PROGRESS']).map(value => <option key={value}>{value}</option>)}</SelectInput><SelectInput aria-label="Filter by priority" value={priority} onChange={event => changeFilters({ priority: event.target.value })}><option value="ALL">All priorities</option>{Object.keys(priorityOrder).map(value => <option key={value}>{value}</option>)}</SelectInput></FilterBar>
      <form ref={quickAdd} className="quick-add" onSubmit={event => { event.preventDefault(); void create() }}><TextInput label="Quick add task" placeholder="Type a title and press Enter" value={title} onChange={event => setTitle(event.target.value)} /><Button type="submit" disabled={creating || !title.trim()}>Add task</Button></form>
      {federalAssessment && <section className="notice"><h3>Federal opportunity context</h3><p>{federalAssessment.technical.requirement}</p><p>{federalAssessment.stage.label}: {federalAssessment.stage.explanation}</p><p>This internal proposal performed no external write.</p></section>}
      <div className="action-workbench"><div className="action-list-pane"><Panel title="My Actions"><div className="action-list" role="list">{displayed.map(item => { const source = actionSource(item); const children = item.subtasks.filter(child => !child.removed); return <div role="listitem" key={item.id} className={`action-row ${selectedId === item.id ? 'selected' : ''}`}><input aria-label={`Complete ${item.title}`} type="checkbox" checked={item.status === 'COMPLETED'} disabled={closed(item)} onChange={() => { select(item); if (children.some(child => !child.done)) { setNotice('Open subtasks remain. Use Complete in the detail pane to review and finish all.'); return } void transition(item, 'COMPLETED').catch(error => setNotice(error.message)) }} /><button ref={element => { if (element) rows.current.set(item.id, element); else rows.current.delete(item.id) }} className="action-select" onClick={() => select(item)}><strong>{item.title}</strong><small>{customerName(item.account_id)}</small></button><StatusBadge value={item.priority} kind="priority" /><span className="action-row-meta"><small>{relativeDue(item.due_date)}</small><small>{item.owner_id ?? 'Unassigned'}</small><small>{children.filter(child => child.done).length}/{children.length} subtasks</small><small className="approval-badge">{item.approval_status.replaceAll('_', ' ')}</small>{source && <a className="source-badge" href={source.href}>{source.label}</a>}</span></div> })}{!displayed.length && <Empty>No results. <Button onClick={clear}>Clear filters</Button></Empty>}</div><WorklistPagination page={page} pageSize={PAGE_SIZE} total={visible.length} onPage={value => changeFilters({ page: String(value) })} /></Panel></div>
        {selected && <ActionDetail key={selected.id} action={selected} accounts={accounts} principal={principal} signals={signals} onItem={onItem} onAccount={onAccount} onClose={closeDetail} onTransition={transition} />}</div>
      {selected && <CrmProposalPanel key={selected.id} action={selected} principal={principal} />}
    </>}
  </div>
}
