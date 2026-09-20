import { type KeyboardEvent, type RefObject, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { Button, Disclosure, Drawer, EvidenceSource, IconButton, PrecisionLoader } from './UI'
import type { OmniContext, OmniConversationReferent, OmniResponse } from '../types/api'
import { OmniRunReceipt } from './OmniRunReceipt'
import './omni-drawer.css'
import { CanonicalRecord } from './CanonicalRecord'
import { OmniMarkdown } from './OmniMarkdown'
import { OmniActionProposal } from './OmniActionProposal'

type Message = { role: 'user' | 'assistant'; text: string; response?: OmniResponse }
type SessionAccount = { id: string; name: string }
type FullMode = 'conversation' | 'evidence' | 'customer'

const starters = ['What should I review today?', 'Explain why this organization matters', 'Compare selected organizations', 'Show the supporting evidence']
const screenStarters: Record<string, string[]> = {
  TODAY: ['What should I review today?', 'Show my open Actions'],
  ACCOUNTS: ['Summarize this screen', 'Compare selected organizations'],
  ACCOUNT_DETAIL: ['Does this organization have quote history?', 'Explain its assessments'],
  MAP: ['Which sites are nearby?', 'What do we know about this organization?'],
  INTELLIGENCE: ['What changed recently?', 'Separate public news from our orders'],
  ACTIONS: ['Show my open Actions', 'What should I review next?'],
}
const surfaceLabels: Record<string, string> = { TODAY: 'Today', ACCOUNTS: 'Customers & Prospects', ACCOUNT_DETAIL: 'Organization 360', INTELLIGENCE: 'Intelligence', MAP: 'Map', ACTIONS: 'Actions', SETTINGS: 'Settings', COMMUNICATIONS: 'Communications', MONITOR: 'Monitor' }
const selectedRelationshipQuestion = (question: string) => /\b(?:selected|this|that)\s+(?:relationship\s+)?(?:route|path|connection|relationship)\b/i.test(question)
const selectedAssessmentQuestion = (question: string) => /\b(?:selected|this|that)\s+(?:intelligence\s+)?assessment\b/i.test(question)

async function waitForSelectedGovernedContext(contextRef: { current: OmniContext }, question: string) {
  let current = contextRef.current
  const relationshipPending = current.surface === 'ACCOUNT_DETAIL' && !current.relationship_selection && selectedRelationshipQuestion(question)
  const assessmentPending = ['TODAY', 'INTELLIGENCE', 'ACCOUNT_DETAIL', 'MAP'].includes(current.surface ?? '') && !current.selected_assessment && selectedAssessmentQuestion(question)
  if (!relationshipPending && !assessmentPending) return current
  const deadline = Date.now() + 5_000
  while (Date.now() < deadline) {
    await new Promise(resolve => window.setTimeout(resolve, 100))
    current = contextRef.current
    if ((!relationshipPending || current.relationship_selection) && (!assessmentPending || current.selected_assessment)) break
  }
  return current
}

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
  const [conversationId, setConversationId] = useState<string>()
  const [saved, setSaved] = useState<Array<{ id: string; title: string }>>([])
  const [retention, setRetention] = useState(30)
  const [progress, setProgress] = useState('')
  const [partial, setPartial] = useState('')
  const controller = useRef<AbortController | null>(null)
  const opener = useRef<HTMLButtonElement>(null)
  const input = useRef<HTMLTextAreaElement>(null)
  const conversation = useRef<HTMLDivElement>(null)
  const contextRef = useRef(context)
  const activeAccount = accountId && clearedAccountId !== accountId ? { id: accountId, name: accountName ?? 'Selected organization' } : !accountId && clearedAccountId !== 'SESSION' ? sessionAccount : undefined
  const latestResponse = [...messages].reverse().find(message => message.response)?.response

  useLayoutEffect(() => { contextRef.current = context }, [context])
  useEffect(() => { const open = () => setView('quick'); window.addEventListener('btx:open-omni', open); return () => window.removeEventListener('btx:open-omni', open) }, [])
  useEffect(() => { if (view !== 'closed') void api.chatHistory().then(value => { setSaved(value.items); setRetention(value.retention_days) }).catch(() => setError('Conversation history is unavailable.')) }, [view, messages])
  useEffect(() => () => controller.current?.abort(), [])

  useEffect(() => {
    const transcript = conversation.current
    if (transcript) transcript.scrollTo({ top: transcript.scrollHeight, behavior: 'auto' })
  }, [messages, loading, view])

  const clearContext = () => { setClearedAccountId(accountId ?? 'SESSION'); setSessionAccount(undefined); setConversationReferent(undefined) }
  const useSelectedContext = () => setClearedAccountId(undefined)
  const resume = async (id: string) => {
    try { const thread = await api.chatResume(id); setConversationId(id); setMessages(thread.turns); const previous = [...thread.turns].reverse().find(t => t.response)?.response; setConversationReferent(previous?.conversation_referent ?? undefined); setSessionAccount(previous?.account_id ? { id: previous.account_id, name: previous.account_name ?? previous.account_id } : undefined) }
    catch { setError('Could not load that conversation.') }
  }
  const newConversation = () => { setConversationId(undefined); setMessages([]); setSessionAccount(undefined); setConversationReferent(undefined); setError('') }
  const historyControls = <Disclosure title="Conversations"><p>Private to your app identity. Retained for {retention} days of inactivity.</p><Button disabled={loading} onClick={newConversation}>New conversation</Button>{saved.map(thread => <div key={thread.id}><Button disabled={loading} onClick={() => void resume(thread.id)}>{thread.title}</Button><Button disabled={loading} onClick={() => { const title = window.prompt('Conversation title', thread.title); if (title?.trim()) void api.chatRename(thread.id, title).then(() => setSaved(old => old.map(t => t.id === thread.id ? { ...t, title } : t))).catch(() => setError('Could not rename conversation.')) }}>Rename</Button><Button disabled={loading} onClick={() => { if (window.confirm('Delete this conversation and its feedback?')) void api.chatDelete(thread.id).then(() => { setSaved(old => old.filter(t => t.id !== thread.id)); if (conversationId === thread.id) newConversation() }).catch(() => setError('Could not delete conversation.')) }}>Delete</Button></div>)}</Disclosure>
  const ask = async (starter?: string) => {
    const text = (starter ?? question).trim()
    if (!text || loading) return
    const history = messages.slice(-6).map(message => `${message.role}: ${message.text}`).join('\n').slice(-1600)
    setMessages(old => [...old, { role: 'user', text }]); setQuestion(''); setLoading(true); setError(''); setProgress('Thinking…'); setPartial('')
    controller.current = new AbortController()
    try {
      const currentContext = await waitForSelectedGovernedContext(contextRef, text)
      if (selectedRelationshipQuestion(text) && currentContext.surface === 'ACCOUNT_DETAIL' && !currentContext.relationship_selection) {
        setMessages(old => old.slice(0, -1))
        setQuestion(text)
        setError('The selected relationship is still refreshing. Wait for the connection update, then send again.')
        return
      }
      if (selectedAssessmentQuestion(text) && ['TODAY', 'INTELLIGENCE', 'ACCOUNT_DETAIL', 'MAP'].includes(currentContext.surface ?? '') && !currentContext.selected_assessment && !conversationReferent?.assessment_id) {
        setMessages(old => old.slice(0, -1))
        setQuestion(text)
        setError('The selected Intelligence assessment is still refreshing. Reopen its evidence and choose Use in Omni, then send again.')
        return
      }
      await api.chatStream({ account_id: activeAccount?.id, question: text, conversation_id: conversationId, context: { ...currentContext, relationship_selection: activeAccount ? currentContext.relationship_selection : undefined, session_account_id: sessionAccount?.id, prior_turns: history, conversation_referent: conversationReferent } }, controller.current.signal, (event, data) => {
        if (event === 'conversation') setConversationId(String(data.id))
        if (event === 'progress') setProgress(String(data.text))
        if (event === 'delta') setPartial(old => old + String(data.text))
        if (event === 'error') throw new Error(String(data.message))
        if (event === 'answer') {
          const response = data.response as OmniResponse
          if (response.account_id && response.account_name) setSessionAccount({ id: response.account_id, name: response.account_name })
          setConversationReferent(response.conversation_referent ?? undefined)
          setMessages(old => [...old, { role: 'assistant', text: response.content, response }]); setPartial('')
        }
      })
    } catch (caught) {
      setError(caught instanceof DOMException && caught.name === 'AbortError' ? 'Stopped. No business data was changed.' : 'Omni could not complete that response. Retry when ready.')
      setQuestion(text)
    } finally { setLoading(false) }
  }
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void ask() } }
  const close = () => { setView('closed'); window.setTimeout(() => opener.current?.focus(), 0) }
  return <>
    <button className="omni-launch" ref={opener} onClick={() => setView('quick')} aria-label="Open Omni assistant">✦ <span>Ask Omni</span></button>
    <Drawer open={view === 'quick'} onClose={close} titleId="quick-omni-title" className="quick-omni" initialFocus={input}>
      <header><h2 id="quick-omni-title">Ask Omni</h2><Button variant="ghost" onClick={() => setView('full')}>Open in Omni</Button><IconButton onClick={close} label="Minimize Omni">−</IconButton><IconButton onClick={close} label="Close Omni">×</IconButton></header>
      <div className="omni-awareness">Aware of: {context.selected_federal_opportunity ? 'selected federal opportunity' : activeAccount?.name ?? (context.surface && surfaceLabels[context.surface]) ?? 'current workspace'}{activeAccount && <button onClick={clearContext}>Clear</button>}{!activeAccount && accountId && <button onClick={useSelectedContext}>Use selected organization</button>}</div>
      {historyControls}
      <Conversation messages={messages} loading={loading} compact transcriptRef={conversation} onStarter={prompt => void ask(prompt)} prompts={screenStarters[context.surface ?? ''] ?? starters} progress={progress} partial={partial} conversationId={conversationId} />
      {loading && <Button onClick={() => controller.current?.abort()}>Cancel</Button>}
      <Composer value={question} loading={loading} inputRef={input} onChange={setQuestion} onKeyDown={onKeyDown} onSubmit={() => void ask()} />
      {error && <p className="omni-error" role="alert">{error}</p>}
    </Drawer>
    <Drawer open={view === 'full'} onClose={close} titleId="full-omni-title" className="full-omni" initialFocus={input}>
      <header><IconButton onClick={() => setView('quick')} label="Back to Quick Omni">‹</IconButton><div><span className="eyebrow">Research · Compare · Explain · Plan</span><h1 id="full-omni-title">Omni</h1></div><IconButton onClick={close} label="Close Full Omni">×</IconButton></header>
      <nav className="omni-modes" aria-label="Omni workspace modes" role="tablist">{(['conversation', 'evidence', 'customer'] as const).map(mode => <button id={`omni-tab-${mode}`} key={mode} className={fullMode === mode ? 'active' : ''} role="tab" aria-selected={fullMode === mode} aria-controls={`omni-panel-${mode}`} tabIndex={fullMode === mode ? 0 : -1} onClick={() => setFullMode(mode)}>{mode === 'customer' ? 'Organization context' : mode[0].toUpperCase() + mode.slice(1)}</button>)}</nav>
      <div className="full-omni-grid">
        <main id="omni-panel-conversation" aria-labelledby="omni-tab-conversation" className={`omni-conversation-pane ${fullMode === 'conversation' ? 'mobile-active' : ''}`} role="tabpanel"><div className="omni-context-chips">{activeAccount && <span>{activeAccount.name}</span>}<span>{(context.surface && surfaceLabels[context.surface]) ?? 'Global'}</span></div>{historyControls}<Conversation messages={messages} loading={loading} transcriptRef={conversation} onStarter={prompt => void ask(prompt)} prompts={screenStarters[context.surface ?? ''] ?? starters} progress={progress} partial={partial} conversationId={conversationId} />{loading && <Button onClick={() => controller.current?.abort()}>Cancel</Button>}<Composer value={question} loading={loading} inputRef={input} onChange={setQuestion} onKeyDown={onKeyDown} onSubmit={() => void ask()} />{error && <p className="omni-error" role="alert">{error}</p>}</main>
        <aside id="omni-panel-evidence" aria-label="Evidence" aria-labelledby="omni-tab-evidence" className={`omni-evidence-pane ${fullMode === 'evidence' ? 'mobile-active' : ''}`}><h2>Evidence &amp; sources</h2><Disclosure title={`View supporting evidence (${latestResponse?.citation_links?.length ?? 0})`}><EvidencePanel response={latestResponse} /></Disclosure></aside>
        <aside id="omni-panel-customer" aria-label="Organization context" aria-labelledby="omni-tab-customer" className={`omni-customer-pane ${fullMode === 'customer' ? 'mobile-active' : ''}`}><h2>Organization context</h2>{activeAccount ? <div className="omni-context-card"><strong>{activeAccount.name}</strong><span>Selected organization</span><p>Omni will use this organization, the selected assessment, and directly related records in its answer.</p><Button variant="ghost" onClick={clearContext}>Clear organization context</Button></div> : <p className="muted">No organization selected. Global questions remain unscoped.</p>}{latestResponse?.recommended_action && <div className="omni-context-card"><strong>Suggested next step</strong><p>{latestResponse.recommended_action}</p><small>Discussion only. Use Actions to create or update work.</small></div>}</aside>
      </div>
    </Drawer>
  </>
}

