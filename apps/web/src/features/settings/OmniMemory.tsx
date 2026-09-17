import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { Account } from '../../types/api'
import type { OmniMemory as Memory, OmniMemoryInput } from '../../types/memory'
import { Button, Panel, StatusMessage } from '../../components/UI'
import { HighCardinalitySelector } from '../../components/HighCardinalitySelector'

const emptyDraft: OmniMemoryInput = { account_id: null, kind: 'ANSWER_STYLE', content: '', ttl_days: 90 }
const draftKey = (principalId: string) => `btx-private-memory-draft:${principalId}`
const readDraft = (principalId: string): OmniMemoryInput => {
  try {
    const value = JSON.parse(sessionStorage.getItem(draftKey(principalId)) ?? 'null') as Partial<OmniMemoryInput> | null
    if (!value || typeof value.content !== 'string' || !['ANSWER_STYLE', 'WORK_PREFERENCE'].includes(value.kind ?? '') || ![14, 30, 90, 365].includes(value.ttl_days ?? 0)) return emptyDraft
    return { account_id: typeof value.account_id === 'string' ? value.account_id : null, kind: value.kind as OmniMemoryInput['kind'], content: value.content.slice(0, 600), ttl_days: value.ttl_days! }
  } catch { return emptyDraft }
}

