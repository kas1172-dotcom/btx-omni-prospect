import { useRef, useState } from 'react'
import type { Account360 } from '../../types/api'
import { api } from '../../api/client'

export function ProfileFunctionCoverage({ detail }: { detail: Account360 }) {
  return <section className="profile-card"><h2>Function coverage</h2><p>Present / Thin / Missing / Unknown. SAMPLE role contacts do not identify real people. Missing requires completed negative research.</p><div className="profile-coverage">{detail.profile.function_coverage.map(row => <div key={row.function}><strong>{row.function}</strong><small>{row.state} · {row.source_state}</small><small>{row.verification_scope.join(', ') || 'Verification unknown'}</small></div>)}</div>{!detail.profile.function_coverage.length && <p>Unknown — no function matrix projected.</p>}</section>
}

export function ProfileContacts({ detail }: { detail: Account360 }) {
  const [pending, setPending] = useState('')
  const [notice, setNotice] = useState('')
  const [created, setCreated] = useState<Record<string, string>>({})
  const keys = useRef(new Map<string, string>())
  const research = async (functionName: string) => {
    if (pending || created[functionName]) return
    const idempotencyKey = keys.current.get(functionName) ?? crypto.randomUUID()
    keys.current.set(functionName, idempotencyKey)
    setPending(functionName); setNotice('')
    try {
      const action = await api.createAction({ account_id: detail.account.id, title: `Research ${functionName} contact coverage`, priority: 'MEDIUM', idempotency_key: idempotencyKey })
      setCreated(current => ({ ...current, [functionName]: action.id }))
      setNotice(`Internal research action ${action.id} created. No person, email or relationship was created.`)
    } catch { setNotice('Research action creation was not confirmed. Retry the same request; no contact data was inferred.') }
    finally { setPending('') }
  }
  return <section className="profile-card"><h2>Contacts</h2><p>Public research and CRM records retain their source states. No last two-way interaction is inferred from an export or verification date.</p><div className="profile-table-wrap"><table className="profile-table"><thead><tr>{['Contact', 'Function', 'Verification date', 'Source', 'Last two-way interaction', 'State / next action'].map(label => <th key={label}>{label}</th>)}</tr></thead><tbody>
    {detail.public_contacts.map((row, index) => <tr key={`public:${index}`}><th scope="row">{row.name ?? 'Person unknown'}</th><td>{row.title_or_function ?? row.role_family ?? 'Unknown'}</td><td>{row.provenance?.last_verified_at?.slice(0, 10) ?? 'Unknown'}</td><td>{row.source_url ? <a href={row.source_url} target="_blank" rel="noreferrer">Public source</a> : 'Source unknown'}</td><td>Unknown</td><td>{row.verification_state} · Research only; no introduction implied</td></tr>)}
    {detail.customer_360.crm.contacts.map(row => <tr key={`crm:${row.id}`}><th scope="row">{row.name ?? 'Person unknown'}</th><td>{row.role_family ?? row.title ?? 'Unknown'}</td><td>Unknown</td><td>{row.provenance?.source_system ?? 'CRM'} · {row.provenance?.data_mode ?? 'UNAVAILABLE'}</td><td>Unknown</td><td>{row.provenance?.evidence_state ?? 'Unknown'}</td></tr>)}
    {detail.profile.function_coverage.filter(row => row.state === 'Unknown' || row.state === 'Missing').map(row => <tr key={`coverage:${row.function}`}><th scope="row">Person unknown</th><td>{row.function}</td><td>Unknown</td><td>{row.source_state}</td><td>{row.last_two_way_at ?? 'Unknown'}</td><td>{row.state} <button disabled={Boolean(pending) || Boolean(created[row.function])} onClick={() => void research(row.function)}>{created[row.function] ? 'Research action created' : pending === row.function ? 'Creating…' : 'Research'}</button></td></tr>)}
    </tbody></table></div>{!detail.public_contacts.length && !detail.customer_360.crm.contacts.length && <p>No identified person is projected. Role-only coverage is not a named contact.</p>}{notice && <p role="status">{notice}</p>}</section>
}