function Conversation({ messages, loading, compact = false, transcriptRef, onStarter, prompts, progress, partial, conversationId }: { messages: Message[]; loading: boolean; compact?: boolean; transcriptRef: RefObject<HTMLDivElement | null>; onStarter: (prompt: string) => void; prompts: string[]; progress: string; partial: string; conversationId?: string }) {
  const [notice, setNotice] = useState('')
  const rate = (run: string, rating: 'up' | 'down') => { if (conversationId) { const reason = window.prompt('Optional feedback reason') ?? ''; void api.chatFeedback(conversationId, run, rating, reason).then(() => setNotice('Feedback saved. It does not change data or scores.')).catch(() => setNotice('Feedback could not be saved.')) } }
  return <div className={`conversation ${compact ? 'compact' : ''}`} ref={transcriptRef} aria-live="polite" aria-label="Omni conversation">{!messages.length && <div className="omni-welcome"><strong>How can I help?</strong><p>Ask about BTX data, public developments, or general questions.</p><div className="starter-prompts" aria-label="Prompt starters">{prompts.map(prompt => <button key={prompt} onClick={() => onStarter(prompt)} disabled={loading}>{prompt}</button>)}</div></div>}{messages.map((message, index) => <article className={`message ${message.role}`} key={`${message.role}-${index}`}><OmniMarkdown text={message.text} />{message.response && <><ChatSources response={message.response} /><Disclosure title="Details"><ResponseDetails response={message.response} /></Disclosure><div className="card-actions"><Button disabled={loading} onClick={() => onStarter(messages[index - 1]?.text ?? '')}>Retry</Button><Button onClick={() => void navigator.clipboard.writeText(message.text).then(() => setNotice('Copied.')).catch(() => setNotice('Copy is unavailable.'))}>Copy</Button>{message.response.run_id && <><Button onClick={() => rate(message.response!.run_id!, 'up')}>Thumbs up</Button><Button onClick={() => rate(message.response!.run_id!, 'down')}>Thumbs down</Button></>}</div>{index === messages.length - 1 && message.response.account_name && <div className="starter-prompts"><button disabled={loading} onClick={() => onStarter('Show its open Actions')}>Open Actions</button><button disabled={loading} onClick={() => onStarter('What is missing from its assessment?')}>What is missing?</button></div>}</>}</article>)}{loading && <div className="message assistant pending" role="status" aria-busy="true"><PrecisionLoader size="compact" /><p>{progress}</p>{partial && <OmniMarkdown text={partial} />}</div>}{notice && <p role="status">{notice}</p>}</div>
}

