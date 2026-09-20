import type { CommunicationDraft, Principal } from '../../types/api'

export type DeliveryState = { state: string; label: string }
export const queueViews = ['All', 'Mine', 'Needs review', 'Approved', 'Rejected'] as const
export type QueueView = typeof queueViews[number]
export function defaultView(principal?: Principal): QueueView {
  return principal?.role === 'MANAGER' ? 'Needs review' : 'Mine'
}
export function inView(item: CommunicationDraft, view: QueueView, principal?: Principal): boolean {
  switch (view) {
    case 'All': return true
    case 'Mine': return Boolean(principal && item.created_by === principal.user_id)
    case 'Needs review': return item.approval_status === 'PENDING' && item.status === 'DRAFT'
    case 'Approved': return item.approval_status === 'APPROVED'
    case 'Rejected': return item.approval_status === 'REJECTED'
  }
}
export function viewCounts(items: CommunicationDraft[], principal?: Principal) {
  return Object.fromEntries(queueViews.map(view => [view, items.filter(item => inView(item, view, principal)).length])) as Record<QueueView, number>
}
export function deliveryAvailable(delivery?: DeliveryState): boolean {
  return delivery?.state === 'CONFIGURED' || delivery?.state === 'CONNECTED'
}
export function canSend(item: CommunicationDraft, delivery?: DeliveryState): boolean {
  return deliveryAvailable(delivery) && item.status === 'READY' && item.approval_status === 'APPROVED' && item.recipients.length > 0
}
export function workflowSteps(item: CommunicationDraft, delivery?: DeliveryState) {
  const approved = item.approval_status === 'APPROVED'
  const reviewed = approved || item.approval_status === 'REJECTED'
  return [
    { label: 'Draft', detail: item.status === 'CANCELED' ? 'Canceled' : 'Saved', complete: item.status !== 'CANCELED' },
    { label: 'In review', detail: reviewed ? 'Reviewed' : item.approval_status === 'PENDING' ? 'Needs review' : 'Not requested', complete: reviewed },
    { label: 'Approved', detail: approved ? 'Approved' : item.approval_status === 'REJECTED' ? 'Rejected' : 'Awaiting approval', complete: approved },
    { label: 'Delivery', detail: item.status === 'SENT' ? 'Sent' : deliveryAvailable(delivery) ? 'Not sent' : delivery?.state === 'NOT_CONFIGURED' ? 'Unavailable' : 'Availability unconfirmed', complete: item.status === 'SENT' },
  ]
}
