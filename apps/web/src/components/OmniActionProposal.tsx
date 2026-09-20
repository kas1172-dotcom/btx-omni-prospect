import { lazy, Suspense, useState } from 'react'
import { api } from '../api/client'
import type { Account, Principal } from '../types/api'
import { Button } from './UI'

const ExistingActionEditor = lazy(() => import('../features/actions/Actions').then(module => ({ default: module.ActionEditor })))

export function OmniActionProposal({ accountId, title }: { accountId: string; title: string }) {
  const [review, setReview] = useState<{ accounts: Account[]; principal: Principal }>()
  const [notice, setNotice] = useState('')
  const open = async () => {
    try { const [accounts, work] = await Promise.all([api.accounts(), api.actions()]); setReview({ accounts: accounts.accounts, principal: work.principal }) }
    catch { setNotice('The Action form is unavailable. Open Actions to review this suggestion.') }
  }
  return <><Button onClick={() => void open()}>Propose an Action</Button>{notice && <p role="status">{notice}</p>}{review && <Suspense fallback={<p>Opening the review form…</p>}><ExistingActionEditor open accounts={review.accounts} principal={review.principal} proposal={{ account_id: accountId, title }} onClose={() => setReview(undefined)} onSaved={() => { setReview(undefined); setNotice('Your reviewed Action was saved. Open Actions to manage it.') }} /></Suspense>}</>
}