function ChatSources({ response }: { response: OmniResponse }) {
  return <>{response.recommended_action && response.account_id && <OmniActionProposal accountId={response.account_id} title={response.recommended_action} />}<Disclosure title="Sources"><h4>BTX data</h4>{response.account_id ? <a href={`#/accounts/${encodeURIComponent(response.account_id)}`}>Open {response.account_name ?? 'organization'} records</a> : <p>No organization records used.</p>}<h4>Public sources</h4><EvidencePanel response={response} /></Disclosure></>
}

function Composer({ value, loading, inputRef, onChange, onKeyDown, onSubmit }: { value: string; loading: boolean; inputRef: RefObject<HTMLTextAreaElement | null>; onChange: (value: string) => void; onKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void; onSubmit: () => void }) {
  return <form className="omni-compose" onSubmit={event => { event.preventDefault(); onSubmit() }}><label className="sr-only" htmlFor="omni-message">Ask Omni</label><textarea id="omni-message" ref={inputRef} value={value} onChange={event => onChange(event.target.value)} onKeyDown={onKeyDown} placeholder="Ask Omni anything…" rows={1} /><Button variant="primary" loading={loading} loadingLabel="Reviewing context…" disabled={!value.trim()} type="submit">Send</Button></form>
}

const fallbackLabels: Record<Exclude<OmniResponse['provider_status'], 'AVAILABLE'>, string> = {
  NOT_CONFIGURED: 'Gemini not configured · structured evidence summary',
  AUTH_FAILED: 'Gemini authentication unavailable · structured evidence summary',
  TIMEOUT: 'Gemini timed out · structured evidence summary',
  QUOTA: 'Gemini quota unavailable · structured evidence summary',
  UNAVAILABLE: 'Gemini temporarily unavailable · structured evidence summary',
}

