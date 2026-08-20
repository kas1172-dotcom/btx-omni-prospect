import { type KeyboardEvent, type PointerEvent, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import type { OmniContext, OmniConversationReferent, OmniResponse } from '../types/api'
import './omni-drawer.css'

type Message = { role: 'user' | 'assistant'; text: string; response?: OmniResponse }
type SessionAccount = { id: string; name: string }

const starters = [
  'What should I review today?',
  'Compare these researched companies.',
  'Explain this score and its gaps.',
  'What public evidence supports this action?',
]
const triggerStorageKey = 'btx-omni-trigger-position'
const triggerMargin = 14
const dragThreshold = 6
type TriggerPosition = { x: number; y: number }

const clampTriggerPosition = (position: TriggerPosition, element?: HTMLElement | null): TriggerPosition => {
  const width = element?.offsetWidth ?? 132
  const height = element?.offsetHeight ?? 52
  return { x: Math.min(Math.max(triggerMargin, position.x), Math.max(triggerMargin, window.innerWidth - width - triggerMargin)), y: Math.min(Math.max(triggerMargin, position.y), Math.max(triggerMargin, window.innerHeight - height - triggerMargin)) }
}
const dockTriggerPosition = (position: TriggerPosition, element?: HTMLElement | null): TriggerPosition => {
  const clamped = clampTriggerPosition(position, element)
  const width = element?.offsetWidth ?? 132
  return { x: Math.max(triggerMargin, window.innerWidth - width - triggerMargin), y: clamped.y }
}

export function OmniDrawer({ accountId, accountName, context }: { accountId?: string; accountName?: string; context: OmniContext }) {
  const [open, setOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sessionAccount, setSessionAccount] = useState<SessionAccount>()
  const [conversationReferent, setConversationReferent] = useState<OmniConversationReferent>()
  const [clearedAccountId, setClearedAccountId] = useState<string>()
  const [triggerPosition, setTriggerPosition] = useState<TriggerPosition>()
  const opener = useRef<HTMLButtonElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const conversation = useRef<HTMLDivElement>(null)
  const drag = useRef<{ start: TriggerPosition; origin: TriggerPosition; moved: boolean } | undefined>(undefined)
  const suppressClick = useRef(false)
  const activeAccount = useMemo(() => accountId && clearedAccountId !== accountId ? { id: accountId, name: accountName ?? 'Selected account' } : !accountId && clearedAccountId !== 'SESSION' ? sessionAccount : undefined, [accountId, accountName, clearedAccountId, sessionAccount])

  useEffect(() => {
    if (open) window.setTimeout(() => input.current?.focus(), 0)
    else opener.current?.focus()
  }, [open])
  useEffect(() => { conversation.current?.scrollTo({ top: conversation.current.scrollHeight, behavior: 'smooth' }) }, [messages, loading])
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(triggerStorageKey)
      if (saved) setTriggerPosition(clampTriggerPosition(JSON.parse(saved), opener.current))
    } catch { window.localStorage.removeItem(triggerStorageKey) }
  }, [])
  useEffect(() => {
    const clamp = () => setTriggerPosition(current => current ? clampTriggerPosition(current, opener.current) : current)
    window.addEventListener('resize', clamp)
    return () => window.removeEventListener('resize', clamp)
  }, [])

  const close = () => setOpen(false)
  const clearContext = () => { setClearedAccountId(accountId ?? 'SESSION'); setSessionAccount(undefined); setConversationReferent(undefined) }
  const ask = async (starter?: string) => {
    const text = (starter ?? question).trim()
    if (!text || loading) return
    const history = messages.slice(-4).map(message => `${message.role}: ${message.text}`).join('\n').slice(0, 1600)
    setMessages(old => [...old, { role: 'user', text }])
    setQuestion('')
    setLoading(true)
    setError('')
    try {
      const response = await api.omni(activeAccount?.id, text, { ...context, session_account_id: sessionAccount?.id, prior_turns: history, conversation_referent: conversationReferent })
      if (response.account_id && response.account_name) setSessionAccount({ id: response.account_id, name: response.account_name })
      setConversationReferent(response.conversation_referent ?? undefined)
      setMessages(old => [...old, { role: 'assistant', text: response.content, response }])
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Omni is unavailable. Your message was not sent.')
    } finally {
      setLoading(false)
    }
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void ask() }
  }
  const persistTriggerPosition = (position: TriggerPosition) => {
    setTriggerPosition(position)
    window.localStorage.setItem(triggerStorageKey, JSON.stringify(position))
  }
  const onTriggerPointerDown = (event: PointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0) return
    const bounds = event.currentTarget.getBoundingClientRect()
    drag.current = { start: { x: event.clientX, y: event.clientY }, origin: triggerPosition ?? { x: bounds.left, y: bounds.top }, moved: false }
    event.currentTarget.setPointerCapture(event.pointerId)
  }
  const onTriggerPointerMove = (event: PointerEvent<HTMLButtonElement>) => {
    if (!drag.current) return
    const deltaX = event.clientX - drag.current.start.x
    const deltaY = event.clientY - drag.current.start.y
    if (!drag.current.moved && Math.hypot(deltaX, deltaY) < dragThreshold) return
    drag.current.moved = true
    event.preventDefault()
    persistTriggerPosition(clampTriggerPosition({ x: drag.current.origin.x + deltaX, y: drag.current.origin.y + deltaY }, event.currentTarget))
  }
  const onTriggerPointerUp = (event: PointerEvent<HTMLButtonElement>) => {
    if (!drag.current) return
    suppressClick.current = drag.current.moved
    if (drag.current.moved) persistTriggerPosition(dockTriggerPosition({ x: event.clientX - drag.current.start.x + drag.current.origin.x, y: event.clientY - drag.current.start.y + drag.current.origin.y }, event.currentTarget))
    drag.current = undefined
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId)
  }
  const openDrawer = () => { if (suppressClick.current) { suppressClick.current = false; return }; setOpen(true) }
  return <>
    <button className={`omni-launch ${triggerPosition ? 'omni-launch-positioned' : ''}`} ref={opener} style={triggerPosition ? { left: triggerPosition.x, top: triggerPosition.y, right: 'auto', bottom: 'auto' } : undefined} onClick={openDrawer} onPointerDown={onTriggerPointerDown} onPointerMove={onTriggerPointerMove} onPointerUp={onTriggerPointerUp} onPointerCancel={onTriggerPointerUp} aria-label="Open Omni assistant">✦ <span>Ask Omni</span></button>
    {open && <div className="drawer-backdrop" onClick={close}>
      <aside className="omni-drawer" role="dialog" aria-modal="true" aria-labelledby="omni-title" onClick={event => event.stopPropagation()} onKeyDown={event => { if (event.key === 'Escape') close() }}>
        <header><div><span className="eyebrow">Product intelligence</span><h2 id="omni-title">✦ Omni</h2></div><button onClick={close} aria-label="Close Omni">×</button></header>
        <div className="context-ribbon"><span>Context</span><strong>{activeAccount?.name ?? 'No account selected'}</strong>{activeAccount ? <button onClick={clearContext}>Clear</button> : accountId ? <button onClick={() => setClearedAccountId(undefined)}>Use selected account</button> : <small>Ask generally or open an Account 360 record.</small>}</div>
        <p className="muted omni-boundary">Grounded only in local POC read models. Public evidence is sourced; BTX commercial, CRM, quote, scoring, and workflow context is simulated. Omni cannot write to CRM.</p>
        {!messages.length && <div className="starter-prompts" aria-label="Prompt starters">{starters.map(prompt => <button key={prompt} onClick={() => void ask(prompt)} disabled={loading}>{prompt}</button>)}</div>}
        <div className="conversation" ref={conversation} aria-live="polite" aria-label="Omni conversation">
          {!messages.length && !loading && <div className="omni-empty"><strong>Start a seller conversation</strong><p>Ask about the curated public-company universe, a company’s public evidence, a score gap, an action, or nearby map context.</p></div>}
          {messages.map((message, index) => <article className={`message ${message.role}`} key={`${message.role}-${index}`}><strong>{message.role === 'user' ? 'You' : 'Omni'}</strong><p>{message.text}</p>{message.response && <ResponseDetails response={message.response} />}</article>)}
          {loading && <div className="message assistant pending"><strong>Omni</strong><p>Checking governed POC context…</p></div>}
        </div>
        <form className="omni-compose" onSubmit={event => { event.preventDefault(); void ask() }}><label htmlFor="omni-message">Message</label><textarea id="omni-message" ref={input} value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={onKeyDown} placeholder="Ask about a company, public event, score, action, or geography" rows={3} /><div><small>Enter to send · Shift+Enter for a new line</small><button className="primary" disabled={loading || !question.trim()} type="submit">{loading ? 'Checking…' : 'Send'}</button></div></form>
        {error && <p className="error" role="alert">{error}</p>}
        <p className="omni-session">Conversation is retained only in this browser session and clears when this page is refreshed. Deterministic fallback—not model-generated advice.</p>
      </aside>
    </div>}
  </>
}

function ResponseDetails({ response }: { response: OmniResponse }) {
  return <div className="omni-response-details">
    {response.citation_links?.length ? <section><strong>Public evidence</strong><ul>{response.citation_links.map(citation => <li key={citation.url}><a href={citation.url} target="_blank" rel="noreferrer">{citation.label} ↗</a></li>)}</ul></section> : null}
    {response.missingness.length ? <section><strong>Missing or unavailable</strong><p>{response.missingness.join(' ')}</p></section> : null}
    {response.recommended_action ? <section><strong>Suggested next step</strong><p>{response.recommended_action}</p></section> : null}
  </div>
}
