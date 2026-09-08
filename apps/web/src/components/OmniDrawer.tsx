import { type KeyboardEvent, type RefObject, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { Button, Disclosure, Drawer, EvidenceSource, IconButton } from './UI'
import type { OmniContext, OmniConversationReferent, OmniResponse } from '../types/api'
import { OmniRunReceipt } from './OmniRunReceipt'
import './omni-drawer.css'
import { CanonicalRecord } from './CanonicalRecord'

type Message = { role: 'user' | 'assistant'; text: string; response?: OmniResponse }
type SessionAccount = { id: string; name: string }
type FullMode = 'conversation' | 'evidence' | 'customer'

const starters = ['What should I review today?', 'Explain why this Customer matters', 'Compare selected Customers', 'Show the supporting evidence']
const surfaceLabels: Record<string, string> = { TODAY: 'Today', ACCOUNTS: 'Customers & Prospects', ACCOUNT_DETAIL: 'Customer 360', INTELLIGENCE: 'Intelligence', MAP: 'Map', ACTIONS: 'Actions', MONITOR: 'Monitor' }

export function OmniDrawer({ accountId, accountName, context }: { accountId?: string; accountName?: string; context: OmniContext }) {
  const [view, setView] = useState<'closed' | 'quick' | 'full'>('closed')
  const [fullMode, setFullMode] = useState<FullMode>('conversation')
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sessionAccount, setSessionAccount] = useState<SessionAccount>()
  const [conversationReferent, setConversationReferent] = useState<OmniConversationReferent>()
  const [clearedAccountId, setClearedAccountId] = useState<string>()
  const opener = useRef<HTMLButtonElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const conversation = useRef<HTMLDivElement>(null)
  const activeAccount = accountId && clearedAccountId !== accountId ? { id: accountId, name: accountName ?? 'Selected Customer' } : !accountId && clearedAccountId !== 'SESSION' ? sessionAccount : undefined
  const latestResponse = [...messages].reverse().find(message => message.response)?.response

  useEffect(() => {
    if (view !== 'closed') window.setTimeout(() => input.current?.focus(), 0)
  }, [view])
  useEffect(() => {
    const transcript = conversation.current
    if (transcript) transcript.scrollTo({ top: transcript.scrollHeight, behavior: 'auto' })
  }, [messages, loading, view])

  const clearContext = () => { setClearedAccountId(accountId ?? 'SESSION'); setSessionAccount(undefined); setConversationReferent(undefined) }
  const useSelectedContext = () => setClearedAccountId(undefined)
  const ask = async (starter?: string) => {
    const text = (starter ?? question).trim()
    if (!text || loading) return
    const history = messages.slice(-6).map(message => `${message.role}: ${message.text}`).join('\n').slice(-1600)
    setMessages(old => [...old, { role: 'user', text }]); setQuestion(''); setLoading(true); setError('')
    try {
      const response = await api.omni(activeAccount?.id, text, { ...context, relationship_selection: activeAccount ? context.relationship_selection : undefined, session_account_id: sessionAccount?.id, prior_turns: history, conversation_referent: conversationReferent })
      if (response.account_id && response.account_name) setSessionAccount({ id: response.account_id, name: response.account_name })
      setConversationReferent(response.conversation_referent ?? undefined)
      setMessages(old => [...old, { role: 'assistant', text: response.content, response }])
    } catch (caught) {
      setError(caught instanceof Error ? 'Omni could not complete that response. Governed context remains available.' : 'Omni is temporarily unavailable.')
    } finally { setLoading(false) }
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void ask() } }
  const close = () => { setView('closed'); window.setTimeout(() => opener.current?.focus(), 0) }
  return <>
    <button className="omni-launch" ref={opener} onClick={() => setView('quick')} aria-label="Open Omni assistant">✦ <span>Ask Omni</span></button>
    <Drawer open={view === 'quick'} onClose={close} titleId="quick-omni-title" className="quick-omni">
      <header><h2 id="quick-omni-title">Ask Omni</h2><Button variant="ghost" onClick={() => setView('full')}>Open in Omni</Button><IconButton onClick={close} label="Minimize Omni">−</IconButton><IconButton onClick={close} label="Close Omni">×</IconButton></header>
      <div className="omni-awareness">Aware of: {activeAccount?.name ?? (context.surface && surfaceLabels[context.surface]) ?? 'current workspace'}{activeAccount && <button onClick={clearContext}>Clear</button>}{!activeAccount && accountId && <button onClick={useSelectedContext}>Use selected Customer</button>}</div>
      <Conversation messages={messages} loading={loading} compact transcriptRef={conversation} onStarter={prompt => void ask(prompt)} />
      <Composer value={question} loading={loading} inputRef={input} onChange={setQuestion} onKeyDown={onKeyDown} onSubmit={() => void ask()} />
      {error && <p className="omni-error" role="alert">{error}</p>}
    </Drawer>
    <Drawer open={view === 'full'} onClose={close} titleId="full-omni-title" className="full-omni">
      <header><IconButton onClick={() => setView('quick')} label="Back to Quick Omni">‹</IconButton><div><span className="eyebrow">Research · Compare · Explain · Plan</span><h1 id="full-omni-title">Omni</h1></div><IconButton onClick={close} label="Close Full Omni">×</IconButton></header>
      <nav className="omni-modes" aria-label="Omni workspace modes" role="tablist">{(['conversation', 'evidence', 'customer'] as const).map(mode => <button id={`omni-tab-${mode}`} key={mode} className={fullMode === mode ? 'active' : ''} role="tab" aria-selected={fullMode === mode} aria-controls={`omni-panel-${mode}`} tabIndex={fullMode === mode ? 0 : -1} onClick={() => setFullMode(mode)}>{mode === 'customer' ? 'Customer context' : mode[0].toUpperCase() + mode.slice(1)}</button>)}</nav>
      <div className="full-omni-grid">
        <main id="omni-panel-conversation" aria-labelledby="omni-tab-conversation" className={`omni-conversation-pane ${fullMode === 'conversation' ? 'mobile-active' : ''}`} role="tabpanel"><div className="omni-context-chips">{activeAccount && <span>{activeAccount.name}</span>}<span>{(context.surface && surfaceLabels[context.surface]) ?? 'Global'}</span></div><Conversation messages={messages} loading={loading} transcriptRef={conversation} onStarter={prompt => void ask(prompt)} /><Composer value={question} loading={loading} inputRef={input} onChange={setQuestion} onKeyDown={onKeyDown} onSubmit={() => void ask()} />{error && <p className="omni-error" role="alert">{error}</p>}</main>
        <aside id="omni-panel-evidence" aria-label="Evidence" aria-labelledby="omni-tab-evidence" className={`omni-evidence-pane ${fullMode === 'evidence' ? 'mobile-active' : ''}`}><h2>Evidence &amp; sources</h2><EvidencePanel response={latestResponse} /></aside>
        <aside id="omni-panel-customer" aria-label="Customer context" aria-labelledby="omni-tab-customer" className={`omni-customer-pane ${fullMode === 'customer' ? 'mobile-active' : ''}`}><h2>Customer context</h2>{activeAccount ? <div className="omni-context-card"><strong>{activeAccount.name}</strong><span>Canonical Customer context</span><p>Current selection and governed conversation referents determine what Omni may read.</p><Button variant="ghost" onClick={clearContext}>Clear Customer context</Button></div> : <p className="muted">No Customer selected. Global questions remain unscoped.</p>}{latestResponse?.recommended_action && <div className="omni-context-card"><strong>Suggested next step</strong><p>{latestResponse.recommended_action}</p><small>Discussion only. Use the governed Actions workspace for mutations.</small></div>}</aside>
      </div>
    </Drawer>
  </>
}