function ResponseDetails({ response }: { response: OmniResponse }) { return <div className="omni-response-summary">{response.run_id && <Disclosure title="Answer receipt"><OmniRunReceipt key={response.run_id} id={response.run_id} /></Disclosure>}{response.structured_relationship && <Disclosure title="Selected route · reasons and constraints"><ol>{response.structured_relationship.route.steps.map(step => <li key={step.id}>{step.label}</li>)}</ol><p>{response.structured_relationship.route.hop_count} connections · route strength {Number(response.structured_relationship.route.utility).toFixed(1)} out of 100, not a probability</p>{response.structured_relationship.route.constraints.map(c => <p key={c.id}>{c.reason}</p>)}<p>{response.structured_relationship.route.next_action}</p><Disclosure title="Technical receipt"><small>{response.structured_relationship.rubric_version} · graph revision {response.structured_relationship.graph_revision}</small></Disclosure></Disclosure>}
    {response.structured_reads && <Disclosure title={`${response.structured_reads.steps.length} supporting record checks`}><p>{response.structured_reads.model_requested_stop ? 'Omni finished the requested checks; unresolved evidence remains identified in the answer.' : 'Some requested checks could not be completed. The records already found remain available.'}</p>
      {response.structured_reads.reads.map((read, index) => <Disclosure key={`${index}:${read.tool}`} title={`Supporting record ${index + 1}`}><div className="commercial-evidence-detail"><CanonicalRecord value={read.result} /></div></Disclosure>)}
      <Disclosure title="Technical receipt"><small>{response.structured_reads.configuration_version} · {response.structured_reads.elapsed_ms} ms · revision {response.structured_reads.revision}</small></Disclosure></Disclosure>}
    <Disclosure title={`${response.citation_links?.length ?? 0} public sources · Inspect evidence`}><EvidencePanel response={response} /></Disclosure>{response.provider_status !== 'AVAILABLE' && <Disclosure title="Answer delivery details"><small>{response.context_used?.synthesis_validation ? 'Showing canonical records because the model wording did not pass evidence checks.' : fallbackLabels[response.provider_status]}</small></Disclosure>}</div> }

function EvidencePanel({ response }: { response?: OmniResponse }) {
  if (!response) return <p className="muted">Sources appear here when a response uses evidence.</p>
  return <div className="omni-evidence-list">{response.citation_links?.map(citation => <EvidenceSource key={`${citation.url}:${citation.label}`} title={citation.label} source="Cited public source" evidenceState="CITED" url={citation.url} />)}{!response.citation_links?.length && <p className="muted">No external source link was supplied for this response.</p>}{response.missingness.length > 0 && <section><strong>Unavailable or needs research</strong><p>{response.missingness.join(' ')}</p></section>}</div>
}