export function OmniMemory({ accounts, principalId }: { accounts: Account[]; principalId: string }) {
  const [items, setItems] = useState<Memory[]>([])
  const [draft, setDraft] = useState<OmniMemoryInput>(() => readDraft(principalId))
  const [editing, setEditing] = useState<Memory>()
  const [deleting, setDeleting] = useState<string>()
  const [pending, setPending] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [loadFailed, setLoadFailed] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [notice, setNotice] = useState('')
  const [refresh, setRefresh] = useState(0)
  const inFlight = useRef(false)
  const hasLoaded = useRef(false)
  const readEpoch = useRef(0)
  const createRequest = useRef<{ fingerprint: string; key: string } | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    const epoch = ++readEpoch.current
    setRefreshing(hasLoaded.current); setLoadFailed(false)
    void api.memories(controller.signal).then(value => { if (!controller.signal.aborted && readEpoch.current === epoch) { setItems(value.items); setLoaded(true); hasLoaded.current = true; setRefreshing(false) } }).catch(() => { if (!controller.signal.aborted && readEpoch.current === epoch) { setLoadFailed(true); setRefreshing(false) } })
    return () => controller.abort()
  }, [refresh])
  useEffect(() => {
    if (draft.content || draft.account_id || draft.kind !== emptyDraft.kind || draft.ttl_days !== emptyDraft.ttl_days) sessionStorage.setItem(draftKey(principalId), JSON.stringify(draft))
    else sessionStorage.removeItem(draftKey(principalId))
  }, [draft, principalId])
  const save = async (event: React.FormEvent) => {
    event.preventDefault()
    if (inFlight.current || !draft.content.trim()) return
    inFlight.current = true
    readEpoch.current += 1
    setPending(true); setNotice('')
    try {
      const fingerprint = JSON.stringify(draft)
      if (!editing && createRequest.current?.fingerprint !== fingerprint) createRequest.current = { fingerprint, key: crypto.randomUUID() }
      const item = editing ? await api.editMemory(editing.id, { ...draft, expected_version: editing.version }) : await api.createMemory({ ...draft, idempotency_key: createRequest.current!.key })
      setItems(current => [item, ...current.filter(m => m.id !== item.id)])
      createRequest.current = null
      setEditing(undefined); setDraft(emptyDraft)
      setNotice(item.create_replayed ? 'The original save was already recorded. Current saved preference shown; content and expiry were not reapplied.' : 'Private preference saved. It does not change facts, scores or permissions.')
    } catch (error) { setNotice(`${error instanceof Error ? error.message : 'Save was not confirmed.'} Refresh and inspect your saved preferences before submitting again.`) }
    finally { inFlight.current = false; setPending(false) }
  }
  const remove = async (item: Memory) => {
    if (inFlight.current) return
    inFlight.current = true
    readEpoch.current += 1
    setPending(true)
    try { await api.deleteMemory(item.id, item.version); setItems(current => current.filter(m => m.id !== item.id)); setDeleting(undefined); setNotice('Preference deleted from active storage. It will not be retrieved by future Omni requests. Earlier responses are not rewritten.') }
    catch (error) { setNotice(error instanceof Error ? error.message : 'Deletion was not confirmed. Refresh and retry.') }
    finally { inFlight.current = false; setPending(false) }
  }
  return <section className="settings-memory" aria-label="Private Omni preferences"><Panel title="Your Omni memory" className="settings-section">
    <p>Explicitly saved style and work preferences, private to your signed-in user. Account preferences apply only after Omni resolves that account. No automatic conversation capture. Do not store credentials.</p>
    <p>Memory cannot establish a public fact, change a deterministic score, or approve an action. Up to eight applicable preferences are used per answer; expired entries are excluded.</p>
    <Button onClick={() => setRefresh(n => n + 1)} disabled={pending || refreshing}>{refreshing ? 'Refreshing memories…' : 'Refresh memories'}</Button>
    {!loaded && !loadFailed && <StatusMessage state="loading" title="Loading private preferences">Only this private memory resource is loading.</StatusMessage>}
    {refreshing && <StatusMessage state="refreshing" title="Refreshing saved preferences">Last-good preferences remain visible and are not labeled as freshly loaded.</StatusMessage>}
    {loadFailed && <StatusMessage state="error" title={loaded ? 'Refresh failed' : 'Memory unavailable'} action={<Button onClick={() => setRefresh(n => n + 1)}>Retry memories</Button>}>{loaded ? 'Last-good preferences remain visible. Retry only this resource.' : 'Private preferences could not be loaded. This is not an empty memory list.'}</StatusMessage>}
    {notice && <p role="status">{notice}</p>}
    {loaded && !loadFailed && items.length === 0 && <StatusMessage state="empty" title="No saved preferences">No eligible private Omni preferences exist for your user.</StatusMessage>}
    {items.map(item => <article className="omni-memory-record" key={item.id}><strong>{item.kind === 'ANSWER_STYLE' ? 'Answer style' : 'Work preference'} · {item.account_id ? accounts.find(account => account.id === item.account_id)?.name ?? accounts.find(account => account.id === item.account_id)?.legal_name ?? 'Selected organization unavailable' : 'Global — all my account contexts'}</strong><p>{item.content}</p><small>{item.expired ? 'Expired' : 'Expires'} {new Date(item.expires_at).toLocaleDateString()} · version {item.version}</small>
      <div><Button disabled={pending} onClick={() => { setEditing(item); setDraft({ account_id: item.account_id, kind: item.kind, content: item.content, ttl_days: 90 }); setNotice('Editing this preference. Saving renews its expiry using the selected duration.') }}>Edit preference</Button><Button disabled={pending} onClick={() => setDeleting(item.id)}>Delete preference</Button></div>
      {deleting === item.id && <div><p>Delete this saved preference? Future Omni requests will no longer retrieve it.</p><Button disabled={pending} onClick={() => void remove(item)}>Confirm delete</Button><Button disabled={pending} onClick={() => setDeleting(undefined)}>Keep preference</Button></div>}</article>)}
    <form className="omni-memory-form" onSubmit={event => void save(event)}><h3>{editing ? 'Edit preference' : 'Save a preference'}</h3>
      <label htmlFor="memory-kind">Preference type</label><select id="memory-kind" disabled={pending} value={draft.kind} onChange={event => setDraft(current => ({ ...current, kind: event.target.value as OmniMemoryInput['kind'] }))}><option value="ANSWER_STYLE">Answer style</option><option value="WORK_PREFERENCE">Work preference</option></select>
      <HighCardinalitySelector label="Private memory scope" disabled={pending} value={draft.account_id ?? ''} onChange={accountId => setDraft(current => ({ ...current, account_id: accountId || null }))} allChoice={{ label: 'Global — all my account contexts', description: 'Use only when the preference applies across organizations' }} recentIds={[draft.account_id, ...items.map(item => item.account_id)].filter((id): id is string => Boolean(id))} choices={accounts.map(account => ({ id: account.id, label: account.name ?? account.legal_name ?? 'Unnamed organization', description: [account.relationship === 'CURRENT_CUSTOMER' ? 'Customer' : account.relationship === 'PROSPECT' || account.relationship === 'TARGET' ? 'Prospect' : 'Classification unavailable', account.location?.state].filter(Boolean).join(' · '), searchText: [account.legal_name, account.domain, ...(account.industries ?? [])].filter(Boolean).join(' ') }))} />
      <label htmlFor="memory-content">Preference</label><textarea id="memory-content" maxLength={600} required disabled={pending} value={draft.content} onChange={event => setDraft(current => ({ ...current, content: event.target.value }))} />
      <label htmlFor="memory-expiry">Expires after</label><select id="memory-expiry" disabled={pending} value={draft.ttl_days} onChange={event => setDraft(current => ({ ...current, ttl_days: Number(event.target.value) }))}>{[14, 30, 90, 365].map(days => <option key={days} value={days}>{days} days</option>)}</select>
      <Button type="submit" disabled={pending || !loaded || !draft.content.trim()}>{pending ? 'Saving…' : editing ? 'Save edited preference' : 'Save private preference'}</Button>
      {editing && <Button disabled={pending} onClick={() => { setEditing(undefined); setDraft(emptyDraft) }}>Cancel edit</Button>}
    </form>
  </Panel></section>
}
