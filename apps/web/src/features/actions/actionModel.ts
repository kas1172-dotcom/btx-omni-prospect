import type { Action } from '../../types/api'
import { workspaceHash } from '../../app/navigation'

export const closed = (action: Action) => ['COMPLETED', 'CANCELED'].includes(action.status)
export function compareDue(a: Pick<Action, 'due_date'>, b: Pick<Action, 'due_date'>): number {
  return Number(!a.due_date) - Number(!b.due_date) || (a.due_date ?? '').localeCompare(b.due_date ?? '')
}
export function localDate(now = new Date()): string {
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`
}
export const overdue = (action: Action, today = localDate()) => Boolean(action.due_date && action.due_date < today && !closed(action))
export function relativeDue(value?: string | null, today = localDate()) {
  if (!value) return 'No due date'
  const days = Math.round((Date.parse(value) - Date.parse(today)) / 86400000)
  return days === 0 ? 'Today' : days === 1 ? 'Tomorrow' : days < 0 ? `${-days}d overdue` : `In ${days}d`
}
export function actionSource(action: Action): { label: string; href: string } | undefined {
  const refs = new Map(action.context_referents)
  const route = refs.get('source_route')
  // Source routes are internal navigation only; never render an arbitrary URL.
  if (route?.startsWith('#/')) return { label: refs.get('source_screen') ?? 'Source', href: route }
  const eventId = refs.get('intelligence_event')
  if (eventId) return { label: 'Intelligence', href: workspaceHash({ surface: 'intelligence', eventId, accountId: action.account_id ?? undefined }) }
  const opportunityId = refs.get('federal_opportunity')
  if (opportunityId) return { label: 'Federal opportunities', href: workspaceHash({ surface: 'intelligence', subview: 'federal', recordId: opportunityId }) }
  if (refs.has('commercial_action') && action.account_id) return { label: 'Customer 360', href: workspaceHash({ surface: 'accounts', accountId: action.account_id }) }
  if (action.source_suggestion_id) return { label: 'Suggested', href: workspaceHash({ surface: 'actions', subview: 'suggestions', recordId: action.source_suggestion_id }) }
  return undefined
}
