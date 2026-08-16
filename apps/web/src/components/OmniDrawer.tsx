import { useState } from 'react'
import { api } from '../api/client'
import type { OmniResponse } from '../types/api'

export function OmniDrawer({ accountId }: { accountId?: string }) {
  const [open, setOpen] = useState(false); const [question, setQuestion] = useState('Explain the governed context and recommended action.'); const [response, setResponse] = useState<OmniResponse>(); const [error, setError] = useState('')
  const ask = async () => { if (!accountId) return setError('Select an account to ground this question.'); try { setError(''); setResponse(await api.omni(accountId, question)) } catch (err) { setError(err instanceof Error ? err.message : 'Omni is unavailable.') } }
  return <><button className="omni-launch" onClick={() => setOpen(true)} aria-label="Open Omni assistant">✦ <span>Ask Omni</span></button>{open && <div className="drawer-backdrop" onClick={() => setOpen(false)}><aside className="omni-drawer" onClick={(event) => event.stopPropagation()}><header><div><span className="eyebrow">Governed assistant</span><h2>Omni</h2></div><button onClick={() => setOpen(false)} aria-label="Close Omni">×</button></header><p className="muted">Grounded only in the current canonical POC context. Never a source of record.</p><label>Question<textarea value={question} onChange={(event) => setQuestion(event.target.value)} /></label><button className="primary" onClick={ask}>Ask about this context</button>{error && <p className="error">{error}</p>}{response && <article className="omni-answer"><p>{response.content}</p>{response.recommended_action && <strong>Recommended: {response.recommended_action}</strong>}<small>Provenance: {response.provenance.join(' · ')}<br />Evidence: {response.citations.join(', ') || 'unavailable'}</small></article>}</aside></div>}</>
}