function Conversation({ messages, loading, compact = false, transcriptRef, onStarter }: { messages: Message[]; loading: boolean; compact?: boolean; transcriptRef: RefObject<HTMLDivElement | null>; onStarter: (prompt: string) => void }) {
  return <div className={`conversation ${compact ? 'compact' : ''}`} ref={transcriptRef} aria-live="polite" aria-label="Omni conversation">{!messages.length && <div className="omni-welcome"><strong>How can I help?</strong><p>Ask about Customers, evidence, relationships, Intelligence, geography, or permitted Actions.</p><div className="starter-prompts" aria-label="Prompt starters">{starters.map(prompt => <button key={prompt} onClick={() => onStarter(prompt)} disabled={loading}>{prompt}</button>)}</div></div>}{messages.map((message, index) => <article className={`message ${message.role}`} key={`${message.role}-${index}`}><p>{message.text}</p>{message.response && <ResponseDetails response={message.response} />}</article>)}{loading && <div className="message assistant pending"><p>Reviewing governed context…</p></div>}</div>
}

function Composer({ value, loading, inputRef, onChange, onKeyDown, onSubmit }: { value: string; loading: boolean; inputRef: RefObject<HTMLTextAreaElement | null>; onChange: (value: string) => void; onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void; onSubmit: () => void }) {
  return <form className="omni-compose" onSubmit={event => { event.preventDefault(); onSubmit() }}><label className="sr-only" htmlFor="omni-message">Ask Omni</label><textarea id="omni-message" ref={inputRef} value={value} onChange={event => onChange(event.target.value)} onKeyDown={onKeyDown} placeholder="Ask Omni anything…" rows={1} /><Button variant="primary" disabled={loading || !value.trim()} type="submit">{loading ? 'Working…' : 'Send'}</Button></form>
}

