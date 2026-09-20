import { useRef, useState } from 'react'
import { HighCardinalitySelector } from '../../components/HighCardinalitySelector'
import { api } from '../../api/client'
import type { Account, Action, ActionPriority, Principal } from '../../types/api'
import { Button, Drawer, SelectInput, TextInput, Textarea } from '../../components/UI'
export function ActionEditor({ open, action, accounts, principal, onClose, onSaved, proposal }: { open: boolean; action?: Action; accounts: Account[]; principal?: Principal; onClose: () => void; onSaved: (item: Action) => void; proposal?: { account_id: string; title: string } }) {
  const [customerSelection, setCustomerId] = useState(action?.account_id ?? proposal?.account_id)
  const customerId = customerSelection ?? accounts[0]?.id ?? ''
  const [title, setTitle] = useState(action?.title ?? proposal?.title ?? '')
  const [description, setDescription] = useState(action?.description ?? '')
  const [priority, setPriority] = useState<ActionPriority>(action?.priority ?? 'MEDIUM')
  const [dueDate, setDueDate] = useState(action?.due_date ?? '')
  const [ownerId, setOwnerId] = useState(action?.owner_id ?? principal?.user_id ?? '')
  const [approvalRequired, setApprovalRequired] = useState(action?.approval_status === 'PENDING')
  const [error, setError] = useState('')
  const inFlight = useRef(false)
  const retry = useRef<{ signature: string; key: string } | undefined>(undefined)
  const submit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (inFlight.current) return
    if (!customerId || !accounts.some(item => item.id === customerId)) { setError('Choose an available Customer. Your draft is retained.'); return }
    if (!title.trim()) { setError('Title is required.'); return }
    const signature = JSON.stringify([customerId, title, description, priority, dueDate, ownerId, approvalRequired])
    if (retry.current?.signature !== signature) retry.current = { signature, key: crypto.randomUUID() }
    inFlight.current = true
    try {
      const saved = action ? await api.editAction(action.id, { title, description: description || undefined, priority, due_date: dueDate || undefined, expected_version: action.version, ...(principal?.role === 'MANAGER' ? { owner_id: ownerId || undefined } : {}) })
        : await api.createAction({ account_id: customerId, title, description: description || undefined, priority, due_date: dueDate || undefined, owner_id: ownerId || undefined, approval_required: approvalRequired, idempotency_key: retry.current.key })
      onSaved(saved)
    } catch (caught) { setError(caught instanceof Error ? caught.message : 'Action could not be saved. Retry retains this request; inspect saved work if the outcome is unknown.') }
    finally { inFlight.current = false }
  }
  return <Drawer open={open} onClose={onClose} titleId="action-editor-title" className="action-editor"><form onSubmit={event => void submit(event)}><header><div><span className="eyebrow">Durable work</span><h2 id="action-editor-title">{action ? 'Edit Action' : 'Create Action'}</h2></div><Button type="button" variant="ghost" onClick={onClose}>Close</Button></header><HighCardinalitySelector label="Customer" value={customerId} disabled={Boolean(action)} onChange={setCustomerId} choices={accounts.map(account => ({ id: account.id, label: account.name ?? account.legal_name ?? 'Unnamed organization', description: account.relationship === 'CURRENT_CUSTOMER' ? 'Customer' : account.relationship === 'PROSPECT' || account.relationship === 'TARGET' ? 'Prospect' : 'Classification unavailable', searchText: [account.legal_name, account.domain, ...(account.industries ?? [])].filter(Boolean).join(' ') }))} recentIds={action?.account_id ? [action.account_id] : []} /><TextInput label="Title" value={title} error={error && !title.trim() ? error : undefined} onChange={event => setTitle(event.target.value)} /><Textarea label="Details" value={description} onChange={event => setDescription(event.target.value)} /><div className="action-form-grid"><SelectInput label="Priority" value={priority} onChange={event => setPriority(event.target.value as ActionPriority)}><option>HIGH</option><option>MEDIUM</option><option>LOW</option></SelectInput><TextInput label="Due date" type="date" value={dueDate} onChange={event => setDueDate(event.target.value)} /></div>{principal?.role === 'MANAGER' && <TextInput label="Owner ID" value={ownerId} onChange={event => setOwnerId(event.target.value)} />}{!action && <label className="action-approval-choice"><input type="checkbox" checked={approvalRequired} onChange={event => setApprovalRequired(event.target.checked)} /> External workflow requires Manager approval</label>}{error && title.trim() && <p className="ui-field-message" role="alert">{error}</p>}<footer><Button type="button" onClick={onClose}>Cancel</Button><Button type="submit" variant="primary">{action ? 'Save changes' : 'Create Action'}</Button></footer></form></Drawer>
}
