import { type KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import type { OmniResponse } from '../types/api'
import './omni-drawer.css'

type Message = { role: 'user' | 'assistant'; text: string; response?: OmniResponse }
type SessionAccount = { id: string; name: string }

const starters = [
  'What should I review today?',
  'Compare these researched companies.',
  'Explain this score and its gaps.',
  'What public evidence supports this action?',
]

export function OmniDrawer({ accountId, accountName, surface }: { accountId?: string; accountName?: string; surface: string }) {
  const [open, setOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sessionAccount, setSessionAccount] = useState<SessionAccount>()
  const [clearedAccountId, setClearedAccountId] = useState<string>()
  const opener = useRef<HTMLButtonElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const conversation = useRef<HTMLDivElement>(null)
  const activeAccount = useMemo(() => accountId && clearedAccountId !== accountId ? { id: accountId, name: accountName ?? 'Selected account' } : !accountId && clearedAccountId !== 'SESSION' ? sessionAccount : undefined, [accountId, accountName, clearedAccountId, sessionAccount])

  useEffect(() => {
    if (open) window.setTimeout(() => input.current?.focus(), 0)
    else opener.current?.focus()
  }, [open])
  useEffect(() => { conversation.current?.scrollTo({ top: conversation.current.scrollHeight, behavior: 'smooth' }) }, [messages, loading])

  const close = () => setOpen(false)
  const clearContext = () => { setClearedAccountId(accountId ?? 'SESSION'); setSessionAccount(undefined) }
  const ask = async (starter?: string) => {
    const text = (starter ?? question).trim()
    if (!text || loading) return
    const history = messages.slice(-4).map(message => `${message.role}: ${message.text}`).join('\n').slice(0, 1600)
    setMessages(old => [...old, { role: 'user', text }])
    setQuestion('')
    setLoading(true)
    setError('')
    try {
      const response = await api.omni(activeAccount?.id, text, { surface, session_account_id: activeAccount?.id ?? '', prior_turns: history })
      if (response.account_id && response.account_name) setSessionAccount({ id: response.account_id, name: response.account_name })
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
  return <>
    <button className="omni-launch" ref={opener} onClick={() => setOpen(true)} aria-label="Open Omni assistant">✦ <span>Ask Omni</span></button>
    {open && <div className="drawer-backdrop" onClick={close}>
      <aside className="omni-drawer" role="dialog" aria-modal="true" aria-labelledby="omni-title" onClick={event => event.stopPropagation()} onKeyDown={event => { if (event.key === 'Escape') close() }}>
        <header><div><span className="eyebrow">Read-only deterministic POC assistant · {surface}</span><h2 id="omni-title">Omni</h2></div><button onClick={close} aria-label="Close Omni">×</button></header>
        <div className="context-ribbon"><span>Context</span><strong>{activeAccount?.name ?? 'No account selected'}</strong>{activeAccount ? <button onClick={clearContext}>Clear</button> : accountId ? <button onClick={() => setClearedAccountId(undefined)}>Use selected account</button> : <small>Ask generally or open an Account 360 record.</small>}</div>
        <p className="muted omni-boundary">Grounded only in local POC read models. Public evidence is sourced; BTX commercial, CRM, quote, scoring, and workflow context is simulated. Omni cannot write to CRM.</p>
        <div className="starter-prompts" aria-label="Prompt starters">{starters.map(prompt => <button key={prompt} onClick={() => void ask(prompt)} disabled={loading}>{prompt}</button>)}</div>
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