const fallbackLabels: Record<Exclude<OmniResponse['provider_status'], 'AVAILABLE'>, string> = {
  NOT_CONFIGURED: 'Gemini not configured · governed fallback',
  AUTH_FAILED: 'Gemini authentication unavailable · governed fallback',
  TIMEOUT: 'Gemini timed out · governed fallback',
  QUOTA: 'Gemini quota unavailable · governed fallback',
  UNAVAILABLE: 'Gemini temporarily unavailable · governed fallback',
}

function ResponseDetails({ response }: { response: OmniResponse }) { return <div className="omni-response-summary">{response.run_id && <Disclosure title="Private answer run · inspect outcome"><OmniRunReceipt key={response.run_id} id={response.run_id} /></Disclosure>}{response.structured_relationship && <Disclosure title="Canonical selected route · factors and constraints"><ol>{response.structured_relationship.route.steps.map(step => <li key={step.id}>{step.label}</li>)}</ol><p>{response.structured_relationship.route.hop_count} actual edges · utility {response.structured_relationship.route.utility}, not a probability · {response.structured_relationship.rubric_version}</p>{response.structured_relationship.route.constraints.map(c => <p key={c.id}>{c.reason}</p>)}<p>{response.structured_relationship.route.next_action}</p><small>Graph revision {response.structured_relationship.graph_revision}</small></Disclosure>}
    {response.structured_reads && <Disclosure title={`${response.structured_reads.steps.length} canonical reads · inspect linked records`}><p>{response.structured_reads.model_requested_stop ? 'The model finished selecting reads; this is not proof that every evidence gap is closed.' : `The bounded read sequence stopped: ${response.structured_reads.stop_reason.toLowerCase().replaceAll('_', ' ')}. Completed records remain available.`}</p>
      {response.structured_reads.reads.map((read, index) => <Disclosure key={`${index}:${read.tool}`} title={read.tool.replaceAll('_', ' ')}><div className="commercial-evidence-detail"><CanonicalRecord value={read.result} /></div></Disclosure>)}
      <small>{response.structured_reads.configuration_version} · {response.structured_reads.elapsed_ms} ms · canonical revision {response.structured_reads.revision}</small></Disclosure>}
    <Disclosure title={`${response.citation_links?.length ?? 0} public sources · Inspect evidence`}><EvidencePanel response={response} /></Disclosure>{response.provider_status !== 'AVAILABLE' && <small>{response.context_used?.synthesis_validation ? 'Showing canonical records because the model wording did not pass evidence checks.' : fallbackLabels[response.provider_status]}</small>}</div> }

function EvidencePanel({ response }: { response?: OmniResponse }) {
  if (!response) return <p className="muted">Sources appear here when a response uses evidence.</p>
  return <div className="omni-evidence-list">{response.citation_links?.map(citation => <EvidenceSource key={`${citation.url}:${citation.label}`} title={citation.label} source="Cited public source" evidenceState="CITED" url={citation.url} />)}{!response.citation_links?.length && <p className="muted">No external source link was supplied for this response.</p>}{response.missingness.length > 0 && <section><strong>Unavailable or needs research</strong><p>{response.missingness.join(' ')}</p></section>}</div>
}
