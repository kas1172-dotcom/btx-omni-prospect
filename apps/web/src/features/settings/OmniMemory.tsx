import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import type { Account } from '../../types/api'
import type { OmniMemory as Memory, OmniMemoryInput } from '../../types/memory'
import { Button, Panel } from '../../components/UI'

export function OmniMemory({ accounts }: { accounts: Account[] }) {
  const [items, setItems] = useState<Memory[]>([])
  const [draft, setDraft] = useState<OmniMemoryInput>({ account_id: null, kind: 'ANSWER_STYLE', content: '', ttl_days: 90 })
  const [editing, setEditing] = useState<Memory>()
  const [deleting, setDeleting] = useState<string>()
  const [pending, setPending] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const [notice, setNotice] = useState('')
  const [refresh, setRefresh] = useState(0)
  const inFlight = useRef(false)
  const readEpoch = useRef(0)
  const createRequest = useRef<{ fingerprint: string; key: string } | null>(null)
  useEffect(() => {
    const controller = new AbortController()
    const epoch = ++readEpoch.current
    void api.memories(controller.signal).then(value => { if (!controller.signal.aborted && readEpoch.current === epoch) { setItems(value.items); setLoaded(true) } }).catch(() => { if (!controller.signal.aborted && readEpoch.current === epoch) setNotice('Memory could not be loaded. Refresh before editing; displayed preferences may be outdated.') })
    return () => controller.abort()
  }, [refresh])
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
      setEditing(undefined); setDraft({ account_id: null, kind: 'ANSWER_STYLE', content: '', ttl_days: 90 })
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
    <Button onClick={() => setRefresh(n => n + 1)} disabled={pending}>Refresh memories</Button>
    {!loaded && !notice && <p role="status">Loading private preferences…</p>}
    {notice && <p role="status">{notice}</p>}
    {loaded && items.length === 0 && <p>No saved preferences.</p>}
    {items.map(item => <article className="omni-memory-record" key={item.id}><strong>{item.kind === 'ANSWER_STYLE' ? 'Answer style' : 'Work preference'} · {item.account_id ?? 'All your account contexts'}</strong><p>{item.content}</p><small>{item.expired ? 'Expired' : 'Expires'} {new Date(item.expires_at).toLocaleDateString()} · version {item.version}</small>
      <div><Button disabled={pending} onClick={() => { setEditing(item); setDraft({ account_id: item.account_id, kind: item.kind, content: item.content, ttl_days: 90 }); setNotice('Editing this preference. Saving renews its expiry using the selected duration.') }}>Edit preference</Button><Button disabled={pending} onClick={() => setDeleting(item.id)}>Delete preference</Button></div>
      {deleting === item.id && <div><p>Delete this saved preference? Future Omni requests will no longer retrieve it.</p><Button disabled={pending} onClick={() => void remove(item)}>Confirm delete</Button><Button disabled={pending} onClick={() => setDeleting(undefined)}>Keep preference</Button></div>}</article>)}
    <form className="omni-memory-form" onSubmit={event => void save(event)}><h3>{editing ? 'Edit preference' : 'Save a preference'}</h3>
      <label htmlFor="memory-kind">Preference type</label><select id="memory-kind" disabled={pending} value={draft.kind} onChange={event => setDraft(current => ({ ...current, kind: event.target.value as OmniMemoryInput['kind'] }))}><option value="ANSWER_STYLE">Answer style</option><option value="WORK_PREFERENCE">Work preference</option></select>
      <label htmlFor="memory-scope">Private scope</label><select id="memory-scope" disabled={pending} value={draft.account_id ?? ''} onChange={event => setDraft(current => ({ ...current, account_id: event.target.value || null }))}><option value="">All my account contexts</option>{accounts.map(account => <option key={account.id} value={account.id}>{account.name ?? account.legal_name ?? account.id}</option>)}</select>
      <label htmlFor="memory-content">Preference</label><textarea id="memory-content" maxLength={600} required disabled={pending} value={draft.content} onChange={event => setDraft(current => ({ ...current, content: event.target.value }))} />
      <label htmlFor="memory-expiry">Expires after</label><select id="memory-expiry" disabled={pending} value={draft.ttl_days} onChange={event => setDraft(current => ({ ...current, ttl_days: Number(event.target.value) }))}>{[14, 30, 90, 365].map(days => <option key={days} value={days}>{days} days</option>)}</select>
      <Button type="submit" disabled={pending || !loaded || !draft.content.trim()}>{pending ? 'Saving…' : editing ? 'Save edited preference' : 'Save private preference'}</Button>
      {editing && <Button disabled={pending} onClick={() => { setEditing(undefined); setDraft({ account_id: null, kind: 'ANSWER_STYLE', content: '', ttl_days: 90 }) }}>Cancel edit</Button>}
    </form>
  </Panel></section>
}
